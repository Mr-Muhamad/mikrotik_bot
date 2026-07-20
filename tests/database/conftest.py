"""Shared fixtures for database/repository tests.

Provides ``temp_db`` with an encrypted-friendly in-memory key mock so repository
modules can be exercised directly (importing from ``database.repositories.*``)
without depending on a real ENCRYPTION_KEY.
"""

import os
import tempfile
from unittest.mock import patch

import pytest

TEST_ENCRYPTION_KEY = "cJgq9rq_LN5KltQzznSzpMRgb2DqY9Z8j4m4W-YFRiM="


@pytest.fixture(autouse=True)
def temp_db():
    """Replace DB_PATH with a temp file and init tables before each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_path = f.name
    with (
        patch("database.models.DB_PATH", tmp_path),
        patch("database.models.os.path.dirname", return_value=os.path.dirname(tmp_path)),
        patch("utils.crypto._get_key") as mock_key,
        patch(
            "database.models.encrypt_password",
            side_effect=lambda p: f"enc_{p}" if p else "",
        ),
        patch(
            "database.models.decrypt_password",
            side_effect=lambda t: t.replace("enc_", "", 1) if t.startswith("enc_") else t,
        ),
    ):
        # Fernet.encrypt/decrypt are bytes-in/bytes-out; crypto encodes/decodes around them.
        mock_key.return_value.encrypt.side_effect = lambda p: b"enc_" + p
        mock_key.return_value.decrypt.side_effect = lambda t: t.replace(b"enc_", b"", 1)
        init_db()
        yield
    import gc

    gc.collect()
    try:
        os.unlink(tmp_path)
    except PermissionError:
        pass


def init_db():
    from database.models import init_db as _init

    _init()
