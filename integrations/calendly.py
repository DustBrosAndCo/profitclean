import hashlib
import hmac
import os
import sqlite3
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import urlencode

from .base import BaseIntegration, DB_PATH

# NOTE: There used to be a second, unused local BaseIntegration class defined
# in this file (with its own DB_PATH pointing at a stray "external_bookings.db"
# file). CalendlyIntegration always actually inherited from the real
# BaseIntegration imported from .base (which stores tokens encrypted in
# profitclean.db) because the `from .base import BaseIntegration` rebinding
# happened after the dead class was defined -- but store_bookings()/sync()
# below were still writing to that unencrypted, never-initialized stray DB
# file. Both are removed now; everything uses the shared DB_PATH (profitclean.db)
# from integrations/base.py.


class CalendlyIntegration(BaseIntegration):
    AUTH_URL = "https://auth.calendly.com/oauth/authorize"
    TOKEN_URL = "https://auth.calendly.com/oauth/token"
    API_BASE = "https://api.calendly.com"

    def __init__(self, company_id: int):
        super().__init__(company_id)
        self.client_id = self.settings.get("client_id") or self._get_secret("CALENDLY_CLIENT_ID")
        self.client_secret = self.settings.get("client_secret") or self._get_secret("CALENDLY_CLIENT_SECRET")
        self.redirect_uri = self.settings.get("redirect_uri") or self._get_secret("CALENDLY_REDIRECT_URI")

        # Load persisted tokens
        self.access_token = self.settings.get("access_token")
        self.refresh_token = self.settings.get("refresh_token")
        expires_str = self.settings.get("token_expires")
        self.token_expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00")) if expires_str else None

    def _get_secret(self, key: str) -> Optional[str]:
        try:
            return __import__("streamlit").secrets[key]
        except (KeyError, ImportError):
            return os.environ.get(key)
        except Exception as e:
            from logger_config import logger
            logger.warning(f"Failed to read secret {key}: {e}")
            return os.environ.get(key)

    def get_integration_type(self) -> str:
        return "calendly"

    def has_required_credentials(self) -> bool:
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def get_oauth_url(self, state: str = None) -> str:
        if not self.client_id or not self.redirect_uri:
            raise ValueError("Calendly OAuth credentials are not configured.")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": "scheduled_events:read users:read webhooks:write webhooks:read",
            "state": state or self.integration_type,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    # === OAuth Methods (Improved) ===
    def exchange_code_for_token(self, code: str) -> Dict:
        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("Calendly OAuth credentials not configured.")

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
            response.raise_for_status()

        token_data = response.json()
        self._update_tokens(token_data)
        self.enabled = True
        self.settings["scope"] = token_data.get("scope")
        self.settings["last_sync"] = datetime.utcnow().isoformat()
        self.save_config()
        self.log_event("oauth", "success", "Connected to Calendly")
        return token_data

    def _update_tokens(self, token_data: Dict):
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        self.token_expires = datetime.utcnow() + timedelta(seconds=expires_in)

        self.settings.update({
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expires": self.token_expires.isoformat(),
        })

    def _ensure_valid_token(self):
        if not self.access_token or not self.token_expires:
            return
        if self.token_expires - timedelta(minutes=5) < datetime.utcnow():
            self.refresh_access_token()

    def refresh_access_token(self) -> bool:
        if not self.refresh_token:
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
        self._update_tokens(token_data)
        self.save_config()
        self.log_event("refresh", "success", "Token refreshed")
        return True

    # === Core Sync (Improved with Pagination) ===
    def fetch_bookings(self, since: Optional[datetime] = None) -> List[Dict]:
        if not self.is_connected():
            self.log_event("fetch", "failed", "Not connected")
            return []

        self._ensure_valid_token()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        # Get user URI
        user_resp = requests.get(f"{self.API_BASE}/users/me", headers=headers, timeout=20)
        user_resp.raise_for_status()
        user_uri = user_resp.json().get("resource", {}).get("uri")
        if not user_uri:
            return []

        params = {"user": user_uri, "status": "active", "count": 100}
        if since:
            params["min_start_time"] = since.isoformat() + "Z" if not since.tzinfo else since.isoformat()

        bookings = []
        url = f"{self.API_BASE}/scheduled_events"

        while url:
            resp = requests.get(url, headers=headers, params=params if url.endswith("/scheduled_events") else None, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            for event in data.get("collection", []):
                inv_resp = requests.get(f"{event.get('uri')}/invitees", headers=headers, timeout=20)
                if inv_resp.status_code == 200:
                    for invitee in inv_resp.json().get("collection", []):
                        email = invitee.get("email", "")
                        hashed_email = hashlib.sha256(email.encode("utf-8")).hexdigest() if email else None
                        bookings.append({
                            "external_id": event.get("uri", "").split("/")[-1],
                            "hashed_email": hashed_email,
                            "invitee_name": invitee.get("name", ""),
                            "start_time": event.get("start_time"),
                            "end_time": event.get("end_time"),
                            "service_type": event.get("name", ""),
                            "status": event.get("status", ""),
                            "raw_questions": str(invitee.get("questions", [])),
                        })

            url = data.get("pagination", {}).get("next_page")

        self.log_event("fetch", "success", f"Fetched {len(bookings)} bookings")
        return bookings

    @staticmethod
    def _ensure_bookings_table(conn: sqlite3.Connection):
        """Create the external_bookings table in the shared app DB if it
        doesn't already exist yet (idempotent)."""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS external_bookings (
                id INTEGER PRIMARY KEY,
                company_id INTEGER,
                source TEXT,
                external_id TEXT,
                hashed_email TEXT,
                invitee_name TEXT,
                start_time TEXT,
                end_time TEXT,
                service_type TEXT,
                status TEXT,
                raw_questions TEXT,
                imported_at TEXT,
                processed INTEGER DEFAULT 0,
                UNIQUE(company_id, source, external_id)
            )
        ''')

    def store_bookings(self, bookings: List[Dict]) -> int:
        conn = sqlite3.connect(DB_PATH)
        self._ensure_bookings_table(conn)
        c = conn.cursor()
        imported_count = 0

        for booking in bookings:
            c.execute(
                "SELECT id FROM external_bookings WHERE company_id = ? AND source = ? AND external_id = ?",
                (self.company_id, self.integration_type, booking["external_id"])
            )
            if c.fetchone():
                continue

            c.execute(
                """INSERT INTO external_bookings 
                   (company_id, source, external_id, hashed_email, invitee_name, start_time, 
                    end_time, service_type, status, raw_questions, imported_at, processed) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    self.company_id, self.integration_type, booking["external_id"],
                    booking["hashed_email"], booking["invitee_name"], booking["start_time"],
                    booking["end_time"], booking["service_type"], booking["status"],
                    booking["raw_questions"], datetime.utcnow().isoformat(), 0
                )
            )
            imported_count += 1

        conn.commit()
        conn.close()
        self.settings["last_sync"] = datetime.utcnow().isoformat()
        self.save_config()
        return imported_count

    def sync(self) -> int:
        last_sync = self.settings.get("last_sync")
        since = datetime.fromisoformat(last_sync) - timedelta(days=1) if last_sync else datetime.utcnow() - timedelta(days=30)
        bookings = self.fetch_bookings(since)
        return self.store_bookings(bookings) if bookings else 0

    # === WEBHOOK SUPPORT ===
    def create_webhook(self, target_url: str, scope: str = "user") -> Dict:
        self._ensure_valid_token()
        headers = {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

        payload = {
            "url": target_url,
            "events": ["invitee.created", "invitee.canceled"],
            "scope": scope
        }

        resp = requests.post(f"{self.API_BASE}/webhook_subscriptions", json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        self.settings["webhook_subscription"] = data.get("resource")
        self.save_config()
        self.log_event("webhook", "created", f"Webhook created for {target_url}")
        return data

    def delete_webhook(self) -> bool:
        subscription = self.settings.get("webhook_subscription")
        if not subscription or not subscription.get("uri"):
            return False
        self._ensure_valid_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        resp = requests.delete(subscription["uri"], headers=headers, timeout=20)
        if resp.status_code in (200, 204):
            self.settings.pop("webhook_subscription", None)
            self.save_config()
            return True
        return False

    def verify_webhook_signature(self, payload: bytes, signature_header: str, signing_key: str = None) -> bool:
        """Verify Calendly webhook signature (t=...&v1=... format)"""
        if not signing_key:
            signing_key = self._get_secret("CALENDLY_SIGNING_KEY") or os.environ.get("CALENDLY_SIGNING_KEY")
        if not signing_key or not signature_header:
            return False

        try:
            # Example header: t=1234567890,v1=abc123...
            parts = dict(item.split("=") for item in signature_header.split(","))
            t = parts.get("t")
            v1 = parts.get("v1")
            if not t or not v1:
                return False

            message = f"{t}.{payload.decode('utf-8')}"
            computed = hmac.new(signing_key.encode(), message.encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(computed, v1)
        except Exception:
            return False

    def handle_webhook(self, payload: Dict) -> bool:
        """Process incoming webhook and store booking"""
        try:
            event_type = payload.get("event")
            if event_type in ["invitee.created", "invitee.canceled"]:
                invitee = payload.get("payload", {}).get("invitee", {})
                event_data = payload.get("payload", {}).get("event", {})

                booking = {
                    "external_id": event_data.get("uuid") or event_data.get("uri", "").split("/")[-1],
                    "hashed_email": hashlib.sha256(invitee.get("email", "").encode()).hexdigest() if invitee.get("email") else None,
                    "invitee_name": invitee.get("name", ""),
                    "start_time": event_data.get("start_time"),
                    "end_time": event_data.get("end_time"),
                    "service_type": event_data.get("name", ""),
                    "status": "canceled" if "canceled" in event_type else "active",
                    "raw_questions": str(invitee.get("questions", [])),
                }
                self.store_bookings([booking])
                self.log_event("webhook", "processed", f"Handled {event_type}")
                return True
        except Exception as e:
            self.log_event("webhook", "error", str(e))
        return False
