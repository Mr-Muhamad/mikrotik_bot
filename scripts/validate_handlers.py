"""Validate that every imported Telegram handler is registered and vice versa.

Detects:
  - handlers used in registrations but not imported
  - handlers imported from bot.handlers but never registered or used

Note: ALL-CAPS constant imports (e.g. ``CALLBACKS``, ``PATTERNS``) are
intentionally ignored because they are not handler functions.
"""

import ast
import sys
from typing import Any

HANDLER_CLASSES = frozenset(
    {
        "CallbackQueryHandler",
        "MessageHandler",
        "CommandHandler",
        "add_error_handler",
    }
)


HANDLER_METHODS = frozenset({"add_handler", "add_error_handler"})
REGISTRY_DECORATORS = frozenset(
    {
        "entry_point",
        "state",
        "fallback",
        "standalone",
        "reg_err",
    }
)


def _get_callee_name(func: ast.AST) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id == "application" or func.attr in HANDLER_CLASSES | HANDLER_METHODS:
            return func.attr
    return None


def _get_root_call_name(node: ast.AST) -> str | None:
    """Return the root function name for chained decorator calls."""
    current = node
    while isinstance(current, ast.Call):
        current = current.func
    while isinstance(current, ast.Attribute):
        current = current.value
        while isinstance(current, ast.Call):
            current = current.func
    if isinstance(current, ast.Name):
        return current.id
    return None


def _extract_handler_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        root_name = _get_root_call_name(node.func)
        if root_name in REGISTRY_DECORATORS:
            for arg in node.args:
                if isinstance(arg, ast.Name) and arg.id not in HANDLER_CLASSES:
                    names.add(arg.id)
            continue

        callee = _get_callee_name(node.func)
        if callee not in HANDLER_CLASSES and callee not in HANDLER_METHODS:
            continue
        for arg in node.args:
            if isinstance(arg, ast.Name) and not arg.id.startswith("filter"):
                names.add(arg.id)
    return names


def _local_defs(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def _validate_handler_imports() -> bool:
    """Validate that every imported handler is registered and vice versa.

    Returns ``True`` when a validation problem was found.
    """
    source_path = "bot/registrations.py"
    with open(source_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("bot.handlers"):
            for alias in node.names:
                imported.add(alias.asname or alias.name)

    defined = _local_defs(tree)
    used = _extract_handler_names(tree)

    used_but_not_imported = used - imported - defined
    imported_but_not_used = imported - used

    has_error = False

    if used_but_not_imported:
        has_error = True
        print("[ERROR] HANDLER USED BUT NOT IMPORTED:")
        for name in sorted(used_but_not_imported):
            print(f"   {name}")

    if imported_but_not_used:
        actual_handlers = {
            n
            for n in imported_but_not_used
            if not n.startswith("WAITING_") and not n.startswith("filters") and not n.isupper()
        }
        if actual_handlers:
            has_error = True
            print("[WARNING] HANDLER IMPORTED BUT NEVER USED (dead code):")
            for name in sorted(actual_handlers):
                print(f"   {name}")

    return has_error


def _has_callback_pattern(item: dict[str, Any]) -> bool:
    """Return ``True`` when *item* is a registered CallbackQueryHandler pattern."""
    return item["cls"].__name__ == "CallbackQueryHandler" and "pattern" in item["kwargs"]


def _collect_registered_patterns(registry: dict[str, Any]) -> list[str]:
    """Collect every registered CallbackQueryHandler pattern from *registry*."""
    registered_pats: list[str] = []
    for item in registry["standalone"]:
        if _has_callback_pattern(item):
            registered_pats.append(item["kwargs"]["pattern"])
    for _state, items in registry["states"].items():
        for item in items:
            if _has_callback_pattern(item):
                registered_pats.append(item["kwargs"]["pattern"])
    for item in registry["entry_points"]:
        if _has_callback_pattern(item):
            registered_pats.append(item["kwargs"]["pattern"])
    return registered_pats


def _collect_keyboard_callback_data() -> set[str]:
    """Extract the literal callback_data values used in ``bot/keyboards/`` package."""
    import glob as glob_mod

    kb_cbs: set[str] = set()
    py_files = glob_mod.glob("bot/keyboards/*.py")
    for path in sorted(py_files):
        with open(path, encoding="utf-8") as kf:
            ktree = ast.parse(kf.read(), filename=path)
        for node in ast.walk(ktree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "InlineKeyboardButton":
                for kw in node.keywords:
                    if kw.arg == "callback_data" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        kb_cbs.add(kw.value.value)
    return kb_cbs


def _audit_keyboard_callbacks() -> bool:
    """Verify every InlineKeyboardButton callback_data has a registered handler.

    Returns ``True`` when an unregistered callback was found.
    """
    # Local imports keep this script importable without bootstrapping the full
    # Telegram application: importing bot.registrations at module level would
    # eagerly pull in handlers and their runtime dependencies.
    import os
    import re

    sys.path.insert(0, os.path.abspath("."))
    import bot.registrations  # noqa: F401 # pyright: ignore[reportUnusedImport]

    _ = bot.registrations
    from utils.handler_registry import _registry  # pyright: ignore[reportPrivateUsage]

    registered_pats = _collect_registered_patterns(_registry)
    kb_cbs = _collect_keyboard_callback_data()

    unregistered_cbs = []
    for cb in sorted(kb_cbs):
        matched = any(re.search(p if isinstance(p, str) else p.pattern, cb) for p in registered_pats)
        if not matched:
            unregistered_cbs.append(cb)

    if unregistered_cbs:
        print("[ERROR] INLINE KEYBOARD CALLBACK_DATA WITH NO REGISTERED HANDLER:")
        for cb in unregistered_cbs:
            print(f"   '{cb}'")
        return True

    return False


def main() -> None:
    """Run handler validation and exit non-zero when problems are found."""
    has_error = _validate_handler_imports()
    if _audit_keyboard_callbacks():
        has_error = True

    if has_error:
        sys.exit(1)

    print("[OK] All handlers validated - every import is registered, every reference is imported.")


if __name__ == "__main__":
    main()
