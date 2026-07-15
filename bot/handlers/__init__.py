from bot.handlers.common import (
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
    skip_uptime, add_back_to_uptime, add_back_to_uptime_from_comment,
    hotspot_add_uptime_type_invalid_text,
)
from bot.handlers.hotspot_delete import (
    hotspot_delete_start, hotspot_delete_search, hotspot_delete_select,
    confirm_callback, confirm_reprompt,
)
from bot.handlers.hotspot_search import (
    hotspot_search_start, hotspot_search_query, hotspot_search_back,
    hotspot_show_host, hotspot_host_kick,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_start, hotspot_edit_search, hotspot_edit_select,
    hotspot_edit_field, hotspot_edit_value, hotspot_edit_kick,
    hotspot_edit_reset, edit_profile_selected, edit_back_to_fields,
    edit_back_search,
)
from bot.handlers.hotspot_common import handle_page_callback
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
    userman_card_profile_selected, userman_card_count,
    userman_list, userman_profiles,
)
from bot.handlers.routers import (
    discover_routers_callback, discovered_router_selected,
    disc_enter_username, disc_enter_password, saved_routers_list,
    saved_router_selected, rename_router_start, rename_router_value,
    connect_router, delete_router_confirm, delete_router_execute,
    refresh_routers, reboot_start, reboot_router_callback,
    reboot_saved_router,
)
from bot.handlers.backup import (
    backup_full, backup_userman,
    schedule_menu, schedule_menu_from_conversation,
    schedule_enable, schedule_set, schedule_disable,
    backup_download_file,
)
from bot.handlers.stats import stats_hotspot, stats_userman
from bot.handlers.settings import pdf_settings_option, pdf_settings_value
from bot.handlers.constants import (
    WAITING_USERNAME, WAITING_PASSWORD, WAITING_PROFILE,
    WAITING_BYTES_TOTAL, WAITING_COMMENT, WAITING_DELETE_ID,
    WAITING_DELETE_SELECT, WAITING_SEARCH, WAITING_CARD_COUNT,
    WAITING_CARD_TYPE, WAITING_CARD_PROFILE, WAITING_PDF_VALUE,
    WAITING_INPUT, WAITING_DISC_USERNAME, WAITING_DISC_PASSWORD,
    WAITING_SCHEDULE_TIME, WAITING_EDIT_FIELD, WAITING_EDIT_VALUE,
    WAITING_RENAME, WAITING_UPTIME_TYPE, WAITING_UPTIME_VALUE,
    WAITING_HOTSPOT_CARD_COUNT, WAITING_HOTSPOT_CARD_LENGTH,
    WAITING_HOTSPOT_CARD_PREFIX, WAITING_HOTSPOT_CARD_TYPE,
    WAITING_HOTSPOT_CARD_PROFILE, WAITING_HOTSPOT_CARD_UPTIME,
    WAITING_HOTSPOT_CARD_BYTES,
    WAITING_USAGE_QUERY,
    WAITING_STATS_DAY,
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
from bot.handlers.hotspot_report import report_command, report_export_csv
from bot.handlers.batch import batches_command, batch_select, batch_regen
