"""Tests for bot/handlers/hotspot_report.py — report, CSV/Excel export."""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.hotspot_report"


async def _call_through(fn, *args, **kwargs):  # type: ignore[reportMissingParameterType]
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


REPORT_ROWS = [
    {
        "name": "u1",
        "profile": "Basic",
        "status": "active",
        "bytes_in": 0,
        "bytes_out": 0,
        "total_bytes": 0,
        "total_str": "",
        "limit_str": "",
        "percent": 0.0,
        "comment": "",
    }
]


class TestBuildCsv:
    def test_generates_csv_with_rows(self):
        from bot.handlers.hotspot_report import build_csv

        report = {"rows": REPORT_ROWS}
        result = build_csv(report)  # type: ignore[reportArgumentType]
        assert "name,profile" in result
        assert "u1" in result
        assert "Basic" in result

    def test_generates_csv_with_no_rows(self):
        from bot.handlers.hotspot_report import build_csv

        result = build_csv({"rows": []})  # type: ignore[reportArgumentType]
        lines = result.strip().split("\n")
        assert len(lines) == 1

    def test_generates_csv_with_missing_keys(self):
        from bot.handlers.hotspot_report import build_csv

        result = build_csv({"rows": [{}]})  # type: ignore[reportArgumentType]
        lines = result.strip().split("\n")
        assert len(lines) == 2


@pytest.fixture(autouse=True)
def _patches():  # type: ignore[reportUnusedFunction]
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]
    with ExitStack() as stack:
        stack.enter_context(
            patch("utils.admin_decorator.ADMIN_IDS", [724730774])
        )
        stack.enter_context(patch(f"{P}.cleanup_state"))
        stack.enter_context(patch(f"{P}.nav_set"))
        stack.enter_context(
            patch(f"{P}.send_step", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch(f"{P}.send_error", new_callable=AsyncMock)
        )
        stack.enter_context(
            patch(
                f"{P}.run_blocking",
                new_callable=AsyncMock,
                side_effect=_call_through,
            )
        )
        stack.enter_context(patch(f"{P}.hotspot_manager"))
        stack.enter_context(patch(f"{P}.mikrotik_api"))
        stack.enter_context(patch(f"{P}.stats_manager"))
        yield
    admin_decorator._rate_limit_data.clear()  # type: ignore[reportPrivateUsage]


class TestReportCommand:
    @pytest.mark.asyncio
    async def test_sends_report_on_success(self):
        with ExitStack() as stack:
            mock_hs = stack.enter_context(
                patch(f"{P}.hotspot_manager")
            )
            mock_hs.build_usage_report.return_value = {
                "rows": [],
            }
            mock_api = stack.enter_context(
                patch(f"{P}.mikrotik_api")
            )
            mock_api.get_router_name.return_value = "TestRouter"
            mock_stats = stack.enter_context(
                patch(f"{P}.stats_manager")
            )
            mock_stats.get_hotspot_stats.return_value = {}
            mock_stats.format_hotspot_stats.return_value = ""
            mock_stats.format_hotspot_usage_report.return_value = (
                "Report Text"
            )
            mock_send = stack.enter_context(
                patch(f"{P}.send_step", new_callable=AsyncMock)
            )
            from bot.handlers.hotspot_report import report_command

            update = make_mock_update(
                user_id=724730774, callback_data="report"
            )
            context = make_mock_context()
            context.user_data["router_key"] = "key1"
            await report_command(update, context)

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][2]
        assert sent_text == "Report Text"

    @pytest.mark.asyncio
    async def test_sends_error_on_exception(self):
        with ExitStack() as stack:
            mock_hs = stack.enter_context(
                patch(f"{P}.hotspot_manager")
            )
            mock_hs.build_usage_report.side_effect = OSError(
                "timeout"
            )
            mock_err = stack.enter_context(
                patch(f"{P}.send_error", new_callable=AsyncMock)
            )
            from bot.handlers.hotspot_report import report_command

            update = make_mock_update(
                user_id=724730774, callback_data="report"
            )
            context = make_mock_context()
            context.user_data["router_key"] = "key1"
            await report_command(update, context)

        mock_err.assert_called_once()

    @pytest.mark.asyncio
    async def test_stores_report_in_user_data(self):
        with ExitStack() as stack:
            mock_hs = stack.enter_context(
                patch(f"{P}.hotspot_manager")
            )
            report_data = {"rows": [{"name": "u1"}]}
            mock_hs.build_usage_report.return_value = report_data
            mock_api = stack.enter_context(
                patch(f"{P}.mikrotik_api")
            )
            mock_api.get_router_name.return_value = "R1"
            fmt = stack.enter_context(
                patch(f"{P}.stats_manager")
            )
            fmt.format_hotspot_usage_report.return_value = "ok"

            from bot.handlers.hotspot_report import report_command

            update = make_mock_update(
                user_id=724730774, callback_data="report"
            )
            context = make_mock_context()
            context.user_data["router_key"] = "k"
            await report_command(update, context)

        assert context.user_data["report"] is report_data


class TestReportExportCsv:
    @pytest.mark.asyncio
    async def test_sends_csv_document(self):
        from bot.handlers.hotspot_report import report_export_csv

        update = make_mock_update(
            user_id=724730774, callback_data="csv"
        )
        context = make_mock_context()
        report = {"rows": REPORT_ROWS, "router_key": "r1"}
        context.user_data["report"] = report

        mock_bot = AsyncMock()
        context.bot = mock_bot
        update.callback_query.message = MagicMock()
        update.callback_query.message.chat_id = 123

        await report_export_csv(update, context)
        mock_bot.send_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_report_sends_warning(self):
        from bot.handlers.hotspot_report import report_export_csv

        update = make_mock_update(
            user_id=724730774, callback_data="csv"
        )
        context = make_mock_context()
        await report_export_csv(update, context)

        update.callback_query.edit_message_text.assert_called_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "لا يوجد تقرير" in text

    @pytest.mark.asyncio
    async def test_send_exception_shows_alert(self):
        from bot.handlers.hotspot_report import report_export_csv

        update = make_mock_update(
            user_id=724730774, callback_data="csv"
        )
        context = make_mock_context()
        context.user_data["report"] = {
            "rows": REPORT_ROWS,
            "router_key": "r1",
        }
        mock_bot = AsyncMock()
        mock_bot.send_document.side_effect = OSError("fail")
        context.bot = mock_bot
        update.callback_query.message = MagicMock()
        update.callback_query.message.chat_id = 123

        await report_export_csv(update, context)
        update.callback_query.answer.assert_called()


class TestReportExportExcel:
    @pytest.mark.asyncio
    async def test_sends_excel_document(self):
        from bot.handlers.hotspot_report import (
            report_export_excel,
        )

        update = make_mock_update(
            user_id=724730774, callback_data="excel"
        )
        context = make_mock_context()
        context.user_data["report"] = {
            "rows": [],
            "router_key": "r1",
        }

        with ExitStack() as stack:
            stack.enter_context(patch(f"{P}.mikrotik_api"))
            stack.enter_context(
                patch(
                    "core.reports_excel"
                    ".build_usage_excel_report",
                    return_value=b"fake_excel",
                )
            )
            mock_bot = AsyncMock()
            context.bot = mock_bot
            await report_export_excel(update, context)

        mock_bot.send_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_report_sends_warning(self):
        from bot.handlers.hotspot_report import (
            report_export_excel,
        )

        update = make_mock_update(
            user_id=724730774, callback_data="excel"
        )
        context = make_mock_context()
        await report_export_excel(update, context)

        update.callback_query.edit_message_text.assert_called_once()
        text = update.callback_query.edit_message_text.call_args[0][0]
        assert "لا يوجد تقرير" in text

    @pytest.mark.asyncio
    async def test_exception_sends_error(self):
        from bot.handlers.hotspot_report import (
            report_export_excel,
        )

        update = make_mock_update(
            user_id=724730774, callback_data="excel"
        )
        context = make_mock_context()
        context.user_data["report"] = {
            "rows": [],
            "router_key": "r1",
        }

        with ExitStack() as stack:
            stack.enter_context(patch(f"{P}.mikrotik_api"))
            stack.enter_context(
                patch(
                    "core.reports_excel"
                    ".build_usage_excel_report",
                    side_effect=OSError("fail"),
                )
            )
            mock_err = stack.enter_context(
                patch(f"{P}.send_error", new_callable=AsyncMock)
            )
            await report_export_excel(update, context)

        mock_err.assert_called_once()
