#!/usr/bin/env python3
"""Verify that every type-ignore comment (both ``# type: ignore`` and
``# pyright: ignore``) includes a documented reason.

Rules:
  1. ``# type: ignore`` must be followed by an error-code bracket (e.g.
     ``[assignment]``) or a text reason on the same line, OR appear in the
     KNOWN_IGNORES whitelist with a documented reason.
  2. ``# pyright: ignore`` must similarly be documented — either via a trailing
     error-code bracket or text reason, or via the KNOWN_IGNORES whitelist.

This enforces Constitution Principle #2: "Never hide an error unless you can
prove it's a false positive, and document the proof."
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files with documented ignores (whitelist)
# Each entry: (file, line_number, reason)
KNOWN_IGNORES = [
    ("core/connection_pool.py", 101, "LibRouterosError base class catch"),
    ("bot/handlers/backup.py", 83, "job_data JSON keys are strings at runtime"),
    ("bot/registrations.py", 37, "side-effect import populates CH registry"),
    ("bot/registrations.py", 38, "side-effect import populates standalone registry"),
    ("scripts/validate_handlers.py", 185, "side-effect import to trigger registry population"),
    ("scripts/validate_handlers.py", 188, "accessing internal registry for validation"),
    ("tests/bot/test_callback_handling.py", 16, "side-effect import for test registration"),
    ("scripts/e2e_smoke.py", 86, "test mock override"),
    ("scripts/e2e_smoke.py", 96, "test mock override"),
]

# Pattern matches `# type: ignore` optionally with error codes like `[assignment]`
TYPE_IGNORE_PATTERN = re.compile(r"#\s*type:\s*ignore")
# Pattern matches `# pyright: ignore` optionally with rule ids like `[reportUnusedImport]`
PYRIGHT_IGNORE_PATTERN = re.compile(r"#\s*pyright:\s*ignore")

IGNORE_PATTERNS = [TYPE_IGNORE_PATTERN, PYRIGHT_IGNORE_PATTERN]


def scan_files():
    """Scan all Python files for type: ignore and pyright: ignore comments."""
    results: list[tuple[str, int, str, re.Pattern[str]]] = []
    py_files = sorted(PROJECT_ROOT.rglob("*.py"))
    for path in py_files:
        if any(skip in path.parts for skip in ("venv", "__pycache__", "Activate.ps1")):
            continue
        rel = path.relative_to(PROJECT_ROOT)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:  # noqa: BLE001 - catch-all: log unexpected error before returning result
            continue
        for i, line in enumerate(lines, 1):
            for pattern in IGNORE_PATTERNS:
                if pattern.search(line):
                    rel_str = str(rel).replace("\\", "/")
                    results.append((rel_str, i, line.strip(), pattern))
    return results


def _has_reason(line_text: str, pattern: re.Pattern[str]) -> bool:
    """Check if there is non-empty text (error code or reason) after the ignore directive."""
    match = pattern.search(line_text)
    if not match:
        return False
    after = line_text[match.end():].strip()
    # If there's a ``-`` separator before the reason, strip it
    if after.startswith("-"):
        after = after[1:].strip()
    return bool(after)


def main():
    findings = scan_files()

    # Build lookup of known ignores by (file, line)
    known: dict[tuple[str, int], str] = {}
    for file_path, line_no, reason in KNOWN_IGNORES:
        key = (file_path.replace("\\", "/"), line_no)
        known[key] = reason

    errors = []
    for file_path, line_no, line_text, pattern in findings:
        key = (file_path, line_no)
        if key in known:
            continue
        if not _has_reason(line_text, pattern):
            errors.append((file_path, line_no, line_text))

    if errors:
        print(f"FAIL: Found {len(errors)} undocumented type-ignore comment(s):\n")
        for file_path, line_no, line_text in errors:
            print(f"  {file_path}:{line_no}")
            print(f"    {line_text}")
        print()
        print(
            "Add a reason after the ignore directive"
            " (e.g., '# type: ignore[assignment]  # librouteros stubs'"
            " or '# pyright: ignore[reportUnusedImport]  # side-effect import')"
        )
        sys.exit(1)
    else:
        print(f"OK: All {len(findings)} type-ignore comments are documented.")
        sys.exit(0)


if __name__ == "__main__":
    main()
