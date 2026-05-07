"""
Encryption utilities for email credentials.

Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).
The encryption key is stored in config/environment variables.
"""

from cryptography.fernet import Fernet, InvalidToken
from app.config import settings


def _get_fernet() -> Fernet:
    """Get Fernet instance from the configured encryption key."""
    key = settings.email_encryption_key
    if not key or key == "change-me-generate-a-real-fernet-key":
        raise ValueError(
            "EMAIL_ENCRYPTION_KEY is not configured. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def encrypt_credentials(plain_text: str) -> str:
    """Encrypt a plaintext string (e.g. password or OAuth token). Returns base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plain_text.encode()).decode()


def decrypt_credentials(encrypted_text: str) -> str:
    """Decrypt a Fernet-encrypted string back to plaintext."""
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_text.encode()).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt credentials — invalid key or corrupted data")
