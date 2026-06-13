import json
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict
from encryption_manager import encryption

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "profitclean.db"))


class BaseIntegration(ABC):
    """Abstract base class for all integrations"""

    def __init__(self, company_id: int):
        self.company_id = company_id
        self.integration_type = self.get_integration_type()
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
        self.settings = {}
        self.enabled = False
        self._load_config()

    @abstractmethod
    def get_integration_type(self) -> str:
        pass

    @abstractmethod
    def get_oauth_url(self) -> str:
        pass

    @abstractmethod
    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def fetch_bookings(self, since: datetime = None) -> list[Dict[str, Any]]:
        pass

    def _load_config(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT access_token, refresh_token, token_expires, settings, enabled FROM company_integrations WHERE company_id = ? AND integration_type = ?",
            (self.company_id, self.integration_type)
        )
        row = c.fetchone()
        conn.close()

        if row:
            self.access_token = encryption.decrypt(row[0]) if row[0] else None
            self.refresh_token = encryption.decrypt(row[1]) if row[1] else None
            self.token_expires = datetime.fromisoformat(row[2]) if row[2] else None
            self.settings = json.loads(row[3]) if row[3] else {}
            self.enabled = bool(row[4])

    def save_config(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT id FROM company_integrations WHERE company_id = ? AND integration_type = ?",
            (self.company_id, self.integration_type)
        )
        exists = c.fetchone()

        if exists:
            c.execute(
                "UPDATE company_integrations SET enabled = ?, access_token = ?, refresh_token = ?, token_expires = ?, settings = ?, last_sync = ?, updated_at = ? WHERE company_id = ? AND integration_type = ?",
                (
                    1 if self.enabled else 0,
                    encryption.encrypt(self.access_token) if self.access_token else None,
                    encryption.encrypt(self.refresh_token) if self.refresh_token else None,
                    self.token_expires.isoformat() if self.token_expires else None,
                    json.dumps(self.settings),
                    self.settings.get("last_sync"),
                    datetime.now().isoformat(),
                    self.company_id,
                    self.integration_type,
                )
            )
        else:
            c.execute(
                "INSERT INTO company_integrations (company_id, integration_type, enabled, access_token, refresh_token, token_expires, settings, last_sync, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    self.company_id,
                    self.integration_type,
                    1 if self.enabled else 0,
                    encryption.encrypt(self.access_token) if self.access_token else None,
                    encryption.encrypt(self.refresh_token) if self.refresh_token else None,
                    self.token_expires.isoformat() if self.token_expires else None,
                    json.dumps(self.settings),
                    self.settings.get("last_sync"),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                )
            )
        conn.commit()
        conn.close()

    def log_event(self, action: str, status: str, message: str = ""):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "INSERT INTO integration_logs (company_id, integration_type, action, status, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (self.company_id, self.integration_type, action, status, message, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()

    def is_connected(self) -> bool:
        if not self.enabled or not self.access_token:
            return False

        if self.token_expires and datetime.now() > self.token_expires:
            return self.refresh_access_token()

        return True

    def refresh_access_token(self) -> bool:
        return False


class IntegrationError(Exception):
    pass
