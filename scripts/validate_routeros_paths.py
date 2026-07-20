"""Guard the RouterOS v6/v7 integration boundary.

The bot supports both RouterOS v6 and v7. The ONLY difference that matters at
the API layer is the User Manager base path:

    v6  -> tool/user-manager/...
    v7  -> user-manager/...

``mikrotik_api.get_userman_base_path(router_key)`` is the single source of truth
for that choice (it inspects the cached router version). Any code that hardcodes
a User Manager path in an ``execute``/``execute_long``/``execute_non_blocking``
call bypasses version detection and silently breaks one of the two versions.

This script fails if such a hardcoded path exists anywhere under ``core/``
(except inside ``mikrotik_api.py``, which legitimately owns the path selector).
It runs statically, needs no router, and is safe for CI.
"""

import ast
import sys
from pathlib import Path

CORE_DIR = Path(__file__).resolve().parent.parent / "core"
ALLOWED_FILE = "mikrotik_api.py"  # owns get_userman_base_path()

EXECUTE_METHODS = frozenset({"execute", "execute_long", "execute_non_blocking"})
FORBIDDEN_MARKER = "user-manager"


def _command_literal(node: ast.Call) -> str | None:
    """Return the literal command text of an execute() call, or None.

    Handles both plain string literals and f-strings, concatenating only the
    constant parts (an f-string like f"{base}/user/print" yields "/user/print").
    """
    if len(node.args) < 2:
        return None
    arg = node.args[1]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        return "".join(
            part.value
            for part in arg.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return None


def _is_execute_call(node: ast.Call) -> bool:
    """True only for ``mikrotik_api.execute*(...)`` calls.

    Scoping to the ``mikrotik_api`` object avoids false positives from any
    unrelated ``.execute`` method that might appear in core/ later.
    """
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr in EXECUTE_METHODS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "mikrotik_api"
    )


def _scan_file(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_execute_call(node):
            continue
        literal = _command_literal(node)
        if literal and FORBIDDEN_MARKER in literal:
            violations.append((node.lineno, literal))
    return violations


def main() -> None:
    has_error = False
    for path in sorted(CORE_DIR.rglob("*.py")):
        if path.name == ALLOWED_FILE:
            continue
        for lineno, literal in _scan_file(path):
            has_error = True
            rel = path.relative_to(CORE_DIR.parent)
            print(
                f"[ERROR] Hardcoded User Manager path in {rel}:{lineno} -> {literal!r}\n"
                f"        Use mikrotik_api.get_userman_base_path(router_key) instead "
                f"to keep v6/v7 support."
            )

    if has_error:
        sys.exit(1)

    print("[OK] No hardcoded User Manager paths in core/ - v6/v7 routing preserved.")


if __name__ == "__main__":
    main()
