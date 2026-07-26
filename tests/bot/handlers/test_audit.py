"""Tests for bot/handlers/audit.py - audit log views, filters, pagination."""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from tests.fixtures.telegram_mocks import make_mock_context, make_mock_update
from utils import admin_decorator

P = "bot.handlers.audit"

MOCK_TIME_OPTIONS = [("24 ساعة", 1), ("3 أيام", 3), ("أسبوع", 7)]

MOCK_SUBMENU_ROUTER = "🔍 اختر الراوتر"
MOCK_SUBMENU_ADMIN = "👤 اختر المشرف"
MOCK_SUBMENU_ACTION = "⚙️ اختر العملية"
MOCK_SUBMENU_TIME = "🕓 اختر المدة"
MOCK_SUBMENU_CHOOSE = "اختر"
MOCK_SUBMENU_COUNT = "{title}\n\n🔢 العدد: {count}"
MOCK_NO_RESULTS = "📭 لا توجد نتائج"
MOCK_AUDIT_LIST_EMPTY = "📋 سجل التدقيق\n\n{header}\n\n{no_results}"
MOCK_AUDIT_PAGE_EMPTY = "📋 سجل التدقيق\n\n{header}\n\n📭 لا توجد سجلات في هذه الصفحة"
MOCK_AUDIT_LIST_HEADER = "📋 <b>سجل التدقيق</b> ({start}-{end} من {total})"
MOCK_AUDIT_NO_FILTERS = "بدون فلاتر"


async def _call_through(fn, *args, **kwargs):
    """Make run_blocking actually invoke the passed function."""
    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def _start_patches():
    stack = ExitStack()
    stack.enter_context(patch("utils.admin_decorator.ADMIN_IDS", [724730774]))
    stack.enter_context(
        patch(f"{P}.run_blocking", new_callable=AsyncMock, side_effect=_call_through)
    )
    stack.enter_context(patch(f"{P}.safe_answer_callback", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.send_step", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.nav_set"))
    stack.enter_context(patch(f"{P}.get_distinct_log_routers", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_distinct_log_admins", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_distinct_log_actions", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_logs", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.get_logs_count", new_callable=AsyncMock))
    stack.enter_context(patch(f"{P}.TIME_OPTIONS", MOCK_TIME_OPTIONS))
    stack.enter_context(patch(f"{P}.AUDIT_SUBMENU_ROUTER", MOCK_SUBMENU_ROUTER))
    stack.enter_context(patch(f"{P}.AUDIT_SUBMENU_ADMIN", MOCK_SUBMENU_ADMIN))
    stack.enter_context(patch(f"{P}.AUDIT_SUBMENU_ACTION", MOCK_SUBMENU_ACTION))
    stack.enter_context(patch(f"{P}.AUDIT_SUBMENU_TIME", MOCK_SUBMENU_TIME))
    stack.enter_context(patch(f"{P}.AUDIT_SUBMENU_CHOOSE", MOCK_SUBMENU_CHOOSE))
    stack.enter_context(patch(f"{P}.AUDIT_SUBMENU_COUNT", MOCK_SUBMENU_COUNT))
    stack.enter_context(patch(f"{P}.NO_RESULTS", MOCK_NO_RESULTS))
    stack.enter_context(patch(f"{P}.AUDIT_LIST_EMPTY", MOCK_AUDIT_LIST_EMPTY))
    stack.enter_context(patch(f"{P}.AUDIT_PAGE_EMPTY", MOCK_AUDIT_PAGE_EMPTY))
    stack.enter_context(patch(f"{P}.AUDIT_LIST_HEADER", MOCK_AUDIT_LIST_HEADER))
    stack.enter_context(patch(f"{P}.AUDIT_NO_FILTERS", MOCK_AUDIT_NO_FILTERS))
    return stack


@pytest.fixture(autouse=True)
def _all_patches():
    admin_decorator._rate_limit_data.clear()
    stack = _start_patches()
    yield
    stack.close()
    admin_decorator._rate_limit_data.clear()


class TestEmptyFilters:
    def test_empty_filters(self):
        from bot.handlers.audit import _empty_filters

        result = _empty_filters()
        assert result == {
            "router": None,
            "admin_id": None,
            "admin_label": None,
            "action": None,
            "since_days": None,
        }
        assert len(result) == 5


class TestGetFilters:
    def test_get_filters_first_call(self):
        from bot.handlers.audit import _get_filters

        ctx = make_mock_context()
        filters = _get_filters(ctx)
        assert filters["router"] is None
        assert "logs_filters" in ctx.user_data

    def test_get_filters_returns_existing(self):
        from bot.handlers.audit import _get_filters

        ctx = make_mock_context()
        ctx.user_data["logs_filters"] = {
            "router": "R1",
            "admin_id": None,
            "admin_label": None,
            "action": None,
            "since_days": None,
        }
        filters = _get_filters(ctx)
        assert filters["router"] == "R1"

    def test_get_filters_default_values(self):
        from bot.handlers.audit import _get_filters

        ctx = make_mock_context()
        f = _get_filters(ctx)
        for key in ("router", "admin_id", "admin_label", "action", "since_days"):
            assert f[key] is None


class TestBuildDbFilters:
    def test_build_db_filters_all_none(self):
        from bot.handlers.audit import _build_db_filters

        result = _build_db_filters({
            "router": None, "admin_id": None, "action": None, "since_days": None,
        })
        assert result == {"router": None, "admin_id": None, "action": None}

    def test_build_db_filters_with_router(self):
        from bot.handlers.audit import _build_db_filters

        result = _build_db_filters({
            "router": "MikroTik-1", "admin_id": None, "action": None, "since_days": None,
        })
        assert result["router"] == "MikroTik-1"

    def test_build_db_filters_with_admin_id(self):
        from bot.handlers.audit import _build_db_filters

        result = _build_db_filters({
            "router": None, "admin_id": 42, "action": None, "since_days": None,
        })
        assert result["admin_id"] == 42

    def test_build_db_filters_with_action(self):
        from bot.handlers.audit import _build_db_filters

        result = _build_db_filters({
            "router": None, "admin_id": None, "action": "backup", "since_days": None,
        })
        assert result["action"] == "backup"

    def test_build_db_filters_with_since_days(self):
        from bot.handlers.audit import _build_db_filters

        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        with patch(f"{P}.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.UTC = UTC
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = _build_db_filters({
                "router": None, "admin_id": None, "action": None, "since_days": 3,
            })
        assert "since" in result
        expected = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        assert result["since"] == expected

    def test_build_db_filters_since_days_zero_ignored(self):
        from bot.handlers.audit import _build_db_filters

        result = _build_db_filters({
            "router": None, "admin_id": None, "action": None, "since_days": 0,
        })
        assert "since" not in result

    def test_build_db_filters_all_set(self):
        from bot.handlers.audit import _build_db_filters

        now = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        with patch(f"{P}.datetime") as mock_dt:
            mock_dt.now.return_value = now
            mock_dt.UTC = UTC
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            result = _build_db_filters({
                "router": "R1", "admin_id": 5, "action": "login", "since_days": 1,
            })
        assert result["router"] == "R1"
        assert result["admin_id"] == 5
        assert result["action"] == "login"
        assert "since" in result


class TestFormatFiltersShort:
    def test_format_no_filters(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": None, "admin_id": None, "admin_label": None,
            "action": None, "since_days": None,
        })
        assert result == MOCK_AUDIT_NO_FILTERS

    def test_format_router_only(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": "RouterA", "admin_id": None, "admin_label": None,
            "action": None, "since_days": None,
        })
        assert "RouterA" in result
        assert "🔍" in result

    def test_format_admin_with_label(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": None, "admin_id": 10, "admin_label": "AdminX",
            "action": None, "since_days": None,
        })
        assert "AdminX" in result
        assert "👤" in result

    def test_format_admin_without_label(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": None, "admin_id": 10, "admin_label": None,
            "action": None, "since_days": None,
        })
        assert "10" in result

    def test_format_action_only(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": None, "admin_id": None, "admin_label": None,
            "action": "reboot", "since_days": None,
        })
        assert "reboot" in result
        assert "⚙️" in result

    def test_format_time_only(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": None, "admin_id": None, "admin_label": None,
            "action": None, "since_days": 3,
        })
        assert "3 أيام" in result
        assert "🕓" in result

    def test_format_time_no_match(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": None, "admin_id": None, "admin_label": None,
            "action": None, "since_days": 999,
        })
        assert "🕓" in result

    def test_format_all_filters(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": "R1", "admin_id": 1, "admin_label": "adm",
            "action": "add", "since_days": 1,
        })
        assert "🔍" in result
        assert "👤" in result
        assert "⚙️" in result
        assert "🕓" in result
        assert "|" in result

    def test_format_separator_count(self):
        from bot.handlers.audit import _format_filters_short

        result = _format_filters_short({
            "router": "R1", "admin_id": 1, "admin_label": "A",
            "action": "x", "since_days": 7,
        })
        assert result.count("|") == 3


class TestLogsCommand:
    @pytest.mark.asyncio
    async def test_logs_command_resets_filters(self):
        from bot.handlers.audit import logs_command

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()
        ctx.user_data["logs_filters"] = {"router": "old"}
        ctx.user_data["logs_menu"] = "router"

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock) as mock_show:
            await logs_command(update, ctx)
        assert ctx.user_data["logs_filters"]["router"] is None
        assert ctx.user_data["logs_menu"] is None
        mock_show.assert_awaited_once_with(update, ctx, page=0, from_callback=False)

    @pytest.mark.asyncio
    async def test_logs_command_calls_show_page(self):
        from bot.handlers.audit import logs_command

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock) as mock_show:
            await logs_command(update, ctx)
        mock_show.assert_awaited_once_with(update, ctx, page=0, from_callback=False)


class TestLogsFilterCallback:
    @pytest.mark.asyncio
    async def test_filter_router(self):
        from bot.handlers.audit import logs_filter_callback

        update = make_mock_update(callback_data="logs_filter_router")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_distinct_log_routers",
                   new_callable=AsyncMock, return_value=["R1", "R2"]),
            patch(f"{P}._show_submenu", new_callable=AsyncMock) as mock_sub,
        ):
            await logs_filter_callback(update, ctx)
        assert ctx.user_data["logs_router_options"] == ["R1", "R2"]
        assert ctx.user_data["logs_menu"] == "router"
        mock_sub.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_admin(self):
        from bot.handlers.audit import logs_filter_callback

        update = make_mock_update(callback_data="logs_filter_admin")
        ctx = make_mock_context()
        admin_list = [{"admin_id": 1, "username": "adm1"}]

        with (
            patch(f"{P}.get_distinct_log_admins",
                   new_callable=AsyncMock, return_value=admin_list),
            patch(f"{P}._show_submenu", new_callable=AsyncMock),
        ):
            await logs_filter_callback(update, ctx)
        assert ctx.user_data["logs_admin_options"] is admin_list
        assert ctx.user_data["logs_menu"] == "admin"

    @pytest.mark.asyncio
    async def test_filter_action(self):
        from bot.handlers.audit import logs_filter_callback

        update = make_mock_update(callback_data="logs_filter_action")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_distinct_log_actions",
                   new_callable=AsyncMock, return_value=["backup", "reboot"]),
            patch(f"{P}._show_submenu", new_callable=AsyncMock),
        ):
            await logs_filter_callback(update, ctx)
        assert ctx.user_data["logs_action_options"] == ["backup", "reboot"]
        assert ctx.user_data["logs_menu"] == "action"

    @pytest.mark.asyncio
    async def test_filter_time(self):
        from bot.handlers.audit import logs_filter_callback

        update = make_mock_update(callback_data="logs_filter_time")
        ctx = make_mock_context()

        with patch(f"{P}._show_submenu", new_callable=AsyncMock) as mock_sub:
            await logs_filter_callback(update, ctx)
        assert ctx.user_data["logs_menu"] == "time"
        mock_sub.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filter_unknown_returns_early(self):
        from bot.handlers.audit import logs_filter_callback

        update = make_mock_update(callback_data="logs_filter_unknown")
        ctx = make_mock_context()

        with patch(f"{P}._show_submenu", new_callable=AsyncMock) as mock_sub:
            await logs_filter_callback(update, ctx)
        mock_sub.assert_not_awaited()


class TestLogsSetCallback:
    @pytest.mark.asyncio
    async def test_set_router_valid(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_router_1")
        ctx = make_mock_context()
        ctx.user_data["logs_router_options"] = ["R1", "R2", "R3"]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["router"] == "R2"
        assert ctx.user_data["logs_menu"] is None

    @pytest.mark.asyncio
    async def test_set_router_out_of_range(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_router_99")
        ctx = make_mock_context()
        ctx.user_data["logs_router_options"] = ["R1"]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["router"] is None

    @pytest.mark.asyncio
    async def test_set_admin_valid(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_admin_0")
        ctx = make_mock_context()
        ctx.user_data["logs_admin_options"] = [
            {"admin_id": 42, "username": "admin1"},
        ]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["admin_id"] == 42
        assert ctx.user_data["logs_filters"]["admin_label"] == "admin1"

    @pytest.mark.asyncio
    async def test_set_admin_no_username(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_admin_0")
        ctx = make_mock_context()
        ctx.user_data["logs_admin_options"] = [
            {"admin_id": 7, "username": None},
        ]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["admin_id"] == 7
        assert ctx.user_data["logs_filters"]["admin_label"] == "7"

    @pytest.mark.asyncio
    async def test_set_admin_empty_string_username(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_admin_0")
        ctx = make_mock_context()
        ctx.user_data["logs_admin_options"] = [
            {"admin_id": 8, "username": ""},
        ]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["admin_label"] == "8"

    @pytest.mark.asyncio
    async def test_set_admin_out_of_range(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_admin_5")
        ctx = make_mock_context()
        ctx.user_data["logs_admin_options"] = []

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["admin_id"] is None
        assert ctx.user_data["logs_filters"]["admin_label"] is None

    @pytest.mark.asyncio
    async def test_set_action_valid(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_action_0")
        ctx = make_mock_context()
        ctx.user_data["logs_action_options"] = ["backup"]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["action"] == "backup"

    @pytest.mark.asyncio
    async def test_set_action_out_of_range(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_action_10")
        ctx = make_mock_context()
        ctx.user_data["logs_action_options"] = []

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["action"] is None

    @pytest.mark.asyncio
    async def test_set_time_valid(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_time_1")
        ctx = make_mock_context()

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["since_days"] == 3

    @pytest.mark.asyncio
    async def test_set_time_out_of_range(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_time_99")
        ctx = make_mock_context()

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_filters"]["since_days"] is None

    @pytest.mark.asyncio
    async def test_set_resets_menu_and_page(self):
        from bot.handlers.audit import logs_set_callback

        update = make_mock_update(callback_data="logs_set_router_0")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "router"
        ctx.user_data["logs_sub_page"] = 5
        ctx.user_data["logs_router_options"] = ["R1"]

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock):
            await logs_set_callback(update, ctx)
        assert ctx.user_data["logs_menu"] is None
        assert ctx.user_data["logs_sub_page"] == 0


class TestLogsClearCallback:
    @pytest.mark.asyncio
    async def test_clear_resets_all(self):
        from bot.handlers.audit import logs_clear_callback

        update = make_mock_update(callback_data="logs_clear")
        ctx = make_mock_context()
        ctx.user_data["logs_filters"] = {
            "router": "R1", "admin_id": 42, "admin_label": "adm",
            "action": "add", "since_days": 3,
        }
        ctx.user_data["logs_menu"] = "router"

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock) as mock_page:
            await logs_clear_callback(update, ctx)
        f = ctx.user_data["logs_filters"]
        assert f["router"] is None
        assert f["admin_id"] is None
        assert f["action"] is None
        assert f["since_days"] is None
        assert ctx.user_data["logs_menu"] is None
        mock_page.assert_awaited_once_with(update, ctx, page=0, from_callback=True)


class TestLogsBackCallback:
    @pytest.mark.asyncio
    async def test_back_clears_menu(self):
        from bot.handlers.audit import logs_back_callback

        update = make_mock_update(callback_data="logs_back")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "action"

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock) as mock_page:
            await logs_back_callback(update, ctx)
        assert ctx.user_data["logs_menu"] is None
        mock_page.assert_awaited_once_with(update, ctx, page=0, from_callback=True)


class TestLogsSubnavCallback:
    @pytest.mark.asyncio
    async def test_subnav_next(self):
        from bot.handlers.audit import logs_subnav_callback

        update = make_mock_update(callback_data="logs_sub_next")
        ctx = make_mock_context()
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}._show_submenu", new_callable=AsyncMock):
            await logs_subnav_callback(update, ctx)
        assert ctx.user_data["logs_sub_page"] == 1

    @pytest.mark.asyncio
    async def test_subnav_prev(self):
        from bot.handlers.audit import logs_subnav_callback

        update = make_mock_update(callback_data="logs_sub_prev")
        ctx = make_mock_context()
        ctx.user_data["logs_sub_page"] = 2

        with patch(f"{P}._show_submenu", new_callable=AsyncMock):
            await logs_subnav_callback(update, ctx)
        assert ctx.user_data["logs_sub_page"] == 1

    @pytest.mark.asyncio
    async def test_subnav_no_data(self):
        from bot.handlers.audit import logs_subnav_callback

        update = make_mock_update(callback_data="logs_sub_next")
        ctx = make_mock_context()
        update.callback_query.data = None

        with patch(f"{P}._show_submenu", new_callable=AsyncMock):
            await logs_subnav_callback(update, ctx)


class TestLogsPageCallback:
    @pytest.mark.asyncio
    async def test_page_valid(self):
        from bot.handlers.audit import logs_page_callback

        update = make_mock_update(callback_data="logs_page_3")
        ctx = make_mock_context()

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock) as mock_page:
            await logs_page_callback(update, ctx)
        mock_page.assert_awaited_once_with(update, ctx, page=3, from_callback=True)

    @pytest.mark.asyncio
    async def test_page_invalid_value(self):
        from bot.handlers.audit import logs_page_callback

        update = make_mock_update(callback_data="logs_page_abc")
        ctx = make_mock_context()

        with patch(f"{P}._show_logs_page", new_callable=AsyncMock) as mock_page:
            await logs_page_callback(update, ctx)
        mock_page.assert_awaited_once_with(update, ctx, page=0, from_callback=True)


class TestShowSubmenu:
    @pytest.mark.asyncio
    async def test_submenu_time(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(callback_data="logs_filter_time")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "time"
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.get_logs_submenu_keyboard") as mock_kb:
            await _show_submenu(update, ctx)
        mock_kb.assert_called_once()
        args = mock_kb.call_args
        assert args[0][0] == "time"

    @pytest.mark.asyncio
    async def test_submenu_router(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(callback_data="logs_filter_router")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "router"
        ctx.user_data["logs_router_options"] = ["R1", "R2"]
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.get_logs_submenu_keyboard") as mock_kb:
            await _show_submenu(update, ctx)
        args = mock_kb.call_args
        assert args[0][0] == "router"
        assert args[0][1] == ["R1", "R2"]

    @pytest.mark.asyncio
    async def test_submenu_admin(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(callback_data="logs_filter_admin")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "admin"
        ctx.user_data["logs_admin_options"] = [
            {"admin_id": 1, "username": "adm"},
        ]
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.get_logs_submenu_keyboard") as mock_kb:
            await _show_submenu(update, ctx)
        args = mock_kb.call_args
        assert args[0][0] == "admin"
        assert "adm" in args[0][1][0]

    @pytest.mark.asyncio
    async def test_submenu_admin_no_username(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(callback_data="logs_filter_admin")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "admin"
        ctx.user_data["logs_admin_options"] = [
            {"admin_id": 99, "username": None},
        ]
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.get_logs_submenu_keyboard") as mock_kb:
            await _show_submenu(update, ctx)
        args = mock_kb.call_args
        assert "99" in args[0][1][0]

    @pytest.mark.asyncio
    async def test_submenu_action(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(callback_data="logs_filter_action")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "action"
        ctx.user_data["logs_action_options"] = ["backup"]
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.get_logs_submenu_keyboard") as mock_kb:
            await _show_submenu(update, ctx)
        args = mock_kb.call_args
        assert args[0][0] == "action"

    @pytest.mark.asyncio
    async def test_submenu_unknown_fallback(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(callback_data="x")
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = None
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.get_logs_submenu_keyboard") as mock_kb:
            await _show_submenu(update, ctx)
        args = mock_kb.call_args
        assert args[0][0] == "router"
        assert args[0][1] == []

    @pytest.mark.asyncio
    async def test_submenu_no_callback_query(self):
        from bot.handlers.audit import _show_submenu

        update = make_mock_update(text="test")
        update.callback_query = None
        ctx = make_mock_context()
        ctx.user_data["logs_menu"] = "time"
        ctx.user_data["logs_sub_page"] = 0

        with patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send:
            await _show_submenu(update, ctx)
        mock_send.assert_awaited_once()


class TestShowLogsPage:
    @pytest.mark.asyncio
    async def test_empty_results_from_command(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_logs_count", return_value=0),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        mock_send.assert_awaited_once()
        assert MOCK_NO_RESULTS in mock_send.call_args[0][2]

    @pytest.mark.asyncio
    async def test_empty_results_from_callback(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(callback_data="logs_page_0")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_logs_count", return_value=0),
            patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock) as mock_edit,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=True)
        mock_edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_page_after_offset(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(callback_data="logs_page_5")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_logs_count", return_value=15),
            patch(f"{P}.get_logs", return_value=[]),
            patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock) as mock_edit,
        ):
            await _show_logs_page(update, ctx, page=5, from_callback=True)
        mock_edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_with_results(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()
        logs = [
            {
                "action": "add", "username": "admin",
                "router_name": "R1", "timestamp": "2025-06-15 12:00:00",
            },
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=1),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        mock_send.assert_awaited_once()
        sent_text = mock_send.call_args[0][2]
        assert "add" in sent_text
        assert "admin" in sent_text
        assert "R1" in sent_text

    @pytest.mark.asyncio
    async def test_logs_timestamp_truncated(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()
        logs = [
            {
                "action": "x", "username": "u",
                "router_name": "r", "timestamp": "2025-06-15 12:34:56",
            },
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=1),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        assert "2025-06-15 12:34" in mock_send.call_args[0][2]

    @pytest.mark.asyncio
    async def test_logs_missing_fields(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_logs_count", return_value=1),
            patch(f"{P}.get_logs", return_value=[{}]),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_short_timestamp(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()
        logs = [
            {
                "action": "x", "username": "u",
                "router_name": "r", "timestamp": "2025-06-15 12",
            },
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=1),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        assert "2025-06-15 12" in mock_send.call_args[0][2]

    @pytest.mark.asyncio
    async def test_logs_page_pagination_header(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(callback_data="logs_page_1")
        ctx = make_mock_context()
        logs = [
            {
                "action": "a", "username": "u",
                "router_name": "R", "timestamp": "2025-01-01 00:00:00",
            },
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=25),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock) as mock_edit,
        ):
            await _show_logs_page(update, ctx, page=1, from_callback=True)
        sent = mock_edit.call_args[0][2]
        assert "11-20" in sent
        assert "25" in sent

    @pytest.mark.asyncio
    async def test_logs_empty_timestamp(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()
        logs = [
            {"action": "a", "username": "u", "router_name": "r", "timestamp": ""},
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=1),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_multiple_entries(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()
        logs = [
            {"action": "a", "username": "u1", "router_name": "R1",
             "timestamp": "2025-01-01 00:00:00"},
            {"action": "b", "username": "u2", "router_name": "R2",
             "timestamp": "2025-01-02 00:00:00"},
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=2),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.send_step", new_callable=AsyncMock) as mock_send,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        sent = mock_send.call_args[0][2]
        assert "u1" in sent
        assert "u2" in sent

    @pytest.mark.asyncio
    async def test_logs_from_callback_with_results(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(callback_data="logs_page_0")
        ctx = make_mock_context()
        logs = [
            {"action": "x", "username": "u", "router_name": "r",
             "timestamp": "2025-01-01 00:00:00"},
        ]

        with (
            patch(f"{P}.get_logs_count", return_value=1),
            patch(f"{P}.get_logs", return_value=logs),
            patch(f"{P}.safe_edit_or_send", new_callable=AsyncMock) as mock_edit,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=True)
        mock_edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_logs_filter_keyboard_called(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_logs_count", return_value=0),
            patch(f"{P}.get_logs_filter_keyboard") as mock_kb,
            patch(f"{P}.send_step", new_callable=AsyncMock),
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        mock_kb.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_nav_set_called(self):
        from bot.handlers.audit import _show_logs_page

        update = make_mock_update(text="/logs")
        ctx = make_mock_context()

        with (
            patch(f"{P}.get_logs_count", return_value=0),
            patch(f"{P}.send_step", new_callable=AsyncMock),
            patch(f"{P}.nav_set") as mock_nav,
        ):
            await _show_logs_page(update, ctx, page=0, from_callback=False)
        mock_nav.assert_called_with(ctx, "main_menu")
