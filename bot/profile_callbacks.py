"""Profile list cache for short callback_data (Telegram 64-byte limit)."""

PROFILE_NAMES_KEY = "profile_names"


def cache_profile_names(context, profile_names: list[str]) -> None:
    context.user_data[PROFILE_NAMES_KEY] = list(profile_names)


def resolve_profile_from_callback(context, callback_data: str | None, prefix: str) -> str | None:
    if not callback_data:
        return None
    suffix = callback_data[len(prefix) :]
    try:
        index = int(suffix)
    except ValueError:
        return None
    names = context.user_data.get(PROFILE_NAMES_KEY, [])
    if 0 <= index < len(names):
        return names[index]
    return None
