# Circuit Breaker Thread-Safety & Backup Refactor Plan

## Summary
Analysis and verification of critical components in Mikrotik admin bot telegram project. All issues addressed, remaining tasks documented.

## Completed Tasks

### 1. Circuit Breaker Thread-Safety Analysis
- **Status**: VERIFIED COMPLETE
- **File**: `core/circuit_breaker.py`
- **Key Change**: Added `_in_trial: dict[str, bool]` for atomic check-and-set in HALF_OPEN state
- **Verification**: RLock + dict tracking ensures only one thread progresses, concurrent threads get `CircuitBreakerOpenError`
- **Commit**: bca1c50 (HEAD)

### 2. Backup Scheduler Refactoring
- **Status**: COMPLETE
- **File**: `core/backup_scheduler.py`
- **Changes**:
  - Extracted `_run_backup_operation()` helper
  - Unified `_run_userman_backup()` and `_run_full_backup()` methods
  - Replaced `telegram.ext` imports with `Any` type annotation
  - Changed result checking from `if result is None` to `if result.get("success")`
- **Tests Updated**: `test_backup_scheduler.py`, `test_backup_scheduler_extended.py`

### 3. FTP Circuit Breaker Cleanup Fix
- **Status**: COMPLETE
- **File**: `core/backup/ftp.py`
- **Change**: Ensured `quit()` called in `finally` on all failure paths (connect, transfer)
- **Tests Updated**: `test_backup_ftp.py` - 2 tests now assert `quit.assert_called_once()`

### 4. Type Issues Resolution
- **Status**: COMPLETE
- **Issues Fixed**:
  - `core/backup_scheduler.py`: telegram.ext import replaced with `Any`
  - Added `AsyncMock` import where needed
- **Verification**: pyright 0 errors, ruff clean

## Remaining Tasks (Not Blocking)

### Architecture Violation Fix (MEDIUM PRIORITY)
- **Status**: RESOLVED — closed
- **Issue**: `core/backup_scheduler.py` imports `telegram.ext`
- **Resolution**: The `telegram.ext` import was replaced with `Any` type annotations (Task 4) and the remaining stale doc constants (`_JOB_QUEUE_DOC`, `_JOB_CONTEXT_DOC`) that referenced `telegram.ext` were removed. `core/backup_scheduler.py` now has zero `telegram` imports; verified via `rg -n "telegram" core/`.
- **Decision**: Extracting the `JobLike` Protocol or moving the scheduler to `bot/` remains a broad refactor with cross-cutting impact and no functional benefit today. The `JobQueue`/`CallbackContext` objects are passed in as `Any` to keep the core layer Telegram-free. Revisit if `core/` is ever imported outside a Telegram runtime.

### Stress Testing Implementation (LOW PRIORITY)
- **Status**: COMPLETE
- **Task**: Create `tests/stress/test_concurrent_routers.py`
- **Files**: `tests/stress/__init__.py`, `tests/stress/test_concurrent_routers.py`
- **Coverage**: HALF-OPEN single-trial barrier, ConnectionPool ceiling under concurrency, retry-storm short-circuit
- **Marker**: registered as `stress` in `pyproject.toml`

### Fault Injection Test Suite (LOW PRIORITY)
- **Status**: COMPLETE
- **Task**: Create `tests/fault/` directory with:
  - `test_db_latency.py` — `timed_execute` success/failure metrics and re-raise
  - `test_ftp_faults.py` — partial-file cleanup, download failure, credential sanitization
  - `test_routeros_malformed.py` — non-dict rows through `sanitize_api_response`
  - `test_circuit_breaker_transitions.py` — CLOSED→OPEN→HALF-OPEN state machine with frozen clock
- **Marker**: registered as `fault` in `pyproject.toml`

## Code Quality Verification

| Check | Status |
|-------|--------|
| pyright | ✅ 0 errors |
| ruff | ✅ Clean |
| validate_handlers.py | ✅ Passed |
| validate_routeros_paths.py | ✅ Passed |
| check_type_ignore.py | ✅ 62 documented |
| pytest | ✅ 78 tests passed |

## Key Architectural Decisions

1. **Circuit Breaker HALF_OPEN**: The `_in_trial` dict approach is correct and thread-safe. Stale flags possible only via thread death mid-trial (acceptable risk).

2. **Backup Result Checking**: Unified method's `result.get("success")` is more robust than `None` check. Confirmed services always return proper dict.

3. **FTP Cleanup**: `try/finally` with `quit()` call is correct per AGENTS.md policy. Exceptions from `quit()` are caught internally.

## Risk Assessment

- **No blocking risks**: All current code passes quality gates
- **Architecture note**: telegram.ext dependency fully removed from core layer; scheduler receives JobQueue/CallbackContext as `Any` to stay Telegram-free
- **Thread-safety**: Verified through code review, not stress tests (recommendation for future)