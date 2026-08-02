"""Audit tool: list all logger.exception sites in handler files.

Run from project root: ``python scripts/list_logger_exception_sites.py``.

Reports remaining sites (still using logger.exception), migrated sites
(using await send_error), and silent sites (try/except: pass) across all
bot/handlers/*.py files. Use this to track A3 migration progress.
"""

import argparse
import re
import sys
from pathlib import Path

HANDLERS_DIR = Path("bot/handlers")


def classify_site(block_start: int, lines: list[str]) -> str:
    """Inspect the body of an except block to classify it."""
    has_logger = False
    has_send_error = False
    has_send_message = False
    end = min(block_start + 8, len(lines))
    for j in range(block_start, end):
        if "logger.exception" in lines[j]:
            has_logger = True
        if "send_error" in lines[j] and "await" in lines[j]:
            has_send_error = True
        if "context.bot.send_message" in lines[j] and "await" in lines[j]:
            has_send_message = True
    if has_send_error or has_send_message:
        return "MIGRATED"
    if has_logger:
        return "REMAINING"
    return "SILENT"


def audit_files(handlers_dir: Path = HANDLERS_DIR) -> dict[str, list[tuple[int, str]]]:
    results: dict[str, list[tuple[int, str]]] = {
        "REMAINING": [],
        "MIGRATED": [],
        "SILENT": [],
    }
    for path in sorted(handlers_dir.glob("*.py")):
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            m = re.match(r"^\s*except\s+Exception(?:\s+as\s+(\w+))?:", line)
            if not m:
                continue
            status = classify_site(i, lines)
            results[status].append((i, f"{path.name}"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit logger.exception migration status in handlers."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--count",
        action="store_true",
        help="Print summary counts only.",
    )
    group.add_argument(
        "--remaining",
        action="store_true",
        help="List remaining logger.exception sites only.",
    )
    group.add_argument(
        "--migrated",
        action="store_true",
        help="List migrated sites only.",
    )
    group.add_argument(
        "--silent",
        action="store_true",
        help="List silent (best-effort) sites only.",
    )
    args = parser.parse_args()

    results = audit_files()

    if args.count:
        for status, sites in results.items():
            print(f"{status}: {len(sites)}")
        return 0

    if args.remaining:
        results = {"REMAINING": results["REMAINING"]}
    elif args.migrated:
        results = {"MIGRATED": results["MIGRATED"]}
    elif args.silent:
        results = {"SILENT": results["SILENT"]}

    for status, sites in results.items():
        if not sites:
            continue
        print(f"=== {status} ({len(sites)}) ===")
        for line_no, fname in sites:
            print(f"  {fname}:L{line_no}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
