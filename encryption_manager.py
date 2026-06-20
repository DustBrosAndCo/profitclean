import os
import base64
from cryptography.fernet import Fernet
import streamlit as st


class EncryptionManager:
    """Handle encryption of sensitive integration tokens"""

    # Store the key file alongside this module, not relative to the process's
    # current working directory, so it's found consistently regardless of
    # where the app is launched from.
    KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".encryption_key")

    def __init__(self):
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)

    def _get_encryption_key(self):
        """Get encryption key from Streamlit secrets, environment, or a
        previously-generated local key file (in that order). Only generates
        a brand-new key if none of those already exist -- otherwise every
        restart would invalidate all previously-encrypted data.
        """
        try:
            key = st.secrets["ENCRYPTION_KEY"]
            return key.encode()
        except KeyError:
            pass
        except Exception as e:
            from logger_config import logger
            logger.warning(f"Failed to read ENCRYPTION_KEY from Streamlit secrets: {e}")

        key = os.environ.get("ENCRYPTION_KEY")
        if key:
            return key.encode()

        # Reuse a previously-generated key if one exists on disk.
        if os.path.exists(self.KEY_FILE):
            try:
                with open(self.KEY_FILE, "rb") as f:
                    existing_key = f.read().strip()
                if existing_key:
                    return existing_key
            except (IOError, OSError) as e:
                from logger_config import logger
                logger.warning(f"Failed to read existing encryption key file: {e}")

        # No key found anywhere -- generate one and persist it so future
        # restarts can decrypt data encrypted with it.
        key = Fernet.generate_key()

        try:
            with open(self.KEY_FILE, "wb") as f:
                f.write(key)
        except (IOError, OSError) as e:
            from logger_config import logger
            logger.warning(f"Failed to write encryption key to file: {e}")

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
