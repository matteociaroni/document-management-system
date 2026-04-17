from cryptography.fernet import Fernet, InvalidToken

from config import settings


def _get_fernet() -> Fernet:
    key = settings.email_encryption_key
    if not key or key == "change-me-generate-a-real-fernet-key":
        raise ValueError(
            "EMAIL_ENCRYPTION_KEY is not configured. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())


def decrypt_credentials(encrypted_text: str) -> str:
    try:
        f = _get_fernet()
        return f.decrypt(encrypted_text.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt credentials — invalid key or corrupted data") from exc
