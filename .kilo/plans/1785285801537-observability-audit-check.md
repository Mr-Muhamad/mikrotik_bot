# Observability & Logging Audit — System Verification Report

## Objective

Verify the existence and integration integrity of the Full Operational Observability & Logging Audit system across the mikrotik_bot codebase, and identify any gaps or integration issues.

---

## ✅ What IS Present and Working

### 1. Request ID Infrastructure (`[req_XXXX]` Correlation)

| Component | File | Status |
|-----------|------|--------|
| `request_id` ContextVar | `utils/request_id.py` | ✅ Present |
| `bind_request_id_from_update` decorator | `utils/request_id.py:21` | ✅ Wraps ALL handlers |
| `request_id_scope` context manager | `utils/request_id.py:40` | ✅ Available for scopes |
| `RequestIdFilter` (injects into every log record) | `utils/logging_setup.py:78` | ✅ On root + all handlers |
| `JsonFormatter` (includes `request_id` in JSON output) | `utils/logging_setup.py:47` | ✅ For file handler |
| `bind_request_id` context manager | `utils/logging_setup.py:68` | ✅ Used by `request_id_scope` |
| `new_request_id()` (UUID-based) | `utils/logging_setup.py:37` | ✅ Available |
| Handler registry wraps every handler | `utils/handler_registry.py:278` | ✅ `bind_request_id_from_update(func)` |
| Error handler also wrapped | `utils/handler_registry.py:345` | ✅ |
| ContextVar propagated to threads | `utils/async_blocking.py:27` | ✅ `contextvars.copy_context()` |

The request_id flows: `update.update_id` → `bind_request_id_from_update` → async handler → core modules (naturally via async context) → thread pool (`run_blocking` copies context) → all log records carry the same `request_id`.

### 2. Incoming Action Logging (`📥 [ACTION INCOMING]`)

| Component | File | Status |
|-----------|------|--------|
| Callback button logging | `utils/admin_decorator.py:124-126` | ✅ |
| Text input logging (truncated to 30 chars) | `utils/admin_decorator.py:132-135` | ✅ |
| Format: `User: <ID> (\<name\>) \| Router: \<key\> \| Button/Input: '\<data\>' \| Handler: \<name\>` | `admin_decorator.py` | ✅ |

### 3. Success & Latency Tracking (`✅ [ACTION SUCCESS]`)

| Component | File | Status |
|-----------|------|--------|
| Success log with elapsed ms | `utils/admin_decorator.py:164-166` | ✅ |
| Failure log with error + elapsed ms + full traceback | `utils/admin_decorator.py:168-173` | ✅ |
| Format: `Time: <ELAPSED>ms` | `admin_decorator.py` | ✅ |

### 4. Audit Logging (`📝 [AUDIT LOG]`)

| Component | File | Status |
|-----------|------|--------|
| `log_action()` function | `database/repositories/audit_logs.py:51-72` | ✅ |
| Logs to both console (📝 prefix) and SQLite `logs` table | `audit_logs.py:54-72` | ✅ |
| Re-exported from `database.models` | `database/models.py:257-334` | ✅ |
| Called from handlers for sensitive operations | 20+ handlers across backup, hotspot, router_flows, roles, usage | ✅ |
| Handlers calling `log_action`: backup, backup_restore, hotspot_add, hotspot_edit, hotspot_delete, hotspot_cards, hotspot_report, hotspot_common, roles, usage, manual_add, discovery, reboot, rename, saved, userman | Various | ✅ |

### 5. Rate Limiting

| Operation | Limit | File |
|-----------|-------|------|
| reboot | 10s | `utils/admin_decorator.py:36` |
| backup | 30s | `utils/admin_decorator.py:37` |
| restore | 60s | `utils/admin_decorator.py:38` |
| delete | 5s | `utils/admin_decorator.py:39` |
| add | 2s | `utils/admin_decorator.py:40` |
| edit | 2s | `utils/admin_decorator.py:41` |
| default | 1s | `utils/admin_decorator.py:35` |

---

## 🔴 Integration Gaps and Issues Found

### Gap 1: `@require_role` Handlers Lack Decorator-Level Observability

**Severity: HIGH**

`@require_role` is used in handlers that do NOT also use `@admin_only`. These handlers are completely missing the decorator-level observability suite:

| Feature | `@admin_only` | `@require_role` |
|---------|---------------|-----------------|
| `📥 [ACTION INCOMING]` logging | ✅ | ❌ **Missing** |
| `✅ [ACTION SUCCESS]` latency tracking | ✅ | ❌ **Missing** |
| `❌ [ACTION FAILED]` error tracking | ✅ | ❌ **Missing** |
| Rate limiting | ✅ | ❌ **Missing** |
| Request ID scope | ✅ (though bounded) | ❌ **Missing** |
| Group chat rejection with logging | ✅ | ✅ (silent, no log) |
| RBAC check | ✅ | ✅ |

**Affected handlers** (handlers using `@require_role` WITHOUT `@admin_only`):
- `bot/handlers/backup.py` — 5 handlers (`@require_role("operator")`)
- `bot/handlers/backup_restore.py` — 6 handlers (`@require_role("admin")`)
- `bot/handlers/hotspot_add.py` — 1 handler (`@require_role("operator")`)
- `bot/handlers/hotspot_cards.py` — 1 handler (`@require_role("operator")`)
- `bot/handlers/hotspot_delete.py` — 1 handler (`@require_role("operator")`)
- `bot/handlers/hotspot_edit.py` — 1 handler (`@require_role("operator")`)
- `bot/handlers/hotspot_report.py` — 2 handlers (`@require_role("operator")`)
- `bot/handlers/roles.py` — 7 handlers (mixed admin/super_admin)
- `bot/handlers/router_flows/manual_add.py` — 2 handlers (`@require_role("admin")`)
- `bot/handlers/router_flows/reboot.py` — 3 handlers (`@require_role("admin")`)
- `bot/handlers/router_flows/rename.py` — 1 handler (`@require_role("operator")`)
- `bot/handlers/router_flows/saved.py` — 3 handlers (`@require_role("admin")`)

**Impact**: Sensitive operations (backup, restore, reboot, router addition, role changes) produce no incoming action log and no success/failure latency log when guarded only by `@require_role`. The `📥 [ACTION INCOMING]` and `✅ [ACTION SUCCESS]` patterns are entirely absent from these code paths.

### Gap 2: `@admin_only` `request_id_scope` Exits Before Logging Calls

**Severity: MEDIUM**

In `utils/admin_decorator.py` lines 119-121, the `request_id_scope(rid)` only covers the `router_key` fetch. After the `with` block exits, all subsequent logging (`📥 [ACTION INCOMING]`, `✅ [ACTION SUCCESS]`, `❌ [ACTION FAILED]`) uses the request_id from `bind_request_id_from_update` (lines 278 in handler_registry.py), NOT the `admin_decorator`'s own fallback `rid`.

**Current code flow:**
```
bind_request_id_from_update sets request_id = update.update_id (or "-")
  → @admin_only wrapper starts
    → request_id_scope(rid) set temporarily for router_key fetch
    → request_id_scope exits → request_id reverts
    → 📥 [ACTION INCOMING] logged (uses bind_request_id_from_update's request_id) → ✅
    → handler executes → ✅ request_id propagated
    → ✅ [ACTION SUCCESS] logged (uses bind_request_id_from_update's request_id) → ✅
```

**The issue**: `admin_decorator.py` generates a fallback `rid = f"req_{int(time.time()*1000)}"` (line 118) that is NEVER used for logging, because the scope ends before logging occurs. This fallback is dead code. However, since `bind_request_id_from_update` already provides a request_id from `update.update_id`, this is not a critical bug — just dead code in the decorator.

**Note**: If `update.update_id` is `None` (unlikely but possible), `bind_request_id_from_update` sets request_id to `"-"`, and the fallback `rid` from `admin_decorator` would also be unused, resulting in `request_id = "-"` in all logs.

### Gap 3: No Audit Logging at Core Layer

**Severity: MEDIUM**

Core modules (`core/mikrotik_api.py`, `core/userman_manager.py`, `core/hotspot_manager.py`, `core/backup_scheduler.py`, etc.) do NOT call `log_action()` or any audit logging function. All audit logging is done at the handler level by explicitly calling `log_action()` in handler code.

**Impact**: If a core module makes a RouterOS API call that is NOT preceded by a `log_action()` call in the handler, that operation is not recorded in the audit database or the audit log format (`📝 [AUDIT LOG]`).

For example:
- `mikrotik_api.py` logs RouterOS API failures to console only (via `logger.error`), but does NOT insert audit records
- `userman_manager.py` logs user CRUD operations via `logger.info` but does NOT call `log_action()`
- `core/backup_scheduler.py` has no audit logging at all

**Recommendation**: Either move audit logging into the core layer (preferred for completeness) or add a decorator on core functions that automatically calls `log_action()`.

### Gap 4: `@require_role` Lacks Rate Limiting

**Severity: MEDIUM**

`@require_role` does not perform rate limiting, while `@admin_only` does. Handlers that use `@require_role` alone (especially `@require_role("admin")` for operations like backup restore, router add, reboot) are not protected against rapid repeated calls.

### Gap 5: `main.py` Console Log Level Mismatch with Documentation

**Severity: LOW**

`AGENTS.md` states: "The console handler shows INFO and above only." However, `main.py` line 28 calls `configure_logging(logging.DEBUG)`, which sets the console handler to DEBUG level. This means DEBUG+ messages appear on console, contradicting the documentation.

### Gap 6: `audit_logs.py` Log Format Does Not Include Request ID

**Severity: LOW**

`database/repositories/audit_logs.py` line 54-60:
```python
logger.info(
    "📝 [AUDIT LOG] Action: %s | User: %s | Router: %s | Admin: %s",
    ...
)
```

This log message format does NOT include `request_id` explicitly. However, the `RequestIdFilter` automatically injects `request_id` into every log record, and the `JsonFormatter` includes it. So in console output, the format is:
```
<timestamp> - audit_logs - INFO - [req_XXXX] - 📝 [AUDIT LOG] Action: ...
```

The `request_id` IS present in both console and JSON logs via the filter, just not in the message template itself. This is consistent with how `📥 [ACTION INCOMING]` and `✅ [ACTION SUCCESS]` also work — they don't include `request_id` in their message template either.

---

## Summary Matrix

| System Component | Exists | Fully Integrated? | Notes |
|-----------------|--------|-------------------|-------|
| Request ID infrastructure | ✅ | ✅ Yes | Working end-to-end |
| `📥 [ACTION INCOMING]` logging | ✅ | ⚠️ Partial | Only via `@admin_only`; missing from `@require_role` handlers |
| `✅ [ACTION SUCCESS]` latency tracking | ✅ | ⚠️ Partial | Only via `@admin_only`; missing from `@require_role` handlers |
| `❌ [ACTION FAILED]` error tracking | ✅ | ⚠️ Partial | Only via `@admin_only`; missing from `@require_role` handlers |
| `📝 [AUDIT LOG]` (audit DB + console) | ✅ | ⚠️ Partial | Only at handler level; core modules don't audit |
| Request ID in all log records | ✅ | ✅ Yes | Via `RequestIdFilter` on all handlers |
| Rate limiting | ✅ | ⚠️ Partial | Only via `@admin_only`; `@require_role` has none |
| Group chat rejection | ✅ | ✅ Yes | Both decorators handle it |
| Secret sanitization in error logs | ✅ | ✅ Yes | `error_response.py` covers this |

---

## Recommended Priority Fixes

1. **HIGH**: Refactor `@admin_only` to extract the observability pattern (incoming log, success/failure with latency, rate limit) into a reusable decorator or mixin that `@require_role` handlers can opt into, OR add `@admin_only` to all `@require_role` handlers that perform sensitive write operations.

2. **HIGH**: Add `📥 [ACTION INCOMING]` logging and `✅ [ACTION SUCCESS]` latency tracking to all `@require_role`-only handlers, especially backup/restore, reboot, and router-add flows.

3. **MEDIUM**: Move audit logging (`log_action()`) into core modules (especially `mikrotik_api.py`, `userman_manager.py`, `backup_scheduler.py`) so that all RouterOS API calls are tracked regardless of which handler or decorator invokes them.

4. **MEDIUM**: Add rate limiting to `@require_role` for sensitive operations (backup, restore, reboot, add, delete).

5. **LOW**: Fix the dead `rid` fallback code in `admin_decorator.py` — either remove it (since `bind_request_id_from_update` already provides request_id) or restructure the scope to actually use it for logging.

6. **LOW**: Align `main.py` console log level with `AGENTS.md` documentation (change `DEBUG` to `INFO` if production intent is INFO-only console).
