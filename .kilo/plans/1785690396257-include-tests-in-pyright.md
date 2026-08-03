# Plan: Include `tests/` in Pyright Strict Scope

## Goal
Remove the temporary `tests` exclusion from `pyrightconfig.json` and add it to the `include` list, so `tests/` is analyzed under the same strict type-checking rules as application code.

## Rationale (verified)
- Current run of `py -3.12 -m pyright --pythonpath ".\venv\Scripts\python.exe" tests/` returns **0 errors, 0 warnings, 0 informations**.
- Project policy requires zero Pyright errors across all production-maintained code.
- Tests are production-maintained and should receive the same static-analysis coverage.

## Changes
1. **`pyrightconfig.json`**
   - Add `"tests"` to the `include` array.
   - Remove `"tests"` from the `exclude` array.

## Validation
Run the standard quality-gate sequence after the edit:
```bash
py -3.12 -m pyright --pythonpath ".\venv\Scripts\python.exe"
ruff check .
py -3.12 scripts/validate_handlers.py
py -3.12 scripts/validate_routeros_paths.py
py -3.12 scripts/check_type_ignore.py
py -3.12 -m pytest --cov=bot --cov=core --cov=database --cov=utils --cov=pdf --cov-fail-under=80 -q
```

Expected result: Pyright still reports 0 errors/warnings across the full project (now including `tests/`). All other gates remain green.

## Risks
- **Low.** The direct Pyright run on `tests/` already confirms zero errors. The only residual risk is a future test edit introducing a type error that would now fail CI — this is the intended outcome.
