_all_items = [
    "admin_only",
    "clean_chat_messages",
    "clean_command",
    "decrypt_password",
    "delete_now",
    "edit_clean",
    "encrypt_password",
    "format_bytes",
    "format_user_list",
    "parse_bytes",
    "reply_final",
    "run_blocking",
    "schedule_delete",
    "send_loading",
    "send_step",
    "validate_password",
    "validate_positive_int",
    "validate_username",
]
__all__ = _all_items  # type: ignore[reportUnsupportedDunderAll]  # resolved via __getattr__

_import_map: dict[str, tuple[str, str]] = {
    "admin_only": ("utils.admin_decorator", "admin_only"),
    "run_blocking": ("utils.async_blocking", "run_blocking"),
    "clean_chat_messages": ("utils.chat_cleaner", "clean_chat_messages"),
    "clean_command": ("utils.chat_cleaner", "clean_command"),
    "delete_now": ("utils.chat_cleaner", "delete_now"),
    "edit_clean": ("utils.chat_cleaner", "edit_clean"),
    "reply_final": ("utils.chat_cleaner", "reply_final"),
    "schedule_delete": ("utils.chat_cleaner", "schedule_delete"),
    "send_loading": ("utils.chat_cleaner", "send_loading"),
    "send_step": ("utils.chat_cleaner", "send_step"),
    "decrypt_password": ("utils.crypto", "decrypt_password"),
    "encrypt_password": ("utils.crypto", "encrypt_password"),
    "format_bytes": ("utils.formatters", "format_bytes"),
    "format_user_list": ("utils.formatters", "format_user_list"),
    "parse_bytes": ("utils.formatters", "parse_bytes"),
    "validate_password": ("utils.validators", "validate_password"),
    "validate_positive_int": ("utils.validators", "validate_positive_int"),
    "validate_username": ("utils.validators", "validate_username"),
}


def __getattr__(name: str):
    if name in _import_map:
        mod_path, attr = _import_map[name]
        import importlib
        mod = importlib.import_module(mod_path)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return __all__
