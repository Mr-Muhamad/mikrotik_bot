"""Single source of truth for Telegram callback_data tokens and registration patterns.

Producers (e.g. ``bot/keyboards.py``) should emit the token strings defined here via
:data:`CALLBACKS` / the builder helpers, and the registration layer
(``bot/registrations.py``) should reference :data:`PATTERNS` by name. Keeping the
tokens in one module prevents drift/typos between what a button sends and what a
handler pattern matches.
"""

from __future__ import annotations

# ── Static callback tokens (exact-match) ───────────────────────
CALLBACKS: dict[str, str] = {
    "select_router": "select_router",
    "main_menu": "main_menu",
    "menu_hotspot": "menu_hotspot",
    "menu_userman": "menu_userman",
    "menu_stats": "menu_stats",
    "menu_backup": "menu_backup",
    "menu_pdf_settings": "menu_pdf_settings",
    "menu_schedule": "menu_schedule",
    "menu_routers": "menu_routers",
    "menu_reports": "menu_reports",
    "sales_summary": "sales_summary",
    "batches_menu": "batches_menu",
    "logs_menu": "logs_menu",
    "reports_menu": "reports_menu",
    "usage_start": "usage_start",
    "cancel_edit": "cancel_edit",
    "clean_chat": "clean_chat",
    "hotspot_stats": "hotspot_stats",
    "userman_list": "userman_list",
    "userman_profiles": "userman_profiles",
    "stats_hotspot": "stats_hotspot",
    "stats_userman": "stats_userman",
    "backup_full": "backup_full",
    "backup_userman": "backup_userman",
    "backup_restore": "backup_restore",
    "userman_restore": "userman_restore",
    "discover_routers": "discover_routers",
    "saved_routers": "saved_routers",
    "refresh_routers": "refresh_routers",
    "schedule_disable": "schedule_disable",
    "schedule_enable": "schedule_enable",
    "logs_clear": "logs_clear",
    "logs_back": "logs_back",
    "watchdog_start": "watchdog_start",
    "watchdog_stop": "watchdog_stop",
    "watchdog_status": "watchdog_status",
    "watchdog_refresh": "watchdog_refresh",
    "report_csv": "report_csv",
    "report_refresh": "report_refresh",
    "batches_refresh": "batches_refresh",
    "hotspot_add": "hotspot_add",
    "hotspot_delete": "hotspot_delete",
    "hotspot_search": "hotspot_search",
    "hotspot_edit": "hotspot_edit",
    "hotspot_cards": "hotspot_cards",
    "userman_cards": "userman_cards",
    "search_back": "search_back",
    "go_back": "go_back",
    "add_back_to_username": "add_back_to_username",
    "skip_password": "skip_password",
    "add_back_to_password": "add_back_to_password",
    "add_back_to_profile": "add_back_to_profile",
    "skip_bytes": "skip_bytes",
    "add_back_to_bytes": "add_back_to_bytes",
    "skip_uptime": "skip_uptime",
    "add_back_to_uptime": "add_back_to_uptime",
    "skip_comment": "skip_comment",
    "hs_back_to_length": "hs_back_to_length",
    "hs_skip_prefix": "hs_skip_prefix",
    "hs_back_to_type": "hs_back_to_type",
    "hs_back_to_profile": "hs_back_to_profile",
    "hs_back_to_uptime": "hs_back_to_uptime",
    "hs_skip_uptime": "hs_skip_uptime",
    "hs_skip_bytes": "hs_skip_bytes",
    "hs_skip_price": "hs_skip_price",
    "hs_back_to_prefix": "hs_back_to_prefix",
    "edit_field_reset": "edit_field_reset",
    "edit_kick_user": "edit_kick_user",
    "edit_back_to_fields": "edit_back_to_fields",
    "edit_back_search": "edit_back_search",
    "userman_search": "userman_search",
    "host_kick_execute": "host_kick_execute",
    "host_reset_counters": "host_reset_counters",
    "host_toggle_disabled": "host_toggle_disabled",
    "um_kick_execute": "um_kick_execute",
    "um_reset_counters": "um_reset_counters",
    "um_toggle_disabled": "um_toggle_disabled",
    "um_delete": "um_delete",
    "um_add_profile": "um_add_profile",
    "reboot_no": "reboot_no",
    "hs_card_type1": "hs_card_type1",
    "hs_card_type2": "hs_card_type2",
    "hs_card_type3": "hs_card_type3",
    "card_type1": "card_type1",
    "card_type2": "card_type2",
    "card_type3": "card_type3",
    "confirm_yes": "confirm_yes",
    "confirm_no": "confirm_no",
    "uptime_hours": "uptime_hours",
    "uptime_days": "uptime_days",
    "edit_field_name": "edit_field_name",
    "edit_field_password": "edit_field_password",
    "edit_field_profile": "edit_field_profile",
    "edit_field_bytes": "edit_field_bytes",
    "edit_field_uptime": "edit_field_uptime",
    "edit_field_comment": "edit_field_comment",
    "edit_field_toggle_disabled": "edit_field_toggle_disabled",
    # PDF settings submenus
    "pdf_group_text": "pdf_group_text",
    "pdf_group_layout": "pdf_group_layout",
    "pdf_group_misc": "pdf_group_misc",
    "pdf_brand_name": "pdf_brand_name",
    "pdf_hotspot_dns": "pdf_hotspot_dns",
    "pdf_show_qr": "pdf_show_qr",
    "pdf_margins": "pdf_margins",
    "pdf_spacing": "pdf_spacing",
    "pdf_cards_per_row": "pdf_cards_per_row",
    "pdf_cards_per_page": "pdf_cards_per_page",
    "pdf_footer": "pdf_footer",
    "pdf_label_spacing": "pdf_label_spacing",
    "pdf_value_font_size": "pdf_value_font_size",
    "logs_filter_router": "logs_filter_router",
    "logs_filter_admin": "logs_filter_admin",
    "logs_filter_action": "logs_filter_action",
    "logs_filter_time": "logs_filter_time",
    "logs_sub_prev": "logs_sub_prev",
    "logs_sub_next": "logs_sub_next",
    "manual_add_router": "manual_add_router",
    "card_paid": "card_paid",
    "card_unpaid": "card_unpaid",
    "card_bind_known": "card_bind_known",
    "card_no_bind": "card_no_bind",
    "card_back_to_type": "card_back_to_type",
    "card_back_to_profile": "card_back_to_profile",
    "card_back_to_payment": "card_back_to_payment",
    "card_back_to_mac": "card_back_to_mac",
    "card_back_to_prefix": "card_back_to_prefix",
    "card_skip_prefix": "card_skip_prefix",
    # حظر MAC
    "blocked_list": "blocked_list",
}

# ── Dynamic token builders (prefix + variable) ────────────────


def connect_router(router_id: str) -> str:
    return f"connect_router_{router_id}"


def delete_router(router_id: str) -> str:
    return f"delete_router_{router_id}"


def reboot_router(router_id: str) -> str:
    return f"reboot_router_{router_id}"


def rename_router(router_id: str) -> str:
    return f"rename_router_{router_id}"


def reboot_confirm(router_key: str) -> str:
    return f"reboot_yes_{router_key}"


def delete_confirm(router_id: str, yes: bool) -> str:
    return f"confirm_delete_router_{'yes' if yes else 'no'}_{router_id}"


def saved_router(router_id: str) -> str:
    return f"saved_router_{router_id}"


def discovered_router(ip_address: str) -> str:
    return f"disc_router_{ip_address}"


def backup_download(backup_type: str, index: str) -> str:
    return f"backup_dl:{backup_type}:{index}"


def batch_select(batch_id: str) -> str:
    return f"batch_sel:{batch_id}"


def batch_regen(batch_id: str) -> str:
    return f"batch_regen:{batch_id}"


def batch_page(page: int | str) -> str:
    return f"batch_page:{page}"


def userman_search_page(page: str) -> str:
    return f"um_search_pg_{page}"


def hotspot_search_page(page: str) -> str:
    return f"hs_search_pg_{page}"


def restore(index: str) -> str:
    return f"restore:{index}"


def userman_restore_tar(index: str) -> str:
    return f"userman_restore_tar:{index}"


def userman_restore_exec() -> str:
    return "userman_restore_exec"


def confirm_restore() -> str:
    return "confirm_restore"


def logs_page(page: str) -> str:
    return f"logs_page_{page}"


def logs_set(suffix: str, index: str) -> str:
    return f"logs_set_{suffix}_{index}"


def page_user(prefix: str, page: str) -> str:
    return f"page_{prefix}_{page}"


def host_select(index: str) -> str:
    return f"host_sel_{index}"


def user_action(prefix: str, user_id: str) -> str:
    return f"{prefix}_{user_id}"


def add_profile(index: str) -> str:
    return f"add_profile_{index}"


def delete_user_star(target: str) -> str:
    return f"delete_user_*{target}"


def edit_user_star(target: str) -> str:
    return f"edit_user_*{target}"


def edit_profile(index: str) -> str:
    return f"edit_profile_{index}"


def hs_card_profile(index: str) -> str:
    return f"hs_card_profile_{index}"


def card_profile(index: str) -> str:
    return f"card_profile_{index}"


def manual_add_confirm(yes: bool):
    return f"confirm_manual_add_{'yes' if yes else 'no'}"


def mark_payment_cb(batch_id: int, status: str) -> str:
    """بناء callback_data لتغيير حالة الدفع: mark_paid:5 / mark_unpaid:5 / mark_deferred:5"""
    return f"mark_{status}:{batch_id}"


def block_mac_cb(mac: str) -> str:
    """بناء callback_data لحظر MAC: block_mac:<mac>"""
    return f"block_mac:{mac}"


def unblock_mac_cb(mac: str) -> str:
    """بناء callback_data لرفع حظر MAC: unblock_mac:<mac>"""
    return f"unblock_mac:{mac}"


def op_assign_cb(operator_id: int, router_id: int) -> str:
    """بناء callback_data لإسناد راوتر لمشغّل: op_assign:<op_id>:<router_id>"""
    return f"op_assign:{operator_id}:{router_id}"


def op_revoke_cb(operator_id: int, router_id: int) -> str:
    """بناء callback_data لسحب راوتر من مشغّل: op_revoke:<op_id>:<router_id>"""
    return f"op_revoke:{operator_id}:{router_id}"


def op_list_cb(operator_id: int) -> str:
    """بناء callback_data لعرض روترات مشغّل: op_list:<op_id>"""
    return f"op_list:{operator_id}"


# ── Registration patterns (referenced by bot/registrations.py) ──
PATTERNS: dict[str, str] = {
    # static exact-match
    "select_router": r"^select_router$",
    "main_menu": r"^main_menu$",
    "menu_hotspot": r"^menu_hotspot$",
    "menu_userman": r"^menu_userman$",
    "menu_stats": r"^menu_stats$",
    "menu_backup": r"^menu_backup$",
    "menu_pdf_settings": r"^menu_pdf_settings$",
    "menu_schedule": r"^menu_schedule$",
    "menu_routers": r"^menu_routers$",
    "menu_reports": r"^menu_reports$",
    "reports_menu": r"^reports_menu$",
    "sales_summary": r"^sales_summary$",
    "batches_menu": r"^batches_menu$",
    "logs_menu": r"^logs_menu$",
    "usage_start": r"^usage_start$",
    "cancel_edit": r"^cancel_edit$",
    "clean_chat": r"^clean_chat$",
    "hotspot_stats": r"^hotspot_stats$",
    "userman_list": r"^userman_list$",
    "userman_profiles": r"^userman_profiles$",
    "stats_hotspot": r"^stats_hotspot$",
    "stats_userman": r"^stats_userman$",
    "stats_chart": r"^stats_chart$",
    "backup_full": r"^backup_full$",
    "backup_userman": r"^backup_userman$",
    "backup_restore": r"^backup_restore$",
    "userman_restore": r"^userman_restore$",
    "discover_routers": r"^discover_routers$",
    "saved_routers": r"^saved_routers$",
    "refresh_routers": r"^refresh_routers$",
    "schedule_disable": r"^schedule_disable$",
    "schedule_enable": r"^schedule_enable$",
    "logs_clear": r"^logs_clear$",
    "logs_back": r"^logs_back$",
    "watchdog_start": r"^watchdog_start$",
    "watchdog_stop": r"^watchdog_stop$",
    "watchdog_status": r"^watchdog_status$",
    "watchdog_refresh": r"^watchdog_refresh$",
    "report_csv": r"^report_csv$",
    "report_excel": r"^report_excel$",
    "report_refresh": r"^report_refresh$",
    "batches_refresh": r"^batches_refresh$",
    "hotspot_add": r"^hotspot_add$",
    "hotspot_delete": r"^hotspot_delete$",
    "hotspot_search": r"^hotspot_search$",
    "hotspot_edit": r"^hotspot_edit$",
    "hotspot_cards": r"^hotspot_cards$",
    "userman_cards": r"^userman_cards$",
    "search_back": r"^search_back$",
    "roles_back": r"^roles_back$",
    "go_back": r"^go_back$",
    "add_back_to_username": r"^add_back_to_username$",
    "skip_password": r"^skip_password$",
    "add_back_to_password": r"^add_back_to_password$",
    "add_back_to_profile": r"^add_back_to_profile$",
    "skip_bytes": r"^skip_bytes$",
    "add_back_to_bytes": r"^add_back_to_bytes$",
    "skip_uptime": r"^skip_uptime$",
    "add_back_to_uptime": r"^add_back_to_uptime$",
    "skip_comment": r"^skip_comment$",
    "hs_back_to_length": r"^hs_back_to_length$",
    "hs_skip_prefix": r"^hs_skip_prefix$",
    "hs_back_to_type": r"^hs_back_to_type$",
    "hs_back_to_profile": r"^hs_back_to_profile$",
    "hs_back_to_uptime": r"^hs_back_to_uptime$",
    "hs_skip_uptime": r"^hs_skip_uptime$",
    "hs_skip_bytes": r"^hs_skip_bytes$",
    "hs_skip_price": r"^hs_skip_price$",
    "hs_back_to_prefix": r"^hs_back_to_prefix$",
    "edit_field_reset": r"^edit_field_reset$",
    "edit_kick_user": r"^edit_kick_user$",
    "edit_back_to_fields": r"^edit_back_to_fields$",
    "edit_back_search": r"^edit_back_search$",
    "userman_search": r"^userman_search$",
    "host_kick_execute": r"^host_kick_execute$",
    "host_reset_counters": r"^host_reset_counters$",
    "host_toggle_disabled": r"^host_toggle_disabled$",
    "um_kick_execute": r"^um_kick_execute$",
    "um_reset_counters": r"^um_reset_counters$",
    "um_toggle_disabled": r"^um_toggle_disabled$",
    "um_delete": r"^um_delete$",
    "um_add_profile": r"^um_add_profile$",
    "reboot_no": r"^reboot_no$",
    "confirm_yes_no": r"^(confirm_yes|confirm_no)$",
    "uptime_type": r"^(uptime_hours|uptime_days|skip_uptime)$",
    "hs_card_type": r"^hs_card_type[123]$",
    "card_type": r"^card_type[123]$",
    "edit_field": (
        r"^edit_field_(name|password|profile|bytes|uptime|" r"comment|toggle_disabled|renewal_day)$"
    ),
    "pdf_options": (
        r"^pdf_(brand_name|hotspot_dns|show_qr|margins|spacing|"
        r"cards_per_row|cards_per_page|footer|label_spacing|value_font_size)$"
    ),
    "logs_filter": r"^logs_filter_(router|admin|action|time)$",
    "logs_sub": r"^logs_sub_(prev|next)$",
    "manual_add_router": r"^manual_add_router$",
    "confirm_manual_add": r"^confirm_manual_add_(yes|no)$",
    # dynamic
    "backup_dl": r"^backup_dl:\w+:\d+$",
    "saved_router": r"^saved_router_\d+$",
    "connect_router": r"^connect_router_\d+$",
    "delete_router": r"^delete_router_\d+$",
    "confirm_delete_router": r"^confirm_delete_router_(yes|no)_\d+$",
    "reboot_yes": r"^reboot_yes_.+$",
    "pdf_group_text": r"^pdf_group_text$",
    "pdf_group_layout": r"^pdf_group_layout$",
    "pdf_group_misc": r"^pdf_group_misc$",
    "reboot_router": r"^reboot_router_\d+$",
    "rename_router": r"^rename_router_\d+$",
    "page_user": r"^page_(edit|delete)_user_\d+$",
    "logs_page": r"^logs_page_\d+$",
    "logs_set": r"^logs_set_(router|admin|action|time)_\d+$",
    "restore": r"^restore:\d+$",
    "confirm_restore": r"^confirm_restore$",
    "userman_restore_tar": r"^userman_restore_tar:\d+$",
    "userman_restore_exec": r"^userman_restore_exec$",
    "batch_sel": r"^batch_sel:\d+$",
    "batch_page": r"^batch_page:\d+$",
    "batch_regen": r"^batch_regen:\d+$",
    "userman_search_page": r"^um_search_pg_\d+$",
    "hotspot_search_page": r"^hs_search_pg_\d+$",
    "disc_router": r"^disc_router_\d+\.\d+\.\d+\.\d+$",
    "add_profile": r"^add_profile_\d+$",
    "delete_user_star": r"^delete_user_.+$",
    "page_delete_user": r"^page_delete_user_\d+$",
    "host_sel": r"^host_sel_\d+$",
    "um_sel": r"^um_sel_\d+$",
    "um_profile": r"^um_profile_\d+$",
    "edit_user_star": r"^edit_user_.+$",
    "page_edit_user": r"^page_edit_user_\d+$",
    "edit_profile": r"^edit_profile_\d+$",
    "hs_card_profile": r"^hs_card_profile_\d+$",
    "card_profile": r"^card_profile_\d+$",
    "card_payment": r"^(card_paid|card_unpaid)$",
    "card_mac_choice": r"^(card_bind_known|card_no_bind)$",
    "card_back_to_type": r"^card_back_to_type$",
    "card_back_to_profile": r"^card_back_to_profile$",
    "card_back_to_payment": r"^card_back_to_payment$",
    "card_back_to_mac": r"^card_back_to_mac$",
    "card_back_to_prefix": r"^card_back_to_prefix$",
    "card_skip_prefix": r"^card_skip_prefix$",
    # حظر MAC — من الأكثر تحديداً للأعم
    "block_mac": r"^block_mac:[0-9A-Fa-f:]+$",
    "unblock_mac": r"^unblock_mac:[0-9A-Fa-f:]+$",
    "blocked_list": r"^blocked_list$",
    # نظام الفواتير — pattern واحد يغطي paid/unpaid/deferred
    "mark_payment": r"^mark_(paid|unpaid|deferred):\d+$",
    # مشاركة كرت WiFi
    "share_card": r"^share_card:\d+$",
    # Tenant Isolation — إسناد روترات للمشغلين
    "op_assign_router": r"^op_assign:\d+:\d+$",
    "op_revoke_router": r"^op_revoke:\d+:\d+$",
    "op_list_routers": r"^op_list:\d+$",
    "set_timeout": r"^set_timeout:\d+$",
    "cancel_timeout": r"^cancel_timeout$",
    "stats_day": r"^stats_day_\d+$",
}
