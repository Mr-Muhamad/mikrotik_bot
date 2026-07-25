#!/usr/bin/env python3
"""Verify that every '# type: ignore' comment includes a reason."""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Files with documented type: ignore (whitelist)
# Each entry: (file, line_number, reason)
KNOWN_IGNORES = [
    ("core/connection_pool.py", 101, "LibRouterosError base class catch"),
    ("core/mikrotik_api.py", 217, "LibRouterosError base class catch"),
    ("bot/handlers/backup.py", 82, "job_data JSON keys are strings at runtime"),
    ("bot/handlers/backup.py", 83, "job_data JSON keys are strings at runtime"),
    ("bot/handlers/settings.py", 181, "dynamic handler dispatch"),
    ("utils/error_response.py", 122, "dynamic classifier dispatch"),
    ("scripts/e2e_smoke.py", 86, "test mock override"),
    ("scripts/e2e_smoke.py", 96, "test mock override"),
]

IGNORE_PATTERN = re.compile(r"#\s*type:\s*ignore")


def scan_files():
    """Scan all Python files for type: ignore comments."""
    results = []
    py_files = sorted(PROJECT_ROOT.rglob("*.py"))
    for path in py_files:
        if any(skip in path.parts for skip in ("venv", "__pycache__", "Activate.ps1")):
            continue
        rel = path.relative_to(PROJECT_ROOT)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            if IGNORE_PATTERN.search(line):
                rel_str = str(rel).replace("\\", "/")
                results.append((rel_str, i, line.strip()))
    return results


def main():
    findings = scan_files()

    # Build lookup of known ignores by (file, line)
    known = {}
    for file_path, line_no, reason in KNOWN_IGNORES:
        key = (file_path.replace("\\", "/"), line_no)
        known[key] = reason

    errors = []
    documented = []
    for file_path, line_no, line_text in findings:
        key = (file_path, line_no)
        if key in known:
            documented.append(key)
        else:
            # Check if the comment has any text after 'ignore'
            match = IGNORE_PATTERN.search(line_text)
            if match:
                after = line_text[match.end() :].strip()
                if after:
                    documented.append(key)
                else:
                    errors.append((file_path, line_no, line_text))
            else:
                errors.append((file_path, line_no, line_text))

    if errors:
        print(f"FAIL: Found {len(errors)} undocumented '# type: ignore' comment(s):\n")
        for file_path, line_no, line_text in errors:
            print(f"  {file_path}:{line_no}")
            print(f"    {line_text}\n")
        print(
            "Add a reason comment after '# type: ignore'"
            " (e.g., '# type: ignore[assignment]  # librouteros stubs')"
        )
        sys.exit(1)
    else:
        print(f"OK: All {len(findings)} '# type: ignore' comments are documented.")
        sys.exit(0)


if __name__ == "__main__":
    main()
