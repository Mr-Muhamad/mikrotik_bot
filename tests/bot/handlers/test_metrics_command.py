"""Tests for the /metrics diagnostic command handler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import telegram.error

from bot.handlers.commands_basic import metrics_command
from utils import admin_decorator

SAMPLE_METRICS = {
    "active_connections": 2,
    "stale_connections": 1,
    "total_attempts": 10,
    "successful": 8,
    "failed": 2,
    "cache_hits": 4,
}


def _get_text(call):
    return call.args[1] if len(call.args) > 1 else call.kwargs.get("text", "")


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    """Bypass the 1-second per-user rate limit between tests."""
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


@pytest.mark.asyncio
async def test_metrics_command_sends_report_and_deletes(mock_update, mock_context):
    sent_msg = MagicMock()
    sent_msg.message_id = 99
    mock_context.bot.send_message = AsyncMock(return_value=sent_msg)

    with (
        patch("bot.handlers.commands_basic.mikrotik_api") as mock_api,
        patch("bot.handlers.commands_basic.schedule_delete", new=AsyncMock()) as mock_sched,
        patch(
            "bot.handlers.commands_basic.run_blocking", new=AsyncMock(return_value=SAMPLE_METRICS)
        ),
    ):
        mock_api.get_metrics = MagicMock(return_value=SAMPLE_METRICS)

        await metrics_command(mock_update, mock_context)

        mock_context.bot.send_message.assert_called_once()
        text = _get_text(mock_context.bot.send_message.call_args)
        assert "أداء الاتصال" in text
        assert "2" in text
        assert "8" in text
        assert "80%" in text
        mock_update.message.delete.assert_called_once()
        mock_sched.assert_called_once_with(mock_context, 724730774, 99, 30)


@pytest.mark.asyncio
async def test_metrics_command_with_zero_attempts(mock_update, mock_context):
    zero = {
        "active_connections": 0,
        "stale_connections": 0,
        "total_attempts": 0,
        "successful": 0,
        "failed": 0,
        "cache_hits": 0,
    }
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    with (
        patch("bot.handlers.commands_basic.mikrotik_api") as mock_api,
        patch("bot.handlers.commands_basic.schedule_delete", new=AsyncMock()),
        patch("bot.handlers.commands_basic.run_blocking", new=AsyncMock(return_value=zero)),
    ):
        mock_api.get_metrics = MagicMock(return_value=zero)

        await metrics_command(mock_update, mock_context)

        text = _get_text(mock_context.bot.send_message.call_args)
        assert "0%" in text


@pytest.mark.asyncio
async def test_metrics_command_continues_on_delete_failure(mock_update, mock_context):
    mock_update.message.delete = AsyncMock(side_effect=telegram.error.TelegramError("nope"))
    mock_context.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))

    with (
        patch("bot.handlers.commands_basic.mikrotik_api") as mock_api,
        patch("bot.handlers.commands_basic.schedule_delete", new=AsyncMock()),
        patch(
            "bot.handlers.commands_basic.run_blocking", new=AsyncMock(return_value=SAMPLE_METRICS)
        ),
    ):
        mock_api.get_metrics = MagicMock(return_value=SAMPLE_METRICS)

        await metrics_command(mock_update, mock_context)
        mock_context.bot.send_message.assert_called_once()
