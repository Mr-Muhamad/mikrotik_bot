"""Comprehensive tests for bot.keyboards — all keyboard builder functions."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from telegram import InlineKeyboardMarkup

from bot.keyboards import (
    SUBMENU_PAGE_SIZE,
    TIME_OPTIONS,
    _logs_time_label,
    _user_button_label,
    get_back_keyboard,
    get_backup_download_keyboard,
    get_backup_keyboard,
    get_backup_restore_keyboard,
    get_batch_detail_keyboard,
    get_batches_keyboard,
    get_blocked_macs_keyboard,
    get_cancel_keyboard,
    get_card_mac_keyboard,
    get_card_payment_keyboard,
    get_card_type_keyboard,
    get_confirm_keyboard,
    get_delete_router_confirm_keyboard,
    get_delete_user_keyboard,
    get_discovered_routers_keyboard,
    get_edit_field_keyboard,
    get_edit_user_keyboard,
    get_host_detail_keyboard,
    get_hotspot_keyboard,
    get_logs_filter_keyboard,
    get_logs_submenu_keyboard,
    get_main_keyboard,
    get_nav_back_keyboard,
    get_operator_router_assignment_keyboard,
    get_paginated_user_keyboard,
    get_pdf_layout_keyboard,
    get_pdf_misc_keyboard,
    get_pdf_settings_keyboard,
    get_pdf_text_keyboard,
    get_profile_keyboard,
    get_reboot_keyboard,
    get_report_keyboard,
    get_reports_keyboard,
    get_restore_confirm_keyboard,
    get_router_action_keyboard,
    get_router_keyboard,
    get_routers_keyboard,
    get_saved_routers_keyboard,
    get_schedule_keyboard,
    get_search_results_keyboard,
    get_skip_keyboard,
    get_stats_keyboard,
    get_user_selection_keyboard,
    get_userman_detail_keyboard,
    get_userman_keyboard,
    get_userman_restore_confirm_keyboard,
    get_userman_restore_keyboard,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _btns(markup: InlineKeyboardMarkup) -> list[str]:
    """Extract all callback_data strings from a markup (flattened, row order)."""
    return [btn.callback_data for row in markup.inline_keyboard for btn in row]


def _row_count(markup: InlineKeyboardMarkup) -> int:
    return len(markup.inline_keyboard)


def _flat_btns(markup: InlineKeyboardMarkup) -> list[str]:
    return [btn.text for row in markup.inline_keyboard for btn in row]


def _mock_paginator(
    items: list[Any] | None = None,
    page: int = 0,
    page_size: int = 10,
    has_prev: bool = False,
    has_next: bool = False,
    total: int = 0,
) -> MagicMock:
    p = MagicMock()
    p.current_items = items if items is not None else []
    p.page = page
    p.page_size = page_size
    p.total = total
    p.has_prev.return_value = has_prev
    p.has_next.return_value = has_next
    p.prev_page.return_value = max(0, page - 1)
    p.next_page.return_value = page + 1
    return p


# ===========================================================================
# 1-7: Simple static keyboards (no parameters / minimal)
# ===========================================================================


class TestGetRouterKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_router_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        m = get_router_keyboard()
        assert _row_count(m) == 3

    def test_manual_add_uses_callback(self):
        m = get_router_keyboard()
        all_data = _btns(m)
        assert "saved_routers" in all_data
        assert "discover_routers" in all_data
        assert "manual_add_router" in all_data


class TestGetMainKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_main_keyboard(), InlineKeyboardMarkup)

    def test_five_rows(self):
        m = get_main_keyboard()
        assert _row_count(m) == 5

    def test_all_expected_callbacks(self):
        m = get_main_keyboard()
        all_data = _btns(m)
        expected = [
            "menu_routers",
            "watchdog_status",
            "menu_hotspot",
            "menu_userman",
            "hotspot_cards",
            "menu_pdf_settings",
            "menu_stats",
            "reports_menu",
            "menu_backup",
        ]
        for cb in expected:
            assert cb in all_data, f"Missing callback: {cb}"


class TestGetRoutersKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_routers_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        m = get_routers_keyboard()
        assert _row_count(m) == 3

    def test_has_manual_add_router(self):
        all_data = _btns(get_routers_keyboard())
        assert "manual_add_router" in all_data

    def test_has_main_menu_back(self):
        all_data = _btns(get_routers_keyboard())
        assert "main_menu" in all_data


class TestGetReportsKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_reports_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        assert _row_count(get_reports_keyboard()) == 3

    def test_callbacks(self):
        all_data = _btns(get_reports_keyboard())
        for cb in ["usage_start", "sales_summary", "batches_menu", "logs_menu", "main_menu"]:
            assert cb in all_data


class TestGetHotspotKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_hotspot_keyboard(), InlineKeyboardMarkup)

    def test_four_rows(self):
        assert _row_count(get_hotspot_keyboard()) == 4

    def test_callbacks(self):
        all_data = _btns(get_hotspot_keyboard())
        for cb in [
            "hotspot_add",
            "hotspot_edit",
            "hotspot_delete",
            "hotspot_search",
            "hotspot_cards",
            "hotspot_stats",
            "main_menu",
        ]:
            assert cb in all_data


class TestGetUsermanKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_userman_keyboard(), InlineKeyboardMarkup)

    def test_four_rows(self):
        assert _row_count(get_userman_keyboard()) == 4

    def test_callbacks(self):
        all_data = _btns(get_userman_keyboard())
        for cb in [
            "userman_cards",
            "userman_list",
            "userman_profiles",
            "userman_search",
            "main_menu",
        ]:
            assert cb in all_data


class TestGetStatsKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_stats_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        assert _row_count(get_stats_keyboard()) == 3

    def test_callbacks(self):
        all_data = _btns(get_stats_keyboard())
        for cb in ["stats_hotspot", "stats_userman", "stats_chart", "main_menu"]:
            assert cb in all_data


# ===========================================================================
# 8: get_report_keyboard
# ===========================================================================


class TestGetReportKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_report_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        assert _row_count(get_report_keyboard()) == 3

    def test_callbacks(self):
        all_data = _btns(get_report_keyboard())
        for cb in ["report_excel", "report_csv", "report_refresh", "main_menu"]:
            assert cb in all_data


# ===========================================================================
# 9: get_batches_keyboard
# ===========================================================================


class TestGetBatchesKeyboard:
    def test_empty_batches(self):
        m = get_batches_keyboard([], page=0, total=0, page_size=10)
        assert isinstance(m, InlineKeyboardMarkup)
        # Only the back button row
        assert _row_count(m) == 1

    def test_single_page_no_nav(self):
        batches = [{"id": 1, "name": "A", "count": 5}]
        m = get_batches_keyboard(batches, page=0, total=1, page_size=10)
        # 1 batch row + 1 back row
        assert _row_count(m) == 2
        assert "batch_sel:1" in _btns(m)

    def test_multi_page_shows_next(self):
        batches = [{"id": i, "name": f"B{i}", "count": i} for i in range(10)]
        m = get_batches_keyboard(batches, page=0, total=20, page_size=10)
        assert any("التالي" in t for t in _flat_btns(m))
        # no prev on first page
        assert not any("السابق" in t for t in _flat_btns(m))

    def test_multi_page_shows_prev_and_next(self):
        batches = [{"id": i, "name": f"B{i}", "count": i} for i in range(10)]
        m = get_batches_keyboard(batches, page=1, total=25, page_size=10)
        flat = _flat_btns(m)
        assert any("السابق" in t for t in flat)
        assert any("التالي" in t for t in flat)

    def test_last_page_no_next(self):
        batches = [{"id": 20, "name": "Last", "count": 1}]
        m = get_batches_keyboard(batches, page=2, total=21, page_size=10)
        flat = _flat_btns(m)
        assert any("السابق" in t for t in flat)
        assert not any("التالي" in t for t in flat)

    def test_batch_label_format(self):
        batches = [{"id": 42, "name": "MyBatch", "count": 99}]
        m = get_batches_keyboard(batches)
        flat = _flat_btns(m)
        assert any("MyBatch" in t and "99" in t for t in flat)


# ===========================================================================
# 10: get_batch_detail_keyboard
# ===========================================================================


class TestGetBatchDetailKeyboard:
    def test_unpaid_status(self):
        m = get_batch_detail_keyboard(5, "unpaid")
        flat = _flat_btns(m)
        assert any("تم الدفع" in t for t in flat)
        assert any("آجل" in t for t in flat)
        # "لم يُدفع" should NOT appear when unpaid
        assert not any("لم يُدفع" in t for t in flat)

    def test_paid_status(self):
        m = get_batch_detail_keyboard(5, "paid")
        flat = _flat_btns(m)
        assert not any("تم الدفع" in t for t in flat)
        assert any("لم يُدفع" in t for t in flat)
        assert any("آجل" in t for t in flat)

    def test_deferred_status(self):
        m = get_batch_detail_keyboard(5, "deferred")
        flat = _flat_btns(m)
        assert any("تم الدفع" in t for t in flat)
        assert any("لم يُدفع" in t for t in flat)
        assert not any("آجل" in t for t in flat)

    def test_always_has_regen_and_share(self):
        for status in ("paid", "unpaid", "deferred"):
            m = get_batch_detail_keyboard(1, status)
            btns = _btns(m)
            assert "batch_regen:1" in btns
            assert "share_card:1" in btns

    def test_always_has_back(self):
        m = get_batch_detail_keyboard(1, "unpaid")
        assert "batches_refresh" in _btns(m)

    def test_payment_cb_format(self):
        m = get_batch_detail_keyboard(7, "unpaid")
        all_data = _btns(m)
        assert "mark_paid:7" in all_data
        assert "mark_deferred:7" in all_data


# ===========================================================================
# 11-15: Backup & PDF keyboards
# ===========================================================================


class TestGetBackupKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_backup_keyboard(), InlineKeyboardMarkup)

    def test_four_rows(self):
        assert _row_count(get_backup_keyboard()) == 4

    def test_callbacks(self):
        all_data = _btns(get_backup_keyboard())
        for cb in [
            "backup_full",
            "backup_userman",
            "menu_schedule",
            "backup_restore",
            "userman_restore",
            "main_menu",
        ]:
            assert cb in all_data


class TestGetPdfSettingsKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_pdf_settings_keyboard(), InlineKeyboardMarkup)

    def test_four_rows(self):
        assert _row_count(get_pdf_settings_keyboard()) == 4

    def test_callbacks(self):
        all_data = _btns(get_pdf_settings_keyboard())
        for cb in ["pdf_group_text", "pdf_group_layout", "pdf_group_misc", "main_menu"]:
            assert cb in all_data


class TestGetPdfTextKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_pdf_text_keyboard(), InlineKeyboardMarkup)

    def test_four_rows(self):
        assert _row_count(get_pdf_text_keyboard()) == 4

    def test_callbacks(self):
        all_data = _btns(get_pdf_text_keyboard())
        for cb in [
            "pdf_brand_name",
            "pdf_hotspot_dns",
            "pdf_footer",
            "pdf_value_font_size",
            "menu_pdf_settings",
        ]:
            assert cb in all_data


class TestGetPdfLayoutKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_pdf_layout_keyboard(), InlineKeyboardMarkup)

    def test_five_rows(self):
        assert _row_count(get_pdf_layout_keyboard()) == 5

    def test_callbacks(self):
        all_data = _btns(get_pdf_layout_keyboard())
        for cb in [
            "pdf_margins",
            "pdf_spacing",
            "pdf_cards_per_row",
            "pdf_cards_per_page",
            "pdf_label_spacing",
            "menu_pdf_settings",
        ]:
            assert cb in all_data


class TestGetPdfMiscKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_pdf_misc_keyboard(), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_pdf_misc_keyboard()) == 2

    def test_callbacks(self):
        all_data = _btns(get_pdf_misc_keyboard())
        assert "pdf_show_qr" in all_data
        assert "menu_pdf_settings" in all_data


# ===========================================================================
# 16-18: Card keyboards
# ===========================================================================


class TestGetCardTypeKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_card_type_keyboard(), InlineKeyboardMarkup)

    def test_four_rows(self):
        assert _row_count(get_card_type_keyboard()) == 4

    def test_callbacks(self):
        all_data = _btns(get_card_type_keyboard())
        for cb in ["card_type1", "card_type2", "card_type3", "menu_userman"]:
            assert cb in all_data


class TestGetCardPaymentKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_card_payment_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        assert _row_count(get_card_payment_keyboard()) == 3

    def test_callbacks(self):
        all_data = _btns(get_card_payment_keyboard())
        for cb in ["card_paid", "card_unpaid", "card_back_to_profile"]:
            assert cb in all_data


class TestGetCardMacKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_card_mac_keyboard(), InlineKeyboardMarkup)

    def test_three_rows(self):
        assert _row_count(get_card_mac_keyboard()) == 3

    def test_callbacks(self):
        all_data = _btns(get_card_mac_keyboard())
        for cb in ["card_bind_known", "card_no_bind", "card_back_to_payment"]:
            assert cb in all_data


# ===========================================================================
# 19: get_profile_keyboard
# ===========================================================================


class TestGetProfileKeyboard:
    def test_empty_profiles(self):
        m = get_profile_keyboard([], "pfx")
        assert isinstance(m, InlineKeyboardMarkup)
        # back + home rows only
        assert _row_count(m) == 2

    def test_profiles_with_prefix(self):
        m = get_profile_keyboard(["1M", "5M", "10M"], "hs_card_profile")
        all_data = _btns(m)
        assert "hs_card_profile_0" in all_data
        assert "hs_card_profile_1" in all_data
        assert "hs_card_profile_2" in all_data

    def test_custom_back_callback(self):
        m = get_profile_keyboard(["P1"], "add_profile", back_callback="custom_back")
        all_data = _btns(m)
        assert "custom_back" in all_data
        assert "main_menu" in all_data

    def test_default_back_callback(self):
        m = get_profile_keyboard(["P1"], "add_profile")
        assert "main_menu" in _btns(m)

    def test_profile_names_in_text(self):
        m = get_profile_keyboard(["Gold", "Silver"], "pfx")
        flat = _flat_btns(m)
        assert "Gold" in flat
        assert "Silver" in flat

    def test_row_count_matches_profiles(self):
        profiles = ["A", "B", "C"]
        m = get_profile_keyboard(profiles, "x")
        # 3 profile rows + back + home = 5
        assert _row_count(m) == len(profiles) + 2


# ===========================================================================
# 20: get_confirm_keyboard
# ===========================================================================


class TestGetConfirmKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_confirm_keyboard(), InlineKeyboardMarkup)

    def test_single_row_two_buttons(self):
        m = get_confirm_keyboard()
        assert _row_count(m) == 1
        assert len(m.inline_keyboard[0]) == 2

    def test_callbacks(self):
        all_data = _btns(get_confirm_keyboard())
        assert "confirm_yes" in all_data
        assert "confirm_no" in all_data


# ===========================================================================
# 21: get_discovered_routers_keyboard
# ===========================================================================


class TestGetDiscoveredRoutersKeyboard:
    def test_empty_list(self):
        m = get_discovered_routers_keyboard([])
        assert isinstance(m, InlineKeyboardMarkup)
        # refresh + back = 2 rows
        assert _row_count(m) == 2

    def test_with_routers(self):
        r1 = MagicMock()
        r1.display_name.return_value = "Router A"
        r1.ip_address = "192.168.1.1"
        r2 = MagicMock()
        r2.display_name.return_value = "Router B"
        r2.ip_address = "10.0.0.1"
        m = get_discovered_routers_keyboard([r1, r2])
        all_data = _btns(m)
        assert "disc_router_192.168.1.1" in all_data
        assert "disc_router_10.0.0.1" in all_data
        assert "discover_routers" in all_data
        assert "main_menu" in all_data
        # 2 routers + refresh + back
        assert _row_count(m) == 4

    def test_router_names_in_text(self):
        r1 = MagicMock()
        r1.display_name.return_value = "MyRouter"
        r1.ip_address = "1.2.3.4"
        m = get_discovered_routers_keyboard([r1])
        flat = _flat_btns(m)
        assert "MyRouter" in flat


# ===========================================================================
# 22: get_saved_routers_keyboard
# ===========================================================================


class TestGetSavedRoutersKeyboard:
    def test_empty_list(self):
        m = get_saved_routers_keyboard([])
        assert isinstance(m, InlineKeyboardMarkup)
        assert _row_count(m) == 2

    def test_router_with_version(self):
        r = {"id": 1, "name_alias": "Main", "ip_address": "10.0.0.1", "version": "7.12"}
        m = get_saved_routers_keyboard([r])
        flat = _flat_btns(m)
        assert any("Main" in t and "v7.12" in t for t in flat)

    def test_router_without_version(self):
        r = {"id": 2, "identity": "Core", "ip_address": "192.168.1.1"}
        m = get_saved_routers_keyboard([r])
        flat = _flat_btns(m)
        assert any("Core" in t for t in flat)

    def test_callback_format(self):
        r = {"id": 42, "name_alias": "R", "ip_address": "1.1.1.1"}
        m = get_saved_routers_keyboard([r])
        assert "saved_router_42" in _btns(m)

    def test_refresh_and_back(self):
        r = {"id": 1, "ip_address": "1.1.1.1"}
        m = get_saved_routers_keyboard([r])
        all_data = _btns(m)
        assert "refresh_routers" in all_data
        assert "main_menu" in all_data

    def test_multiple_routers(self):
        routers = [
            {"id": i, "name_alias": f"R{i}", "ip_address": f"10.0.0.{i}"}
            for i in range(5)
        ]
        m = get_saved_routers_keyboard(routers)
        # 5 routers + refresh + back = 7 rows
        assert _row_count(m) == 7

    def test_alias_takes_priority(self):
        r = {"id": 1, "name_alias": "Alias", "identity": "Identity", "ip_address": "1.1.1.1"}
        m = get_saved_routers_keyboard([r])
        flat = _flat_btns(m)
        assert any("Alias" in t for t in flat)


# ===========================================================================
# 23-24: Router action / delete confirm keyboards
# ===========================================================================


class TestGetRouterActionKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_router_action_keyboard(42), InlineKeyboardMarkup)

    def test_three_rows(self):
        assert _row_count(get_router_action_keyboard(1)) == 3

    def test_callbacks(self):
        all_data = _btns(get_router_action_keyboard(7))
        assert "connect_router_7" in all_data
        assert "reboot_router_7" in all_data
        assert "rename_router_7" in all_data
        assert "delete_router_7" in all_data
        assert "saved_routers" in all_data


class TestGetDeleteRouterConfirmKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_delete_router_confirm_keyboard(99), InlineKeyboardMarkup)

    def test_single_row_two_buttons(self):
        m = get_delete_router_confirm_keyboard(99)
        assert _row_count(m) == 1
        assert len(m.inline_keyboard[0]) == 2

    def test_callbacks(self):
        all_data = _btns(get_delete_router_confirm_keyboard(5))
        assert "confirm_delete_router_yes_5" in all_data
        assert "confirm_delete_router_no_5" in all_data


# ===========================================================================
# 25: get_schedule_keyboard
# ===========================================================================


class TestGetScheduleKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_schedule_keyboard(), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_schedule_keyboard()) == 2

    def test_callbacks(self):
        all_data = _btns(get_schedule_keyboard())
        assert "schedule_enable" in all_data
        assert "schedule_disable" in all_data
        assert "menu_backup" in all_data


# ===========================================================================
# 26: get_reboot_keyboard
# ===========================================================================


class TestGetRebootKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_reboot_keyboard("router_key_1"), InlineKeyboardMarkup)

    def test_single_row_two_buttons(self):
        m = get_reboot_keyboard("rk")
        assert _row_count(m) == 1
        assert len(m.inline_keyboard[0]) == 2

    def test_callback_includes_router_key(self):
        m = get_reboot_keyboard("my_router")
        all_data = _btns(m)
        assert "reboot_yes_my_router" in all_data
        assert "reboot_no" in all_data


# ===========================================================================
# 27-28: _user_button_label and get_user_selection_keyboard
# ===========================================================================


class TestUserButtonLabel:
    def test_name_only(self):
        assert _user_button_label({"name": "John"}) == "John"

    def test_name_with_comment(self):
        assert _user_button_label({"name": "John", "comment": "Admin"}) == "John (Admin)"

    def test_empty_comment(self):
        assert _user_button_label({"name": "John", "comment": ""}) == "John"

    def test_missing_name(self):
        assert _user_button_label({}) == "N/A"

    def test_truncation_at_35_chars(self):
        long_name = "A" * 40
        result = _user_button_label({"name": long_name})
        assert len(result) == 35
        assert result.endswith("...")

    def test_exact_35_chars_no_truncation(self):
        name = "A" * 35
        assert _user_button_label({"name": name}) == name

    def test_36_chars_truncated(self):
        name = "A" * 36
        result = _user_button_label({"name": name})
        assert result == "A" * 32 + "..."
        assert len(result) == 35

    def test_truncation_with_comment(self):
        # name + comment + " ()" should exceed 35
        result = _user_button_label({"name": "A" * 20, "comment": "B" * 20})
        assert len(result) == 35
        assert result.endswith("...")


class TestGetUserSelectionKeyboard:
    def test_empty_users(self):
        m = get_user_selection_keyboard([], "edit_user")
        assert isinstance(m, InlineKeyboardMarkup)
        assert _row_count(m) == 2

    def test_with_users(self):
        users = [
            {".id": "*1", "name": "Alice"},
            {".id": "*2", "name": "Bob"},
        ]
        m = get_user_selection_keyboard(users, "edit_user")
        all_data = _btns(m)
        assert "edit_user_*1" in all_data
        assert "edit_user_*2" in all_data

    def test_user_id_fallback(self):
        users = [{"name": "NoId"}]
        m = get_user_selection_keyboard(users, "del_user")
        assert "del_user_*0" in _btns(m)

    def test_custom_back_callback(self):
        m = get_user_selection_keyboard([], "x", back_callback="custom_back")
        assert "custom_back" in _btns(m)

    def test_default_back_callback(self):
        m = get_user_selection_keyboard([], "x")
        assert "menu_hotspot" in _btns(m)

    def test_user_names_in_text(self):
        users = [{".id": "*1", "name": "Charlie"}]
        m = get_user_selection_keyboard(users, "edit_user")
        flat = _flat_btns(m)
        assert "Charlie" in flat

    def test_home_always_present(self):
        m = get_user_selection_keyboard([], "x")
        assert "main_menu" in _btns(m)


# ===========================================================================
# 29: get_paginated_user_keyboard
# ===========================================================================


class TestGetPaginatedUserKeyboard:
    def test_empty_items(self):
        p = _mock_paginator(items=[], page=0, has_prev=False, has_next=False)
        m = get_paginated_user_keyboard([], "edit_user", p)
        assert isinstance(m, InlineKeyboardMarkup)
        # only back + home
        assert _row_count(m) == 2

    def test_with_users(self):
        users = [{".id": "*1", "name": "Alice"}, {".id": "*2", "name": "Bob"}]
        p = _mock_paginator(items=users, page=0, has_prev=False, has_next=False)
        m = get_paginated_user_keyboard(users, "edit_user", p)
        all_data = _btns(m)
        assert "edit_user_*1" in all_data
        assert "edit_user_*2" in all_data

    def test_pagination_with_prev_and_next(self):
        users = [{".id": "*1", "name": "X"}]
        p = _mock_paginator(items=users, page=1, has_prev=True, has_next=True)
        m = get_paginated_user_keyboard(users, "hs_del", p)
        flat = _flat_btns(m)
        assert any("السابق" in t for t in flat)
        assert any("التالي" in t for t in flat)

    def test_pagination_prev_only(self):
        users = [{".id": "*1", "name": "X"}]
        p = _mock_paginator(items=users, page=2, has_prev=True, has_next=False)
        m = get_paginated_user_keyboard(users, "hs_del", p)
        flat = _flat_btns(m)
        assert any("السابق" in t for t in flat)
        assert not any("التالي" in t for t in flat)

    def test_pagination_next_only(self):
        users = [{".id": "*1", "name": "X"}]
        p = _mock_paginator(items=users, page=0, has_prev=False, has_next=True)
        m = get_paginated_user_keyboard(users, "hs_del", p)
        flat = _flat_btns(m)
        assert not any("السابق" in t for t in flat)
        assert any("التالي" in t for t in flat)

    def test_custom_back(self):
        p = _mock_paginator(items=[], page=0, has_prev=False, has_next=False)
        m = get_paginated_user_keyboard([], "x", p, back_callback="go_back")
        assert "go_back" in _btns(m)

    def test_page_numbers_in_nav(self):
        users = [{".id": "*1", "name": "X"}]
        p = _mock_paginator(items=users, page=1, has_prev=True, has_next=True)
        m = get_paginated_user_keyboard(users, "edit_user", p)
        flat = _flat_btns(m)
        # prev page label should show current page (1)
        assert any("1" in t and "السابق" in t for t in flat)
        # next page label should show page+2 (3)
        assert any("3" in t and "التالي" in t for t in flat)


# ===========================================================================
# 30-31: get_edit_user_keyboard, get_delete_user_keyboard
# ===========================================================================


class TestGetEditUserKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_edit_user_keyboard([]), InlineKeyboardMarkup)

    def test_uses_edit_user_prefix(self):
        users = [{".id": "*5", "name": "Test"}]
        m = get_edit_user_keyboard(users)
        assert "edit_user_*5" in _btns(m)

    def test_back_is_menu_hotspot(self):
        m = get_edit_user_keyboard([])
        assert "menu_hotspot" in _btns(m)


class TestGetDeleteUserKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_delete_user_keyboard([]), InlineKeyboardMarkup)

    def test_uses_delete_user_prefix(self):
        users = [{".id": "*3", "name": "Del"}]
        m = get_delete_user_keyboard(users)
        assert "delete_user_*3" in _btns(m)

    def test_back_is_menu_hotspot(self):
        m = get_delete_user_keyboard([])
        assert "menu_hotspot" in _btns(m)


# ===========================================================================
# 32: get_edit_field_keyboard
# ===========================================================================


class TestGetEditFieldKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_edit_field_keyboard(), InlineKeyboardMarkup)

    def test_not_disabled_default(self):
        m = get_edit_field_keyboard()
        flat = _flat_btns(m)
        assert any("تعطيل" in t for t in flat)
        assert not any("تفعيل المستخدم" in t for t in flat)

    def test_disabled_shows_enable(self):
        m = get_edit_field_keyboard(is_disabled=True)
        flat = _flat_btns(m)
        assert any("تفعيل" in t for t in flat)

    def test_not_disabled_shows_disable(self):
        m = get_edit_field_keyboard(is_disabled=False)
        flat = _flat_btns(m)
        assert any("تعطيل" in t for t in flat)

    def test_all_field_callbacks(self):
        m = get_edit_field_keyboard()
        all_data = _btns(m)
        expected = [
            "edit_field_name",
            "edit_field_password",
            "edit_field_profile",
            "edit_field_bytes",
            "edit_field_uptime",
            "edit_field_comment",
            "edit_field_renewal_day",
            "edit_field_toggle_disabled",
            "edit_field_reset",
            "edit_kick_user",
            "edit_back_search",
            "main_menu",
        ]
        for cb in expected:
            assert cb in all_data, f"Missing: {cb}"


# ===========================================================================
# 33-36: Back / nav / skip / cancel keyboards
# ===========================================================================


class TestGetBackKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_back_keyboard("some_cb"), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_back_keyboard("x")) == 2

    def test_custom_callback(self):
        m = get_back_keyboard("custom_back")
        assert "custom_back" in _btns(m)
        assert "main_menu" in _btns(m)


class TestGetNavBackKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_nav_back_keyboard(), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_nav_back_keyboard()) == 2

    def test_callbacks(self):
        all_data = _btns(get_nav_back_keyboard())
        assert "go_back" in all_data
        assert "main_menu" in all_data


class TestGetSkipKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_skip_keyboard("skip_cb", "back_cb"), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_skip_keyboard("a", "b")) == 2

    def test_callbacks(self):
        m = get_skip_keyboard("skip_me", "go_back")
        all_data = _btns(m)
        assert "skip_me" in all_data
        assert "go_back" in all_data
        assert "main_menu" in all_data


class TestGetCancelKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_cancel_keyboard(), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_cancel_keyboard()) == 2

    def test_callbacks(self):
        all_data = _btns(get_cancel_keyboard())
        assert "cancel_edit" in all_data
        assert "main_menu" in all_data


# ===========================================================================
# 37: get_search_results_keyboard
# ===========================================================================


class TestGetSearchResultsKeyboard:
    def test_empty_paginator(self):
        p = _mock_paginator(items=[], page=0, page_size=10, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p, is_userman=False)
        assert isinstance(m, InlineKeyboardMarkup)
        # Only back row
        assert _row_count(m) == 1

    def test_hotspot_search_items(self):
        items = [{"name": "host1", "address": "192.168.1.5"}]
        p = _mock_paginator(items=items, page=0, page_size=10, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p, is_userman=False)
        flat = _flat_btns(m)
        assert any("host1" in t for t in flat)
        all_data = _btns(m)
        assert "host_sel_0" in all_data

    def test_userman_search_items(self):
        items = [{"user": "user1", "address": "10.0.0.5"}]
        p = _mock_paginator(items=items, page=0, page_size=10, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p, is_userman=True)
        all_data = _btns(m)
        assert "um_sel_0" in all_data

    def test_userman_pagination(self):
        items = [{"user": "u1"}]
        p = _mock_paginator(items=items, page=1, page_size=5, has_prev=True, has_next=True)
        m = get_search_results_keyboard(p, is_userman=True)
        flat = _flat_btns(m)
        assert any("السابق" in t for t in flat)
        assert any("التالي" in t for t in flat)
        all_data = _btns(m)
        assert "um_search_pg_0" in all_data
        assert "um_search_pg_2" in all_data

    def test_hotspot_pagination(self):
        items = [{"name": "h1"}]
        p = _mock_paginator(items=items, page=1, page_size=5, has_prev=True, has_next=False)
        m = get_search_results_keyboard(p, is_userman=False)
        all_data = _btns(m)
        assert "hs_search_pg_0" in all_data

    def test_absolute_index_offset(self):
        items = [{"name": "h1"}, {"name": "h2"}]
        p = _mock_paginator(items=items, page=2, page_size=5, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p, is_userman=False)
        all_data = _btns(m)
        # start_idx = 2*5=10, so first item index=10, second=11
        assert "host_sel_10" in all_data
        assert "host_sel_11" in all_data

    def test_fallback_name_fields(self):
        items = [{"host-name": "hn", "address": "1.1.1.1"}]
        p = _mock_paginator(items=items, page=0, page_size=10, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p, is_userman=False)
        flat = _flat_btns(m)
        assert any("hn" in t for t in flat)

    def test_unknown_fallback(self):
        items: list[dict[str, Any]] = [{"address": "5.5.5.5"}]
        p = _mock_paginator(items=items, page=0, page_size=10, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p, is_userman=False)
        flat = _flat_btns(m)
        assert any("غير معروف" in t for t in flat)

    def test_back_button(self):
        p = _mock_paginator(items=[], page=0, page_size=10, has_prev=False, has_next=False)
        m = get_search_results_keyboard(p)
        assert "search_back" in _btns(m)


# ===========================================================================
# 38: get_host_detail_keyboard
# ===========================================================================


class TestGetHostDetailKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_host_detail_keyboard(), InlineKeyboardMarkup)

    def test_not_disabled_default(self):
        m = get_host_detail_keyboard()
        flat = _flat_btns(m)
        assert any("تعطيل المستخدم" in t for t in flat)

    def test_disabled_shows_enable(self):
        m = get_host_detail_keyboard(is_disabled=True)
        flat = _flat_btns(m)
        assert any("تفعيل المستخدم" in t for t in flat)

    def test_with_mac_shows_block(self):
        m = get_host_detail_keyboard(mac="AA:BB:CC:DD:EE:FF")
        all_data = _btns(m)
        assert "block_mac:AA:BB:CC:DD:EE:FF" in all_data

    def test_without_mac_no_block(self):
        m = get_host_detail_keyboard(mac="")
        all_data = _btns(m)
        assert not any("block_mac:" in cb for cb in all_data)

    def test_always_has_kick(self):
        m = get_host_detail_keyboard()
        all_data = _btns(m)
        assert "host_kick_execute" in all_data

    def test_always_has_blocked_list_and_back(self):
        m = get_host_detail_keyboard()
        all_data = _btns(m)
        assert "blocked_list" in all_data
        assert "search_back" in all_data


# ===========================================================================
# 39: get_blocked_macs_keyboard
# ===========================================================================


class TestGetBlockedMacsKeyboard:
    def test_empty_list(self):
        m = get_blocked_macs_keyboard([])
        assert isinstance(m, InlineKeyboardMarkup)
        assert _row_count(m) == 1

    def test_with_entries(self):
        blocked = [
            {"address": "AA:BB:CC:DD:EE:FF", "comment": "Spam"},
            {"address": "11:22:33:44:55:66", "comment": ""},
        ]
        m = get_blocked_macs_keyboard(blocked)
        all_data = _btns(m)
        assert "unblock_mac:AA:BB:CC:DD:EE:FF" in all_data
        assert "unblock_mac:11:22:33:44:55:66" in all_data
        assert _row_count(m) == 3

    def test_label_format_with_comment(self):
        blocked = [{"address": "AA:BB:CC:DD:EE:FF", "comment": "EvilDevice"}]
        m = get_blocked_macs_keyboard(blocked)
        flat = _flat_btns(m)
        assert any("AA:BB:CC:DD:EE:FF" in t for t in flat)

    def test_comment_truncation(self):
        blocked = [{"address": "AA:BB:CC:DD:EE:FF", "comment": "A" * 30}]
        m = get_blocked_macs_keyboard(blocked)
        flat = _flat_btns(m)
        assert any("A" * 15 in t for t in flat)

    def test_back_button(self):
        m = get_blocked_macs_keyboard([])
        assert "hotspot_search" in _btns(m)


# ===========================================================================
# 40: get_userman_detail_keyboard
# ===========================================================================


class TestGetUsermanDetailKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_userman_detail_keyboard(), InlineKeyboardMarkup)

    def test_five_rows(self):
        assert _row_count(get_userman_detail_keyboard()) == 5

    def test_not_disabled(self):
        m = get_userman_detail_keyboard(is_disabled=False)
        flat = _flat_btns(m)
        assert any("تعطيل المستخدم" in t for t in flat)

    def test_disabled(self):
        m = get_userman_detail_keyboard(is_disabled=True)
        flat = _flat_btns(m)
        assert any("تفعيل المستخدم" in t for t in flat)

    def test_callbacks(self):
        all_data = _btns(get_userman_detail_keyboard())
        for cb in [
            "um_kick_execute",
            "um_reset_counters",
            "um_toggle_disabled",
            "um_add_profile",
            "um_delete",
            "search_back",
        ]:
            assert cb in all_data


# ===========================================================================
# 41-42: _logs_time_label and get_logs_filter_keyboard
# ===========================================================================


class TestLogsTimeLabel:
    def test_none_days(self):
        assert _logs_time_label({}) == "الكل"

    def test_none_explicit(self):
        assert _logs_time_label({"since_days": None}) == "الكل"

    def test_one_day(self):
        assert _logs_time_label({"since_days": 1}) == "اليوم"

    def test_seven_days(self):
        assert _logs_time_label({"since_days": 7}) == "آخر 7 أيام"

    def test_thirty_days(self):
        assert _logs_time_label({"since_days": 30}) == "آخر 30 يوماً"

    def test_unknown_value(self):
        assert _logs_time_label({"since_days": 99}) == "الكل"


class TestGetLogsFilterKeyboard:
    def test_empty_filters(self):
        m = get_logs_filter_keyboard({}, page=0, total=0, page_size=10)
        assert isinstance(m, InlineKeyboardMarkup)
        flat = _flat_btns(m)
        # All labels show "الكل"
        assert any("الكل" in t for t in flat)

    def test_with_filters(self):
        f = {"router": "R1", "admin_label": "Admin", "action": "backup", "since_days": 7}
        m = get_logs_filter_keyboard(f)
        flat = _flat_btns(m)
        assert any("R1" in t for t in flat)
        assert any("Admin" in t for t in flat)
        assert any("backup" in t for t in flat)

    def test_filter_button_callbacks(self):
        m = get_logs_filter_keyboard({})
        all_data = _btns(m)
        assert "logs_filter_router" in all_data
        assert "logs_filter_admin" in all_data
        assert "logs_filter_action" in all_data
        assert "logs_filter_time" in all_data

    def test_clear_button_when_filters_active(self):
        f = {"router": "R1"}
        m = get_logs_filter_keyboard(f)
        all_data = _btns(m)
        assert "logs_clear" in all_data

    def test_no_clear_button_without_filters(self):
        m = get_logs_filter_keyboard({})
        all_data = _btns(m)
        assert "logs_clear" not in all_data

    def test_pagination_no_nav(self):
        m = get_logs_filter_keyboard({}, page=0, total=5, page_size=10)
        flat = _flat_btns(m)
        assert not any("السابق" in t for t in flat)
        assert not any("التالي" in t for t in flat)

    def test_pagination_prev_and_next(self):
        m = get_logs_filter_keyboard({}, page=1, total=25, page_size=10)
        flat = _flat_btns(m)
        assert any("السابس" in t for t in flat)
        assert any("التالي" in t for t in flat)

    def test_pagination_prev_only(self):
        m = get_logs_filter_keyboard({}, page=2, total=25, page_size=10)
        flat = _flat_btns(m)
        assert any("السابس" in t for t in flat)
        assert not any("التالي" in t for t in flat)

    def test_nav_callbacks(self):
        m = get_logs_filter_keyboard({}, page=1, total=25, page_size=10)
        all_data = _btns(m)
        assert "logs_page_0" in all_data
        assert "logs_page_2" in all_data

    def test_admin_id_fallback(self):
        f = {"admin_id": "12345"}
        m = get_logs_filter_keyboard(f)
        flat = _flat_btns(m)
        assert any("12345" in t for t in flat)

    def test_home_button(self):
        m = get_logs_filter_keyboard({})
        assert "main_menu" in _btns(m)


# ===========================================================================
# 43: get_logs_submenu_keyboard
# ===========================================================================


class TestGetLogsSubmenuKeyboard:
    def test_empty_options(self):
        m = get_logs_submenu_keyboard("router", [])
        assert isinstance(m, InlineKeyboardMarkup)
        # only back button
        assert _row_count(m) == 1

    def test_options_within_page(self):
        opts = ["opt1", "opt2", "opt3"]
        m = get_logs_submenu_keyboard("router", opts, page=0, page_size=20)
        # 3 option rows + back = 4
        assert _row_count(m) == 4
        all_data = _btns(m)
        assert "logs_set_router_0" in all_data
        assert "logs_set_router_1" in all_data
        assert "logs_set_router_2" in all_data

    def test_pagination_shows_next(self):
        opts = list(range(25))
        m = get_logs_submenu_keyboard("admin", opts, page=0, page_size=20)
        flat = _flat_btns(m)
        assert any("التالي" in t for t in flat)

    def test_pagination_shows_prev_and_next(self):
        opts = list(range(45))
        m = get_logs_submenu_keyboard("action", opts, page=1, page_size=20)
        flat = _flat_btns(m)
        assert any("السابق" in t for t in flat)
        assert any("التالي" in t for t in flat)

    def test_long_label_truncation(self):
        opts = ["A" * 80]
        m = get_logs_submenu_keyboard("router", opts, page=0, page_size=20)
        flat = _flat_btns(m)
        assert any("..." in t for t in flat)
        assert not any("A" * 80 in t for t in flat)

    def test_label_under_60_not_truncated(self):
        opts = ["A" * 60]
        m = get_logs_submenu_keyboard("router", opts, page=0, page_size=20)
        flat = _flat_btns(m)
        assert any("A" * 60 in t for t in flat)

    def test_back_button(self):
        m = get_logs_submenu_keyboard("router", ["x"])
        assert "logs_back" in _btns(m)


# ===========================================================================
# 44-46: Backup restore / confirm / download keyboards
# ===========================================================================


class TestGetBackupRestoreKeyboard:
    def test_empty_list(self):
        m = get_backup_restore_keyboard([])
        assert isinstance(m, InlineKeyboardMarkup)
        assert _row_count(m) == 1

    def test_with_backups(self):
        backups = [
            {"name": "backup1.rsc", "type": "system"},
            {"name": "backup2.tar", "type": "userman"},
        ]
        m = get_backup_restore_keyboard(backups)
        all_data = _btns(m)
        assert "restore:0" in all_data
        assert "restore:1" in all_data
        assert _row_count(m) == 3

    def test_system_type_icon(self):
        backups = [{"name": "b.rsc", "type": "system"}]
        m = get_backup_restore_keyboard(backups)
        flat = _flat_btns(m)
        assert any("📦" in t for t in flat)

    def test_non_system_type_icon(self):
        backups = [{"name": "b.tar", "type": "other"}]
        m = get_backup_restore_keyboard(backups)
        flat = _flat_btns(m)
        assert any("📄" in t for t in flat)

    def test_max_10_backups(self):
        backups = [{"name": f"b{i}.rsc", "type": "system"} for i in range(20)]
        m = get_backup_restore_keyboard(backups)
        # 10 backups + back
        assert _row_count(m) == 11

    def test_back_button(self):
        m = get_backup_restore_keyboard([])
        assert "menu_backup" in _btns(m)


class TestGetRestoreConfirmKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_restore_confirm_keyboard(), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_restore_confirm_keyboard()) == 2

    def test_callbacks(self):
        all_data = _btns(get_restore_confirm_keyboard())
        assert "confirm_restore" in all_data
        assert "menu_backup" in all_data


class TestGetBackupDownloadKeyboard:
    def test_empty_downloads(self):
        m = get_backup_download_keyboard([], "full")
        assert isinstance(m, InlineKeyboardMarkup)
        assert _row_count(m) == 1

    def test_with_files(self):
        m = get_backup_download_keyboard(["file1.rsc", "file2.rsc"], "full")
        all_data = _btns(m)
        assert "backup_dl:full:0" in all_data
        assert "backup_dl:full:1" in all_data
        assert _row_count(m) == 3

    def test_userman_type(self):
        m = get_backup_download_keyboard(["db.tar"], "userman")
        all_data = _btns(m)
        assert "backup_dl:userman:0" in all_data

    def test_back_button(self):
        m = get_backup_download_keyboard(["f.rsc"], "full")
        assert "menu_backup" in _btns(m)


# ===========================================================================
# 47-48: Userman restore keyboards
# ===========================================================================


class TestGetUsermanRestoreKeyboard:
    def test_empty_list(self):
        m = get_userman_restore_keyboard([])
        assert isinstance(m, InlineKeyboardMarkup)
        assert _row_count(m) == 1

    def test_with_files(self):
        files = [
            {"filename": "um_backup.tar", "size": 204800},
            {"filename": "um_small.tar", "size": 1024},
        ]
        m = get_userman_restore_keyboard(files)
        all_data = _btns(m)
        assert "userman_restore_tar:0" in all_data
        assert "userman_restore_tar:1" in all_data
        flat = _flat_btns(m)
        assert any("200KB" in t for t in flat)
        assert any("1KB" in t for t in flat)

    def test_back_button(self):
        m = get_userman_restore_keyboard([])
        assert "menu_backup" in _btns(m)

    def test_row_count(self):
        files = [{"filename": "a.tar", "size": 1024}]
        m = get_userman_restore_keyboard(files)
        assert _row_count(m) == 2


class TestGetUsermanRestoreConfirmKeyboard:
    def test_returns_markup(self):
        assert isinstance(get_userman_restore_confirm_keyboard(), InlineKeyboardMarkup)

    def test_two_rows(self):
        assert _row_count(get_userman_restore_confirm_keyboard()) == 2

    def test_callbacks(self):
        all_data = _btns(get_userman_restore_confirm_keyboard())
        assert "userman_restore_exec" in all_data
        assert "menu_backup" in all_data


# ===========================================================================
# 49: get_operator_router_assignment_keyboard
# ===========================================================================


class TestGetOperatorRouterAssignmentKeyboard:
    def test_empty_routers(self):
        m = get_operator_router_assignment_keyboard(1, [], [])
        assert isinstance(m, InlineKeyboardMarkup)
        # only back row
        assert _row_count(m) == 1

    def test_assigned_router(self):
        routers = [{"id": 10, "name_alias": "R1", "ip_address": "1.1.1.1"}]
        m = get_operator_router_assignment_keyboard(1, routers, [10])
        flat = _flat_btns(m)
        assert any("✅" in t for t in flat)
        all_data = _btns(m)
        assert "op_revoke:1:10" in all_data

    def test_unassigned_router(self):
        routers = [{"id": 10, "name_alias": "R1", "ip_address": "1.1.1.1"}]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        assert any("⬜" in t for t in flat)
        all_data = _btns(m)
        assert "op_assign:1:10" in all_data

    def test_mixed_assigned_and_unassigned(self):
        routers = [
            {"id": 1, "name_alias": "A", "ip_address": "1.1.1.1"},
            {"id": 2, "name_alias": "B", "ip_address": "2.2.2.2"},
        ]
        m = get_operator_router_assignment_keyboard(5, routers, [1])
        all_data = _btns(m)
        assert "op_revoke:5:1" in all_data
        assert "op_assign:5:2" in all_data

    def test_router_without_id_skipped(self):
        routers = [{"name_alias": "NoId", "ip_address": "1.1.1.1"}]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        # only back button
        assert not any("NoId" in t for t in flat)

    def test_fallback_name_fields(self):
        routers = [{"id": 3, "identity": "IdentityOnly", "ip_address": ""}]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        assert any("IdentityOnly" in t for t in flat)

    def test_name_alias_priority(self):
        routers = [
            {"id": 3, "name_alias": "Alias", "identity": "Identity", "ip_address": "1.1.1.1"}
        ]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        assert any("Alias" in t for t in flat)

    def test_ip_in_label_when_present(self):
        routers = [{"id": 1, "name_alias": "R", "ip_address": "10.0.0.1"}]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        assert any("10.0.0.1" in t for t in flat)

    def test_no_ip_in_label_when_empty(self):
        routers = [{"id": 1, "name_alias": "R", "ip_address": ""}]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        # Only the name alias, no IP
        assert any("R" in t and "()" not in t for t in flat)

    def test_id_fallback_name(self):
        routers = [{"id": 42, "ip_address": "1.1.1.1"}]
        m = get_operator_router_assignment_keyboard(1, routers, [])
        flat = _flat_btns(m)
        assert any("42" in t for t in flat)

    def test_back_button(self):
        m = get_operator_router_assignment_keyboard(1, [], [])
        assert "roles_back" in _btns(m)


# ===========================================================================
# Constants and module-level data
# ===========================================================================


class TestModuleConstants:
    def test_submenu_page_size(self):
        assert SUBMENU_PAGE_SIZE == 20

    def test_time_options(self):
        assert len(TIME_OPTIONS) == 4
        labels = [t[0] for t in TIME_OPTIONS]
        assert "اليوم" in labels
        assert "الكل" in labels

    def test_time_options_days_values(self):
        days = [t[1] for t in TIME_OPTIONS]
        assert 1 in days
        assert 7 in days
        assert 30 in days
        assert None in days
