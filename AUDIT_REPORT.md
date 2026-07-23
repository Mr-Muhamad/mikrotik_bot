# Comprehensive Audit Report: MikroTik Telegram Admin Bot

**Date:** 2024 (Audit performed by AI code reviewer)
**Scope:** Full codebase analysis — architecture, security, reliability, performance, test coverage
**Project Root:** `D:\New Projects 21-5\Mikrotik admin bot telegram\mikrotik_bot`

---

## Table of Contents

1. [Project Identity](#1-project-identity)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Module Map](#4-module-map)
5. [User Flow Catalog](#5-user-flow-catalog)
6. [Security Analysis](#6-security-analysis)
7. [Performance & Concurrency Analysis](#7-performance--concurrency-analysis)
8. [Failure Modes & Error Handling](#8-failure-modes--error-handling)
9. [Test Coverage Assessment](#9-test-coverage-assessment)
10. [Findings Summary (Severity-Ranked)](#10-findings-summary-severity-ranked)
11. [Recommendations](#11-recommendations)

---

## 1. Project Identity

**Purpose:** Telegram Bot for remote administration of MikroTik RouterOS devices via the RouterOS API (librouteros). Targets ISP operators and network administrators managing Hotspot-based internet services.

**Key Capabilities:**
- Router discovery (MNDP, ARP, Port Scan) and manual add
- Hotspot user CRUD (add/edit/delete/search/kick/block)
- Hotspot card generation (batch create + PDF/QR export)
- User Manager integration (v6 and v7 path detection)
- Backup/restore (scheduled + manual, system + UserManager)
- Router health monitoring (watchdog with CPU/memory alerts)
- Multi-role RBAC (super_admin → viewer)
- Audit logging, PDF customization, connection pooling

**Language:** Python 3.12+
**Primary Framework:** `python-telegram-bot` v21+ (async, `ConversationHandler`)

---

## 2. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Bot Framework | `python-telegram-bot[job-queue]` ≥21.0 | Telegram Bot API, ConversationHandler, JobQueue |
| Router API | `librouteros` ≥3.3.0 | MikroTik RouterOS API (plaintext port 8728) |
| Database | SQLite via `sqlalchemy` ≥2.0 + `alembic` ≥1.13 | Persistent storage, migrations |
| Encryption | `cryptography` (Fernet) ≥41.0 | Password encryption at rest |
| PDF | `reportlab` ≥4.0, `qrcode[pil]` ≥7.0, `Pillow` ≥10.0 | Card PDF generation |
| Arabic Text | `arabic-reshaper` ≥3.0, `python-bidi` ≥0.4 | RTL text rendering in PDF |
| System Monitor | `psutil` ≥5.9 | Server CPU/RAM metrics |
| Config | `python-dotenv` ≥1.0 | `.env` file loading |
| Testing | `pytest` ≥7.0, `pytest-asyncio` ≥0.23 | Unit/integration tests |
| Linting | `ruff` ≥0.3 | Static analysis |

---

## 3. Architecture Overview

### 3.1 Layered Architecture

```
┌─────────────────────────────────────────────────┐
│  Telegram Interface (bot/handlers/*)             │
│  - ConversationHandler (main CH, 28+ states)     │
│  - Standalone CommandHandlers                     │
│  - Separate ConversationHandlers (rename, manual) │
│  - callback_constants.py (centralized tokens)     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Core Business Logic (core/*)                     │
│  - MikrotikAPI facade (rate limit, retry, cache)  │
│  - ConnectionPool (thread-safe queues per router)  │
│  - HotspotManager (CRUD, cards, blocking, expiry) │
│  - BackupService / BackupScheduler                │
│  - Watchdog (health checks, state machine)         │
│  - NetworkScanner (MNDP/ARP/Port Scan)            │
│  - StatsManager                                   │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Data Layer (database/*)                          │
│  - SQLite with WAL mode + busy_timeout=5000       │
│  - Alembic migrations                             │
│  - Repository pattern (admin_roles, routers, etc) │
│  - get_db() context manager (commit/rollback)     │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│  Utilities (utils/*)                              │
│  - admin_decorator (@admin_only, @require_role)   │
│  - callback_utils (dedup, safe_answer)            │
│  - error_response (classify, sanitize, format)    │
│  - crypto (Fernet encrypt/decrypt singleton)      │
│  - validators (IP, port, username, password, MAC) │
│  - handler_registry (decorator-based registration)│
│  - chat_cleaner (message tracking + GC)           │
└─────────────────────────────────────────────────┘
```

### 3.2 Startup Flow (`main.py`)

1. Suppress noisy library loggers (httpx, httpcore, apscheduler, PIL, librouteros, chat_cleaner)
2. `configure_logging(logging.INFO)` — structured logging with file + console handlers
3. `single_instance(force=...)` — prevent concurrent bot instances via file lock
4. `init_db()` — Alembic migrations → seed admin roles → migrate passwords → add columns
5. Build `Application` with `concurrent_updates(False)` (critical for ConversationHandler stability)
6. `build_all(application)` — register all handlers in correct order via `bot/registrations.py`
7. Register `atexit` for connection pool cleanup
8. `post_init()` → set bot commands, load watchdog status, restore backup schedule, start watchdog + chat_cleaner GC
9. `asyncio.run(run_with_shutdown())` — graceful shutdown via SIGTERM/SIGINT

### 3.3 Handler Registration Order (`bot/registrations.py`)

Registration is layered to ensure correct dispatch precedence:

1. **Common handlers** (standalone): `/start`, `/help`, `/clean`, `/metrics`, `/sync`
2. **Hotspot handlers** (standalone): `/add`, `/edit`, `/delete`, `/search`, `/cards`
3. **Admin handlers** (standalone): `/userman`, `/backup`, `/settings`, `/reboot`, `/timeout`, `/logs`, `/usage`, `/watchdog*`, `/addrouter`, `/routers`
4. **Separate ConversationHandlers**: `rename`, `manual_add` (must precede standalone `/cancel`)
5. **Standalone `/cancel`** CommandHandler
6. **Main ConversationHandler** (MUST be last — its `state=None` catch-all would swallow all commands if placed earlier)

**Regression Test:** `tests/test_registration_order.py` guards against ordering bugs.

### 3.4 State Machine (`bot/handlers/states.py`)

`WaitingState` IntEnum with 28+ states across 0–53 range:

| Range | Domain |
|-------|--------|
| 0–14 | Base states (input, username, password, profile, bytes, comment, edit, delete, search, cards, PDF, discovery, schedule) |
| 15–18 | Extended single states (card type, card profile, delete select, rename) |
| 19–20 | Hotspot add uptime sub-flow |
| 21–27 | Hotspot card creation sub-flow |
| 34 | Usage query |
| 35–40 | Manual router add flow |
| 41–42 | Stats day, card payment |
| 50–51 | User Manager card MAC binding, prefix |
| 52 | User Manager search |
| 53 | WiFi card share recipient |

---

## 4. Module Map

### 4.1 Entry Point

| File | Lines | Purpose |
|------|-------|---------|
| `main.py` | 127 | Application lifecycle: init, polling, graceful shutdown |

### 4.2 Configuration

| File | Lines | Purpose |
|------|-------|---------|
| `config.py` | 58 | `.env` loading, Fernet key validation, constants (DEFAULT_API_PORT=8728, WATCHDOG_INTERVAL=300) |

### 4.3 Bot Layer (`bot/`)

| File | Lines | Purpose |
|------|-------|---------|
| `registrations.py` | ~300 | Central handler registration — 3 layers + separate CHs + main CH |
| `handlers/common.py` | ~200 | `/start`, `/help`, `/clean`, `/metrics`, `/sync` |
| `handlers/hotspot_add.py` | ~250 | Multi-step add user flow (username → password → profile → uptime → bytes → comment) |
| `handlers/hotspot_edit.py` | ~200 | Edit user fields (name, password, profile, limit-bytes, limit-uptime) |
| `handlers/hotspot_delete.py` | ~150 | Delete user with confirmation |
| `handlers/hotspot_search.py` | ~300 | Search users/hosts, kick active, block MAC |
| `handlers/hotspot_cards.py` | ~250 | Batch card creation + PDF generation |
| `handlers/backup.py` | ~250 | Manual backup (full/userman), schedule management, download |
| `handlers/userman.py` | ~200 | User Manager cards/list/profiles |
| `handlers/watchdog.py` | ~200 | Health dashboard, manual check, start/stop monitoring |
| `handlers/settings.py` | ~150 | PDF settings (brand, DNS, margins, QR, etc.) |
| `handlers/states.py` | 73 | `WaitingState` IntEnum (28+ states) |
| `handlers/callback_constants.py` | ~150 | Centralized `CALLBACKS` dict + `PATTERNS` for regex matching |
| `handlers/router_flows/discovery.py` | ~200 | MNDP-based auto-discovery |
| `handlers/router_flows/manual_add.py` | ~300 | Manual add with IP/port/user/pass/alias + multi-strategy discovery |
| `keyboards.py` | ~200 | InlineKeyboard builders |
| `messages.py` | ~100 | Arabic message templates |
| `router_selector.py` | ~100 | Per-user router selection state |

### 4.4 Core Layer (`core/`)

| File | Lines | Purpose |
|------|-------|---------|
| `mikrotik_api.py` | 395 | **Facade** — `execute()`, `execute_long()`, `execute_non_blocking()`, rate limiting (100ms), retry logic, version detection, SSL probe |
| `connection_pool.py` | 263 | Thread-safe queues per router, max 3 connections, reconnect, metrics |
| `hotspot_manager.py` | 484 | CRUD + cards + blocking + expiry + stats (delegates to sub-modules) |
| `backup_service.py` | ~150 | Compatibility shim over `backup/system.py` + `backup/userman.py` |
| `backup/system.py` | ~200 | `system/backup/save` + `export` + FTP download |
| `backup/userman.py` | ~150 | User Manager export + FTP upload |
| `backup/restore.py` | ~100 | Import .backup files |
| `backup/files.py` | ~150 | Path safety, tar creation, cleanup |
| `backup/ftp.py` | ~100 | FTP upload/download (plaintext warning) |
| `backup_scheduler.py` | 274 | Daily scheduled backup + expiry check + stats snapshot |
| `watchdog.py` | 214 | Health checks, CPU/memory thresholds, state machine (online→offline→recovered) |
| `stats.py` | ~200 | Hotspot + UserManager statistics aggregation |
| `network_scanner.py` | ~200 | Multi-strategy discovery: MNDP + ARP + Port Scan |
| `hotspot_search.py` | ~150 | Host search + DHCP lease enrichment + kick |
| `hotspot_blocking.py` | ~100 | MAC block/unblock via address-list |
| `hotspot_expiry.py` | ~100 | Expiring user detection |
| `hotspot_stats.py` | ~200 | Hotspot statistics with reset-day filtering |
| `cache.py` | ~80 | Generic `TTLCache` (in-memory, dict-based) |
| `profile_cache.py` | ~60 | Profile name TTL cache |

### 4.5 Data Layer (`database/`)

| File | Lines | Purpose |
|------|-------|---------|
| `models.py` | 363 | **Re-export shim** — `get_db()`, `init_db()`, migrations, `__all__` exports from repositories |
| `repositories/admin_roles.py` | ~80 | CRUD for admin_roles table |
| `repositories/routers.py` | ~120 | CRUD for discovered_routers table |
| `repositories/backups.py` | ~100 | backup_jobs + backup_settings |
| `repositories/audit_logs.py` | ~100 | logs table + cleanup |
| `repositories/card_batches.py` | ~100 | card_batches table + sales summary |
| `repositories/user_sessions.py` | ~60 | user_sessions table + activity tracking |
| `repositories/pdf_settings.py` | ~60 | pdf_settings table (whitelist-based updates) |
| `repositories/router_health.py` | ~80 | router_health_log table |
| `repositories/stats_snapshots.py` | ~60 | stats_snapshots table |
| `repositories/chat_messages.py` | ~60 | tracked_messages table |
| `repositories/operator_permissions.py` | ~40 | operator_permissions table |

### 4.6 Utilities (`utils/`)

| File | Lines | Purpose |
|------|-------|---------|
| `admin_decorator.py` | 186 | `@admin_only` (RBAC + rate limit + group chat block), `@require_role(min_role)` |
| `callback_utils.py` | 65 | `is_duplicate_callback()` (1s window), `safe_answer_callback()` |
| `error_response.py` | 239 | Error classification (6 categories), sanitization (secret patterns), `send_error()`, `send_text()` |
| `crypto.py` | 68 | Fernet singleton, `encrypt_password/decrypt_password`, `encrypt_data/decrypt_data` |
| `validators.py` | 91 | `validate_ip`, `validate_port`, `validate_username`, `validate_password`, `validate_mac` |
| `handler_registry.py` | ~200 | Decorator-based ConversationHandler building |
| `bot_commands.py` | ~40 | `/command` list for Telegram menu |
| `chat_cleaner.py` | ~100 | Message tracking + periodic GC |
| `logging_setup.py` | ~80 | Structured logging with request_id |
| `singleton_lock.py` | ~40 | File-based single instance lock |
| `formatters.py` | ~80 | `parse_bytes`, `format_bytes` |

### 4.7 Tests (`tests/`)

| Directory | Files | Coverage |
|-----------|-------|----------|
| `tests/core/` | 14 files | MikrotikAPI, ConnectionPool, HotspotManager, Watchdog, Backup, Stats, NetworkScanner |
| `tests/database/` | 6 files | models, repositories, card_batches, operator_permissions |
| `tests/bot/` | ~5 files | handlers, keyboards |
| `tests/utils/` | 11 files | crypto, validators, formatters, admin_decorator, callback_utils, error_response |
| `tests/test_*.py` | 6 files | validators, crypto, formatters, registration_order |

**Total test files:** ~42

---

## 5. User Flow Catalog

### 5.1 Router Discovery Flow

```
/routers → [inline keyboard: discover/manual/list]
  ├─ [discover] → WAITING_FOR_DISCOVERY_CHOICE (MNDP/ARP/Scan)
  │   ├─ [mndp] → _do_discovery → show results → [add] → test_connection → save → /start
  │   ├─ [arp] → _do_discovery → show results → [add] → test_connection → save → /start
  │   └─ [scan] → DISC_USERNAME → DISC_PASSWORD → _do_discovery → show results
  └─ [manual] → MANUAL_IP → MANUAL_PORT → MANUAL_USER → MANUAL_PASS → MANUAL_ALIAS → test → save
```

**Key safety:** `test_connection()` performs socket reachability check (2s) before full API authentication.

### 5.2 Hotspot User Add Flow

```
/add → INPUT (username or prefix) → USERNAME → PASSWORD → PROFILE → UPTIME_TYPE → UPTIME_VALUE → BYTES_TOTAL → COMMENT → execute add → success message
```

**With prefix:** generates random usernames; validates uniqueness via API-side `?name=` filter.

### 5.3 Hotspot Card Creation Flow

```
/cards → HOTSPOT_CARD_COUNT → HOTSPOT_CARD_LENGTH → HOTSPOT_CARD_PREFIX → HOTSPOT_CARD_TYPE (same/different) → HOTSPOT_CARD_PROFILE → HOTSPOT_CARD_UPTIME → HOTSPOT_CARD_BYTES → batch create (chunked 50) → PDF generation → send document
```

**Chunked batch insertion:** Cards created in chunks of 50 to avoid API timeout on large batches.

### 5.4 Backup Flow

```
/backup → [manual/schedule/download]
  ├─ [manual] → [full/userman] → execute backup → save to DB → send file
  ├─ [schedule] → SCHEDULE_TIME → save config → start/stop daily job
  └─ [download] → show recent backups → [select] → send file
```

**Scheduled backup:** `BackupScheduler` runs at configured time daily with:
1. Health check per router (skip unhealthy)
2. UserManager backup
3. Full system backup (if `SCHEDULE_FULL_BACKUP=true`)
4. Admin notification on failure
5. Expiry check (5 min after backup)
6. Stats snapshot (10 min after backup)

### 5.5 Router Rename Flow

Separate `ConversationHandler` (not main CH):
```
/routers → [rename] → SELECT_ROUTER → RENAME_INPUT → confirm → update DB + invalidate name cache
```

### 5.6 Reboot Flow

```
/reboot → [confirm button] → execute `system/reboot` → handle connection loss → success message
```

**Safety:** `is_duplicate_callback()` prevents double-reboot. Rate limit: 10s between reboots.

---

## 6. Security Analysis

### 6.1 Authentication & Authorization

| Mechanism | Implementation | Assessment |
|-----------|---------------|------------|
| Bot access | `ADMIN_IDS` from `.env` + `admin_roles` table in DB | **Strong** — dual-layer (env + DB) |
| Role-based access | `@admin_only` decorator (checks `ADMIN_IDS` then `get_admin_role()`) | **Strong** — 5 tiers (super_admin=40 → viewer=10) |
| Group chat blocking | `_is_group_chat()` rejects non-private chats | **Strong** — prevents accidental exposure |
| Rate limiting | Per-user, per-function (reboot=10s, backup=30s, restore=60s, delete=5s, add/edit=2s, default=1s) | **Strong** — with periodic cleanup |
| Callback dedup | 1s window per `user_id:callback_data` | **Good** — prevents double-action |

### 6.2 Data Protection

| Mechanism | Implementation | Assessment |
|-----------|---------------|------------|
| Password encryption | Fernet symmetric encryption via `cryptography` | **Strong** — validated at startup |
| Key validation | `config.py` validates Fernet format + min 32 chars at import time | **Strong** — fails fast |
| Password masking in logs | `_debug_log()` replaces password fields with `***` | **Good** |
| Error sanitization | `_sanitize_error_text()` hides password/secret/token patterns | **Good** |
| Error sanitization (connect) | `_sanitize_connect_detail()` strips credential patterns | **Good** |
| Decryption failure | `decrypt_password()` returns `""` (never returns ciphertext) | **Good** |
| DB password migration | `migrate_passwords()` encrypts plaintext on startup (checks `gAAAAA` prefix) | **Good** |

### 6.3 Input Validation

| Validator | Location | Assessment |
|-----------|----------|------------|
| `validate_ip()` | `utils/validators.py:18` | Uses `ipaddress.ip_address()` — handles IPv4+IPv6 |
| `validate_port()` | `utils/validators.py:29` | Range check 1–65535 |
| `validate_username()` | `utils/validators.py:42` | Length 3–64, alphanumeric + `_-:.` |
| `validate_password()` | `utils/validators.py:53` | Length 4–64, rejects `\n\r\t` |
| `validate_mac()` | `utils/validators.py:75` | Regex-based, normalizes to `AA:BB:CC:DD:EE:FF` |
| SQL injection | `database/models.py:59-68` | `_VALID_IDENTIFIER_RE` whitelist for table/column names in migrations |

### 6.4 Network Security Concerns

| Issue | Severity | Detail |
|-------|----------|--------|
| **API port 8728 is plaintext** | **HIGH** | RouterOS API on port 8728 transmits credentials in cleartext. Bot documents this requires isolated management network. |
| **FTP backup is plaintext** | **HIGH** | `backup/ftp.py` uses port 21 (no SFTP/FTPS). Transmits router passwords when downloading backups. `config.SCHEDULE_FULL_BACKUP` defaults to `false` with explicit warning. |
| **SSL probe is diagnostic only** | **INFO** | `_probe_api_ssl()` checks port 8729 for informational purposes but doesn't enforce SSL. |

### 6.5 Security Recommendations

1. **CRITICAL:** Document that the bot MUST run in an isolated management network (VLAN) with firewall rules blocking API port access from untrusted networks.
2. **HIGH:** Consider adding optional API-SSL support (port 8729) with certificate verification.
3. **HIGH:** Replace FTP with SFTP for backup file transfer.
4. **MEDIUM:** Add `ENCRYPTION_KEY` rotation support.
5. **MEDIUM:** Add audit trail for all connection attempts (successful + failed).

---

## 7. Performance & Concurrency Analysis

### 7.1 Connection Pool (`core/connection_pool.py`)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `MAX_CONNECTIONS_PER_ROUTER` | 3 | Prevents connection flooding; queue-based wait with 30s timeout |
| `CONNECT_TIMEOUT` | 10s | For establishing new connections |
| `API_TIMEOUT` | 30s | Standard commands |
| `LONG_TIMEOUT` | 120s | Backup, large user lists (1000+ users) |
| `MAX_RETRIES` | 2 | 3 total attempts per operation |
| `RETRY_DELAY` | 1s between retries | |

**Assessment:** Well-designed. The `queue.Queue(maxsize=3)` pattern with thread-safe `active_counts` tracking prevents connection leaks. The `release_connection()` method properly handles both healthy return (back to queue) and broken connection (close + decrement count).

**Concern:** `get_connection()` blocks with `q.get(timeout=30)` when pool is exhausted. Under heavy load (many concurrent Telegram users hitting the same router), this could cause user-visible latency.

### 7.2 Rate Limiting

| Layer | Mechanism | Value |
|-------|-----------|-------|
| API-level | `_throttle()` in `mikrotik_api.py` | 100ms between commands per router |
| User-level | `@admin_only` decorator | 1s default, up to 60s for restore |
| Callback-level | `is_duplicate_callback()` | 1s window |

**Assessment:** Three-layer rate limiting is appropriate. The API-level throttle prevents overwhelming the RouterOS API. The user-level rate limit prevents abuse. The callback dedup prevents accidental double-actions.

**Concern:** The `_throttle()` uses `time.sleep()` which blocks the thread. In a high-concurrency scenario, this could thread-starve the event loop. However, `concurrent_updates(False)` mitigates this by serializing updates.

### 7.3 Caching

| Cache | TTL | Max Size | Purpose |
|-------|-----|----------|---------|
| `router_versions` | 24 hours | 50 | Version detection (v6/v7 path selection) |
| `router_names` | 24 hours | 50 | Router display names |
| `_users_cache` (HotspotManager) | 5 seconds | 20 | User list for duplicate checking |
| `_profiles_cache` (HotspotManager) | 10 seconds | 20 | Profile list |

**Assessment:** Short TTLs (5s/10s) for hotspot data prevent stale reads. Long TTLs (24h) for version/names are appropriate since these change rarely. The `TTLCache` in `core/cache.py` is simple dict-based — adequate for the expected scale (<50 routers).

### 7.4 Threading Model

- **Event loop:** Single asyncio event loop (python-telegram-bot default)
- **Blocking operations:** `run_blocking()` wraps sync MikroTik API calls for async context
- **Connection pool:** `threading.RLock` for pool state, `queue.Queue` for connection management
- **Watchdog:** `threading.Lock` for `_router_status` state machine
- **Rate limiting:** `threading.Lock` for `_rate_limit_data`
- **Backup locks:** Per-router `threading.RLock` (`_BACKUP_LOCKS`)

**Assessment:** The threading model is appropriate for the use case. The `concurrent_updates(False)` setting is critical — it serializes all Telegram updates through the main ConversationHandler, preventing state corruption. The use of `run_blocking()` for sync MikroTik API calls in async handlers is the correct pattern.

### 7.5 Performance Recommendations

1. **MEDIUM:** Consider adding connection pool metrics to `/metrics` command output (already partially implemented via `get_metrics()`).
2. **LOW:** The `TTLCache` could be replaced with `cachetools.TTLCache` for better thread safety, though the current implementation works because it's protected by `threading.Lock`.
3. **LOW:** Consider adding request timeout per-handler for slow MikroTik operations (e.g., backup of 1000+ users).

---

## 8. Failure Modes & Error Handling

### 8.1 Error Classification (`utils/error_response.py`)

The system classifies errors into 6 categories with user-friendly Arabic messages:

| Category | Triggers | User Message |
|----------|----------|-------------|
| `connection` | refused, closed, reset, unreachable | "تعذر الاتصال بالروتر..." |
| `auth` | password, login, credentials | "فشل تسجيل الدخول..." |
| `timeout` | timeout, timed out | "لم يستجب الروتر..." |
| `not_found` | not found, no such | "الروتر غير موجود..." |
| `storage` | disk full, nospc | "مساحة التخزين غير كافية..." |
| `general` | anything else | "حدث خطأ غير متوقع..." |

**Benign error suppression:** "Message is not modified", "Message to edit not found", "exactly the same content" are logged at DEBUG level and not shown to users.

### 8.2 Connection Failure Recovery

1. **Socket pre-check:** `test_connection()` performs 2s TCP reachability check before full MikroTik authentication
2. **Retry with fresh connection:** `_execute_with_retry()` catches `LibRouterosError`/`ConnectionError`/`OSError`, then retries with `force_reconnect=True`
3. **Non-retryable errors:** `{"unknown parameter", "no such command"}` are raised immediately without retry
4. **Reboot handling:** `system/reboot` command logs connection loss as INFO (expected behavior)
5. **Non-blocking operations:** `execute_non_blocking()` swallows all errors (for fire-and-forget commands)

### 8.3 Backup Failure Recovery

1. **Health check before backup:** `_do_backup()` checks `check_connection_health()` before each router
2. **Per-router isolation:** Failure on one router doesn't affect others
3. **Admin notification:** Failed routers are reported to all `ADMIN_IDS` via Telegram message
4. **DB recording:** Both success and failure are recorded in `backup_jobs` table
5. **Per-router RLock:** `_BACKUP_LOCKS` prevents concurrent backup operations on the same router

### 8.4 Watchdog State Machine

```
                ┌──────────────┐
                │   UNKNOWN    │
                │  (startup)   │
                └──────┬───────┘
                       │
            ┌──────────▼──────────┐
            │      ONLINE         │◄─────────────────┐
            │  (last_ok set)      │                   │
            └──────────┬──────────┘                   │
                       │ health check fails            │
            ┌──────────▼──────────┐       recovered   │
            │     OFFLINE         │───────────────────┘
            │  (last_fail set)    │
            │  (alert_sent=True)  │
            └─────────────────────┘
```

**State transitions:**
- `record_check_result()`: Returns `ALERT_WENT_OFFLINE` on first failure, `ALERT_RECOVERED` on recovery
- **Alert dedup:** `alert_sent` flag ensures only one alert per outage
- **DB persistence:** `load_status_from_db()` restores state on restart

### 8.5 Failure Mode Recommendations

1. **HIGH:** The watchdog's ISP ping check (`socket.create_connection(("8.8.8.8", 53))`) only checks if DNS port is reachable — it doesn't actually verify DNS resolution. Consider using `socket.getaddrinfo()` or a real DNS query.
2. **MEDIUM:** Add exponential backoff for repeated connection failures to the same router.
3. **MEDIUM:** The `_do_backup()` method catches `full_result.get("success")` but the full backup is always attempted even if userman backup fails. Consider making full backup conditional on userman success.
4. **LOW:** Add circuit breaker pattern for routers that consistently fail connection health checks.

---

## 9. Test Coverage Assessment

### 9.1 Test Infrastructure

- **Framework:** pytest + pytest-asyncio
- **DB isolation:** Autouse `temp_db` fixture patches `DB_PATH` to temp directory
- **API mocking:** `MikrotikAPIMock` singleton for MikroTik API responses
- **Config:** `pyproject.toml` configured with `asyncio_mode = "auto"`

### 9.2 Test Categories

| Category | Files | Coverage |
|----------|-------|----------|
| Core (MikrotikAPI) | `tests/core/test_mikrotik_api.py` | Retry logic, rate limiting, version detection, error classification |
| Core (ConnectionPool) | `tests/core/test_connection_pool.py` | Pool creation, max connections, reconnect, metrics |
| Core (HotspotManager) | `tests/core/test_hotspot_manager.py` | CRUD, search, cards, blocking, expiry |
| Core (Watchdog) | `tests/core/test_watchdog.py` | Health checks, state transitions, alerts |
| Core (Backup) | `tests/core/test_backup*.py` | Full backup, userman backup, FTP, restore |
| Core (Stats) | `tests/core/test_stats.py` | Hotspot stats, UserManager stats |
| Core (NetworkScanner) | `tests/core/test_network_scanner.py` | MNDP, ARP, port scan |
| Database | `tests/database/test_*.py` | Models, repositories, card_batches, operator_permissions |
| Utils | `tests/utils/test_*.py` | Crypto, validators, formatters, admin_decorator, callback_utils, error_response |
| Regression | `tests/test_registration_order.py` | Handler registration order, standalone vs ConversationHandler precedence |

### 9.3 Test Quality Indicators

**Strengths:**
- Registration order regression tests prevent handler dispatch bugs
- Temp DB isolation prevents test pollution
- Mock API allows testing without real MikroTik devices
- Coverage of critical paths (retry logic, error classification, state machine)

**Gaps:**
- No integration tests with real Telegram bot API (expected — requires bot token)
- No load/concurrency tests for connection pool under stress
- Limited testing of PDF generation (reportlab-specific)
- No tests for `chat_cleaner.py` message tracking/GC
- No tests for `singleton_lock.py`

### 9.4 Quality Gates (from AGENTS.md)

| Gate | Command | Target |
|------|---------|--------|
| Pyright (strict) | `pyright` | 0 errors |
| Ruff | `ruff check .` | 0 errors |
| Black | `black .` | Formatted |
| Pytest | `pytest -q` | 100% pass |
| Handler validation | `scripts/validate_handlers.py` | Pass |

---

## 10. Findings Summary (Severity-Ranked)

### CRITICAL

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| C1 | **API port 8728 transmits credentials in cleartext** | `core/connection_pool.py:68` (connect call), `config.py:42` (DEFAULT_API_PORT) | MitM can intercept router credentials. Requires isolated management network. |
| C2 | **FTP backup uses plaintext (port 21)** | `core/backup/ftp.py` | Transmits router backup (including config with passwords) over unencrypted channel. |

### HIGH

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| H1 | **No input sanitization on router API responses displayed to users** | `error_response.py:132` (truncation only) | Router responses could contain crafted data shown to users. Low risk since router admin controls the device. |
| H2 | **Watchdog ISP check is simplistic** | `watchdog.py:68-74` (`socket.create_connection(("8.8.8.8", 53))`) | Only checks TCP connectivity to port 53, not actual DNS resolution. Could report false positives for ISP status. |
| H3 | **`_MIN_INTERVAL = 0.1s` rate limit is per-router, not per-connection** | `mikrotik_api.py:18` | Under concurrent load, multiple threads could queue up and cause latency spikes for a single router. |

### MEDIUM

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| M1 | **No exponential backoff for repeated connection failures** | `connection_pool.py:78-100` (`_connect_with_retry`) | Fixed 1s delay between retries. A router under heavy load gets hammered with reconnection attempts. |
| M2 | **Full backup always attempted even if userman backup fails** | `backup_scheduler.py:79` | Wastes resources and produces misleading "full backup ok" results when userman is already broken. |
| M3 | **`TTLCache` is not fully thread-safe** | `core/cache.py` | The cache itself doesn't use locks — callers must lock externally. Current code does this, but it's fragile. |
| M4 | **No ENCRYPTION_KEY rotation support** | `utils/crypto.py` | Changing the key requires manual re-encryption of all passwords. |
| M5 | **`concurrent_updates(False)` limits throughput** | `main.py:74` | All Telegram updates are serialized. Under heavy load, slow MikroTik operations block all other users. |
| M6 | **No graceful handling of database migration failures** | `database/models.py:193-217` (`init_db`) | Alembic failure would crash the bot at startup without user-friendly error message. |

### LOW

| # | Finding | Location | Impact |
|---|---------|----------|--------|
| L1 | **No tests for `chat_cleaner.py`** | `utils/chat_cleaner.py` | Message tracking/GC logic untested. |
| L2 | **No tests for `singleton_lock.py`** | `utils/singleton_lock.py` | Single-instance enforcement untested. |
| L3 | **No load/concurrency tests for connection pool** | `tests/core/test_connection_pool.py` | Pool behavior under stress is unverified. |
| L4 | **`test_connection()` has 2s socket timeout — could be too short on slow networks** | `mikrotik_api.py:248` | May falsely report routers as unreachable on high-latency networks. |
| L5 | **PDF generation not tested** | `pdf/` directory | Card rendering and layout logic untested. |

---

## 11. Recommendations

### Priority 1 (Security Hardening)

1. **Add network isolation documentation** — Create a `SECURITY.md` file documenting that the bot MUST run in an isolated management network with firewall rules blocking API port access from untrusted networks.

2. **Replace FTP with SFTP** — Add `paramiko` or `pysftp` dependency for encrypted backup file transfer. Deprecate plaintext FTP.

3. **Add ENCRYPTION_KEY rotation** — Implement a migration that re-encrypts all passwords with a new key. Store the key version alongside the encrypted data.

### Priority 2 (Reliability)

4. **Add exponential backoff** — Replace fixed `RETRY_DELAY=1` with exponential backoff (1s → 2s → 4s) for connection retries.

5. **Add circuit breaker** — Track consecutive failures per router. After N failures, stop attempting operations and report the router as degraded.

6. **Make full backup conditional** — Only attempt full system backup if userman backup succeeds.

7. **Improve ISP check** — Use `socket.getaddrinfo()` or a real DNS query to verify DNS resolution, not just TCP connectivity.

### Priority 3 (Code Quality)

8. **Add concurrency tests** — Test connection pool behavior with multiple concurrent users hitting the same router.

9. **Add `chat_cleaner` tests** — Test message tracking and GC logic.

10. **Add PDF generation tests** — Test card rendering with mock data.

11. **Consider adding SFTP support** — Replace FTP with SFTP for encrypted backup file transfer.

### Priority 4 (Monitoring)

12. **Add connection pool metrics to `/metrics`** — Already partially implemented; ensure all pool stats are exposed.

13. **Add Prometheus/OpenTelemetry integration** — For production monitoring of API latency, error rates, connection pool utilization.

14. **Add structured logging for all MikroTik API calls** — Include router_key, command, duration, success/failure in JSON log format.

---

## Appendix A: Key Configuration Values

| Constant | Value | Location |
|----------|-------|----------|
| `DEFAULT_API_PORT` | 8728 | `config.py:42` |
| `WATCHDOG_INTERVAL` | 300s (5 min) | `config.py:45` |
| `WATCHDOG_FIRST_DELAY` | 1s | `config.py:46` |
| `MAX_CONNECTIONS_PER_ROUTER` | 3 | `connection_pool.py:22` |
| `API_TIMEOUT` | 30s | `connection_pool.py:20` |
| `LONG_TIMEOUT` | 120s | `connection_pool.py:21` |
| `CONNECT_TIMEOUT` | 10s | `connection_pool.py:19` |
| `MAX_RETRIES` | 2 (3 total) | `connection_pool.py:17` |
| `_MIN_INTERVAL` | 0.1s (100ms) | `mikrotik_api.py:18` |
| `_DEDUP_WINDOW` | 1.0s | `callback_utils.py:14` |
| `_DEDUP_CLEANUP_INTERVAL` | 30.0s | `callback_utils.py:16` |
| `_RATE_LIMIT_MAX_AGE` | 3600s | `admin_decorator.py:41` |
| `_RATE_LIMIT_CLEANUP_INTERVAL` | 300.0s | `admin_decorator.py:42` |
| CPU threshold | 90% | `watchdog.py` (implied) |
| Memory threshold | 90% | `watchdog.py` (implied) |
| Card batch chunk size | 50 | `hotspot_manager.py:368` |
| `_CACHE_TTL` | 3600s (1 hour) | `connection_pool.py:25` |
| `router_versions` cache TTL | 86400s (24 hours) | `connection_pool.py:41` |

## Appendix B: Role Hierarchy

| Role | Level | Capabilities |
|------|-------|-------------|
| `super_admin` | 40 | All operations (env-based ADMIN_IDS) |
| `admin` / `customer` | 30 | Most operations, router management |
| `operator` | 20 | Limited operations (per operator_permissions) |
| `viewer` | 10 | Read-only access |

## Appendix C: MikroTik API Command Reference

| Command | Timeout | Used For |
|---------|---------|----------|
| `system/resource/print` | 30s | Health check, version detection |
| `system/identity/print` | 30s | Router name |
| `system/reboot` | 30s | Reboot (connection loss expected) |
| `ip/hotspot/user/print` | 30s | User listing |
| `ip/hotspot/user/add` | 30s | Add user |
| `ip/hotspot/user/set` | 30s | Edit user |
| `ip/hotspot/user/remove` | 30s | Delete user |
| `ip/hotspot/user/enable` | 30s | Enable user |
| `ip/hotspot/user/disable` | 30s | Disable user |
| `ip/hotspot/user/reset-counters` | 30s | Reset traffic counters |
| `ip/hotspot/user/profile/print` | 30s | Profile listing |
| `ip/hotspot/active/print` | 30s | Active sessions |
| `ip/hotspot/host/print` | 30s | Connected hosts |
| `ip/dhcp-server/lease/print` | 30s | DHCP leases (for host enrichment) |
| `tool/user-manager/...` (v6) / `user-manager/...` (v7) | 120s | UserManager operations |
| `system/backup/save` | 120s | System backup |
| `export` | 120s | Configuration export |
| `/certificate/sign` | 30s | SSL certificate operations |

---

*End of Audit Report*
