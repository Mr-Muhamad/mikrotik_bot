"""Tests for role-based access control via utils.admin_decorator.require_role."""
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from database.models import init_db, set_admin_role
from utils.admin_decorator import INSUFFICIENT_ROLE_MSG, require_role

ADMIN_ID = 700000001


@pytest.fixture
def role_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp = f.name
    with patch("database.models.DB_PATH", tmp), \
         patch("utils.crypto._get_key") as mk, \
         patch("database.models.encrypt_password", side_effect=lambda p: f"enc_{p}" if p else ""), \
         patch("database.models.decrypt_password", side_effect=lambda t: t.replace("enc_", "", 1) if t.startswith("enc_") else t), \
         patch("utils.admin_decorator.ADMIN_IDS", [ADMIN_ID]):
        mk.return_value.encrypt.side_effect = lambda p: f"enc_{p.decode()}" if isinstance(p, bytes) else f"enc_{p}"
        mk.return_value.decrypt.side_effect = lambda t: t.decode().replace("enc_", "", 1).encode()
        init_db()
        yield
    try:
        os.unlink(tmp)
    except OSError:
        pass


def _callback_update(user_id):
    update = MagicMock()
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=1, type="private")
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "x"
    update.callback_query = query
    update.message = None
    return update


@pytest.mark.asyncio
async def test_viewer_blocked_from_admin_command(role_db):
    set_admin_role(ADMIN_ID, "viewer")

    @require_role("admin")
    async def guarded(update, context):
        return "allowed"

    update = _callback_update(ADMIN_ID)
    result = await guarded(update, MagicMock())
    assert result is None
    edit_args = str(update.callback_query.edit_message_text.call_args)
    assert INSUFFICIENT_ROLE_MSG in edit_args


@pytest.mark.asyncio
async def test_admin_passes_admin_command(role_db):
    set_admin_role(ADMIN_ID, "admin")

    @require_role("admin")
    async def guarded(update, context):
        return "allowed"

    result = await guarded(_callback_update(ADMIN_ID), MagicMock())
    assert result == "allowed"


@pytest.mark.asyncio
async def test_operator_blocked_from_admin_command(role_db):
    set_admin_role(ADMIN_ID, "operator")

    @require_role("admin")
    async def guarded(update, context):
        return "allowed"

    update = _callback_update(ADMIN_ID)
    result = await guarded(update, MagicMock())
    assert result is None
    assert INSUFFICIENT_ROLE_MSG in str(update.callback_query.edit_message_text.call_args)


@pytest.mark.asyncio
async def test_operator_passes_operator_command(role_db):
    set_admin_role(ADMIN_ID, "operator")

    @require_role("operator")
    async def guarded(update, context):
        return "allowed"

    result = await guarded(_callback_update(ADMIN_ID), MagicMock())
    assert result == "allowed"


@pytest.mark.asyncio
async def test_unknown_role_defaults_to_admin(role_db):
    @require_role("admin")
    async def guarded(update, context):
        return "allowed"

    result = await guarded(_callback_update(ADMIN_ID), MagicMock())
    assert result == "allowed"
