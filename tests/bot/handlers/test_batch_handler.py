"""Handler tests for card batch listing and PDF regeneration."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import batch as batch_module


def _make_query(data="batch_regen:7"):
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = data
    query.message = MagicMock()
    query.message.chat_id = 42
    query.edit_message_text = AsyncMock()
    return query


@pytest.mark.asyncio
async def test_batches_command_lists_batches():
    update = MagicMock()
    update.callback_query = None
    update.effective_user = MagicMock(id=1)
    update.effective_chat = MagicMock(id=1, type="private")
    ctx = MagicMock()
    ctx.user_data = {"router_key": "discovered_1"}

    batches = [{"id": 1, "name": "b1", "batch_type": "hotspot", "count": 3, "created_at": "2026-01-01 00:00:00"}]
    mock_send = AsyncMock()
    with patch("utils.admin_decorator.ADMIN_IDS", [1]), \
         patch("bot.router_selector.get_selected_router", return_value="discovered_1"), \
         patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=batches)), \
         patch.object(batch_module, "send_step", new=mock_send):
        await batch_module.batches_command(update, ctx)

        mock_send.assert_called_once()
        text = mock_send.call_args.args[2]
        assert "الدفعات" in text


@pytest.mark.asyncio
async def test_batch_regen_sends_pdf():
    update = MagicMock()
    update.callback_query = _make_query("batch_regen:7")
    ctx = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_document = AsyncMock()

    batch = {
        "id": 7, "name": "b7", "batch_type": "hotspot", "profile": "10GB",
        "count": 2, "created_at": "2026-01-01",
        "cards": [
            {"username": "u1", "password": "p1", "card_number": 1, "profile": "10GB", "limit_bytes": "1000", "comment": ""},
            {"username": "u2", "password": "", "card_number": 2, "profile": "10GB", "limit_bytes": "2000", "comment": ""},
        ],
    }
    with patch.object(batch_module, "run_blocking", new=AsyncMock(side_effect=[batch, "/tmp/fake.pdf"])), \
         patch("builtins.open", MagicMock()), patch("os.remove"), patch("os.path.exists", return_value=True):
        await batch_module.batch_regen(update, ctx)

    ctx.bot.send_document.assert_called_once()
    fname = ctx.bot.send_document.call_args.kwargs.get("filename")
    assert fname == "batch_7.pdf"
    update.callback_query.answer.assert_called()


@pytest.mark.asyncio
async def test_batch_regen_missing_batch_prompts():
    update = MagicMock()
    update.callback_query = _make_query("batch_regen:99")
    ctx = MagicMock()

    with patch.object(batch_module, "run_blocking", new=AsyncMock(return_value=None)):
        await batch_module.batch_regen(update, ctx)

    update.callback_query.answer.assert_called_once()
