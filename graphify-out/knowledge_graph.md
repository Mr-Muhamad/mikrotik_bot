# Graph Report - .  (2026-07-20)

## Corpus Check
- 267 files · ~156,815 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2920 nodes · 7812 edges · 180 communities (153 shown, 27 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 521 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 120
- Community 121
- Community 122
- Community 123
- Community 124
- Community 125
- Community 126
- Community 127
- Community 128
- Community 129
- Community 130
- Community 131
- Community 132
- Community 133
- Community 134
- Community 135
- Community 136
- Community 137
- Community 138
- Community 139
- Community 140
- Community 141
- Community 142
- Community 143
- Community 144
- Community 145
- Community 146
- Community 147
- Community 148
- Community 149
- Community 150
- Community 151
- Community 152
- Community 153
- Community 154
- Community 155
- Community 156
- Community 157
- Community 158
- Community 159
- Community 160
- Community 161
- Community 162
- Community 163
- Community 164
- Community 165

## God Nodes (most connected - your core abstractions)
1. `make_mock_update()` - 144 edges
2. `safe_answer_callback()` - 125 edges
3. `run_blocking()` - 104 edges
4. `get_db()` - 86 edges
5. `cleanup_state()` - 81 edges
6. `make_mock_context()` - 79 edges
7. `send_step()` - 78 edges
8. `send_error()` - 65 edges
9. `get_selected_router()` - 61 edges
10. `CardData` - 44 edges

## Surprising Connections (you probably didn't know these)
- `test_singleton_satisfies_protocol()` --indirect_call--> `MikrotikClient`  [INFERRED]
  tests/core/test_mikrotik_client_contract.py → core/mikrotik_client.py
- `logs_filter_callback()` --indirect_call--> `get_distinct_log_actions()`  [INFERRED]
  bot/handlers/audit.py → database/repositories/audit_logs.py
- `logs_filter_callback()` --indirect_call--> `get_distinct_log_admins()`  [INFERRED]
  bot/handlers/audit.py → database/repositories/audit_logs.py
- `logs_filter_callback()` --indirect_call--> `get_distinct_log_routers()`  [INFERRED]
  bot/handlers/audit.py → database/repositories/audit_logs.py
- `_show_logs_page()` --indirect_call--> `get_logs()`  [INFERRED]
  bot/handlers/audit.py → database/repositories/audit_logs.py

## Import Cycles
- None detected.

## Communities (180 total, 27 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.09
Nodes (41): List saved User Manager tar backups for restore., userman_restore_start(), get_query_chat_id(), get_query_message(), make_back_step(), Shared helpers for Telegram callback handlers.  تلخّص العمليات المتكررة في han, Factory لدوال "الرجوع" البسيطة المتكررة.      تُنشئ دالة async تستقبل (update,, أعد رسالة الـ callback مضيّقةً إلى ``Message``، أو None.      ``query.message` (+33 more)

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (16): TestBackNavigation, TestHotspotAddComment, TestHotspotAddPassword, TestHotspotAddStart, TestHotspotAddUsername, TestSkipComment, TestSkipHandlers, TestBackNavigation (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.12
Nodes (53): add_back_to_profile(), hotspot_add_bytes(), hotspot_add_comment(), hotspot_add_password(), hotspot_add_profile(), hotspot_add_profile_selected(), hotspot_add_start(), hotspot_add_uptime_type_invalid_text() (+45 more)

### Community 3 - "Community 3"
Cohesion: 0.08
Nodes (28): add_tracked_message(), get_tracked_messages(), Track a newly sent bot message., Get all tracked message IDs for a chat., _ctx(), Tests for utils.chat_cleaner — message tracking, cleanup, and truncation., TestCleanChatMessages, TestCleanCommand (+20 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (46): _add_column_if_missing(), _column_exists(), _create_indexes(), _get_connection(), get_db(), init_db(), migrate_add_name_alias(), migrate_backup_schedule_columns() (+38 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (38): _callback_update(), _ctx(), Tests for utils.error_response benign-error handling and chat_cleaner safe edits, TestIsBenignTelegramError, TestSafeEditsBenign, TestSendErrorBenign, _dispatch_message(), _get_chat_id() (+30 more)

### Community 6 - "Community 6"
Cohesion: 0.09
Nodes (35): add_customer_command(), assign_router_command(), op_assign_router_callback(), op_revoke_router_callback(), DEFAULT_TYPE, Update, Super Admin removes a customer: /remove_customer <id>., عرض واجهة إسناد الروترات لمشغّل معين.      الاستخدام: /assign_router <operator (+27 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (15): batch_page(), block_mac_cb(), delete_router(), hotspot_search_page(), op_assign_cb(), op_list_cb(), op_revoke_cb(), Single source of truth for Telegram callback_data tokens and registration patter (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (36): pdf_group_layout(), pdf_group_misc(), pdf_group_text(), DEFAULT_TYPE, Update, cmd_timeout(), handle_timeout_selection(), DEFAULT_TYPE (+28 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (28): build_all(), Build all handlers from registry and add to application.      Registration ord, _BotBase, Chat, _cb(), FakeBot, main(), _make_chat() (+20 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (21): check_router_health(), clear_status(), get_router_status(), get_router_status_detail(), mark_alert_sent(), Check if an alert was already sent for current outage., Mark that an alert has been sent for this router., Clear status for a router (e.g. after deletion). (+13 more)

### Community 11 - "Community 11"
Cohesion: 0.07
Nodes (35): handle_page_callback(), DEFAULT_TYPE, Update, معالجة أزرار التنقييم (page_edit_N / page_delete_N)., confirm_callback(), confirm_reprompt(), hotspot_delete_search(), hotspot_delete_select() (+27 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (8): Unit tests for database/repositories/* — exercised directly (not via the facade), TestAdminRolesRepository, TestAuditLogsRepository, TestBackupsRepository, TestCardBatchesRepository, TestPdfSettingsRepository, TestRoutersRepository, TestUserSessionsRepository

### Community 13 - "Community 13"
Cohesion: 0.14
Nodes (14): get_hotspot_edit_session(), Retrieve or initialize the HotspotEditSession from user_data., save_user_session(), _make_context(), _seed_user(), TestConfirmCallback, TestHotspotDeleteSelect, _make_context() (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (19): CardData, CardSystem, هيكل بيانات الكارت المشترك بين User Manager و Hotspot., إظهار الباسورد فقط إذا كان مختلفاً عن اليوزر., أنظمة إنشاء الكروت الثلاثة., _fake_cards(), _patch_router(), Unit tests for bot/handlers/hotspot_cards.py — card generation flow. (+11 more)

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (8): pdf_settings_option(), pdf_settings_value(), _ctx(), _query_update(), Tests for bot.handlers.settings., TestPdfSettingsOption, TestPdfSettingsValue, _text_update()

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (18): cleanup_old_backups(), cleanup_old_files(), cleanup_router_files(), is_safe_filename(), is_valid_router_backup_name(), parse_router_creation_time(), resolve_local_backup_file(), resolve_userman_backup_file() (+10 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (22): cancel(), clean_chat(), _get_router_part(), help_command(), _internal_main_menu(), main_menu(), Internal main_menu without @admin_only — safe for go_back/end_conversation., Return a formatted router name string, or empty string if unavailable. (+14 more)

### Community 18 - "Community 18"
Cohesion: 0.17
Nodes (29): ack_callback(), parse_router_id(), CallbackQuery, أجب على callback query بأمان وأعده، أو None إن لم يوجد query.      يستبدل النم, استخرج معرّف الراوتر الصحيح من بيانات الـ callback.      عند الفشل يرسل ``ERRO, DEFAULT_TYPE, Update, reboot_router_callback() (+21 more)

### Community 19 - "Community 19"
Cohesion: 0.12
Nodes (12): hotspot_host_action(), hotspot_search_back(), hotspot_show_host(), _admin_update(), _ctx(), Tests for bot.handlers.hotspot_search., Create a mock update with effective_chat.type='private' for @admin_only tests., TestHotspotHostKick (+4 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (21): disc_enter_password(), disc_enter_username(), discovered_router_selected(), DEFAULT_TYPE, Update, DEFAULT_TYPE, Update, rename_router_start() (+13 more)

### Community 21 - "Community 21"
Cohesion: 0.10
Nodes (25): AST, _extract_handler_names(), _get_callee_name(), _get_root_call_name(), _local_defs(), main(), Validate that every imported Telegram handler is registered and vice versa.  Det, Return the root function name for chained decorator calls. (+17 more)

### Community 22 - "Community 22"
Cohesion: 0.13
Nodes (27): _background_backup_job(), backup_download_file(), backup_full(), backup_userman(), _is_backup_running(), DEFAULT_TYPE, Update, إرسال ملف الباكوب عند ضغط المستخدم على زر التحميل. (+19 more)

### Community 23 - "Community 23"
Cohesion: 0.15
Nodes (15): execute_add_user(), search_users_for_action(), get_hotspot_add_session(), HotspotAddSession, HotspotEditSession, Any, Retrieve or initialize the HotspotAddSession from user_data., Strongly-typed session state for the hotspot_edit flow. (+7 more)

### Community 24 - "Community 24"
Cohesion: 0.12
Nodes (17): cleanup_old_logs(), get_distinct_log_actions(), get_distinct_log_admins(), get_distinct_log_routers(), get_logs(), get_logs_count(), log_action(), _logs_where_clauses() (+9 more)

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (28): _build_db_filters(), _empty_filters(), _format_filters_short(), _get_filters(), logs_back_callback(), logs_clear_callback(), logs_command(), logs_filter_callback() (+20 more)

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (15): LogRecord, Tests for the request-id tracking utilities., Child loggers (e.g. apscheduler) propagate to root handlers —         the handl, TestConfigureLogging, TestRequestIdContext, TestRequestIdFilter, TestRequestIdInRealLog, configure_logging() (+7 more)

### Community 27 - "Community 27"
Cohesion: 0.13
Nodes (10): _ctx(), _query_update(), TestUsermanCardCount, TestUsermanCardMacSelected, TestUsermanCardPaymentSelected, TestUsermanCardProfileSelected, TestUsermanCardsStart, TestUsermanCardTypeSelected (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.14
Nodes (8): _admin_update(), _ctx(), TestUsermanSearchAction, TestUsermanSearchAddProfile, TestUsermanSearchBack, TestUsermanSearchQuery, TestUsermanSearchSelect, TestUsermanSearchStart

### Community 29 - "Community 29"
Cohesion: 0.18
Nodes (28): edit_back_to_fields(), edit_profile_selected(), hotspot_edit_field(), hotspot_edit_kick(), hotspot_edit_reset(), hotspot_edit_search(), hotspot_edit_select(), hotspot_edit_start() (+20 more)

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (18): backup_restore_confirm(), backup_restore_select(), backup_restore_start(), DEFAULT_TYPE, Update, Execute backup restore after confirmation., Show confirmation dialog for selected userman backup., Execute User Manager restore from selected tar file. (+10 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (14): Set the selected router key for a user in the database., Ensure a router is selected before running a handler.      Lives in the bot (p, require_router(), set_selected_router(), _clear_rate_limit(), _ctx(), Tests for utils.admin_decorator — admin gating and rate limiting., Reset rate limit cache between tests. (+6 more)

### Community 32 - "Community 32"
Cohesion: 0.08
Nodes (12): Retrieves and formats Hotspot and User Manager statistics from MikroTik routers., تنسيق آخر 7 أيام كـ ASCII bar chart نصي بسيط.          كل سطر: التاريخ | شريط |, مقارنة المستخدمين النشطين اليوم مقابل الأمس.          يُعيد نص HTML مثل: ↑5 مقار, Return aggregated hotspot user counts and total byte usage., Return User Manager card counts by enabled/disabled status., Format hotspot stats dict into an Arabic display string., Format User Manager stats dict into an Arabic display string., Format a Hotspot usage report dict into an Arabic Telegram summary. (+4 more)

### Community 33 - "Community 33"
Cohesion: 0.12
Nodes (6): BackupScheduler, فحص يومي لاشتراكات Hotspot المشارفة على الانتهاء وإرسال تنبيه للمشرفين., حفظ snapshot يومي لإحصائيات كل راوتر في قاعدة البيانات., MockJob, Unit tests for core/backup_scheduler.py — BackupScheduler class.  Lazy imports, TestBackupScheduler

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (14): HotspotManager, Search hotspot users by name or comment (case-insensitive substring match)., Manages MikroTik Hotspot users, hosts, profiles, and session kick operations., Return up to limit hotspot users from the router., Return a single hotspot user dict by its .id, or None if not found., Return list of hotspot user profiles from the router., Format a hotspot user dict into a human-readable Arabic string., Return hotspot statistics, optionally filtered to a single reset day.          D (+6 more)

### Community 35 - "Community 35"
Cohesion: 0.13
Nodes (9): TestValidatePassword, TestValidatePositiveInt, TestValidateUsername, Validate a hotspot username for length and allowed characters., Validate a hotspot password for length and disallowed whitespace characters., Validate that a value is a positive integer., validate_password(), validate_positive_int() (+1 more)

### Community 36 - "Community 36"
Cohesion: 0.14
Nodes (13): Tests for utils.crypto — Fernet password encryption (no session fallback, ENCRYP, ENCRYPTION_KEY is REQUIRED - no session fallback., TestDecryptPassword, TestEncryptPassword, TestGetKey, _valid_key(), decrypt_data(), decrypt_password() (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.14
Nodes (25): block_mac_handler(), _format_search_results_text(), hotspot_search_page_handler(), hotspot_search_query(), DEFAULT_TYPE, Update, Search hotspot hosts by a specific field (mac-address or address).      Delega, حظر MAC دائم في address-list=hotspot_blocked على الراوتر. (+17 more)

### Community 38 - "Community 38"
Cohesion: 0.14
Nodes (12): discover_routers_callback(), get_saved_routers(), جلب الروترات المحفوظة من قاعدة البيانات.      Args:         active_only: تصفي, test(), _all_saved_routers(), _fake_router(), _make_context(), Integration-style tests for router discovery and saved router flows.  Tests th (+4 more)

### Community 39 - "Community 39"
Cohesion: 0.11
Nodes (22): DEFAULT_TYPE, Update, _show_stats(), stats_hotspot(), stats_userman(), DEFAULT_TYPE, Update, _show_usage_report() (+14 more)

### Community 40 - "Community 40"
Cohesion: 0.11
Nodes (24): navigation_guard(), Central navigation guard: enforce an active router session.      Wraps any han, build_application(), _build_handler(), entry_point(), error_handler(), fallback(), _load_guard() (+16 more)

### Community 41 - "Community 41"
Cohesion: 0.08
Nodes (6): Injected client, or the shared module singleton (late-bound for tests)., MikrotikClient, Protocol, Command execution and router-metadata contract used across the app., Injected client, or the shared module singleton (late-bound for tests)., Injected client, or the shared module singleton (late-bound for tests).

### Community 42 - "Community 42"
Cohesion: 0.14
Nodes (16): Tests for utils.singleton_lock — single-instance enforcement., Ensure lock is released after each test., _reset_lock(), TestAcquireLock, TestGetLockPath, TestReleaseLock, TestSingleInstanceContext, acquire_lock() (+8 more)

### Community 43 - "Community 43"
Cohesion: 0.17
Nodes (22): manual_add_confirm(), _confirm_keyboard(), manual_add_alias(), manual_add_confirm(), manual_add_ip(), manual_add_pass(), manual_add_port(), manual_add_start() (+14 more)

### Community 45 - "Community 45"
Cohesion: 0.12
Nodes (10): block_mac(), get_blocked_macs(), Hotspot MAC blocking operations (firewall address-list management).  Extracted f, يضيف MAC إلى address-list باسم hotspot_blocked في /ip/firewall/address-list., يحذف MAC من address-list=hotspot_blocked.      يُعيد True عند النجاح وFalse عند, يُعيد قائمة MACs في address-list=hotspot_blocked.      يُعيد قائمة فارغة عند الف, unblock_mac(), Abstraction (Port) for the MikroTik client.  Defines the public contract that (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.18
Nodes (23): _batch_label(), batch_page_handler(), batch_regen(), batch_select(), batches_command(), _dump(), _format_batch_text(), mark_batch_paid_handler() (+15 more)

### Community 47 - "Community 47"
Cohesion: 0.23
Nodes (20): _format_userman_detail(), _format_userman_search_results(), DEFAULT_TYPE, Update, userman_search_action(), userman_search_add_profile(), userman_search_add_profile_selected(), userman_search_back() (+12 more)

### Community 48 - "Community 48"
Cohesion: 0.11
Nodes (20): clear_alert_sent(), load_status_from_db(), Reset alert flag so next offline triggers a new alert., تحميل آخر حالة معروفة لكل الراوترات من DB إلى الـ in-memory dicts.      يُستدع, cleanup_health_history(), get_all_latest_health(), get_health_history(), get_latest_health() (+12 more)

### Community 49 - "Community 49"
Cohesion: 0.12
Nodes (5): mock_mikrotik_api(), Patch the singleton mikrotik_api with an in-memory mock.      Patches all modu, MikrotikAPIMock, In-memory mock that mimics MikrotikAPI behaviour.      Stores users/profiles/h, Mock health check — always returns healthy.

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (10): hotspot_add_uptime_type(), _patch_router(), Unit tests for bot/handlers/hotspot_add.py — full add flow coverage.  These te, Patch router_selector AND clear admin_only rate limit cache.      Patches both, TestGetUptimeTypeKeyboard, TestHotspotAddBytes, TestHotspotAddProfile, TestHotspotAddProfileSelected (+2 more)

### Community 51 - "Community 51"
Cohesion: 0.11
Nodes (11): _arabic_text(), Draw rounded rectangle border., Draw brand name and separator line., Draw card data title., Pick the largest integer font size so *text* fits *max_width_mm*., Draw username and password fields with dynamic font sizing., Draw QR code for hotspot login., Draw footer line and footer text. (+3 more)

### Community 52 - "Community 52"
Cohesion: 0.11
Nodes (10): ProfileSync, Fetches User Manager profile names from a MikroTik router., Injected client, or the shared module singleton (late-bound for tests)., Return a list of User Manager profile names from the router., Contract test: the MikroTik singleton must satisfy the MikrotikClient Protocol., test_class_instance_satisfies_protocol(), test_managers_default_to_protocol_client(), test_singleton_satisfies_protocol() (+2 more)

### Community 53 - "Community 53"
Cohesion: 0.19
Nodes (18): _internal_backup_menu(), _internal_hotspot_menu(), _internal_reports_menu(), _internal_routers_menu(), _internal_stats_menu(), _internal_userman_menu(), Show the router management submenu (discover / saved / manual add)., Show the reports submenu (usage / sales / batches / audit log). (+10 more)

### Community 54 - "Community 54"
Cohesion: 0.19
Nodes (18): _check_all_routers(), _notify_admins(), DEFAULT_TYPE, Update, Force an immediate ping to all routers and refresh status., Send or edit in place depending on whether triggered from a callback., Periodic job: check all saved routers concurrently and send alerts., Send a notification to all configured admins. (+10 more)

### Community 55 - "Community 55"
Cohesion: 0.18
Nodes (10): get_last_backup(), get_recent_backups(), _prune_backup_jobs(), Backup schedule/results repository.  Manages ``backup_settings`` and ``backup_, Return the most recent backup record for a router, or None., Return the most recent backup records across all routers., Persist the result of a single backup run and return its row id.      Records, record_backup_result() (+2 more)

### Community 56 - "Community 56"
Cohesion: 0.11
Nodes (8): Typed key for identifying a router across the bot.  يستبدل الـ string الخام "d, مفتاح راوتر قوي النوع.      الأنماط المدعومة:     - RouterKey.discovered(db_i, إنشاء مفتاح لراوتم مكتشف في DB., تحليل string إلى RouterKey (يقبل أي قيمة)., معرّف DB للراوتر، أو None إذا لم يكن راوتر مكتشف., النص الخام (للتسجيل والعرض)., هل المفتاح يشير لراوتر مكتشف في DB؟, RouterKey

### Community 57 - "Community 57"
Cohesion: 0.18
Nodes (10): _base_stats(), _bypass_decorators(), _direct_hotspot_stats(), _message_update(), _query_update(), Tests for bot.handlers.hotspot., Direct invocation bypassing @admin_only decorator., Replace handlers with the unwrapped functions to bypass decorators.      The h (+2 more)

### Community 58 - "Community 58"
Cohesion: 0.15
Nodes (8): pool(), Unit tests for core/connection_pool.py — ConnectionPool class., _router_db_row(), TestCloseAll, TestGetConnection, TestMetrics, TestReleaseConnection, TestRetry

### Community 59 - "Community 59"
Cohesion: 0.11
Nodes (7): Tests for the MikrotikAPI facade and ConnectionPool integration., TestExecuteNonBlocking, TestGetMetrics, TestGetUsermanBasePath, TestInvalidateRouterName, TestInvalidateVersion, TestIsVersion7

### Community 60 - "Community 60"
Cohesion: 0.16
Nodes (5): get_backup_schedule(), save_backup_schedule(), Unit tests for database/models.py facade — operations against a temp DB., TestBackupSchedule, TestInitDB

### Community 61 - "Community 61"
Cohesion: 0.17
Nodes (10): ensure_admin_role(), get_admin_role(), list_admin_roles(), Admin role repository.  Isolated from the former god-object ``database.models`, Insert a role row for an admin if none exists yet (idempotent)., Ensure every configured admin has a role row (default full access)., Return the role string for an admin, or None if not recorded., Return all recorded admin role rows ordered by admin_id. (+2 more)

### Community 62 - "Community 62"
Cohesion: 0.26
Nodes (17): backup_menu(), _end_conversation(), end_conversation_to_backup(), end_conversation_to_hotspot(), end_conversation_to_main(), end_conversation_to_pdf_settings(), end_conversation_to_reports(), end_conversation_to_routers() (+9 more)

### Community 63 - "Community 63"
Cohesion: 0.26
Nodes (6): cache_profile_names(), resolve_profile_from_callback(), _ctx(), Tests for bot.profile_callbacks., TestCacheProfileNames, TestResolveProfileFromCallback

### Community 64 - "Community 64"
Cohesion: 0.15
Nodes (7): _GroupStateBuilder, Register a CallbackQueryHandler for this state., Register a MessageHandler for this state., Register a CommandHandler for this state., Start building a state handler registration.      Usage:         @state("WAIT, state(), _StateBuilder

### Community 65 - "Community 65"
Cohesion: 0.20
Nodes (13): deserialize_cards(), Serialize a list of CardData into a JSON string., Reconstruct a list of CardData from a serialized JSON string., serialize_cards(), get_card_batch(), Return a single batch row including decrypted ``cards`` (list of dicts)., Unit tests for HotspotManager using the in-memory MikrotikAPIMock., Tests for card batch persistence and serialization. (+5 more)

### Community 66 - "Community 66"
Cohesion: 0.26
Nodes (9): get_week_snapshots(), حفظ snapshot يومي لإحصائيات راوتر.      data: dict يحتوي على active_users, tot, استرداد snapshots آخر 7 أيام للراوتر، مرتبة من الأقدم للأحدث., save_snapshot(), _make_get_db(), Tests for database/repositories/stats_snapshots and core/stats trend methods., Return a get_db context manager backed by a fresh in-memory SQLite DB., TestGetWeekSnapshots (+1 more)

### Community 67 - "Community 67"
Cohesion: 0.17
Nodes (6): Tests for utils.callback_utils module., Reset _CALLBACK_DEDUP before each test., reset_dedup(), TestIsDuplicateCallback, TestSafeAnswerCallback, is_duplicate_callback()

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (3): Tests for the handler registry decorator API and build_application., TestBuildApplication, TestDecoratorRegistration

### Community 69 - "Community 69"
Cohesion: 0.26
Nodes (5): _fast_reachability_check(), إجراء فحص سريع للاتصال بالراوتر (1 ثانية كحد أقصى)., get_router_by_id(), save_discovered_router(), TestDiscoveredRouters

### Community 70 - "Community 70"
Cohesion: 0.14
Nodes (4): ConnectionPool, Closes all idle connections for a specific router., Check if the router currently has any active or idle connections., Manages MikroTik RouterOS API connections with thread-safe queues per router.

### Community 71 - "Community 71"
Cohesion: 0.17
Nodes (5): MikrotikAPI, أمر طويل — مهلة 120 ثانية، يعيد المحاولة عند الخطأ., Facade over ConnectionPool providing command execution and router metadata., يلغي كاش الإصدار المخزّن للراوتر.          يُستخدم بعد ترقية RouterOS أو إعادة, Returns the version from cache without hitting the network.

### Community 72 - "Community 72"
Cohesion: 0.19
Nodes (7): فحص صحة الاتصال بالروتر بشكل استباقي., ينفذ أمر MikroTik واحد على اتصال موجود (بدون retry)., يسجل kwargs مع إخفاء كلمات المرور., القالب الأساسي: throttle → تنفيذ → retry عند الخطأ القابل للإصلاح., الأمر العادي — مهلة 30 ثانية، يعيد المحاولة عند الخطأ., أمر غير متزامن — لا يعيد المحاولة، يسجل الخطأ ويتجاوزه., api()

### Community 73 - "Community 73"
Cohesion: 0.19
Nodes (8): parse_arp_table_linux(), parse_arp_table_windows(), Parse ``arp -a`` output on Windows.      Returns ``{ip: mac}`` for dynamic ent, Parse ``ip neigh`` output on Linux.      Returns ``{ip: mac}`` for valid entri, Return ``[{ip, mac, source}]`` for each dynamic ARP entry., Tests for core.network_probe — pure helpers and probe classes., TestParseArpTableLinux, TestParseArpTableWindows

### Community 74 - "Community 74"
Cohesion: 0.17
Nodes (5): PDFRenderer, Generates PDF files with card layouts for printing., Generate a PDF with all cards arranged in a grid layout., Tests for pdf.pdf_renderer., TestPDFRenderer

### Community 75 - "Community 75"
Cohesion: 0.14
Nodes (7): ProfileCache, In-memory TTL cache for MikroTik profile names.  يقلل عدد طلبات API المتكررة ل, كاش بسيط مع TTL لمعلومات البروفايلات لكل راوتر.      thread-safe للاستخدام من, جلب البروفايلات من الكاش. يُرجع None عند انتهاء الصلاحية أو عدم وجود., تخزين البروفايلات في الكاش., حذف البروفايلات لراوتر محدد (مثلاً بعد edit profile)., إحصائيات الكاش للمراقبة.

### Community 76 - "Community 76"
Cohesion: 0.20
Nodes (12): format_hotspot_stats(), format_hotspot_usage_report(), format_trend_chart(), format_userman_stats(), format_vs_yesterday(), Format hotspot stats dict into an Arabic display string., Format User Manager stats dict into an Arabic display string., Format a Hotspot usage report dict into an Arabic Telegram summary. (+4 more)

### Community 77 - "Community 77"
Cohesion: 0.14
Nodes (7): Resolve a username to its .id, handling numeric names safely., Set caller-id on an existing User Manager user after creation., Return a single User Manager user dict by name, or None if not found., Delete a User Manager user by name., Enable a User Manager user., Disable a User Manager user., Reset counters / clear profiles for a User Manager user.

### Community 78 - "Community 78"
Cohesion: 0.16
Nodes (7): Manages User Manager card creation, listing, and random credential generation., Return a list of active User Manager sessions., Terminate a specific User Manager session by its .id or numbers., Format a card dict into a display string with index number., Generate a random numeric username of the given length., Generate a random numeric password of the given length., UserManager

### Community 79 - "Community 79"
Cohesion: 0.21
Nodes (6): get_pdf_settings(), PDF settings repository.  Holds the tunable PDF label/card layout settings. Is, update_pdf_settings(), PDFSettings, Manages PDF card generation settings., TestPDFSettings

### Community 80 - "Community 80"
Cohesion: 0.24
Nodes (5): CardRenderer, Renders individual hotspot/userman cards onto a PDF canvas., TestCardRendererInit, TestDrawFooterCallerId, TestDynamicFontSize

### Community 83 - "Community 83"
Cohesion: 0.15
Nodes (3): Cache مع صلاحية محددة (TTL) لتخزين البيانات المؤقتة., إرجاع قائمة بالمفاتيح الحالية في الكاش (لأغراض المراقبة)., TTLCache

### Community 84 - "Community 84"
Cohesion: 0.19
Nodes (9): MNDPListenerProbe, Async probe that broadcasts MNDP discovery packets and listens for replies., Return ``[{ip, source, last_seen, ...attributes}]`` for each MNDP reply., MNDPPermissionError, Raised when MNDP socket requires admin/root privileges., PermissionError, OSError from socket creation is caught inside _discover_sync, returns []., PermissionError from socket creation propagates to caller. (+1 more)

### Community 85 - "Community 85"
Cohesion: 0.32
Nodes (12): Set (insert or update) the role for an admin., set_admin_role(), _callback_update(), Tests for role-based access control via utils.admin_decorator.require_role., role_db(), test_admin_passes_admin_command(), test_operator_blocked_from_admin_command(), test_operator_passes_operator_command() (+4 more)

### Community 86 - "Community 86"
Cohesion: 0.18
Nodes (9): clear_router_session(), get_user_session(), User session repository.  Stores per-user conversation/session state (selected, Update the last_activity timestamp for a user., Set the session timeout duration for a user., Clear the selected router from the user's session (used on timeout)., set_session_timeout(), update_activity() (+1 more)

### Community 87 - "Community 87"
Cohesion: 0.15
Nodes (9): mock_config(), mock_context(), mock_update(), Central test fixtures for all test modules., Basic mock Update — user typed no text, no callback., Mock Context with clean user_data and bot_data., Ensure config values are available during tests., CallbackQueryMock (+1 more)

### Community 88 - "Community 88"
Cohesion: 0.27
Nodes (3): TestParseBytes, parse_bytes(), Convert human-readable byte strings (e.g. 1.5G, 500M) to raw numeric byte values

### Community 89 - "Community 89"
Cohesion: 0.15
Nodes (3): Tests for utils.request_id — context scope and update binding decorator., TestBindRequestIdDecorator, TestRequestIdScope

### Community 90 - "Community 90"
Cohesion: 0.24
Nodes (5): DiscoveredRouter, Represents a MikroTik router discovered on the network., Return a short name string with identity, version, and board., Return a formatted multi-line display string with status emoji., TestDiscoveredRouter

### Community 91 - "Community 91"
Cohesion: 0.20
Nodes (6): Create a User Manager user and attach the selected profile.          The user, Link a profile to a v7 User Manager user via the ``user-profile`` table., Attach and activate a profile for a v6 User Manager user.          RouterOS v6, Read back the user<->profile link and confirm it was applied.          RouterO, Link an additional User Manager profile to an existing user.          A User M, Create multiple User Manager cards with the specified type and profile.

### Community 92 - "Community 92"
Cohesion: 0.23
Nodes (6): _mock_deps(), _query_update(), Tests for bot.handlers.stats., Replace stats_hotspot/stats_userman with direct function references.      Sinc, TestStatsHotspot, TestStatsUserman

### Community 93 - "Community 93"
Cohesion: 0.17
Nodes (3): Tests for core.userman_manager.UserManager., TestUserManagerCredentials, TestUserManagerFormatCard

### Community 95 - "Community 95"
Cohesion: 0.17
Nodes (4): Paginator, Pagination utility for user lists and other paginated content., معلومات الصفحة الحالية لعرضها في الرسالة., يقسم القائمة إلى صفحات مع أزرار التنقييم.

### Community 96 - "Community 96"
Cohesion: 0.25
Nodes (8): Classify a registered handler from its kwargs.      Returns True when the hand, requires_router_check(), _router_mgmt_regexes(), Tests for the centralized navigation guard (string-based classification)., test_requires_router_check_command_management_exempt(), test_requires_router_check_command_operational_guarded(), test_requires_router_check_pattern_management_exempt(), test_requires_router_check_pattern_operational_guarded()

### Community 97 - "Community 97"
Cohesion: 0.18
Nodes (5): Update allowed fields of an existing hotspot user by its .id., Reset traffic counters for a hotspot user., Enable a hotspot user by its .id., Disable a hotspot user by its .id., Delete a hotspot user by its .id.

### Community 98 - "Community 98"
Cohesion: 0.22
Nodes (5): Exception, يتحقق ما إذا كان الخطأ مهلة اتصال (winerror/errno 10060 أو نص timed out)., تنظيف نص خطأ الاتصال من أي أسرار محتملة قبل عرضه للمستخدم., يبني رسالة عربية واضحة وقابلة للفعل من خطأ اتصال raw., فحص استطلاعي لمنفذ 8729 (api-ssl) كسرّ تشخيصي فقط. لا يبدّل المسار الأساسي.

### Community 99 - "Community 99"
Cohesion: 0.31
Nodes (3): decode_mndp_packet(), Decode a single MNDP packet payload into a dict of attributes.      Returns ke, TestDecodeMndpPacket

### Community 100 - "Community 100"
Cohesion: 0.27
Nodes (4): PortScanProbe, Async probe that tests TCP connectivity on the MikroTik API port (8728)., Return ``[{ip, port, source}]`` for IPs that accept TCP connections., TestPortScanProbe

### Community 101 - "Community 101"
Cohesion: 0.25
Nodes (6): discover_routers(), Router discovery orchestrator using MNDP (MikroTik Neighbor Discovery Protocol)., Discover MikroTik routers using MNDP protocol.      MNDP (MikroTik Neighbor Disc, ProgressCallback, Integration tests for core.network_scanner using mocked probes., TestDiscoverRoutersOrchestrator

### Community 102 - "Community 102"
Cohesion: 0.27
Nodes (4): Initialize Arabic text reshaping and bidirectional support., _setup_arabic_support(), Tests for pdf.card_renderer and pdf.card_generator — PDF rendering pipeline., TestSetupArabicSupport

### Community 103 - "Community 103"
Cohesion: 0.24
Nodes (8): Process, main(), monitor_resources(), Monitors CPU and RAM usage in the background., Simulates high concurrent load on the HotspotManager., simulate_load(), Sample hotspot user data for tests — mimics RouterOS API output., Complete mock for MikrotikAPI — no real RouterOS connections.

### Community 105 - "Community 105"
Cohesion: 0.31
Nodes (3): TestValidateMac, Validate and normalize a MAC address for User Manager caller-id binding., validate_mac()

### Community 106 - "Community 106"
Cohesion: 0.18
Nodes (7): group(), _GroupBuilder, Create or retrieve a named group for a separate ConversationHandler.      Usag, Builder for a named ConversationHandler group., Register an entry point for this group's CH., Register a fallback for this group's CH., Start building a state for this group's CH.

### Community 107 - "Community 107"
Cohesion: 0.29
Nodes (4): Api, يحصل على اتصال جاهز من الطابور، أو ينشئ اتصالاً جديداً إذا لم يتجاوز الحد., يجب مناداة هذه الدالة دائماً لإعادة الاتصال للطابور بعد الانتهاء.         إذا ك, Close cache and establish a fresh connection.

### Community 108 - "Community 108"
Cohesion: 0.20
Nodes (10): get_callback_data(), get_effective_message(), get_message_text(), get_user_id(), Message, Update, أعد معرّف المستخدم من التحديث، أو None إن غاب ``effective_user``.      تستبدل, أعد بيانات الـ callback query، أو None إن غاب الـ query. (+2 more)

### Community 109 - "Community 109"
Cohesion: 0.27
Nodes (9): context_user_data_get(), context_user_data_set(), get_router_system_part(), _probe_path(), Router subsystem detection (Hotspot vs User Manager vs both).  Extracted from ``, Best-effort read of cached router system type from module-level cache., Store the detected router system type in the module-level cache., Return True if the given API path is reachable (empty list counts as present). (+1 more)

### Community 110 - "Community 110"
Cohesion: 0.22
Nodes (5): Add a new hotspot user with optional bandwidth limit, uptime limit, and comment., Generate a cryptographically secure random number of specified length., Create multiple hotspot users with random numbers and duplicate checking., Fetch all existing hotspot usernames from the router., Generate a unique username that doesn't exist on the router.

### Community 111 - "Community 111"
Cohesion: 0.22
Nodes (8): Extract the reset day (1-31) from a hotspot user comment.          Delegates to, build_usage_report(), get_hotspot_stats(), parse_reset_day(), Hotspot statistics and usage-report builders.  Extracted from ``core.hotspot_man, Build an exportable Hotspot usage report for a router.      Fetches all hotspot, Extract the reset day (1-31) from a hotspot user comment.      Supports the curr, Return hotspot statistics, optionally filtered to a single reset day.      When

### Community 112 - "Community 112"
Cohesion: 0.22
Nodes (9): get_metrics_text(), get_uptime(), Prometheus metrics exporter for MikroTik Bot.  Provides a simple HTTP endpoint, Record a message of given type., Record a MikroTik API request with its duration., Get bot uptime in seconds., Generate Prometheus metrics in text format., record_message_type() (+1 more)

### Community 113 - "Community 113"
Cohesion: 0.20
Nodes (7): _get_local_ips(), NetworkProbe, Protocol, Network probe abstractions for router discovery.  This module provides pluggab, A discovery strategy that yields IP candidates or full router metadata.      I, Return a set of local IPv4 addresses for self-echo filtering.      When we bro, Single-socket send+listen cycle (runs in executor thread).

### Community 114 - "Community 114"
Cohesion: 0.33
Nodes (3): merge_probe_results(), Merge candidate dicts from the three probes into a deduplicated list of routers., TestMergeProbeResults

### Community 115 - "Community 115"
Cohesion: 0.29
Nodes (4): _make_context(), Integration-style tests for the Hotspot host search flow.  Tests the search th, TestHotspotSearchQuery, TestHotspotSearchStart

### Community 116 - "Community 116"
Cohesion: 0.33
Nodes (3): TestFormatBytes, format_bytes(), Format a byte count into a human-readable string with appropriate units.      Re

### Community 117 - "Community 117"
Cohesion: 0.25
Nodes (9): _internal_pdf_settings_menu(), pdf_settings_menu(), get_pdf_settings_keyboard(), Return the PDF settings main categories keyboard., _is_benign_edit_error(), Exception, Edit the callback message in place; fall back to a new message if edit fails., تحديد أخطاء تعديل الرسائل الحميدة التي يجب تجاهلها بصمت. (+1 more)

### Community 118 - "Community 118"
Cohesion: 0.36
Nodes (8): metrics_command(), _get_text(), Tests for the /metrics diagnostic command handler., Bypass the 1-second per-user rate limit between tests., _reset_rate_limit(), test_metrics_command_continues_on_delete_failure(), test_metrics_command_sends_report_and_deletes(), test_metrics_command_with_zero_attempts()

### Community 119 - "Community 119"
Cohesion: 0.28
Nodes (9): _categories_kwargs(), hotspot_stats(), hotspot_stats_day_input(), DEFAULT_TYPE, Update, Handle a day number typed by the user and show that day's reset list., Show hotspot statistics summary and ask for the reset day as text input., _reset_block_text() (+1 more)

### Community 120 - "Community 120"
Cohesion: 0.28
Nodes (8): MikrotikBotError, Exception, Custom exception hierarchy for MikroTik Bot.  يتيح هذا الملف التمييز بين أنواع ا, الصنف الأساسي لكل أخطاء البوت المخصصة., فشل الاتصال بالراوتر (شبكة، timeout، رفض اتصال)., نجح الاتصال لكن الأمر فشل (unknown parameter، no such command، إلخ)., RouterCommandError, RouterConnectionError

### Community 121 - "Community 121"
Cohesion: 0.33
Nodes (3): _query_update(), TestBackupFull, TestBackupUserman

### Community 124 - "Community 124"
Cohesion: 0.36
Nodes (3): TestFormatUserList, format_user_list(), Format a list of user dicts into a numbered Arabic display string.

### Community 125 - "Community 125"
Cohesion: 0.25
Nodes (4): Search hotspot hosts by IP or MAC address with enriched host names from DHCP lea, Remove a hotspot host by MAC or IP address., Kick an active hotspot user and remove all matching host entries., Fetch DHCP leases and return a dict keyed by lower-case MAC address.

### Community 126 - "Community 126"
Cohesion: 0.39
Nodes (3): ARPTableProbe, Reads the OS ARP table to discover IP/MAC pairs on the local network.      Syn, TestARPTableProbe

### Community 127 - "Community 127"
Cohesion: 0.32
Nodes (4): get_yesterday_snapshot(), Repository for daily stats snapshots — تاريخ إحصائيات الروترات., استرداد snapshot أمس للراوتر المحدد. يُعيد None إن لم يوجد., TestGetYesterdaySnapshot

### Community 128 - "Community 128"
Cohesion: 0.46
Nodes (3): CardGenerator, _sample_card(), TestCardGenerator

### Community 131 - "Community 131"
Cohesion: 0.43
Nodes (6): build_csv(), Build a UTF-8-sig CSV string from a usage report's rows., _fake_users(), Tests for Hotspot usage report building and CSV export., test_build_csv_header_and_rows(), test_build_usage_report_classifies_users()

### Community 132 - "Community 132"
Cohesion: 0.57
Nodes (5): get_ftp_port(), download_files_via_ftp(), get_router_ftp_info(), upload_file_via_ftp(), _warn_plaintext_ftp()

### Community 133 - "Community 133"
Cohesion: 0.38
Nodes (4): الراوتر غير موجود في قاعدة البيانات أو المفتاح غير صالح., RouterNotFoundError, TestConnectionPoolInit, TestRouterInfo

### Community 135 - "Community 135"
Cohesion: 0.38
Nodes (6): audit_files(), classify_site(), main(), Path, Audit tool: list all logger.exception sites in handler files.  Run from project, Inspect the body of an except block to classify it.

### Community 136 - "Community 136"
Cohesion: 0.38
Nodes (6): build_zip(), Path, Snapshot the project to a zip file in _releases/v1.1-quality/.  Excludes: - .env, Return True if path should be excluded from the zip., Create the snapshot zip. Returns number of files added., should_exclude()

### Community 138 - "Community 138"
Cohesion: 0.33
Nodes (6): error_handler(), Global error handler — filters non-critical Telegram errors., clear_action(), Clear the current action for a user while preserving selected router., Send a message and track it for cleanup — unified helper., send_and_track()

### Community 139 - "Community 139"
Cohesion: 0.33
Nodes (5): Manual retry of set_bot_commands — useful if menu didn't load at startup., sync_commands(), Application, Set bot commands menu for both private chats and groups — retries 3 times., set_bot_commands()

### Community 140 - "Community 140"
Cohesion: 0.47
Nodes (3): get_user_routers(), Return the list of routers this user is allowed to manage.      - للـ Super Ad, TestGetUserRouters

### Community 141 - "Community 141"
Cohesion: 0.47
Nodes (4): _make_query(), Handler tests for card batch listing and PDF regeneration., test_batch_regen_missing_batch_prompts(), test_batch_regen_sends_pdf()

### Community 142 - "Community 142"
Cohesion: 0.53
Nodes (5): _make_query(), Handler tests for Hotspot usage report export., _report(), test_report_export_csv_sends_document(), test_report_export_csv_without_report_prompts()

### Community 143 - "Community 143"
Cohesion: 0.40
Nodes (4): Run migrations in 'offline' mode.      This configures the context with just a U, Run migrations in 'online' mode.      In this scenario we need to create an Engi, run_migrations_offline(), run_migrations_online()

### Community 144 - "Community 144"
Cohesion: 0.40
Nodes (5): go_back(), Resolve a navigation target by name, with lazy imports., _resolve_nav_target(), nav_get(), Return the current navigation back target, defaulting to main_menu.

### Community 145 - "Community 145"
Cohesion: 0.40
Nodes (4): ConversationHandler state constants grouped by feature domain.      All values, WaitingState, Enum, IntEnum

### Community 150 - "Community 150"
Cohesion: 0.50
Nodes (4): init_db(), Shared fixtures for database/repository tests.  Provides ``temp_db`` with an e, Replace DB_PATH with a temp file and init tables before each test., temp_db()

### Community 152 - "Community 152"
Cohesion: 0.40
Nodes (3): _json_serializer(), JsonFormatter, Formatter that outputs structured JSON logs for ELK/Loki/Grafana.

### Community 157 - "Community 157"
Cohesion: 0.50
Nodes (4): Register an already-sent message for future cleanup via /clean., تتبع رسالة للتنظيف التلقائي عبر قاعدة البيانات.      لا يُتتبَّع إلا رسائل الب, track_message(), _track_msg()

### Community 158 - "Community 158"
Cohesion: 0.67
Nodes (3): _get_user_id(), Update, أعد معرّف المستخدم أو None إن غاب ``effective_user`` (تجنّب الدورة الاستيرادية).

## Knowledge Gaps
- **1 isolated node(s):** `files`
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MikrotikAPI` connect `Community 71` to `Community 129`, `Community 98`, `Community 134`, `Community 70`, `Community 72`, `Community 41`, `Community 45`, `Community 147`, `Community 52`, `Community 122`, `Community 59`, `Community 156`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `CardData` connect `Community 14` to `Community 128`, `Community 65`, `Community 34`, `Community 1`, `Community 102`, `Community 8`, `Community 44`, `Community 45`, `Community 110`, `Community 80`, `Community 82`, `Community 51`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `run_blocking()` connect `Community 39` to `Community 0`, `Community 2`, `Community 8`, `Community 11`, `Community 17`, `Community 18`, `Community 19`, `Community 20`, `Community 22`, `Community 23`, `Community 25`, `Community 29`, `Community 30`, `Community 33`, `Community 36`, `Community 37`, `Community 43`, `Community 46`, `Community 47`, `Community 53`, `Community 54`, `Community 55`, `Community 109`, `Community 118`, `Community 119`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `get_db()` (e.g. with `.test_returns_snapshots_ordered_asc()` and `.test_returns_yesterday_row()`) actually correct?**
  _`get_db()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `files` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.08557692307692308 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.07322068612391193 - nodes in this community are weakly interconnected._