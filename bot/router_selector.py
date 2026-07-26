from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import get_router_keyboard
from bot.messages import NO_ROUTER_SELECTED
from core.mikrotik_client import RouterOSRow
from database.models import get_user_session, save_user_session

logger = logging.getLogger(__name__)


def _get_user_id(update: Update) -> int | None:
    """أعد معرّف المستخدم أو None إن غاب ``effective_user`` (تجنّب الدورة الاستيرادية)."""
    user = update.effective_user
    return user.id if user is not None else None


# ── Navigation guard allowlist ────────────────────────────────
# Operational features require an active router session (business rule).
# Handlers matching these commands/patterns are ROUTER-MANAGEMENT screens and
# must stay accessible even when no router is selected. The guard classifies a
# registered handler purely from its registration kwargs (command= / pattern=),
# so no per-handler opt-in is needed.

ROUTER_MGMT_COMMANDS = frozenset(
    {
        "start",
        "help",
        "cancel",
        "clean",
        "sync",
        "routers",
        "addrouter",
        "reboot",
        "roles",
        "role",
        "watchdog",
        "watchdog_start",
        "metrics",
        "assign_router",
    }
)

# Exact-match callback tokens that belong to router management.
ROUTER_MGMT_TOKENS = frozenset(
    {
        "select_router",
        "main_menu",
        "saved_routers",
        "saved_router",
        "discover_routers",
        "connect_router",
        "delete_router",
        "confirm_delete_router",
        "refresh_routers",
        "reboot_yes",
        "reboot_no",
        "reboot_router",
        "rename_router",
        "manual_add_router",
        "confirm_manual_add",
        "disc_router",
        "cancel_edit",
        "go_back",
    }
)

# Callback pattern *names* (keys of PATTERNS) exempt from the router requirement.
ROUTER_MGMT_PATTERN_NAMES = frozenset(
    {
        "select_router",
        "main_menu",
        "saved_routers",
        "saved_router",
        "discover_routers",
        "connect_router",
        "delete_router",
        "confirm_delete_router",
        "refresh_routers",
        "reboot_yes",
        "reboot_no",
        "reboot_router",
        "rename_router",
        "manual_add_router",
        "confirm_manual_add",
        "disc_router",
        "cancel_edit",
        "go_back",
    }
)

# Resolved regex strings (from PATTERNS) for the exempt callback names.
# Built lazily to avoid importing callback_constants at module import time.
_router_mgmt_pattern_regexes: frozenset[str] | None = None


def _router_mgmt_regexes() -> frozenset[str]:
    global _router_mgmt_pattern_regexes
    if _router_mgmt_pattern_regexes is None:
        from bot.handlers.callback_constants import PATTERNS

        _router_mgmt_pattern_regexes = frozenset(
            PATTERNS[name] for name in ROUTER_MGMT_PATTERN_NAMES
        )
    return _router_mgmt_pattern_regexes


PRESERVED_USER_DATA_KEYS = {
    "nav_back",
    "router_key",
    "profile_names",
}

CONVERSATION_USER_DATA_KEYS = (
    "add_username",
    "add_password",
    "add_profile",
    "add_bytes",
    "add_uptime",
    "edit_user_id",
    "edit_user_data",
    "edit_field",
    "delete_user_id",
    "search_hosts",
    "kick_host_idx",
    "users_cache",
    "search_um_hosts",
    "kick_um_idx",
    "add_profile_username",
    "add_profile_list",
    "card_type",
    "card_profile",
    "card_payment",
    "card_caller_id",
    "pdf_option",
    "disc_ip",
    "disc_username",
    "disc_router_id",
    "rename_router_id",
    "last_msg",
    "hs_card_count",
    "hs_card_length",
    "hs_card_prefix",
    "hs_card_system",
    "hs_card_profile",
    "hs_card_uptime",
    "hs_card_bytes",
    "hs_uptime_unit",
    "uptime_unit",
    "usage_router",
    "backup_local_path",
    "backup_downloaded",
    "backup_type",
    "backup_downloaded_list",
    "restore_backup_list",
    "restore_backup_name",
    "userman_restore_list",
    "userman_restore_tar",
)


def get_user_routers(user_id: int) -> list[RouterOSRow]:
    """Return the list of routers this user is allowed to manage.

    - للـ Super Admin (ADMIN_IDS): كل الروترات النشطة.
    - للعميل (المسجل في roles): الروترات التي يملكها فقط (owner_id).
    - إن لم يملك روترات: قائمة فارغة.
    """
    from config import ADMIN_IDS
    from database.models import get_saved_routers

    if user_id in ADMIN_IDS:
        return get_saved_routers(active_only=True)

    # عميل — نُصفّي حسب المالك
    return get_saved_routers(active_only=True, owner_id=user_id)


def get_selected_router(user_id: int) -> str | None:
    """Return the currently selected router key for a user, or None if expired/not set."""
    session = get_user_session(user_id)
    if not session:
        return None

    selected_router = session.get("selected_router")
    if not selected_router:
        return None

    router_key = str(selected_router)

    # Check session timeout
    from datetime import datetime

    from database.models import UTC_TIMESTAMP_FORMAT
    from database.repositories.user_sessions import clear_router_session

    last_activity_raw = session.get("last_activity")
    last_activity_str: str = str(last_activity_raw) if last_activity_raw else ""
    timeout_raw = session.get("session_timeout")
    timeout_mins: float = float(str(timeout_raw)) if timeout_raw else 15.0

    # Only enforce if timeout_mins is > 0. If timeout_mins <= 0, it means no timeout.
    if last_activity_str and timeout_mins > 0:
        try:
            last_activity = datetime.strptime(last_activity_str, UTC_TIMESTAMP_FORMAT).replace(
                tzinfo=UTC
            )
            now = datetime.now(UTC)
            diff = (now - last_activity).total_seconds() / 60.0

            if diff > timeout_mins:
                # Session expired
                logger.info(
                    f"User {user_id} session expired after {diff:.1f} minutes of inactivity."
                )
                clear_router_session(user_id)
                return None
        except Exception as e:
            logger.warning(f"Failed to parse last_activity for user {user_id}: {e}")

    return router_key


def set_selected_router(user_id: int, router_key: str) -> None:
    """Set the selected router key for a user in the database."""
    save_user_session(user_id, selected_router=router_key)


def set_current_action(user_id: int, action: str, data: str | None = None) -> None:
    """Set the current in-progress action and optional data for a user."""
    save_user_session(user_id, current_action=action, action_data=data)


def clear_action(user_id: int) -> None:
    """Clear the current action for a user while preserving selected router."""
    save_user_session(user_id, current_action=None, action_data=None)


def clear_router(user_id: int) -> None:
    """Clear all session state for a user (router selection and current action)."""
    save_user_session(user_id, selected_router="", current_action=None, action_data=None)


def nav_set(context: ContextTypes.DEFAULT_TYPE, back_to: str) -> None:
    """Set the navigation back target in user_data for the current conversation."""
    context.user_data["nav_back"] = back_to


def nav_get(context: ContextTypes.DEFAULT_TYPE) -> str:
    """Return the current navigation back target, defaulting to main_menu."""
    return context.user_data.get("nav_back", "main_menu")


def cleanup_state(user_id: int, user_data: dict[str, object] | None) -> None:
    """Clear the user's database action state and conversation-specific user_data keys.

    Preserves nav_back, router_key, and profile_names to maintain navigation state.
    """
    clear_action(user_id)
    if user_data is not None:
        for key in CONVERSATION_USER_DATA_KEYS:
            user_data.pop(key, None)


# Cache for fast reachability check results: {router_key: (is_reachable: bool, timestamp: float)}
_REACHABILITY_CACHE: dict[str, tuple[bool, float]] = {}
_REACHABILITY_CACHE_TTL = 30.0  # seconds


async def _fast_reachability_check(router_key: str) -> bool:
    """
    Perform a quick router reachability check (max 1 second)
    with 30-second result caching.
    """
    import time

    now = time.monotonic()
    if router_key in _REACHABILITY_CACHE:
        result, ts = _REACHABILITY_CACHE[router_key]
        if now - ts < _REACHABILITY_CACHE_TTL:
            return result

    try:
        from config import ROUTER_KEY_PREFIX
        from database.repositories.routers import get_router_by_id

        db_id = router_key.replace(ROUTER_KEY_PREFIX, "")
        router_cfg = get_router_by_id(int(db_id))

        if not router_cfg:
            _REACHABILITY_CACHE[router_key] = (False, now)
            return False

        ip = str(router_cfg["ip_address"])
        port = int(router_cfg["port"])  # type: ignore[arg-type]

        _reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=1.0)
        writer.close()
        await writer.wait_closed()
        _REACHABILITY_CACHE[router_key] = (True, now)
        return True
    except Exception as e:
        logger.warning(f"Fast reachability check failed for {router_key}: {e}")
        _REACHABILITY_CACHE[router_key] = (False, now)
        return False


def require_router(func: Callable[..., Awaitable[object]]) -> Callable[..., Awaitable[object]]:
    """Ensure a router is selected before running a handler.

    Lives in the bot (presentation) layer because it depends on presentation
    concerns (keyboards and user-facing messages). It reads the module-level
    ``get_selected_router`` so tests can monkeypatch it.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = _get_user_id(update)
        if user_id is None:
            return
        router_key = get_selected_router(user_id)

        if not router_key:
            keyboard = get_router_keyboard()
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    NO_ROUTER_SELECTED, reply_markup=keyboard
                )
            elif update.message:
                await update.message.reply_text(NO_ROUTER_SELECTED, reply_markup=keyboard)
            return

        if not await _fast_reachability_check(router_key):
            keyboard = get_router_keyboard()
            error_msg = (
                "⚠️ الراوتر المحدد مطفأ أو لا يستجيب حالياً. "
                "يرجى اختيار راوتر آخر أو المحاولة لاحقاً."
            )
            if update.callback_query:
                await update.callback_query.answer(error_msg, show_alert=True)
                await update.callback_query.edit_message_text(error_msg, reply_markup=keyboard)
            elif update.message:
                await update.message.reply_text(error_msg, reply_markup=keyboard)
            return

        context.user_data["router_key"] = router_key
        return await func(update, context)

    return wrapper


def navigation_guard(func: Callable[..., Awaitable[object]]) -> Callable[..., Awaitable[object]]:
    """Central navigation guard: enforce an active router session.

    Wraps any handler and, when no router is selected, shows the router
    picker instead of running the handler. Used by the handler registry to
    guard every *operational* handler automatically (string-based
    classification), so individual handlers never repeat the check.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = _get_user_id(update)
        if user_id is None:
            return
        router_key = get_selected_router(user_id)

        if not router_key:
            keyboard = get_router_keyboard()
            if update.callback_query:
                await update.callback_query.answer()
                await update.callback_query.edit_message_text(
                    NO_ROUTER_SELECTED, reply_markup=keyboard
                )
            elif update.message:
                await update.message.reply_text(NO_ROUTER_SELECTED, reply_markup=keyboard)
            return

        if not await _fast_reachability_check(router_key):
            keyboard = get_router_keyboard()
            error_msg = (
                "⚠️ الراوتر المحدد مطفأ أو لا يستجيب حالياً. "
                "يرجى اختيار راوتر آخر أو المحاولة لاحقاً."
            )
            if update.callback_query:
                await update.callback_query.answer(error_msg, show_alert=True)
                await update.callback_query.edit_message_text(error_msg, reply_markup=keyboard)
            elif update.message:
                await update.message.reply_text(error_msg, reply_markup=keyboard)
            return

        context.user_data["router_key"] = router_key
        return await func(update, context)

    return wrapper


def requires_router_check(
    command: str | None,
    pattern: str | None,
    func: Callable[..., object] | None = None,
) -> bool:
    """Classify a registered handler from its kwargs and target function.

    Returns True when the handler is OPERATIONAL and must be guarded
    (i.e. it is NOT a router-management screen). Pure string-based decision
    so no per-handler opt-in is required.

    Args:
        command: the CommandHandler command string, or None.
        pattern: the CallbackQueryHandler regex string, or None.
        func: the target callback function to check for exemptions.
    """
    if func is not None:
        func_name = getattr(func, "__name__", "")
        # Exempt router discovery/add text handlers
        if func_name.startswith("disc_") or func_name.startswith("manual_add_"):
            return False

    if command is not None:
        return command not in ROUTER_MGMT_COMMANDS
    if pattern is not None:
        return pattern not in _router_mgmt_regexes()
    # MessageHandler / other: treat as operational (guarded).
    return True


# Public alias — external callers should use this name.
fast_reachability_check = _fast_reachability_check
