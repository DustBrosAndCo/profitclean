import os
import base64
from cryptography.fernet import Fernet
import streamlit as st


class EncryptionManager:
    """Handle encryption of sensitive integration tokens"""

    def __init__(self):
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)

    def _get_encryption_key(self):
        """Get encryption key from Streamlit secrets or environment."""
        try:
            key = st.secrets["ENCRYPTION_KEY"]
            return key.encode()
        except Exception:
            pass

        key = os.environ.get("ENCRYPTION_KEY")
        if key:
            return key.encode()

        key = Fernet.generate_key()

        try:
            with open(".encryption_key", "wb") as f:
                f.write(key)
        except Exception:
            pass

        return key

    def encrypt(self, data: str) -> str:
        if not data:
            return None
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        if not encrypted_data:
            return None
        return self.cipher.decrypt(encrypted_data.encode()).decode()


encryption = EncryptionManager()
