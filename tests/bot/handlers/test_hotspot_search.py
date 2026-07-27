"""Tests for bot.handlers.hotspot_search - comprehensive coverage suite."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

from bot.handlers.constants import WAITING_HOTSPOT_SEARCH
from bot.handlers.hotspot_search import (
    _enrich_hosts,
    _format_search_results_text,
    _search_hosts_by_field,
    _search_hosts_with_users,
    _search_users,
    block_mac_handler,
    hotspot_host_action,
    hotspot_search_back,
    hotspot_search_page_handler,
    hotspot_search_query,
    hotspot_search_start,
    hotspot_show_host,
    show_blocked_list,
    unblock_mac_handler,
)
from bot.messages import (
    HOTSPOT_SEARCH_FOUND,
    HOTSPOT_SEARCH_OFFLINE,
    NO_RESULTS,
    UNKNOWN_NAME,
)
from utils import admin_decorator
from utils.pagination import Paginator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


def _ctx():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.bot = MagicMock()
    return ctx


def _admin_update(**kwargs):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    chat = MagicMock()
    chat.type = "private"
    update.effective_chat = chat
    for k, v in kwargs.items():
        setattr(update, k, v)
    return update


def _make_query(data=""):
    query = MagicMock()
    query.answer = AsyncMock()
    query.data = data
    query.from_user = MagicMock(id=ADMIN_ID)
    query.edit_message_text = AsyncMock()
    return query


def _make_update_with_query(data=""):
    update = _admin_update()
    query = _make_query(data)
    update.callback_query = query
    return update


def _make_update_with_message(text=""):
    update = _admin_update()
    update.message = MagicMock()
    update.message.text = text
    return update


class TestSearchStart:
    @pytest.mark.asyncio
    async def test_callback_path(self):
        update = _make_update_with_query("hotspot_search")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.cleanup_state"), patch(
            "bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()
        ), patch("bot.handlers.hotspot_search.edit_clean", new=AsyncMock()) as mock_edit, patch(
            "bot.handlers.hotspot_search.set_current_action"
        ), patch(
            "bot.handlers.hotspot_search.nav_set"
        ):
            result = await hotspot_search_start(update, ctx)

        assert result == WAITING_HOTSPOT_SEARCH
        mock_edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_message_path(self):
        update = _make_update_with_message("/search")
        update.callback_query = None
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.cleanup_state"), patch(
            "bot.handlers.hotspot_search.send_step", new=AsyncMock()
        ) as mock_send, patch("bot.handlers.hotspot_search.set_current_action"), patch(
            "bot.handlers.hotspot_search.nav_set"
        ):
            result = await hotspot_search_start(update, ctx)

        assert result == WAITING_HOTSPOT_SEARCH
        mock_send.assert_awaited_once()


class TestSearchQuery:
    def _make_search_update(self, text="ali"):
        update = _make_update_with_message(text)
        update.effective_chat.id = 123
        return update

    def _patch_query_deps(self, hosts=None):
        if hosts is None:
            hosts = []
        loading_mock = MagicMock()
        loading_mock.message_id = 42
        return {
            "get_selected_router": patch(
                "bot.handlers.hotspot_search.get_selected_router",
                return_value="discovered_1",
            ),
            "send_loading": patch(
                "bot.handlers.hotspot_search.send_loading",
                new=AsyncMock(return_value=loading_mock),
            ),
            "delete_now": patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()),
            "send_step": patch("bot.handlers.hotspot_search.send_step", new=AsyncMock()),
            "run_blocking": patch(
                "bot.handlers.hotspot_search.run_blocking",
                new=AsyncMock(return_value=hosts),
            ),
        }

    @pytest.mark.asyncio
    async def test_no_router(self):
        update = self._make_search_update("test")
        ctx = _ctx()
        with patch("bot.handlers.hotspot_search.get_selected_router", return_value=None), patch(
            "bot.handlers.hotspot_search.reply_final", new=AsyncMock()
        ), patch("bot.handlers.hotspot_search.cleanup_state"):
            result = await hotspot_search_query(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_user_prefix(self):
        update = self._make_search_update("user:admin")
        ctx = _ctx()
        deps = self._patch_query_deps([{"name": "admin"}])
        with deps["get_selected_router"], deps["send_loading"], deps["delete_now"], deps[
            "send_step"
        ], deps["run_blocking"]:
            result = await hotspot_search_query(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert "search_hosts" in ctx.user_data

    @pytest.mark.asyncio
    async def test_mac_prefix(self):
        update = self._make_search_update("mac:AA:BB:CC")
        ctx = _ctx()
        deps = self._patch_query_deps(
            [{"host-name": "h1", "mac-address": "AA:BB:CC:DD:EE:FF", "address": "10.0.0.1"}]
        )
        with deps["get_selected_router"], deps["send_loading"], deps["delete_now"], deps[
            "send_step"
        ], deps["run_blocking"]:
            result = await hotspot_search_query(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_comment_prefix(self):
        update = self._make_search_update("comment:premium")
        ctx = _ctx()
        deps = self._patch_query_deps([{"name": "u1", "comment": "premium user"}])
        with deps["get_selected_router"], deps["send_loading"], deps["delete_now"], deps[
            "send_step"
        ], deps["run_blocking"]:
            result = await hotspot_search_query(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_ip_prefix(self):
        update = self._make_search_update("ip:10.0.0.5")
        ctx = _ctx()
        deps = self._patch_query_deps(
            [{"host-name": "h1", "address": "10.0.0.5", "mac-address": "AA:BB"}]
        )
        with deps["get_selected_router"], deps["send_loading"], deps["delete_now"], deps[
            "send_step"
        ], deps["run_blocking"]:
            result = await hotspot_search_query(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_plain_text(self):
        update = self._make_search_update("phone")
        ctx = _ctx()
        hosts = [{"host-name": "Phone1", "address": "10.0.0.5", "mac-address": "AA:BB:CC"}]
        deps = self._patch_query_deps(hosts)
        with deps["get_selected_router"], deps["send_loading"], deps["delete_now"], deps[
            "send_step"
        ], deps["run_blocking"]:
            result = await hotspot_search_query(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert ctx.user_data["search_hosts"] == hosts

    @pytest.mark.asyncio
    async def test_exception_returns_search_state(self):
        update = self._make_search_update("x")
        ctx = _ctx()
        loading_mock = MagicMock()
        loading_mock.message_id = 42
        with patch("bot.handlers.hotspot_search.get_selected_router", return_value="r1"), patch(
            "bot.handlers.hotspot_search.send_loading", new=AsyncMock(return_value=loading_mock)
        ), patch("bot.handlers.hotspot_search.delete_now", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(side_effect=OSError("net"))
        ), patch(
            "bot.handlers.hotspot_search.send_step", new=AsyncMock()
        ):
            result = await hotspot_search_query(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH


class TestSearchPageHandler:
    @pytest.mark.asyncio
    async def test_valid_page(self):
        update = _make_update_with_query("page_1")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"host-name": f"h{i}", "address": f"10.0.0.{i}", "mac-address": f"AA:{i}"}
            for i in range(15)
        ]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()):
            result = await hotspot_search_page_handler(update, ctx)

        assert result == WAITING_HOTSPOT_SEARCH
        update.callback_query.edit_message_text.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_hosts_expired_session(self):
        update = _make_update_with_query("page_0")
        ctx = _ctx()
        ctx.user_data.pop("search_hosts", None)

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await hotspot_search_page_handler(update, ctx)

        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_invalid_page_number_falls_to_zero(self):
        update = _make_update_with_query("page_xyz")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"host-name": "h1", "address": "1.1.1.1", "mac-address": "AA"}
        ]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()):
            result = await hotspot_search_page_handler(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_page_zero(self):
        update = _make_update_with_query("page_0")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"host-name": f"h{i}", "address": f"10.0.0.{i}", "mac-address": f"AA:{i}"}
            for i in range(3)
        ]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()):
            result = await hotspot_search_page_handler(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        update.callback_query.edit_message_text.assert_awaited_once()


class TestSearchUsers:
    @pytest.mark.asyncio
    async def test_success(self):
        users = [
            {
                "name": "admin",
                "limit-bytes-total": "104857600",
                "limit-uptime": "1d",
                "comment": "main",
                "disabled": "false",
            }
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=users)):
            result = await _search_users("r1", "admin")

        assert len(result) == 1
        assert result[0]["host-name"] == "admin"
        assert result[0]["user"] == "admin"
        assert result[0]["_limit"] == "104857600"
        assert result[0]["_uptime"] == "1d"
        assert result[0]["_comment"] == "main"
        assert result[0]["_disabled"] == "false"
        assert result[0]["address"] == ""
        assert result[0]["mac-address"] == ""

    @pytest.mark.asyncio
    async def test_success_empty_name(self):
        users = [
            {
                "name": "",
                "limit-bytes-total": "",
                "limit-uptime": "",
                "comment": "",
                "disabled": "false",
            }
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=users)):
            result = await _search_users("r1", "x")
        assert len(result) == 1
        assert result[0]["host-name"] == ""

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        with patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(side_effect=OSError("fail"))
        ):
            result = await _search_users("r1", "x")
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_name_key(self):
        users = [{"limit-bytes-total": "0"}]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=users)):
            result = await _search_users("r1", "x")
        assert result[0]["host-name"] == "\u2014"
        assert result[0]["user"] == ""

    @pytest.mark.asyncio
    async def test_multiple_users(self):
        users = [
            {
                "name": "a",
                "limit-bytes-total": "100",
                "limit-uptime": "1h",
                "comment": "",
                "disabled": "false",
            },
            {
                "name": "b",
                "limit-bytes-total": "200",
                "limit-uptime": "2h",
                "comment": "",
                "disabled": "true",
            },
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=users)):
            result = await _search_users("r1", "x")
        assert len(result) == 2
        assert result[1]["_disabled"] == "true"


class TestSearchHostsByField:
    @pytest.mark.asyncio
    async def test_success_mac(self):
        hosts = [
            {"host-name": "h1", "mac-address": "AA:BB:CC:DD:EE:FF", "address": "10.0.0.1"},
            {"host-name": "h2", "mac-address": "11:22:33:44:55:66", "address": "10.0.0.2"},
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=hosts)):
            result = await _search_hosts_by_field("r1", "mac-address", "AA:BB")
        assert len(result) == 1
        assert result[0]["host-name"] == "h1"

    @pytest.mark.asyncio
    async def test_success_ip(self):
        hosts = [
            {"host-name": "h1", "mac-address": "AA:BB", "address": "10.0.0.1"},
            {"host-name": "h2", "mac-address": "CC:DD", "address": "192.168.1.1"},
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=hosts)):
            result = await _search_hosts_by_field("r1", "address", "192.168")
        assert len(result) == 1
        assert result[0]["host-name"] == "h2"

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        with patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(side_effect=OSError("fail"))
        ):
            result = await _search_hosts_by_field("r1", "mac-address", "x")
        assert result == []

    @pytest.mark.asyncio
    async def test_field_none_value_filtered(self):
        hosts = [
            {"host-name": "h1", "mac-address": None, "address": "10.0.0.1"},
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=hosts)):
            result = await _search_hosts_by_field("r1", "mac-address", "aa")
        assert result == []

    @pytest.mark.asyncio
    async def test_case_insensitive(self):
        hosts = [{"host-name": "h1", "mac-address": "AA:BB:CC", "address": ""}]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=hosts)):
            result = await _search_hosts_by_field("r1", "mac-address", "aa:bb")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_no_match(self):
        hosts = [
            {"host-name": "h1", "mac-address": "AA:BB:CC", "address": "10.0.0.1"},
            {"host-name": "h2", "mac-address": "DD:EE:FF", "address": "10.0.0.2"},
        ]
        with patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=hosts)):
            result = await _search_hosts_by_field("r1", "mac-address", "ZZ:ZZ")
        assert result == []


class TestSearchHostsWithUsers:
    @pytest.mark.asyncio
    async def test_success(self):
        hosts = [
            {"host-name": "h1", "user": "admin", "address": "10.0.0.1", "mac-address": "AA:BB"}
        ]
        users = [{"name": "admin", "limit-bytes-total": "1024", "limit-uptime": "2h"}]
        with patch(
            "bot.handlers.hotspot_search.run_blocking",
            new=AsyncMock(side_effect=[hosts, users]),
        ):
            result = await _search_hosts_with_users("r1", "admin")
        assert len(result) == 1
        assert result[0]["_limit"] == "1024"

    @pytest.mark.asyncio
    async def test_hosts_exception(self):
        with patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(side_effect=OSError("fail"))
        ):
            result = await _search_hosts_with_users("r1", "x")
        assert result == []

    @pytest.mark.asyncio
    async def test_users_exception(self):
        hosts = [{"host-name": "h1", "user": "admin", "address": "", "mac-address": ""}]
        with patch(
            "bot.handlers.hotspot_search.run_blocking",
            new=AsyncMock(side_effect=[hosts, OSError("user fail")]),
        ):
            result = await _search_hosts_with_users("r1", "admin")
        assert len(result) == 1
        assert "_limit" not in result[0]

    @pytest.mark.asyncio
    async def test_empty_results(self):
        with patch(
            "bot.handlers.hotspot_search.run_blocking",
            new=AsyncMock(side_effect=[[], []]),
        ):
            result = await _search_hosts_with_users("r1", "x")
        assert result == []


class TestEnrichHosts:
    def test_matching_user(self):
        hosts = [{"host-name": "h1", "user": "admin", "address": "1.1.1.1", "mac-address": "AA"}]
        users = [
            {
                "name": "admin",
                "limit-bytes-total": "5000",
                "limit-uptime": "1d",
                "comment": "tester",
                "disabled": "true",
            }
        ]
        result = _enrich_hosts(hosts, users)
        assert result[0]["_limit"] == "5000"
        assert result[0]["_uptime"] == "1d"
        assert result[0]["_comment"] == "tester"
        assert result[0]["_disabled"] == "true"

    def test_no_matching_user(self):
        hosts = [{"host-name": "h1", "user": "guest", "address": "1.1.1.1", "mac-address": "AA"}]
        users = [{"name": "admin", "limit-bytes-total": "5000"}]
        result = _enrich_hosts(hosts, users)
        assert "_limit" not in result[0]

    def test_empty_hosts(self):
        assert _enrich_hosts([], [{"name": "admin"}]) == []

    def test_empty_users(self):
        hosts = [{"host-name": "h1", "user": "admin"}]
        result = _enrich_hosts(hosts, [])
        assert "_limit" not in result[0]

    def test_user_no_name(self):
        hosts = [{"host-name": "h1", "user": "admin"}]
        users = [{"name": "", "limit-bytes-total": "999"}]
        result = _enrich_hosts(hosts, users)
        assert "_limit" not in result[0]

    def test_host_no_user_field(self):
        hosts = [{"host-name": "h1", "address": "1.1.1.1", "mac-address": "AA"}]
        users = [{"name": "admin", "limit-bytes-total": "100"}]
        result = _enrich_hosts(hosts, users)
        assert "_limit" not in result[0]

    def test_host_user_none(self):
        hosts = [{"host-name": "h1", "user": None, "address": "1.1.1.1", "mac-address": "AA"}]
        users = [{"name": "admin", "limit-bytes-total": "100"}]
        result = _enrich_hosts(hosts, users)
        assert "_limit" not in result[0]

    def test_multiple_hosts_partial_match(self):
        hosts = [
            {"host-name": "h1", "user": "admin", "address": "1.1.1.1", "mac-address": "AA"},
            {"host-name": "h2", "user": "guest", "address": "1.1.1.2", "mac-address": "BB"},
        ]
        users = [{"name": "admin", "limit-bytes-total": "5000", "limit-uptime": "1d"}]
        result = _enrich_hosts(hosts, users)
        assert result[0]["_limit"] == "5000"
        assert "_limit" not in result[1]


class TestFormatSearchResultsText:
    def test_empty_results(self):
        paginator = Paginator([], page=0)
        text = _format_search_results_text(paginator)
        assert text == NO_RESULTS

    def test_with_results(self):
        hosts = [{"host-name": "Phone", "address": "10.0.0.5", "mac-address": "AA:BB:CC:DD:EE:FF"}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "Phone" in text
        assert "10.0.0.5" in text
        assert "AA:BB:CC:DD:EE:FF" in text
        assert "1" in text

    def test_with_limit_and_uptime(self):
        hosts = [
            {
                "host-name": "Dev",
                "address": "10.0.0.1",
                "mac-address": "AA:BB",
                "_limit": "1048576",
                "_uptime": "2h30m",
            }
        ]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "Dev" in text
        assert "2h30m" in text

    def test_with_comment(self):
        hosts = [
            {
                "host-name": "User1",
                "address": "10.0.0.1",
                "mac-address": "AA:BB",
                "_comment": "This is a long comment that should be truncated at 30 chars",
            }
        ]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "User1" in text

    def test_disabled_host(self):
        hosts = [
            {
                "host-name": "Off",
                "address": "10.0.0.1",
                "mac-address": "AA:BB",
                "_disabled": "true",
            }
        ]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert HOTSPOT_SEARCH_OFFLINE.strip() in text

    def test_no_hostname_uses_user(self):
        hosts = [{"user": "testuser", "address": "10.0.0.1", "mac-address": "AA:BB"}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "testuser" in text

    def test_no_name_no_user_uses_unknown(self):
        hosts = [{"address": "10.0.0.1", "mac-address": "AA:BB"}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert UNKNOWN_NAME in text

    def test_no_ip(self):
        hosts = [{"host-name": "h1", "mac-address": "AA:BB"}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "\u2014" in text

    def test_no_mac(self):
        hosts = [{"host-name": "h1", "address": "10.0.0.1"}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "\u2014" in text

    def test_header_format(self):
        hosts = [{"host-name": "h1", "address": "1.1.1.1", "mac-address": "AA:BB"}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert HOTSPOT_SEARCH_FOUND.format(count=1) in text
        assert "1" in text

    def test_multiple_pages_header(self):
        hosts = [
            {"host-name": f"h{i}", "address": f"1.1.1.{i}", "mac-address": f"AA:{i}"}
            for i in range(15)
        ]
        paginator = Paginator(hosts, page=1)
        text = _format_search_results_text(paginator)
        assert "2" in text
        assert "11" in text

    def test_disabled_false_not_shown(self):
        hosts = [
            {"host-name": "h1", "address": "1.1.1.1", "mac-address": "AA", "_disabled": "false"}
        ]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert HOTSPOT_SEARCH_OFFLINE.strip() not in text

    def test_empty_comment_not_shown(self):
        hosts = [{"host-name": "h1", "address": "1.1.1.1", "mac-address": "AA", "_comment": ""}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "\U0001f4ac" not in text

    def test_empty_limit_not_shown(self):
        hosts = [{"host-name": "h1", "address": "1.1.1.1", "mac-address": "AA", "_limit": ""}]
        paginator = Paginator(hosts, page=0)
        text = _format_search_results_text(paginator)
        assert "\U0001f4ca" not in text


class TestSearchBack:
    @pytest.mark.asyncio
    async def test_back_from_host_detail(self):
        update = _make_update_with_query("back")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"host-name": "x"}]
        ctx.user_data["kick_host_idx"] = 0

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.edit_clean", new=AsyncMock()
        ):
            result = await hotspot_search_back(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert "kick_host_idx" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_back_to_prompt_from_results(self):
        update = _make_update_with_query("back")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"host-name": "x"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.edit_clean", new=AsyncMock()
        ):
            result = await hotspot_search_back(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert "search_hosts" not in ctx.user_data

    @pytest.mark.asyncio
    async def test_back_initial_prompt(self):
        update = _make_update_with_query("back")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.edit_clean", new=AsyncMock()
        ):
            result = await hotspot_search_back(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_back_from_host_detail_clears_both_keys(self):
        update = _make_update_with_query("back")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"host-name": "x"}]
        ctx.user_data["kick_host_idx"] = 0

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.edit_clean", new=AsyncMock()
        ):
            result = await hotspot_search_back(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert "kick_host_idx" not in ctx.user_data


class TestShowHost:
    @pytest.mark.asyncio
    async def test_valid_index(self):
        update = _make_update_with_query("host_sel_0")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"host-name": "Phone", "address": "10.0.0.5", "mac-address": "AA:BB:CC:DD:EE:FF"}
        ]

        result = await hotspot_show_host(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert ctx.user_data["kick_host_idx"] == 0

    @pytest.mark.asyncio
    async def test_invalid_index(self):
        update = _make_update_with_query("host_sel_99")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"host-name": "x"}]

        with patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_show_host(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_negative_index(self):
        update = _make_update_with_query("host_sel_-1")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"host-name": "x"}]

        with patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_show_host(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_exception(self):
        update = _make_update_with_query("host_sel_abc")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"host-name": "x"}]

        with patch("bot.handlers.hotspot_search.send_error", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_show_host(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_uses_user_when_no_hostname(self):
        update = _make_update_with_query("host_sel_0")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"user": "user1", "address": "10.0.0.6", "mac-address": ""}
        ]

        result = await hotspot_show_host(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH
        assert ctx.user_data["kick_host_idx"] == 0

    @pytest.mark.asyncio
    async def test_no_name_no_user_uses_unknown(self):
        update = _make_update_with_query("host_sel_0")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [{"address": "10.0.0.1", "mac-address": "AA"}]

        result = await hotspot_show_host(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_disabled_host_detail(self):
        update = _make_update_with_query("host_sel_0")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"host-name": "Off", "address": "10.0.0.1", "mac-address": "AA:BB", "_disabled": "true"}
        ]

        with patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()):
            result = await hotspot_show_host(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_mac_dash_passthrough(self):
        update = _make_update_with_query("host_sel_0")
        ctx = _ctx()
        ctx.user_data["search_hosts"] = [
            {"host-name": "NoMac", "address": "10.0.0.1", "mac-address": ""}
        ]

        with patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()):
            result = await hotspot_show_host(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH


class TestHostAction:
    @pytest.mark.asyncio
    async def test_no_host_selected(self):
        update = _make_update_with_query("host_kick_execute")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch("bot.handlers.hotspot_search.cleanup_state"):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_invalid_host_index(self):
        update = _make_update_with_query("host_kick_execute")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = 99
        ctx.user_data["search_hosts"] = []

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch("bot.handlers.hotspot_search.cleanup_state"):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_no_router(self):
        update = _make_update_with_query("host_kick_execute")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = 0
        ctx.user_data["search_hosts"] = [{"mac-address": "AA:BB"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value=None
        ), patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_success(self):
        update = _make_update_with_query("host_kick_execute")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = 0
        ctx.user_data["search_hosts"] = [{"mac-address": "AA:BB:CC:DD:EE:FF"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=(True, "Phone"))
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_kick_failure(self):
        update = _make_update_with_query("host_kick_confirm")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = 0
        ctx.user_data["search_hosts"] = [{"mac-address": "AA:BB:CC:DD:EE:FF"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=(False, ""))
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_exception(self):
        update = _make_update_with_query("host_kick_confirm")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = 0
        ctx.user_data["search_hosts"] = [{"mac-address": "AA:BB"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(side_effect=OSError("boom"))
        ), patch(
            "bot.handlers.hotspot_search.send_error", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_fallback_to_address(self):
        update = _make_update_with_query("host_kick_execute")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = 0
        ctx.user_data["search_hosts"] = [{"address": "10.0.0.1"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=(True, "Host"))
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_negative_index(self):
        update = _make_update_with_query("host_kick_execute")
        ctx = _ctx()
        ctx.user_data["kick_host_idx"] = -1
        ctx.user_data["search_hosts"] = [{"mac-address": "AA:BB"}]

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch("bot.handlers.hotspot_search.cleanup_state"):
            result = await hotspot_host_action(update, ctx)
        assert result == ConversationHandler.END


class TestBlockMac:
    @pytest.mark.asyncio
    async def test_success(self):
        update = _make_update_with_query("block:AA:BB:CC:DD:EE:FF")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "utils.callback_utils.is_duplicate_callback", return_value=False
        ), patch("bot.handlers.hotspot_search.get_selected_router", return_value="r1"), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=True)
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await block_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_failure(self):
        update = _make_update_with_query("block:AA:BB:CC")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "utils.callback_utils.is_duplicate_callback", return_value=False
        ), patch("bot.handlers.hotspot_search.get_selected_router", return_value="r1"), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=False)
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await block_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_invalid_data(self):
        update = _make_update_with_query("block")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "utils.callback_utils.is_duplicate_callback", return_value=False
        ), patch("bot.handlers.hotspot_search.get_selected_router", return_value="r1"), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await block_mac_handler(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_no_router(self):
        update = _make_update_with_query("block:AA:BB:CC")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "utils.callback_utils.is_duplicate_callback", return_value=False
        ), patch("bot.handlers.hotspot_search.get_selected_router", return_value=None), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await block_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_duplicate(self):
        update = _make_update_with_query("block:AA:BB:CC")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "utils.callback_utils.is_duplicate_callback", return_value=True
        ):
            result = await block_mac_handler(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_value_error_on_split(self):
        update = _make_update_with_query("block:")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "utils.callback_utils.is_duplicate_callback", return_value=False
        ), patch("bot.handlers.hotspot_search.get_selected_router", return_value="r1"), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=False)
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await block_mac_handler(update, ctx)
        assert result == ConversationHandler.END


class TestUnblockMac:
    @pytest.mark.asyncio
    async def test_success(self):
        update = _make_update_with_query("unblock:AA:BB:CC:DD:EE:FF")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=True)
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await unblock_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_failure(self):
        update = _make_update_with_query("unblock:AA:BB:CC")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=False)
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await unblock_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_invalid_data(self):
        update = _make_update_with_query("unblock")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()):
            result = await unblock_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_no_router(self):
        update = _make_update_with_query("unblock:AA:BB:CC")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value=None
        ), patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()):
            result = await unblock_mac_handler(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_empty_mac_after_split(self):
        update = _make_update_with_query("unblock:")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=True)
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await unblock_mac_handler(update, ctx)
        assert result == ConversationHandler.END


class TestShowBlockedList:
    @pytest.mark.asyncio
    async def test_empty_list(self):
        update = _make_update_with_query("blocked_list")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch("bot.handlers.hotspot_search.run_blocking", new=AsyncMock(return_value=[])), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ):
            result = await show_blocked_list(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_with_entries(self):
        update = _make_update_with_query("blocked_list")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking",
            new=AsyncMock(return_value=["AA:BB:CC", "DD:EE:FF"]),
        ), patch(
            "bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.get_blocked_macs_keyboard", return_value=MagicMock()
        ):
            result = await show_blocked_list(update, ctx)
        assert result == WAITING_HOTSPOT_SEARCH

    @pytest.mark.asyncio
    async def test_no_router(self):
        update = _make_update_with_query("blocked_list")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value=None
        ), patch("bot.handlers.hotspot_search.safe_edit_plain", new=AsyncMock()):
            result = await show_blocked_list(update, ctx)
        assert result == ConversationHandler.END

    @pytest.mark.asyncio
    async def test_exception(self):
        update = _make_update_with_query("blocked_list")
        ctx = _ctx()

        with patch("bot.handlers.hotspot_search.safe_answer_callback", new=AsyncMock()), patch(
            "bot.handlers.hotspot_search.get_selected_router", return_value="r1"
        ), patch(
            "bot.handlers.hotspot_search.run_blocking", new=AsyncMock(side_effect=OSError("fail"))
        ), patch(
            "bot.handlers.hotspot_search.send_error", new=AsyncMock()
        ), patch(
            "bot.handlers.hotspot_search.cleanup_state"
        ):
            result = await show_blocked_list(update, ctx)
        assert result == ConversationHandler.END
