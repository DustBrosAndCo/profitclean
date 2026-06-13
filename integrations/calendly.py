import hashlib
import os
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List
from .base import BaseIntegration


class CalendlyIntegration(BaseIntegration):
    AUTH_URL = "https://auth.calendly.com/oauth/authorize"
    TOKEN_URL = "https://auth.calendly.com/oauth/token"
    API_BASE = "https://api.calendly.com"

    def __init__(self, company_id: int):
        # Initialize base first so company-level settings are loaded into self.settings
        super().__init__(company_id)
        # Prefer company-specific credentials stored in integration settings
        self.client_id = self.settings.get("client_id") or self._get_secret("CALENDLY_CLIENT_ID")
        # client_secret is stored encrypted in settings; it will be decrypted by BaseIntegration loader if present
        self.client_secret = self.settings.get("client_secret") or self._get_secret("CALENDLY_CLIENT_SECRET")
        self.redirect_uri = self.settings.get("redirect_uri") or self._get_secret("CALENDLY_REDIRECT_URI")

    def _get_secret(self, key: str) -> str:
        try:
            return __import__("streamlit").secrets[key]
        except Exception:
            return os.environ.get(key)

    def get_integration_type(self) -> str:
        return "calendly"

    def has_required_credentials(self) -> bool:
        """Check if Calendly OAuth credentials are configured."""
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def get_oauth_url(self) -> str:
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Calendly OAuth credentials are not configured.")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "default",
            "state": self.integration_type,
        }
        return f"{self.AUTH_URL}?{requests.compat.urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Dict[str, str]:
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise ValueError("Calendly OAuth credentials are not configured.")

        response = requests.post(
            self.TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )

        if response.status_code != 200:
            self.log_event("oauth", "failed", response.text)
            raise Exception(f"OAuth failed: {response.status_code} {response.text}")

        token_data = response.json()
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        self.token_expires = datetime.now() + timedelta(seconds=expires_in)
        self.enabled = True
        self.settings["scope"] = token_data.get("scope")
        self.settings["last_sync"] = datetime.now().isoformat()
        self.save_config()
        self.log_event("oauth", "success", "Connected to Calendly")
        return token_data

    def refresh_access_token(self) -> bool:
        if not self.refresh_token or not self.client_id or not self.client_secret:
            return False

        response = requests.post(
            self.TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=20,
        )

        if response.status_code != 200:
            self.enabled = False
            self.save_config()
            self.log_event("refresh", "failed", response.text)
            return False

        token_data = response.json()
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        self.token_expires = datetime.now() + timedelta(seconds=expires_in)
        self.save_config()
        self.log_event("refresh", "success", "Token refreshed")
        return True

    def fetch_bookings(self, since: datetime = None) -> List[Dict[str, str]]:
        if not self.is_connected():
            self.log_event("fetch", "failed", "Not connected")
            return []

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        user_response = requests.get(f"{self.API_BASE}/users/me", headers=headers, timeout=20)
        if user_response.status_code != 200:
            self.log_event("fetch", "failed", "Could not fetch user info")
            return []

        user_uri = user_response.json().get("resource", {}).get("uri")
        if not user_uri:
            self.log_event("fetch", "failed", "Calendly user URI missing")
            return []

        params = {
            "user": user_uri,
            "status": "active",
            "count": 100,
        }
        if since:
            params["min_start_time"] = since.isoformat()

        events_response = requests.get(f"{self.API_BASE}/scheduled_events", headers=headers, params=params, timeout=20)
        if events_response.status_code != 200:
            self.log_event("fetch", "failed", f"API error: {events_response.status_code}")
            return []

        bookings = []
        event_collection = events_response.json().get("collection", [])
        for event in event_collection:
            invitees_response = requests.get(f"{event.get('uri')}/invitees", headers=headers, timeout=20)
            invitees = []
            if invitees_response.status_code == 200:
                invitees = invitees_response.json().get("collection", [])

            for invitee in invitees:
                email = invitee.get("email", "")
                hashed_email = hashlib.sha256(email.encode()).hexdigest() if email else None
                bookings.append(
                    {
                        "external_id": event.get("uri", "").split("/")[-1],
                        "hashed_email": hashed_email,
                        "invitee_name": invitee.get("name", ""),
                        "start_time": event.get("start_time"),
                        "end_time": event.get("end_time"),
                        "service_type": event.get("name", ""),
                        "status": event.get("status", ""),
                        "raw_questions": str(invitee.get("questions", [])),
                    }
                )

        self.log_event("fetch", "success", f"Fetched {len(bookings)} bookings")
        return bookings

    def store_bookings(self, bookings: List[Dict[str, str]]) -> int:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        imported_count = 0

        for booking in bookings:
            c.execute(
                "SELECT id FROM external_bookings WHERE company_id = ? AND source = ? AND external_id = ?",
                (self.company_id, self.integration_type, booking["external_id"]),
            )
            if c.fetchone():
                continue

            c.execute(
                "INSERT INTO external_bookings (company_id, source, external_id, hashed_email, invitee_name, start_time, end_time, service_type, status, raw_questions, imported_at, processed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.company_id,
                    self.integration_type,
                    booking["external_id"],
                    booking["hashed_email"],
                    booking["invitee_name"],
                    booking["start_time"],
                    booking["end_time"],
                    booking["service_type"],
                    booking["status"],
                    booking["raw_questions"],
                    datetime.now().isoformat(),
                    0,
                ),
            )
            imported_count += 1

        conn.commit()
        conn.close()
        self.settings["last_sync"] = datetime.now().isoformat()
        self.save_config()
        return imported_count

    def sync(self) -> int:
        last_sync_value = self.settings.get("last_sync")
        if last_sync_value:
            since = datetime.fromisoformat(last_sync_value) - timedelta(days=1)
        else:
            since = datetime.now() - timedelta(days=30)

        bookings = self.fetch_bookings(since)
        if not bookings:
            return 0
        return self.store_bookings(bookings)
