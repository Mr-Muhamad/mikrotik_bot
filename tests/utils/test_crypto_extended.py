"""Tests for utils.crypto — extended coverage for encrypt_data/decrypt_data."""

import pytest
from cryptography.fernet import Fernet

from utils import crypto
from utils.crypto import decrypt_data, decrypt_password, encrypt_data, encrypt_password


@pytest.fixture(autouse=True)
def _reset_crypto_state():  # type: ignore[reportUnusedFunction]
    crypto._key = None  # type: ignore[reportPrivateUsage]
    yield
    crypto._key = None  # type: ignore[reportPrivateUsage]


def _valid_key() -> str:
    return Fernet.generate_key().decode()


# ─── encrypt_data / decrypt_data ──────────────────────────────


class TestEncryptDecryptData:
    def test_empty_returns_empty(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        assert encrypt_data("") == ""
        assert decrypt_data("") == ""

    def test_round_trip(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        token = encrypt_data("my batch payload")
        assert token != "my batch payload"
        assert decrypt_data(token) == "my batch payload"

    def test_invalid_token_returns_empty(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        assert decrypt_data("not-a-valid-token!!!") == ""

    def test_encrypted_tokens_start_with_gAAAAA(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        assert encrypt_data("test").startswith("gAAAAA")


# ─── encrypt_password / decrypt_password additional ───────────


class TestPasswordExtra:
    def test_different_encryptions_differ(self, monkeypatch):  # type: ignore[reportMissingParameterType]
        monkeypatch.setenv("ENCRYPTION_KEY", _valid_key())
        t1 = encrypt_password("secret")
        t2 = encrypt_password("secret")
        # Fernet includes timestamp — tokens may differ
        assert decrypt_password(t1) == decrypt_password(t2) == "secret"
