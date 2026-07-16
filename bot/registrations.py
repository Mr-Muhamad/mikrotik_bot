"""Centralised handler registration catalog.

Imports every handler function and registers it with the handler_registry.
main.py then reads the registry to build the application.
"""

from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler as CH
from utils.handler_registry import entry_point, state, fallback, standalone, error_handler as reg_err, build_application
from bot.handlers.callback_constants import PATTERNS

# ─── IMPORT ALL HANDLERS ──────────────────────────────────────

from bot.handlers.common import (
    start, help_command, select_router_callback, main_menu,
    end_conversation_to_main, end_conversation_to_hotspot,
    end_conversation_to_stats, end_conversation_to_backup, end_conversation_to_pdf_settings,
    hotspot_menu, userman_menu, menu_userman_from_conversation,
    stats_menu, backup_menu, pdf_settings_menu,
    cancel, error_handler, go_back, clean_chat, metrics_command,
    sync_commands,
    reprompt_select_user, reprompt_card_type_text, reprompt_card_profile_text,
)
from bot.handlers.hotspot import hotspot_stats, hotspot_stats_day_input
from bot.handlers.hotspot_add import (
    hotspot_add_start, hotspot_add_username, hotspot_add_password,
    hotspot_add_profile, hotspot_add_profile_selected, hotspot_add_bytes,
    hotspot_add_comment, add_back_to_username, add_back_to_password,
    add_back_to_profile, add_back_to_bytes, skip_password, skip_bytes,
    skip_comment, hotspot_add_uptime_type, hotspot_add_uptime_value,
    skip_uptime, add_back_to_uptime_from_comment,
    hotspot_add_uptime_type_invalid_text,
)
from bot.handlers.hotspot_delete import (
    hotspot_delete_start, hotspot_delete_search, hotspot_delete_select,
    confirm_callback, confirm_reprompt,
)
from bot.handlers.userman_search import (
    userman_search_start, userman_search_query, userman_search_back,
    userman_search_select, userman_search_action,
    userman_search_add_profile, userman_search_add_profile_selected,
)
from bot.handlers.hotspot_search import (
    hotspot_search_start, hotspot_search_query, hotspot_search_back,
    hotspot_show_host, hotspot_host_action,
    block_mac_handler, unblock_mac_handler, show_blocked_list,
)
from bot.handlers.hotspot_common import handle_page_callback
from bot.handlers.hotspot_edit import (
    hotspot_edit_start, hotspot_edit_search, hotspot_edit_select,
    hotspot_edit_field, hotspot_edit_value, hotspot_edit_kick,
    hotspot_edit_reset, edit_profile_selected, edit_back_to_fields,
    edit_back_search,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_start, hotspot_cards_count, hotspot_cards_length,
    hotspot_cards_prefix, hotspot_cards_skip_prefix,
    hotspot_cards_type_selected, hotspot_cards_profile_selected,
    hotspot_cards_uptime_type, hotspot_cards_uptime_value,
    hotspot_cards_skip_uptime, hotspot_cards_skip_uptime_type,
    hotspot_cards_bytes, hotspot_cards_skip_bytes,
    hs_back_to_length, hs_back_to_type, hs_back_to_profile, hs_back_to_uptime,
)
from bot.handlers.userman import (
    userman_cards_start, userman_card_type_selected,
    userman_card_profile_selected, userman_card_payment_selected,
    userman_card_count,
    userman_card_mac_selected,
    userman_list, userman_profiles,
    userman_back_to_type, userman_back_to_profile,
    userman_back_to_payment, userman_back_to_mac,
    userman_card_prefix, userman_card_skip_prefix, userman_back_to_prefix,
)
from bot.handlers.routers import (
    discover_routers_callback, discovered_router_selected,
    disc_enter_username, disc_enter_password, saved_routers_list,
    saved_router_selected, rename_router_start, rename_router_value,
    connect_router, delete_router_confirm, delete_router_execute,
    refresh_routers, reboot_start, reboot_router_callback,
    reboot_saved_router,
    manual_add_start, manual_add_ip, manual_add_port, manual_add_user,
    manual_add_pass, manual_add_alias, manual_add_confirm,
)
from bot.handlers.backup import (
    backup_full, backup_userman,
    schedule_menu, schedule_menu_from_conversation,
    schedule_enable, schedule_set, schedule_disable,
    backup_download_file,
)
from bot.handlers.stats import stats_hotspot, stats_userman
from bot.handlers.settings import (
    pdf_settings_option, pdf_settings_value,
    pdf_group_text, pdf_group_layout, pdf_group_misc
)
from bot.handlers.audit import (
    logs_back_callback,
    logs_clear_callback,
    logs_command,
    logs_filter_callback,
    logs_page_callback,
    logs_set_callback,
    logs_subnav_callback,
)
from bot.handlers.backup_restore import backup_restore_start, backup_restore_select, backup_restore_confirm, userman_restore_start, userman_restore_select, userman_restore_execute
from bot.handlers.watchdog import watchdog_start, watchdog_stop, watchdog_status
from bot.handlers.usage import usage_start, usage_query
from bot.handlers.roles import roles_command, role_set_command
from bot.handlers.hotspot_report import report_command, report_export_csv
from bot.handlers.batch import (
    batches_command, batch_select, batch_regen,
    mark_batch_paid_handler, show_sales_summary,
    share_card_start, share_card_send,
)
import bot.handlers.constants as constants

# ─── STANDALONE HANDLERS ──────────────────────────────────────

standalone(CommandHandler, command="start")(start)
standalone(CommandHandler, command="help")(help_command)
standalone(CommandHandler, command="cancel")(cancel)
standalone(CommandHandler, command="clean")(clean_chat)
standalone(CommandHandler, command="metrics")(metrics_command)
standalone(CommandHandler, command="reboot")(reboot_start)
standalone(CommandHandler, command="backup")(backup_menu)
standalone(CommandHandler, command="settings")(pdf_settings_menu)
standalone(CommandHandler, command="routers")(saved_routers_list)
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

standalone(CallbackQueryHandler, pattern=PATTERNS["select_router"])(select_router_callback)
standalone(CallbackQueryHandler, pattern=PATTERNS["main_menu"])(main_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_hotspot"])(hotspot_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_userman"])(userman_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_stats"])(stats_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_backup"])(backup_menu)
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
standalone(CommandHandler, command="watchdog")(watchdog_status)
standalone(CommandHandler, command="watchdog_start")(watchdog_start)
standalone(CommandHandler, command="roles")(roles_command)
standalone(CommandHandler, command="role")(role_set_command)
standalone(CommandHandler, command="report")(report_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["report_csv"])(report_export_csv)
standalone(CallbackQueryHandler, pattern=PATTERNS["report_refresh"])(report_command)
standalone(CommandHandler, command="batches")(batches_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["batch_sel"])(batch_select)
standalone(CallbackQueryHandler, pattern=PATTERNS["batch_regen"])(batch_regen)
standalone(CallbackQueryHandler, pattern=PATTERNS["batches_refresh"])(batches_command)
standalone(CallbackQueryHandler, pattern=PATTERNS["mark_payment"])(mark_batch_paid_handler)
standalone(CommandHandler, command="sales")(show_sales_summary)
entry_point(CallbackQueryHandler, pattern=PATTERNS["share_card"])(share_card_start)
# حظر MAC — standalone لأن unblock قد يأتي من خارج conversation
standalone(CallbackQueryHandler, pattern=PATTERNS["unblock_mac"])(unblock_mac_handler)

# ─── ERROR HANDLER ────────────────────────────────────────────

reg_err(error_handler)

# ─── ENTRY POINTS (main ConversationHandler) ───────────────────

entry_point(CommandHandler, command="add")(hotspot_add_start)
entry_point(CommandHandler, command="edit")(hotspot_edit_start)
entry_point(CommandHandler, command="delete")(hotspot_delete_start)
entry_point(CommandHandler, command="search")(hotspot_search_start)
entry_point(CommandHandler, command="cards")(hotspot_cards_start)
entry_point(CommandHandler, command="userman")(userman_cards_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_add"])(hotspot_add_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_delete"])(hotspot_delete_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_search"])(hotspot_search_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_edit"])(hotspot_edit_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_cards"])(hotspot_cards_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["userman_cards"])(userman_cards_start)
entry_point(CallbackQueryHandler, pattern=PATTERNS["disc_router"])(discovered_router_selected)
entry_point(
    CallbackQueryHandler,
    pattern=PATTERNS["pdf_options"],
)(pdf_settings_option)
entry_point(CallbackQueryHandler, pattern=PATTERNS["schedule_enable"])(schedule_enable)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_stats"])(hotspot_stats)
entry_point(CommandHandler, command="usage")(usage_start)

# ─── FALLBACKS (main ConversationHandler) ──────────────────────

fallback(CommandHandler, command="cancel")(cancel)
fallback(CommandHandler, command="start")(start)
fallback(CallbackQueryHandler, pattern=PATTERNS["cancel_edit"])(cancel)
fallback(CallbackQueryHandler, pattern=PATTERNS["hotspot_add"])(hotspot_add_start)
fallback(CallbackQueryHandler, pattern=PATTERNS["hotspot_delete"])(hotspot_delete_start)
fallback(CallbackQueryHandler, pattern=PATTERNS["hotspot_search"])(hotspot_search_start)
fallback(CallbackQueryHandler, pattern=PATTERNS["hotspot_edit"])(hotspot_edit_start)
fallback(CallbackQueryHandler, pattern=PATTERNS["hotspot_cards"])(hotspot_cards_start)
fallback(CallbackQueryHandler, pattern=PATTERNS["userman_cards"])(userman_cards_start)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_userman"])(menu_userman_from_conversation)
fallback(CallbackQueryHandler, pattern=PATTERNS["main_menu"])(end_conversation_to_main)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_hotspot"])(end_conversation_to_hotspot)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_stats"])(end_conversation_to_stats)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_backup"])(end_conversation_to_backup)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_pdf_settings"])(end_conversation_to_pdf_settings)
fallback(CallbackQueryHandler, pattern=PATTERNS["select_router"])(select_router_callback)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_schedule"])(schedule_menu_from_conversation)
fallback(CallbackQueryHandler, pattern=PATTERNS["schedule_enable"])(schedule_enable)
fallback(CallbackQueryHandler, pattern=PATTERNS["go_back"])(go_back)
fallback(CommandHandler, command="usage")(usage_start)

# ─── STATES (main ConversationHandler) ─────────────────────────

# hotspot_add flow
state("WAITING_USERNAME").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_username)
state("WAITING_PASSWORD").callback(PATTERNS["add_back_to_username"])(add_back_to_username)
state("WAITING_PASSWORD").callback(PATTERNS["skip_password"])(skip_password)
state("WAITING_PASSWORD").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_password)
state("WAITING_PROFILE").callback(PATTERNS["add_back_to_password"])(add_back_to_password)
state("WAITING_PROFILE").callback(PATTERNS["add_profile"])(hotspot_add_profile_selected)
state("WAITING_PROFILE").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_profile)
state("WAITING_BYTES_TOTAL").callback(PATTERNS["add_back_to_profile"])(add_back_to_profile)
state("WAITING_BYTES_TOTAL").callback(PATTERNS["skip_bytes"])(skip_bytes)
state("WAITING_BYTES_TOTAL").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_bytes)
state("WAITING_UPTIME_TYPE").callback(PATTERNS["uptime_type"])(hotspot_add_uptime_type)
state("WAITING_UPTIME_TYPE").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_uptime_type_invalid_text)
state("WAITING_UPTIME_VALUE").callback(PATTERNS["skip_uptime"])(skip_uptime)
state("WAITING_UPTIME_VALUE").callback(PATTERNS["add_back_to_bytes"])(add_back_to_bytes)
state("WAITING_UPTIME_VALUE").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_uptime_value)
state("WAITING_COMMENT").callback(PATTERNS["add_back_to_uptime"])(add_back_to_uptime_from_comment)
state("WAITING_COMMENT").callback(PATTERNS["skip_comment"])(skip_comment)
state("WAITING_COMMENT").message(filters.TEXT & ~filters.COMMAND)(hotspot_add_comment)

# hotspot_delete flow
state("WAITING_DELETE_ID").message(filters.TEXT & ~filters.COMMAND)(hotspot_delete_search)
state("WAITING_DELETE_SELECT").callback(PATTERNS["delete_user_star"])(hotspot_delete_select)
state("WAITING_DELETE_SELECT").callback(PATTERNS["page_delete_user"])(handle_page_callback)
state("WAITING_DELETE_SELECT").message(filters.TEXT & ~filters.COMMAND)(reprompt_select_user)

# hotspot_search flow
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["search_back"])(hotspot_search_back)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["host_sel"])(hotspot_show_host)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["host_kick_execute"])(hotspot_host_action)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["host_reset_counters"])(hotspot_host_action)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["host_toggle_disabled"])(hotspot_host_action)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["block_mac"])(block_mac_handler)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["blocked_list"])(show_blocked_list)
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["unblock_mac"])(unblock_mac_handler)
state("WAITING_HOTSPOT_SEARCH").message(filters.TEXT & ~filters.COMMAND)(hotspot_search_query)

# userman_search flow
entry_point(CallbackQueryHandler, pattern=PATTERNS["userman_search"])(userman_search_start)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["search_back"])(userman_search_back)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_sel"])(userman_search_select)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_kick_execute"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_reset_counters"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_toggle_disabled"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_delete"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_add_profile"])(userman_search_add_profile)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_profile"])(userman_search_add_profile_selected)
state("WAITING_USERMAN_SEARCH").message(filters.TEXT & ~filters.COMMAND)(userman_search_query)

# share_card flow — مشاركة كرت WiFi للعميل
state("WAITING_SHARE_RECIPIENT").message(filters.TEXT & ~filters.COMMAND)(share_card_send)

# hotspot_edit flow
state("WAITING_EDIT_FIELD").message(filters.TEXT & ~filters.COMMAND)(hotspot_edit_search)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_user_star"])(hotspot_edit_select)
state("WAITING_EDIT_VALUE").callback(PATTERNS["page_edit_user"])(handle_page_callback)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_field_reset"])(hotspot_edit_reset)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_field"])(hotspot_edit_field)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_kick_user"])(hotspot_edit_kick)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_profile"])(edit_profile_selected)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_back_to_fields"])(edit_back_to_fields)
state("WAITING_EDIT_VALUE").callback(PATTERNS["edit_back_search"])(edit_back_search)
state("WAITING_EDIT_VALUE").message(filters.TEXT & ~filters.COMMAND)(hotspot_edit_value)

# hotspot_cards flow
state("WAITING_HOTSPOT_CARD_COUNT").message(filters.TEXT & ~filters.COMMAND)(hotspot_cards_count)
state("WAITING_HOTSPOT_CARD_LENGTH").message(filters.TEXT & ~filters.COMMAND)(hotspot_cards_length)
state("WAITING_HOTSPOT_CARD_PREFIX").callback(PATTERNS["hs_back_to_length"])(hs_back_to_length)
state("WAITING_HOTSPOT_CARD_PREFIX").callback(PATTERNS["hs_skip_prefix"])(hotspot_cards_skip_prefix)
state("WAITING_HOTSPOT_CARD_PREFIX").message(filters.TEXT & ~filters.COMMAND)(hotspot_cards_prefix)
state("WAITING_HOTSPOT_CARD_TYPE").callback(PATTERNS["hs_card_type"])(hotspot_cards_type_selected)
state("WAITING_HOTSPOT_CARD_PROFILE").callback(PATTERNS["hs_back_to_type"])(hs_back_to_type)
state("WAITING_HOTSPOT_CARD_PROFILE").callback(PATTERNS["hs_back_to_profile"])(hs_back_to_profile)
state("WAITING_HOTSPOT_CARD_PROFILE").callback(PATTERNS["hs_card_profile"])(hotspot_cards_profile_selected)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["hs_back_to_profile"])(hs_back_to_profile)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["hs_back_to_uptime"])(hs_back_to_uptime)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["hs_skip_uptime"])(hotspot_cards_skip_uptime)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["skip_uptime"])(hotspot_cards_skip_uptime_type)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["uptime_type"])(hotspot_cards_uptime_type)
state("WAITING_HOTSPOT_CARD_UPTIME").message(filters.TEXT & ~filters.COMMAND)(hotspot_cards_uptime_value)
state("WAITING_HOTSPOT_CARD_BYTES").callback(PATTERNS["hs_back_to_uptime"])(hs_back_to_uptime)
state("WAITING_HOTSPOT_CARD_BYTES").callback(PATTERNS["hs_skip_bytes"])(hotspot_cards_skip_bytes)
state("WAITING_HOTSPOT_CARD_BYTES").message(filters.TEXT & ~filters.COMMAND)(hotspot_cards_bytes)

# userman flow
state("WAITING_CARD_TYPE").callback(PATTERNS["card_type"])(userman_card_type_selected)
state("WAITING_CARD_TYPE").message(filters.TEXT & ~filters.COMMAND)(reprompt_card_type_text)

state("WAITING_CARD_PROFILE").callback(PATTERNS["card_back_to_type"])(userman_back_to_type)
state("WAITING_CARD_PROFILE").callback(PATTERNS["card_profile"])(userman_card_profile_selected)
state("WAITING_CARD_PROFILE").message(filters.TEXT & ~filters.COMMAND)(reprompt_card_profile_text)

state("WAITING_CARD_PAYMENT").callback(PATTERNS["card_back_to_profile"])(userman_back_to_profile)
state("WAITING_CARD_PAYMENT").callback(PATTERNS["card_payment"])(userman_card_payment_selected)

state("WAITING_CARD_MAC").callback(PATTERNS["card_back_to_payment"])(userman_back_to_payment)
state("WAITING_CARD_MAC").callback(PATTERNS["card_mac_choice"])(userman_card_mac_selected)

state("WAITING_CARD_PREFIX").callback(PATTERNS["card_back_to_mac"])(userman_back_to_mac)
state("WAITING_CARD_PREFIX").callback(PATTERNS["card_skip_prefix"])(userman_card_skip_prefix)
state("WAITING_CARD_PREFIX").message(filters.TEXT & ~filters.COMMAND)(userman_card_prefix)

state("WAITING_CARD_COUNT").callback(PATTERNS["card_back_to_prefix"])(userman_back_to_prefix)
state("WAITING_CARD_COUNT").message(filters.TEXT & ~filters.COMMAND)(userman_card_count)

# settings flow
standalone(CallbackQueryHandler, pattern=PATTERNS["menu_pdf_settings"])(pdf_settings_menu)
standalone(CallbackQueryHandler, pattern=PATTERNS["pdf_group_text"])(pdf_group_text)
standalone(CallbackQueryHandler, pattern=PATTERNS["pdf_group_layout"])(pdf_group_layout)
standalone(CallbackQueryHandler, pattern=PATTERNS["pdf_group_misc"])(pdf_group_misc)
state("WAITING_PDF_VALUE").callback(PATTERNS["pdf_options"])(pdf_settings_option)
state("WAITING_PDF_VALUE").message(filters.TEXT & ~filters.COMMAND)(pdf_settings_value)

# confirm delete flow
state("WAITING_INPUT").callback(PATTERNS["confirm_yes_no"])(confirm_callback)
state("WAITING_INPUT").message(filters.TEXT & ~filters.COMMAND)(confirm_reprompt)

# router discovery flow
state("WAITING_DISC_USERNAME").message(filters.TEXT & ~filters.COMMAND)(disc_enter_username)
state("WAITING_DISC_PASSWORD").message(filters.TEXT & ~filters.COMMAND)(disc_enter_password)

# backup schedule flow
state("WAITING_SCHEDULE_TIME").message(filters.TEXT & ~filters.COMMAND)(schedule_set)

# ─── PHASE 1: USAGE FLOW ───────────────────────────────────────

state("WAITING_USAGE_QUERY").message(filters.TEXT & ~filters.COMMAND)(usage_query)

# hotspot stats day text input
state("WAITING_STATS_DAY").message(filters.TEXT & ~filters.COMMAND)(hotspot_stats_day_input)

# RENAME has its own ConversationHandler (built in build_all below)


# ─── BUILD WRAPPER ────────────────────────────────────────────


def build_all(application):
    """Build all handlers from registry and add to application.

    Creates:
      1. Main ConversationHandler (hotspot add/edit/delete/search, cards, userman, etc.)
      2. Rename ConversationHandler (separate shorter conversation)
      3. All standalone handlers (commands, navigation callbacks, etc.)
    """

    # Separate ConversationHandlers must be registered BEFORE the standalone
    # handlers (added inside build_application) so their fallbacks
    # (cancel/start/go_back) take precedence while a conversation is active.
    # Otherwise the standalone `cancel` CommandHandler preempts them and the
    # conversation is never properly ended (its state stays STUCK).

    # 1. Rename ConversationHandler (separate — needs its own CH instance)
    rename_conv = CH(
        entry_points=[CallbackQueryHandler(rename_router_start, pattern=PATTERNS["rename_router"])],
        states={
            constants.WAITING_RENAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, rename_router_value)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )
    application.add_handler(rename_conv)

    # 2. Manual router add ConversationHandler (separate — needs its own CH instance)
    manual_add_conv = CH(
        entry_points=[
            CallbackQueryHandler(manual_add_start, pattern=PATTERNS["manual_add_router"]),
            CommandHandler("addrouter", manual_add_start),
        ],
        states={
            constants.WAITING_MANUAL_IP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_ip)
            ],
            constants.WAITING_MANUAL_PORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_port)
            ],
            constants.WAITING_MANUAL_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_user)
            ],
            constants.WAITING_MANUAL_PASS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_pass)
            ],
            constants.WAITING_MANUAL_ALIAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manual_add_alias)
            ],
            constants.WAITING_MANUAL_CONFIRM: [
                CallbackQueryHandler(manual_add_confirm, pattern=PATTERNS["confirm_manual_add"])
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern=PATTERNS["cancel_edit"]),
            CallbackQueryHandler(go_back, pattern=PATTERNS["go_back"]),
        ],
        per_message=False,
        conversation_timeout=300,
    )
    application.add_handler(manual_add_conv)

    # 3. Main ConversationHandler + standalone handlers (added LAST so the
    #    separate CHs above win while active; main CH keeps priority over
    #    standalone for its own fallback commands).
    build_application(application, constants)
