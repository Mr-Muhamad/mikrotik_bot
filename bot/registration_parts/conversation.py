"""ConversationHandler registrations (entry points, states, fallbacks).

Split from ``bot/registrations.py`` (Step 3b of SRP refactor). All
``entry_point(...)``/``state(...)``/``fallback(...)`` calls live here in
the same order they appeared in ``bot/registrations.py`` so decorator
execution order is preserved.

Importing this module has the side-effect of populating the handler
registry; it must be imported exactly once (via ``bot.registrations``)
AFTER ``bot.registration_parts.standalone`` so standalone decorators
run first.
"""

from telegram.ext import CallbackQueryHandler, CommandHandler, filters

from bot.handlers.backup import schedule_enable, schedule_menu_from_conversation, schedule_set
from bot.handlers.batch import share_card_send, share_card_start
from bot.handlers.callback_constants import PATTERNS

# ─── IMPORT ALL HANDLERS USED BY CONVERSATION REGISTRATIONS ───
from bot.handlers.commands_basic import (
    cancel,
    error_handler,
    reprompt_card_profile_text,
    reprompt_card_type_text,
    reprompt_select_user,
    select_router_callback,
    start,
)
from bot.handlers.hotspot import hotspot_stats
from bot.handlers.hotspot_add import (
    add_back_to_bytes,
    add_back_to_password,
    add_back_to_profile,
    add_back_to_uptime_from_comment,
    add_back_to_username,
    hotspot_add_bytes,
    hotspot_add_comment,
    hotspot_add_password,
    hotspot_add_profile,
    hotspot_add_profile_selected,
    hotspot_add_start,
    hotspot_add_uptime_type,
    hotspot_add_uptime_type_invalid_text,
    hotspot_add_uptime_value,
    hotspot_add_username,
    skip_bytes,
    skip_comment,
    skip_password,
    skip_uptime,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_bytes,
    hotspot_cards_count,
    hotspot_cards_length,
    hotspot_cards_prefix,
    hotspot_cards_profile_selected,
    hotspot_cards_skip_bytes,
    hotspot_cards_skip_prefix,
    hotspot_cards_skip_uptime,
    hotspot_cards_skip_uptime_type,
    hotspot_cards_start,
    hotspot_cards_type_selected,
    hotspot_cards_uptime_type,
    hotspot_cards_uptime_value,
    hs_back_to_length,
    hs_back_to_profile,
    hs_back_to_type,
    hs_back_to_uptime,
)
from bot.handlers.hotspot_common import handle_page_callback
from bot.handlers.hotspot_delete import (
    confirm_callback,
    confirm_reprompt,
    hotspot_delete_search,
    hotspot_delete_select,
    hotspot_delete_start,
)
from bot.handlers.hotspot_edit import (
    edit_back_search,
    edit_back_to_fields,
    edit_profile_selected,
    hotspot_edit_field,
    hotspot_edit_kick,
    hotspot_edit_reset,
    hotspot_edit_search,
    hotspot_edit_select,
    hotspot_edit_start,
    hotspot_edit_value,
)
from bot.handlers.hotspot_search import (
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
from bot.handlers.menus import (
    end_conversation_to_backup,
    end_conversation_to_hotspot,
    end_conversation_to_main,
    end_conversation_to_pdf_settings,
    end_conversation_to_reports,
    end_conversation_to_routers,
    end_conversation_to_stats,
    go_back,
    menu_userman_from_conversation,
)
from bot.handlers.routers import (
    disc_enter_password,
    disc_enter_username,
    discovered_router_selected,
)
from bot.handlers.settings import pdf_settings_option, pdf_settings_value
from bot.handlers.usage import usage_query, usage_start
from bot.handlers.userman import (
    userman_back_to_mac,
    userman_back_to_payment,
    userman_back_to_prefix,
    userman_back_to_profile,
    userman_back_to_type,
    userman_card_count,
    userman_card_mac_selected,
    userman_card_payment_selected,
    userman_card_prefix,
    userman_card_profile_selected,
    userman_card_skip_prefix,
    userman_card_type_selected,
    userman_cards_start,
)
from bot.handlers.userman_search import (
    userman_search_action,
    userman_search_add_profile,
    userman_search_add_profile_selected,
    userman_search_back,
    userman_search_page_handler,
    userman_search_query,
    userman_search_select,
    userman_search_start,
)
from utils.handler_registry import (
    entry_point,
    fallback,
    state,
)
from utils.handler_registry import (
    error_handler as reg_err,
)

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
entry_point(
    CallbackQueryHandler,
    pattern=PATTERNS["pdf_options"],
)(pdf_settings_option)
entry_point(CallbackQueryHandler, pattern=PATTERNS["schedule_enable"])(schedule_enable)
entry_point(CallbackQueryHandler, pattern=PATTERNS["hotspot_stats"])(hotspot_stats)
entry_point(CommandHandler, command="usage")(usage_start)

# share_card flow — مشاركة كرت WiFi للعميل
entry_point(CallbackQueryHandler, pattern=PATTERNS["share_card"])(share_card_start)

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
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_pdf_settings"])(
    end_conversation_to_pdf_settings
)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_routers"])(end_conversation_to_routers)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_reports"])(end_conversation_to_reports)
fallback(CallbackQueryHandler, pattern=PATTERNS["select_router"])(select_router_callback)
fallback(CallbackQueryHandler, pattern=PATTERNS["menu_schedule"])(schedule_menu_from_conversation)
fallback(CallbackQueryHandler, pattern=PATTERNS["schedule_enable"])(schedule_enable)
fallback(CallbackQueryHandler, pattern=PATTERNS["go_back"])(go_back)
fallback(CommandHandler, command="usage")(usage_start)

# Catch-all fallback for stale callbacks from old messages.
# Must be LAST fallback so it only fires when no other handler matches.
async def _unhandled_callback_handler(update, context):
    query = update.callback_query
    if query:
        from utils.callback_utils import safe_answer_callback

        await safe_answer_callback(
            query,
            text=(
                "⚠️ هذه القائمة قديمة أو منتهية. يرجى التفاعل مع آخر رسالة"
                " أو كتابة /start لتحديث الواجهة."
            ),
            show_alert=True,
        )


fallback(CallbackQueryHandler, pattern=r"^.*$")(_unhandled_callback_handler)

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
state("WAITING_UPTIME_TYPE").message(filters.TEXT & ~filters.COMMAND)(
    hotspot_add_uptime_type_invalid_text
)
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
state("WAITING_HOTSPOT_SEARCH").callback(PATTERNS["hotspot_search_page"])(
    hotspot_search_page_handler
)
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
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["userman_search_page"])(
    userman_search_page_handler
)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_kick_execute"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_reset_counters"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_toggle_disabled"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_delete"])(userman_search_action)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_add_profile"])(userman_search_add_profile)
state("WAITING_USERMAN_SEARCH").callback(PATTERNS["um_profile"])(
    userman_search_add_profile_selected
)
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
state("WAITING_HOTSPOT_CARD_PROFILE").callback(PATTERNS["hs_card_profile"])(
    hotspot_cards_profile_selected
)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["hs_back_to_profile"])(hs_back_to_profile)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["hs_back_to_uptime"])(hs_back_to_uptime)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["hs_skip_uptime"])(hotspot_cards_skip_uptime)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["skip_uptime"])(
    hotspot_cards_skip_uptime_type
)
state("WAITING_HOTSPOT_CARD_UPTIME").callback(PATTERNS["uptime_type"])(hotspot_cards_uptime_type)
state("WAITING_HOTSPOT_CARD_UPTIME").message(filters.TEXT & ~filters.COMMAND)(
    hotspot_cards_uptime_value
)
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
state("WAITING_PDF_VALUE").callback(PATTERNS["pdf_options"])(pdf_settings_option)
state("WAITING_PDF_VALUE").message(filters.TEXT & ~filters.COMMAND)(pdf_settings_value)

# confirm delete flow
state("WAITING_INPUT").callback(PATTERNS["confirm_yes_no"])(confirm_callback)
state("WAITING_INPUT").message(filters.TEXT & ~filters.COMMAND)(confirm_reprompt)

# backup schedule flow
state("WAITING_SCHEDULE_TIME").message(filters.TEXT & ~filters.COMMAND)(schedule_set)

# ─── PHASE 1: USAGE FLOW ───────────────────────────────────────

state("WAITING_USAGE_QUERY").message(filters.TEXT & ~filters.COMMAND)(usage_query)

# hotspot stats day text input
from bot.handlers.hotspot import hotspot_stats_day_input  # noqa: E402

state("WAITING_STATS_DAY").message(filters.TEXT & ~filters.COMMAND)(hotspot_stats_day_input)
