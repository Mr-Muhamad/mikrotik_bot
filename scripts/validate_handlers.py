"""Validate that every imported Telegram handler is registered and vice versa.

Detects:
  - handlers used in registrations but not imported
  - handlers imported from bot.handlers but never registered or used

Note: ALL-CAPS constant imports (e.g. ``CALLBACKS``, ``PATTERNS``) are
intentionally ignored because they are not handler functions.
"""

import ast
import sys

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


def _extract_handler_names(tree: ast.AST) -> set:
    names = set()
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


def _local_defs(tree: ast.AST) -> set:
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def main():
    source_path = "bot/registrations.py"
    with open(source_path, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imported: set = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("bot.handlers")
        ):
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

    if has_error:
        sys.exit(1)

    print("[OK] All handlers validated - every import is registered, every reference is imported.")


if __name__ == "__main__":
    main()
