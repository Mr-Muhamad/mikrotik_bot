"""Tests for utils.crypto — Fernet password encryption (no session fallback, ENCRYPTION_KEY required)."""  # noqa: E501

import pytest
from cryptography.fernet import Fernet

from utils import crypto
from utils.crypto import decrypt_password, encrypt_password


@pytest.fixture(autouse=True)
def _reset_crypto_state():
    """Reset crypto module state between tests."""
    crypto._KEY = None
    yield
    crypto._KEY = None


def _valid_key() -> str:
    return Fernet.generate_key().decode()


# ─── encrypt_password tests ────────────────────────────────────


class TestEncryptPassword:
    def test_empty_password_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        assert encrypt_password("") == ""

    def test_encrypts_with_valid_key(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        token = encrypt_password("secret123")
        assert token != "secret123"
        # Fernet tokens start with 'gAAAAA'
        assert token.startswith("gAAAAA")

    def test_no_fallback_when_key_missing(self, monkeypatch):
        """ENCRYPTION_KEY is REQUIRED - no session fallback."""
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY not set"):
            encrypt_password("secret123")

    def test_invalid_key_raises(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", "not-a-valid-fernet-key!!!")
        with pytest.raises(ValueError, match="ENCRYPTION_KEY in .env is invalid"):
            encrypt_password("secret")


# ─── decrypt_password tests ────────────────────────────────────


class TestDecryptPassword:
    def test_empty_token_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        assert decrypt_password("") == ""

    def test_round_trip(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        token = encrypt_password("my-password")
        assert decrypt_password(token) == "my-password"

    def test_invalid_token_returns_empty(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        assert decrypt_password("not-a-valid-fernet-token!!!") == ""

    def test_garbage_returns_empty_not_raises(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        # Should NEVER raise — returns empty string
        assert decrypt_password("💀 garbage") == ""
        assert decrypt_password("gAAAAAinvalidsuffix") == ""

    def test_no_fallback_when_key_missing(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        # decrypt_password catches all exceptions and returns empty string
        assert decrypt_password("some-token") == ""


# ─── _get_key tests ────────────────────────────────────────────


class TestGetKey:
    def test_caches_key_after_first_call(self, monkeypatch):
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        k1 = crypto._get_key()
        k2 = crypto._get_key()
        assert k1 is k2  # cached

    def test_raises_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
        with pytest.raises(RuntimeError, match="ENCRYPTION_KEY not set"):
            crypto._get_key()
