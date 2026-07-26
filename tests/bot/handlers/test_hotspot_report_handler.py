"""Handler tests for Hotspot usage report export."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import hotspot_report as report_module


def _make_query():
    query = MagicMock()
    query.answer = AsyncMock()
    query.message = MagicMock()
    query.message.chat_id = 99
    query.edit_message_text = AsyncMock()
    return query


def _report():
    return {
        "router_key": "discovered_1",
        "rows": [
            {
                "name": "userA",
                "profile": "10GB",
                "status": "active",
                "bytes_in": 100,
                "bytes_out": 200,
                "total_bytes": 300,
                "total_str": "300 B",
                "limit_str": "—",
                "percent": 0.0,
                "comment": "x",
            },
        ],
    }


@pytest.mark.asyncio
async def test_report_export_csv_sends_document():
    update = MagicMock()
    update.callback_query = _make_query()
    ctx = MagicMock()
    ctx.user_data = {"report": _report()}
    ctx.bot = MagicMock()
    ctx.bot.send_document = AsyncMock()

    with (
        patch("bot.handlers.hotspot_report.tempfile.mkstemp", return_value=(3, "x.csv")),
        patch("os.fdopen"),
        patch("builtins.open", MagicMock()),
        patch("os.remove"),
    ):
        await report_module.report_export_csv(update, ctx)

    ctx.bot.send_document.assert_called_once()
    filename = ctx.bot.send_document.call_args.kwargs.get("filename")
    assert filename == "hotspot_report_discovered_1.csv"
    update.callback_query.answer.assert_any_call("✅ تم إرسال ملف CSV", show_alert=False)


@pytest.mark.asyncio
async def test_report_export_csv_without_report_prompts():
    update = MagicMock()
    update.callback_query = _make_query()
    ctx = MagicMock()
    ctx.user_data = {}

    await report_module.report_export_csv(update, ctx)

    update.callback_query.edit_message_text.assert_called_once()
    update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_report_export_excel_sends_document():
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 724730774
    update.callback_query = _make_query()
    update.effective_chat = MagicMock()
    update.effective_chat.id = 99
    ctx = MagicMock()
    ctx.user_data = {"report": _report()}
    ctx.bot = MagicMock()
    ctx.bot.send_document = AsyncMock()

    with patch(
        "bot.handlers.hotspot_report.run_blocking", new=AsyncMock(return_value=b"PKfakeexcelbytes")
    ):
        await report_module.report_export_excel(update, ctx)

    ctx.bot.send_document.assert_called_once()
    filename = ctx.bot.send_document.call_args.kwargs.get("filename")
    assert filename == "hotspot_report_discovered_1.xlsx"
