from bot.handlers.audit import (
    logs_back_callback as logs_back_callback,
)
from bot.handlers.audit import (
    logs_clear_callback as logs_clear_callback,
)
from bot.handlers.audit import (
    logs_command as logs_command,
)
from bot.handlers.audit import (
    logs_filter_callback as logs_filter_callback,
)
from bot.handlers.audit import (
    logs_page_callback as logs_page_callback,
)
from bot.handlers.audit import (
    logs_set_callback as logs_set_callback,
)
from bot.handlers.audit import (
    logs_subnav_callback as logs_subnav_callback,
)
from bot.handlers.backup import (
    backup_download_file as backup_download_file,
)
from bot.handlers.backup import (
    backup_full as backup_full,
)
from bot.handlers.backup import (
    backup_userman as backup_userman,
)
from bot.handlers.backup import (
    schedule_disable as schedule_disable,
)
from bot.handlers.backup import (
    schedule_enable as schedule_enable,
)
from bot.handlers.backup import (
    schedule_menu as schedule_menu,
)
from bot.handlers.backup import (
    schedule_menu_from_conversation as schedule_menu_from_conversation,
)
from bot.handlers.backup import (
    schedule_set as schedule_set,
)
from bot.handlers.backup_restore import (
    backup_restore_confirm as backup_restore_confirm,
)
from bot.handlers.backup_restore import (
    backup_restore_select as backup_restore_select,
)
from bot.handlers.backup_restore import (
    backup_restore_start as backup_restore_start,
)
from bot.handlers.backup_restore import (
    userman_restore_execute as userman_restore_execute,
)
from bot.handlers.backup_restore import (
    userman_restore_select as userman_restore_select,
)
from bot.handlers.backup_restore import (
    userman_restore_start as userman_restore_start,
)
from bot.handlers.batch import (
    batch_regen as batch_regen,
)
from bot.handlers.batch import (
    batch_select as batch_select,
)
from bot.handlers.batch import (
    batches_command as batches_command,
)
from bot.handlers.commands_basic import (
    cancel as cancel,
)
from bot.handlers.commands_basic import (
    clean_chat as clean_chat,
)
from bot.handlers.commands_basic import (
    error_handler as error_handler,
)
from bot.handlers.commands_basic import (
    metrics_command as metrics_command,
)
from bot.handlers.commands_basic import (
    reprompt_card_profile_text as reprompt_card_profile_text,
)
from bot.handlers.commands_basic import (
    reprompt_card_type_text as reprompt_card_type_text,
)
from bot.handlers.commands_basic import (
    reprompt_select_user as reprompt_select_user,
)
from bot.handlers.commands_basic import (
    sync_commands as sync_commands,
)
from bot.handlers.constants import (
    WAITING_BYTES_TOTAL as WAITING_BYTES_TOTAL,
)
from bot.handlers.constants import (
    WAITING_CARD_COUNT as WAITING_CARD_COUNT,
)
from bot.handlers.constants import (
    WAITING_CARD_PROFILE as WAITING_CARD_PROFILE,
)
from bot.handlers.constants import (
    WAITING_CARD_TYPE as WAITING_CARD_TYPE,
)
from bot.handlers.constants import (
    WAITING_COMMENT as WAITING_COMMENT,
)
from bot.handlers.constants import (
    WAITING_DELETE_ID as WAITING_DELETE_ID,
)
from bot.handlers.constants import (
    WAITING_DELETE_SELECT as WAITING_DELETE_SELECT,
)
from bot.handlers.constants import (
    WAITING_DISC_PASSWORD as WAITING_DISC_PASSWORD,
)
from bot.handlers.constants import (
    WAITING_DISC_USERNAME as WAITING_DISC_USERNAME,
)
from bot.handlers.constants import (
    WAITING_EDIT_FIELD as WAITING_EDIT_FIELD,
)
from bot.handlers.constants import (
    WAITING_EDIT_VALUE as WAITING_EDIT_VALUE,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_BYTES as WAITING_HOTSPOT_CARD_BYTES,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_COUNT as WAITING_HOTSPOT_CARD_COUNT,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_LENGTH as WAITING_HOTSPOT_CARD_LENGTH,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_PREFIX as WAITING_HOTSPOT_CARD_PREFIX,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_PROFILE as WAITING_HOTSPOT_CARD_PROFILE,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_TYPE as WAITING_HOTSPOT_CARD_TYPE,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_CARD_UPTIME as WAITING_HOTSPOT_CARD_UPTIME,
)
from bot.handlers.constants import (
    WAITING_HOTSPOT_SEARCH as WAITING_HOTSPOT_SEARCH,
)
from bot.handlers.constants import (
    WAITING_INPUT as WAITING_INPUT,
)
from bot.handlers.constants import (
    WAITING_PASSWORD as WAITING_PASSWORD,
)
from bot.handlers.constants import (
    WAITING_PDF_VALUE as WAITING_PDF_VALUE,
)
from bot.handlers.constants import (
    WAITING_PROFILE as WAITING_PROFILE,
)
from bot.handlers.constants import (
    WAITING_RENAME as WAITING_RENAME,
)
from bot.handlers.constants import (
    WAITING_SCHEDULE_TIME as WAITING_SCHEDULE_TIME,
)
from bot.handlers.constants import (
    WAITING_STATS_DAY as WAITING_STATS_DAY,
)
from bot.handlers.constants import (
    WAITING_UPTIME_TYPE as WAITING_UPTIME_TYPE,
)
from bot.handlers.constants import (
    WAITING_UPTIME_VALUE as WAITING_UPTIME_VALUE,
)
from bot.handlers.constants import (
    WAITING_USAGE_QUERY as WAITING_USAGE_QUERY,
)
from bot.handlers.constants import (
    WAITING_USERMAN_SEARCH as WAITING_USERMAN_SEARCH,
)
from bot.handlers.constants import (
    WAITING_USERNAME as WAITING_USERNAME,
)
from bot.handlers.hotspot import (
    hotspot_stats as hotspot_stats,
)
from bot.handlers.hotspot import (
    hotspot_stats_day_input as hotspot_stats_day_input,
)
from bot.handlers.hotspot_add import (
    add_back_to_bytes as add_back_to_bytes,
)
from bot.handlers.hotspot_add import (
    add_back_to_password as add_back_to_password,
)
from bot.handlers.hotspot_add import (
    add_back_to_profile as add_back_to_profile,
)
from bot.handlers.hotspot_add import (
    add_back_to_uptime as add_back_to_uptime,
)
from bot.handlers.hotspot_add import (
    add_back_to_uptime_from_comment as add_back_to_uptime_from_comment,
)
from bot.handlers.hotspot_add import (
    add_back_to_username as add_back_to_username,
)
from bot.handlers.hotspot_add import (
    hotspot_add_bytes as hotspot_add_bytes,
)
from bot.handlers.hotspot_add import (
    hotspot_add_comment as hotspot_add_comment,
)
from bot.handlers.hotspot_add import (
    hotspot_add_password as hotspot_add_password,
)
from bot.handlers.hotspot_add import (
    hotspot_add_profile as hotspot_add_profile,
)
from bot.handlers.hotspot_add import (
    hotspot_add_profile_selected as hotspot_add_profile_selected,
)
from bot.handlers.hotspot_add import (
    hotspot_add_start as hotspot_add_start,
)
from bot.handlers.hotspot_add import (
    hotspot_add_uptime_type as hotspot_add_uptime_type,
)
from bot.handlers.hotspot_add import (
    hotspot_add_uptime_type_invalid_text as hotspot_add_uptime_type_invalid_text,
)
from bot.handlers.hotspot_add import (
    hotspot_add_uptime_value as hotspot_add_uptime_value,
)
from bot.handlers.hotspot_add import (
    hotspot_add_username as hotspot_add_username,
)
from bot.handlers.hotspot_add import (
    skip_bytes as skip_bytes,
)
from bot.handlers.hotspot_add import (
    skip_comment as skip_comment,
)
from bot.handlers.hotspot_add import (
    skip_password as skip_password,
)
from bot.handlers.hotspot_add import (
    skip_uptime as skip_uptime,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_bytes as hotspot_cards_bytes,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_count as hotspot_cards_count,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_length as hotspot_cards_length,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_prefix as hotspot_cards_prefix,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_profile_selected as hotspot_cards_profile_selected,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_skip_bytes as hotspot_cards_skip_bytes,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_skip_prefix as hotspot_cards_skip_prefix,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_skip_uptime as hotspot_cards_skip_uptime,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_skip_uptime_type as hotspot_cards_skip_uptime_type,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_start as hotspot_cards_start,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_type_selected as hotspot_cards_type_selected,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_uptime_type as hotspot_cards_uptime_type,
)
from bot.handlers.hotspot_cards import (
    hotspot_cards_uptime_value as hotspot_cards_uptime_value,
)
from bot.handlers.hotspot_cards import (
    hs_back_to_length as hs_back_to_length,
)
from bot.handlers.hotspot_cards import (
    hs_back_to_profile as hs_back_to_profile,
)
from bot.handlers.hotspot_cards import (
    hs_back_to_type as hs_back_to_type,
)
from bot.handlers.hotspot_cards import (
    hs_back_to_uptime as hs_back_to_uptime,
)
from bot.handlers.hotspot_common import handle_page_callback as handle_page_callback
from bot.handlers.hotspot_delete import (
    confirm_callback as confirm_callback,
)
from bot.handlers.hotspot_delete import (
    confirm_reprompt as confirm_reprompt,
)
from bot.handlers.hotspot_delete import (
    hotspot_delete_search as hotspot_delete_search,
)
from bot.handlers.hotspot_delete import (
    hotspot_delete_select as hotspot_delete_select,
)
from bot.handlers.hotspot_delete import (
    hotspot_delete_start as hotspot_delete_start,
)
from bot.handlers.hotspot_edit import (
    edit_back_search as edit_back_search,
)
from bot.handlers.hotspot_edit import (
    edit_back_to_fields as edit_back_to_fields,
)
from bot.handlers.hotspot_edit import (
    edit_profile_selected as edit_profile_selected,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_field as hotspot_edit_field,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_kick as hotspot_edit_kick,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_reset as hotspot_edit_reset,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_search as hotspot_edit_search,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_select as hotspot_edit_select,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_start as hotspot_edit_start,
)
from bot.handlers.hotspot_edit import (
    hotspot_edit_value as hotspot_edit_value,
)
from bot.handlers.hotspot_report import (
    report_command as report_command,
)
from bot.handlers.hotspot_report import (
    report_export_csv as report_export_csv,
)
from bot.handlers.hotspot_search import (
    hotspot_host_action as hotspot_host_action,
)
from bot.handlers.hotspot_search import (
    hotspot_search_back as hotspot_search_back,
)
from bot.handlers.hotspot_search import (
    hotspot_search_query as hotspot_search_query,
)
from bot.handlers.hotspot_search import (
    hotspot_search_start as hotspot_search_start,
)
from bot.handlers.hotspot_search import (
    hotspot_show_host as hotspot_show_host,
)
from bot.handlers.menus import (
    go_back as go_back,
)
from bot.handlers.routers import (
    connect_router as connect_router,
)
from bot.handlers.routers import (
    delete_router_confirm as delete_router_confirm,
)
from bot.handlers.routers import (
    delete_router_execute as delete_router_execute,
)
from bot.handlers.routers import (
    disc_enter_password as disc_enter_password,
)
from bot.handlers.routers import (
    disc_enter_username as disc_enter_username,
)
from bot.handlers.routers import (
    discover_routers_callback as discover_routers_callback,
)
from bot.handlers.routers import (
    discovered_router_selected as discovered_router_selected,
)
from bot.handlers.routers import (
    reboot_router_callback as reboot_router_callback,
)
from bot.handlers.routers import (
    reboot_saved_router as reboot_saved_router,
)
from bot.handlers.routers import (
    reboot_start as reboot_start,
)
from bot.handlers.routers import (
    refresh_routers as refresh_routers,
)
from bot.handlers.routers import (
    rename_router_start as rename_router_start,
)
from bot.handlers.routers import (
    rename_router_value as rename_router_value,
)
from bot.handlers.routers import (
    saved_router_selected as saved_router_selected,
)
from bot.handlers.routers import (
    saved_routers_list as saved_routers_list,
)
from bot.handlers.settings import (
    pdf_settings_option as pdf_settings_option,
)
from bot.handlers.settings import (
    pdf_settings_value as pdf_settings_value,
)
from bot.handlers.stats import (
    stats_hotspot as stats_hotspot,
)
from bot.handlers.stats import (
    stats_userman as stats_userman,
)
from bot.handlers.usage import (
    usage_query as usage_query,
)
from bot.handlers.usage import (
    usage_start as usage_start,
)
from bot.handlers.userman import (
    userman_card_count as userman_card_count,
)
from bot.handlers.userman import (
    userman_card_mac_selected as userman_card_mac_selected,
)
from bot.handlers.userman import (
    userman_card_payment_selected as userman_card_payment_selected,
)
from bot.handlers.userman import (
    userman_card_profile_selected as userman_card_profile_selected,
)
from bot.handlers.userman import (
    userman_card_type_selected as userman_card_type_selected,
)
from bot.handlers.userman import (
    userman_cards_start as userman_cards_start,
)
from bot.handlers.userman import (
    userman_list as userman_list,
)
from bot.handlers.userman import (
    userman_profiles as userman_profiles,
)
from bot.handlers.userman_search import (
    userman_search_action as userman_search_action,
)
from bot.handlers.userman_search import (
    userman_search_back as userman_search_back,
)
from bot.handlers.userman_search import (
    userman_search_query as userman_search_query,
)
from bot.handlers.userman_search import (
    userman_search_select as userman_search_select,
)
from bot.handlers.userman_search import (
    userman_search_start as userman_search_start,
)
from bot.handlers.watchdog import (
    watchdog_refresh as watchdog_refresh,
)
from bot.handlers.watchdog import (
    watchdog_start as watchdog_start,
)
from bot.handlers.watchdog import (
    watchdog_status as watchdog_status,
)
from bot.handlers.watchdog import (
    watchdog_stop as watchdog_stop,
)
