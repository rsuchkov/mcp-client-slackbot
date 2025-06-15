import os
import base64
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    def __init__(self, master_key: Optional[str] = None):
        if master_key:
            self.fernet = Fernet(master_key.encode())
        else:
            self.fernet = self._create_fernet_from_env()

    def _create_fernet_from_env(self) -> Fernet:
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if encryption_key:
            return Fernet(encryption_key.encode())
        
        master_password = os.getenv("MASTER_PASSWORD")
        if not master_password:
            raise ValueError(
                "Either ENCRYPTION_KEY or MASTER_PASSWORD must be set in environment variables"
            )
        
        salt = os.getenv("ENCRYPTION_SALT", "mcp-slackbot-default-salt").encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        return self.fernet.decrypt(ciphertext.encode()).decode()

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode()


_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service