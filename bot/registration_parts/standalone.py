"""Standalone (non-conversation) handler registrations.

Split from ``bot/registrations.py`` (Step 3b of SRP refactor). All
``standalone(...)`` calls live here in the same order they appeared in
``bot/registrations.py`` so decorator execution order is preserved.

Importing this module has the side-effect of populating the handler
registry; it must be imported exactly once (via ``bot.registrations``).
"""

from telegram.ext import CallbackQueryHandler, CommandHandler

from bot.handlers.audit import (
    logs_back_callback,
    logs_clear_callback,
    logs_command,
    logs_filter_callback,
    logs_page_callback,
    logs_set_callback,
    logs_subnav_callback,
)
from bot.handlers.backup import (
    backup_download_file,
    backup_full,
    backup_userman,
    schedule_disable,
    schedule_menu,
)
from bot.handlers.backup_restore import (
    backup_restore_confirm,
    backup_restore_select,
    backup_restore_start,
    userman_restore_execute,
    userman_restore_select,
    userman_restore_start,
)
from bot.handlers.batch import (
    batch_page_handler,
    batch_regen,
    batch_select,
    batches_command,
    mark_batch_paid_handler,
    show_sales_summary,
)
from bot.handlers.callback_constants import PATTERNS

# ─── IMPORT ALL HANDLERS USED BY STANDALONE REGISTRATIONS ──────
from bot.handlers.commands_basic import (
    cancel,
    clean_chat,
    help_command,
    metrics_command,
    start,
    sync_commands,
)
from bot.handlers.hotspot import hotspot_stats
from bot.handlers.hotspot_add import hotspot_add_start
from bot.handlers.hotspot_cards import hotspot_cards_start
from bot.handlers.hotspot_common import handle_page_callback
from bot.handlers.hotspot_delete import hotspot_delete_start
from bot.handlers.hotspot_edit import hotspot_edit_start
from bot.handlers.hotspot_report import report_command, report_export_csv
from bot.handlers.hotspot_search import (
    hotspot_search_start,
    unblock_mac_handler,
)
from bot.handlers.menus import (
    backup_menu,
    hotspot_menu,
    main_menu,
    pdf_settings_menu,
    reports_menu,
    routers_menu,
    stats_menu,
    userman_menu,
)
from bot.handlers.roles import (
    add_customer_command,
    assign_router_command,
    op_assign_router_callback,
    op_revoke_router_callback,
    remove_customer_command,
    role_set_command,
    roles_command,
)
from bot.handlers.routers import (
    connect_router,
    delete_router_confirm,
    delete_router_execute,
    discover_routers_callback,
    reboot_router_callback,
    reboot_saved_router,
    reboot_start,
    refresh_routers,
    saved_router_selected,
    saved_routers_list,
)
from bot.handlers.settings import pdf_group_layout, pdf_group_misc, pdf_group_text
from bot.handlers.stats import stats_hotspot, stats_userman
from bot.handlers.timeout import cmd_timeout, handle_timeout_selection
from bot.handlers.usage import usage_start
from bot.handlers.userman import userman_cards_start, userman_list, userman_profiles
from bot.handlers.watchdog import (
    watchdog_refresh,
    watchdog_start,
    watchdog_status,
    watchdog_stop,
)
from utils.handler_registry import standalone

# ─── STANDALONE REGISTRATIONS ─────────────────────────────────

standalone(CommandHandler, command="start")(start)
standalone(CommandHandler, command="help")(help_command)
standalone(CommandHandler, command="cancel")(cancel)
standalone(CommandHandler, command="clean")(clean_chat)
standalone(CommandHandler, command="metrics")(metrics_command)
standalone(CommandHandler, command="reboot")(reboot_start)
standalone(CommandHandler, command="backup")(backup_menu)
standalone(CommandHandler, command="settings")(pdf_settings_menu)
standalone(CommandHandler, command="routers")(routers_menu)
standalone(CommandHandler, command="sync")(sync_commands)
standalone(CommandHandler, command="add")(hotspot_add_start)
standalone(CommandHandler, command="edit")(hotspot_edit_start)
standalone(CommandHandler, command="delete")(hotspot_delete_start)
standalone(CommandHandler, command="search")(hotspot_search_start)
standalone(CommandHandler, command="cards")(hotspot_cards_start)
standalone(CommandHandler, command="userman")(userman_cards_start)
standalone(CommandHandler, command="hotspot")(hotspot_menu)
standalone(CommandHandler, command="stats")(stats_menu)
standalone(CommandHandler, command="usage")(usage_start)
standalone(CommandHandler, command="timeout")(cmd_timeout)

standalone(CallbackQueryHandler, pattern=PATTERNS["set_timeout"])(handle_timeout_selection)
standalone(CallbackQueryHandler, pattern=PATTERNS["cancel_timeout"])(handle_timeout_selection)

standalone(CallbackQueryHandler, pattern=PATTERNS["select_router"])(start)
standalone(CallbackQueryHandler, pattern=PATTERNS["main_menu"])(main_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_hotspot"])(hotspot_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_userman"])(userman_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_stats"])(stats_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_backup"])(backup_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_routers"])(routers_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_reports"])(reports_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_pdf_settings"])(pdf_settings_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["cancel_edit"])(cancel)
standalone(CallbackQueryHandler, pattern=PATTERNS["clean_chat"])(clean_chat)
standalone(CallbackQueryHandler, pattern=PATTERNS["hotspot_stats"])(hotspot_stats)
standalone(CallbackQueryHandler, pattern=PATTERNS["userman_list"])(userman_list)
standalone(CallbackQueryHandler, pattern=PATTERNS["userman_profiles"])(userman_profiles)
standalone(CallbackQueryHandler, pattern=PATTERNS["stats_hotspot"])(stats_hotspot)
standalone(CallbackQueryHandler, pattern=PATTERNS["stats_userman"])(stats_userman)
standalone(CallbackQueryHandler, pattern=PATTERNS["backup_full"])(backup_full)
standalone(CallbackQueryHandler, pattern=PATTERNS["backup_userman"])(backup_userman)
standalone(CallbackQueryHandler, pattern=PATTERNS["backup_dl"])(backup_download_file)
standalone(CallbackQueryHandler, pattern=PATTERNS["discover_routers"])(discover_routers_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["saved_routers"])(saved_routers_list)
standalone(CallbackQueryHandler, pattern=PATTERNS["saved_router"])(saved_router_selected)
standalone(CallbackQueryHandler, pattern=PATTERNS["connect_router"])(connect_router)
standalone(CallbackQueryHandler, pattern=PATTERNS["delete_router"])(delete_router_confirm)
standalone(CallbackQueryHandler, pattern=PATTERNS["confirm_delete_router"])(delete_router_execute)
standalone(CallbackQueryHandler, pattern=PATTERNS["refresh_routers"])(refresh_routers)
standalone(CallbackQueryHandler, pattern=PATTERNS["reboot_yes"])(reboot_router_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["reboot_no"])(reboot_router_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["reboot_router"])(reboot_saved_router)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_schedule"])(schedule_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["schedule_disable"])(schedule_disable)
standalone(CallbackQueryHandler, pattern=PATTERNS["page_user"])(handle_page_callback)
standalone(CommandHandler, command="logs")(logs_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_page"])(logs_page_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_filter"])(logs_filter_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_set"])(logs_set_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_clear"])(logs_clear_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_back"])(logs_back_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_sub"])(logs_subnav_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["backup_restore"])(backup_restore_start)
standalone(CallbackQueryHandler, pattern=PATTERNS["restore"])(backup_restore_select)
standalone(CallbackQueryHandler, pattern=PATTERNS["confirm_restore"])(backup_restore_confirm)
standalone(CallbackQueryHandler, pattern=PATTERNS["userman_restore"])(userman_restore_start)
standalone(CallbackQueryHandler, pattern=PATTERNS["userman_restore_tar"])(userman_restore_select)
standalone(CallbackQueryHandler, pattern=PATTERNS["userman_restore_exec"])(userman_restore_execute)
standalone(CallbackQueryHandler, pattern=PATTERNS["watchdog_start"])(watchdog_start)
standalone(CallbackQueryHandler, pattern=PATTERNS["watchdog_stop"])(watchdog_stop)
standalone(CallbackQueryHandler, pattern=PATTERNS["watchdog_status"])(watchdog_status)
standalone(CallbackQueryHandler, pattern=PATTERNS["watchdog_refresh"])(watchdog_refresh)
standalone(CommandHandler, command="watchdog")(watchdog_status)
standalone(CommandHandler, command="watchdog_start")(watchdog_start)
standalone(CommandHandler, command="roles")(roles_command)
standalone(CommandHandler, command="role")(role_set_command)
standalone(CommandHandler, command="assign_router")(assign_router_command)
standalone(CommandHandler, command="add_customer")(add_customer_command)
standalone(CommandHandler, command="remove_customer")(remove_customer_command)
standalone(CommandHandler, command="report")(report_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["report_csv"])(report_export_csv)
standalone(CallbackQueryHandler, pattern=PATTERNS["report_refresh"])(report_command)
standalone(CommandHandler, command="batches")(batches_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["batch_sel"])(batch_select)
standalone(CallbackQueryHandler, pattern=PATTERNS["batch_page"])(batch_page_handler)
standalone(CallbackQueryHandler, pattern=PATTERNS["batch_regen"])(batch_regen)
standalone(CallbackQueryHandler, pattern=PATTERNS["batches_refresh"])(batches_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["mark_payment"])(mark_batch_paid_handler)
standalone(CommandHandler, command="sales")(show_sales_summary)
standalone(CallbackQueryHandler, pattern=PATTERNS["sales_summary"])(show_sales_summary)
standalone(CallbackQueryHandler, pattern=PATTERNS["batches_menu"])(batches_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["logs_menu"])(logs_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["usage_start"])(usage_start)
# حظر MAC — standalone لأن unblock قد يأتي من خارج conversation
standalone(CallbackQueryHandler, pattern=PATTERNS["unblock_mac"])(unblock_mac_handler)
# Tenant Isolation — إسناد الروترات للمشغلين
standalone(CommandHandler, command="assign_router")(assign_router_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["reports_menu"])(reports_menu)
standalone(CommandHandler, command="reports")(reports_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["op_assign_router"])(op_assign_router_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["op_revoke_router"])(op_revoke_router_callback)

# PDF settings standalone callbacks
standalone(CallbackQueryHandler, pattern=PATTERNS["pdf_group_text"])(pdf_group_text)
standalone(CallbackQueryHandler, pattern=PATTERNS["pdf_group_layout"])(pdf_group_layout)
standalone(CallbackQueryHandler, pattern=PATTERNS["pdf_group_misc"])(pdf_group_misc)
