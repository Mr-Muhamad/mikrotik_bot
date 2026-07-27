import logging
import os

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_key: Fernet | None = None


def _get_key() -> Fernet:
    global _key
    if _key is not None:
        return _key
    raw = os.getenv("ENCRYPTION_KEY")
    if not raw:
        raise RuntimeError("ENCRYPTION_KEY not set — config.py should have exited already")
    try:
        _key = Fernet(raw.encode())
        logger.info("Encryption key loaded successfully from environment")
        return _key
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY format: {e}")
        raise ValueError("ENCRYPTION_KEY in .env is invalid. Fix or remove it.") from e


def encrypt_password(password: str) -> str:
    """Encrypt a plaintext password using Fernet symmetric encryption."""
    if not password:
        return ""
    f = _get_key()
    return f.encrypt(password.encode()).decode()


def decrypt_password(token: str) -> str:
    """Decrypt a Fernet-encrypted token back to plaintext.

    Returns empty string on failure (never returns the ciphertext).
    """
    if not token:
        return ""
    try:
        f = _get_key()
        return f.decrypt(token.encode()).decode()
    except (InvalidToken, ValueError, RuntimeError) as e:
        logger.error(f"Failed to decrypt password token: {e}")
        return ""


def encrypt_data(plaintext: str) -> str:
    """Encrypt an arbitrary string (e.g. a batch payload) with Fernet."""
    if not plaintext:
        return ""
    return _get_key().encrypt(plaintext.encode()).decode()


def decrypt_data(token: str) -> str:
    """Decrypt a Fernet-encrypted string back to plaintext.

    Returns empty string on failure (never returns the ciphertext).
    """
    if not token:
        return ""
    try:
        return _get_key().decrypt(token.encode()).decode()
    except (InvalidToken, ValueError, RuntimeError) as e:
        logger.error(f"Failed to decrypt data token: {e}")
        return ""
