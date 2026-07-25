import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from core.mikrotik_client import RouterOSRow

__all__ = [
    "userman_search_start",
    "userman_search_query",
    "userman_search_select",
    "userman_search_action",
    "userman_search_back",
    "userman_search_page_handler",
    "userman_search_add_profile",
    "userman_search_add_profile_selected",
]

from bot.handlers.constants import WAITING_USERMAN_SEARCH
from bot.keyboards import (
    get_cancel_keyboard,
    get_profile_keyboard,
    get_router_keyboard,
    get_search_results_keyboard,
    get_userman_detail_keyboard,
)
from bot.messages import (
    INVALID_SELECTION,
    NO_RESULTS,
    NO_ROUTER_SELECTED,
    UNKNOWN_NAME,
    USERMAN_ADD_PROFILE_FAILED,
    USERMAN_ADD_PROFILE_PROMPT,
    USERMAN_ADD_PROFILE_SUCCESS,
    USERMAN_NO_PROFILES_TO_ADD,
    USERMAN_SEARCH_DELETED,
    USERMAN_SEARCH_DISABLED,
    USERMAN_SEARCH_ENABLED,
    USERMAN_SEARCH_ERROR,
    USERMAN_SEARCH_FOUND,
    USERMAN_SEARCH_KICKED,
    USERMAN_SEARCH_LOADING,
    USERMAN_SEARCH_OFFLINE,
    USERMAN_SEARCH_PROMPT,
    USERMAN_SEARCH_RESET,
    USERMAN_SEARCH_RESULT,
    USERMAN_SEARCH_SESSION_EXPIRED,
    USERMAN_SEARCH_STATUS_OFF,
    USERMAN_SEARCH_STATUS_ON,
    USERMAN_SEARCH_UNKNOWN_ERR,
)
from bot.router_selector import (
    cleanup_state,
    get_selected_router,
    nav_set,
    set_current_action,
)
from core.profile_sync import profile_sync
from core.userman_manager import userman_manager
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import is_duplicate_callback, safe_answer_callback
from utils.chat_cleaner import (
    delete_now,
    edit_clean,
    reply_final,
    safe_edit_plain,
    send_loading,
    send_step,
)
from utils.pagination import Paginator

logger = logging.getLogger(__name__)
MAX_SEARCH_RESULTS = 50


def _format_userman_search_results(paginator: Paginator) -> str:
    if not paginator.items:
        return NO_RESULTS
    lines = []
    # Use absolute index
    start_idx = paginator.page * paginator.page_size
    for i, u in enumerate(paginator.current_items):
        abs_idx = start_idx + i
        name = u.get("name") or u.get("username") or UNKNOWN_NAME
        profile = u.get("profile", "—")
        detail = f"{abs_idx + 1}️⃣ 👤 {name} | 📋 {profile}"
        if str(u.get("disabled", "false")).lower() == "true":
            detail += USERMAN_SEARCH_OFFLINE
        lines.append(detail)
    header = USERMAN_SEARCH_FOUND.format(count=len(paginator.items))
    header += f"\nالصفحة {paginator.page + 1} من {paginator.total_pages} ({paginator.slice_info})"
    return header + ":\n\n" + "\n".join(lines)


def _format_userman_detail(user: RouterOSRow) -> str:
    name = user.get("name") or user.get("username") or UNKNOWN_NAME
    raw_pwd = user.get("password") or "—"
    pwd = raw_pwd if raw_pwd == "—" else (raw_pwd[:2] + "••••" if len(raw_pwd) > 2 else "••••")
    profile = user.get("profile") or "—"
    is_disabled = str(user.get("disabled", "false")).lower() == "true"
    status = USERMAN_SEARCH_STATUS_OFF if is_disabled else USERMAN_SEARCH_STATUS_ON
    return USERMAN_SEARCH_RESULT.format(name=name, pwd=pwd, profile=profile, status=status)


@admin_only
async def userman_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, USERMAN_SEARCH_PROMPT, get_cancel_keyboard())
    else:
        await send_step(update, context, USERMAN_SEARCH_PROMPT, get_cancel_keyboard())
    set_current_action(update.effective_user.id, "userman_search")
    nav_set(context, "menu_userman")
    return WAITING_USERMAN_SEARCH


@admin_only
async def userman_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        await reply_final(update, context, NO_ROUTER_SELECTED, get_router_keyboard())
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    text = update.message.text.strip()
    loading = await send_loading(update, context, USERMAN_SEARCH_LOADING)

    try:
        hosts = await run_blocking(userman_manager.search_users, router_key, text)
    except Exception:
        hosts = []

    context.user_data["search_um_hosts"] = hosts
    await delete_now(context, update.effective_chat.id, loading.message_id)

    paginator = Paginator(hosts, page=0)

    res_text = _format_userman_search_results(paginator)
    await send_step(
        update, context, res_text, get_search_results_keyboard(paginator, is_userman=True)
    )
    return WAITING_USERMAN_SEARCH


@admin_only
async def userman_search_page_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    try:
        page = int(query.data.split("_")[-1])
    except (ValueError, IndexError):
        page = 0

    hosts = context.user_data.get("search_um_hosts")
    if hosts is None:
        await safe_edit_plain(
            query,
            context,
            "⚠️ عذراً، انتهت صلاحية البحث. يرجى البحث مجدداً.",
            get_cancel_keyboard(),
        )
        return WAITING_USERMAN_SEARCH

    paginator = Paginator(hosts, page=page)
    res_text = _format_userman_search_results(paginator)
    await query.edit_message_text(
        res_text, reply_markup=get_search_results_keyboard(paginator, is_userman=True)
    )
    return WAITING_USERMAN_SEARCH


@admin_only
async def userman_search_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    idx = int(query.data.split("_")[-1])
    hosts = context.user_data.get("search_um_hosts")
    if not hosts or idx >= len(hosts):
        await safe_edit_plain(query, context, INVALID_SELECTION, get_cancel_keyboard())
        return WAITING_USERMAN_SEARCH

    context.user_data["kick_um_idx"] = idx
    h = hosts[idx]

    msg = _format_userman_detail(h)
    is_disabled = str(h.get("disabled", "false")).lower() == "true"
    await edit_clean(query, context, msg, get_userman_detail_keyboard(is_disabled))

    return WAITING_USERMAN_SEARCH


async def _execute_um_action(
    action: str,
    h: RouterOSRow,
    router_key: str,
    hosts: list[RouterOSRow],
    idx: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    """Execute a userman action (kick, reset, toggle, delete) and return result message."""
    username = h.get("name") or h.get("username")

    if action == "um_kick_execute":
        sessions = await run_blocking(userman_manager.get_active_sessions, router_key)
        killed = 0
        for s in sessions:
            if str(s.get("user")) == str(username):
                await run_blocking(userman_manager.terminate_session, router_key, s.get(".id"))
                killed += 1
        return USERMAN_SEARCH_KICKED.format(killed=killed, username=username)

    if action == "um_reset_counters":
        await run_blocking(userman_manager.reset_user_counters, router_key, username)
        return USERMAN_SEARCH_RESET.format(username=username)

    if action == "um_toggle_disabled":
        is_disabled = str(h.get("disabled", "false")).lower() == "true"
        if is_disabled:
            await run_blocking(userman_manager.enable_user, router_key, username)
            h["disabled"] = "false"
            return USERMAN_SEARCH_ENABLED.format(username=username)
        await run_blocking(userman_manager.disable_user, router_key, username)
        h["disabled"] = "true"
        return USERMAN_SEARCH_DISABLED.format(username=username)

    if action == "um_delete":
        await run_blocking(userman_manager.delete_user, router_key, username)
        hosts.pop(idx)
        context.user_data.pop("kick_um_idx", None)
        return USERMAN_SEARCH_DELETED.format(username=username)

    return ""


async def userman_search_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    if is_duplicate_callback(query.data, update.effective_user.id):
        return
    action = str(query.data)

    idx = context.user_data.get("kick_um_idx")
    hosts = context.user_data.get("search_um_hosts")
    router_key = get_selected_router(update.effective_user.id)
    if idx is None or not hosts or not router_key:
        await safe_edit_plain(
            query,
            context,
            USERMAN_SEARCH_SESSION_EXPIRED,
            get_cancel_keyboard(),
        )
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    h = hosts[idx]

    try:
        msg = await _execute_um_action(action, h, router_key, hosts, idx, context)

        if action == "um_delete":
            paginator = Paginator(hosts, page=0)
            await edit_clean(
                query,
                context,
                msg + "\n\n" + _format_userman_search_results(paginator),
                get_search_results_keyboard(paginator, is_userman=True),
            )
            return WAITING_USERMAN_SEARCH

        is_disabled = str(h.get("disabled", "false")).lower() == "true"
        await query.edit_message_text(
            f"{msg}\n\n" + _format_userman_detail(h),
            reply_markup=get_userman_detail_keyboard(is_disabled),
        )
    except Exception as e:
        from utils.error_response import sanitize_error_text

        sanitized_err = sanitize_error_text(str(e))
        kb = (
            get_userman_detail_keyboard(str(h.get("disabled", "false")).lower() == "true")
            if "h" in locals() and h
            else get_cancel_keyboard()
        )
        await safe_edit_plain(
            query,
            context,
            USERMAN_SEARCH_ERROR.format(e=sanitized_err),
            kb,
        )

    return WAITING_USERMAN_SEARCH


@admin_only
async def userman_search_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    hosts = context.user_data.get("search_um_hosts")
    on_detail = context.user_data.get("kick_um_idx") is not None

    if on_detail and hosts:
        context.user_data.pop("kick_um_idx", None)

        paginator = Paginator(hosts, page=0)
        res_text = _format_userman_search_results(paginator)
        await edit_clean(
            query,
            context,
            res_text,
            get_search_results_keyboard(paginator, is_userman=True),
        )
        return WAITING_USERMAN_SEARCH

    context.user_data.pop("search_um_hosts", None)
    context.user_data.pop("kick_um_idx", None)
    await edit_clean(query, context, USERMAN_SEARCH_PROMPT, get_cancel_keyboard())
    return WAITING_USERMAN_SEARCH


@admin_only
async def userman_search_add_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    idx = context.user_data.get("kick_um_idx")
    hosts = context.user_data.get("search_um_hosts")
    router_key = get_selected_router(update.effective_user.id)
    if idx is None or not hosts or not router_key:
        return ConversationHandler.END

    h = hosts[idx]
    username = h.get("name") or h.get("username")
    context.user_data["add_profile_username"] = username

    try:
        profiles = await run_blocking(profile_sync.get_userman_profiles, router_key)
    except Exception:
        profiles = []

    if not profiles:
        await safe_edit_plain(
            query,
            context,
            USERMAN_NO_PROFILES_TO_ADD,
            get_userman_detail_keyboard(str(h.get("disabled", "false")).lower() == "true"),
        )
        return WAITING_USERMAN_SEARCH

    context.user_data["add_profile_list"] = profiles
    await safe_edit_plain(
        query,
        context,
        USERMAN_ADD_PROFILE_PROMPT,
        get_profile_keyboard(profiles, "um_profile", back_callback="search_back"),
    )
    return WAITING_USERMAN_SEARCH


@admin_only
async def userman_search_add_profile_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    if is_duplicate_callback(query.data, update.effective_user.id):
        return

    username = context.user_data.get("add_profile_username")
    profiles = context.user_data.get("add_profile_list")
    router_key = get_selected_router(update.effective_user.id)
    if not username or not profiles or not router_key:
        return ConversationHandler.END

    try:
        idx = int(query.data.split("_")[-1])
        profile = profiles[idx]
    except (ValueError, IndexError):
        await safe_edit_plain(query, context, INVALID_SELECTION, get_userman_detail_keyboard(False))
        return WAITING_USERMAN_SEARCH

    try:
        linked, err = await run_blocking(
            userman_manager.add_profile_to_user, router_key, username, profile
        )
    except Exception:
        linked, err = False, "حدث خطأ غير متوقع"

    if linked:
        msg = USERMAN_ADD_PROFILE_SUCCESS.format(profile=profile, username=username)
    else:
        msg = USERMAN_ADD_PROFILE_FAILED.format(
            profile=profile, username=username, error=err or USERMAN_SEARCH_UNKNOWN_ERR
        )

    hosts = context.user_data.get("search_um_hosts")
    sel_idx = context.user_data.get("kick_um_idx")
    selected = hosts[sel_idx] if (hosts and sel_idx is not None and sel_idx < len(hosts)) else {}
    is_disabled = str(selected.get("disabled", "false")).lower() == "true"
    await safe_edit_plain(query, context, msg, get_userman_detail_keyboard(is_disabled))
    context.user_data.pop("add_profile_username", None)
    context.user_data.pop("add_profile_list", None)
    return WAITING_USERMAN_SEARCH
