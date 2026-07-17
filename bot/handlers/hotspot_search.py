import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import (
    get_blocked_macs_keyboard,
    get_cancel_keyboard,
    get_host_detail_keyboard,
    get_hotspot_keyboard,
    get_router_keyboard,
    get_search_results_keyboard,
)
from bot.messages import (
    BLOCK_MAC_FAIL,
    BLOCK_MAC_SUCCESS,
    BLOCKED_LIST_EMPTY,
    BLOCKED_LIST_HEADER,
    DEVICE_NOT_FOUND,
    DEVICE_NOT_SELECTED,
    HOST_KICK_FAILED,
    INVALID_SELECTION,
    NO_RESULTS,
    NO_ROUTER_SELECTED,
    SEARCH_PROMPT,
    SEARCHING_HOSTS,
    UNBLOCK_MAC_FAIL,
    UNBLOCK_MAC_SUCCESS,
    UNKNOWN_NAME,
    SEARCH_ADVANCED_HINT,
)
from utils.formatters import format_bytes
from bot.router_selector import cleanup_state, get_selected_router, nav_set, set_current_action
from core.hotspot_manager import hotspot_manager
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import delete_now, edit_clean, reply_final, safe_edit_plain, send_loading, send_step
from utils.error_response import send_error
from .constants import WAITING_HOTSPOT_SEARCH

logger = logging.getLogger(__name__)

SEARCH_PROMPT_ADV = SEARCH_PROMPT + SEARCH_ADVANCED_HINT
MAX_SEARCH_RESULTS = 50


@admin_only
async def hotspot_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, SEARCH_PROMPT_ADV, get_cancel_keyboard())
    else:
        await send_step(update, context, SEARCH_PROMPT_ADV, get_cancel_keyboard())
    set_current_action(update.effective_user.id, "hotspot_search")
    nav_set(context, "menu_hotspot")
    return WAITING_HOTSPOT_SEARCH




@admin_only
async def hotspot_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        await reply_final(update, context, NO_ROUTER_SELECTED, get_router_keyboard())
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    text = update.message.text.strip()
    loading = await send_loading(update, context, SEARCHING_HOSTS)

    if text.startswith("user:"):
        hosts = await _search_users(router_key, text[5:].strip())
    elif text.startswith("mac:"):
        hosts = await _search_hosts_by_field(router_key, "mac-address", text[4:].strip())
    elif text.startswith("comment:"):
        hosts = await _search_users(router_key, text[8:].strip())
    elif text.startswith("ip:"):
        hosts = await _search_hosts_by_field(router_key, "address", text[3:].strip())
    else:
        hosts = await _search_hosts_with_users(router_key, text)

    if len(hosts) > MAX_SEARCH_RESULTS:
        hosts = hosts[:MAX_SEARCH_RESULTS]
    context.user_data["search_hosts"] = hosts
    await delete_now(context, update.effective_chat.id, loading.message_id)
    await send_step(update, context, _format_search_results_text(hosts), get_search_results_keyboard(hosts, is_userman=False))
    return WAITING_HOTSPOT_SEARCH


async def _search_users(router_key: str, term: str) -> list[dict]:
    try:
        users = await run_blocking(hotspot_manager.search_users, router_key, term)
    except Exception:
        return []
    return [{
        "host-name": u.get("name", "—"),
        "address": "", "mac-address": "",
        "user": u.get("name", ""),
        "_limit": u.get("limit-bytes-total", ""),
        "_uptime": u.get("limit-uptime", ""),
        "_comment": u.get("comment", ""),
        "_disabled": u.get("disabled", "false"),
    } for u in users]


async def _search_hosts_by_field(router_key: str, field: str, value: str) -> list[dict]:
    """Search hotspot hosts by a specific field (mac-address or address).

    Delegates to :meth:`HotspotManager.search_hosts` so the host list is fetched
    and enriched through the core layer; the field-specific substring filter is
    then applied to preserve the exact prefix semantics (``mac:`` / ``ip:``).
    """
    try:
        hosts = await run_blocking(hotspot_manager.search_hosts, router_key, value)
    except Exception:
        return []
    value = value.lower().strip()
    return [h for h in hosts if value in str(h.get(field) or "").lower()]


async def _search_hosts_with_users(router_key: str, query: str) -> list[dict]:
    try:
        hosts = await run_blocking(hotspot_manager.search_hosts, router_key, query)
        try:
            users = await run_blocking(hotspot_manager.search_users, router_key, query)
        except Exception:
            users = []
    except Exception:
        return []
    user_map = {}
    for u in users:
        key = str(u.get("name") or "").lower()
        user_map[key] = u
    for h in hosts:
        uname = str(h.get("user") or "").lower()
        if uname in user_map:
            u = user_map[uname]
            h["_limit"] = u.get("limit-bytes-total", "")
            h["_uptime"] = u.get("limit-uptime", "")
            h["_comment"] = u.get("comment", "")
            h["_disabled"] = u.get("disabled", "false")
    return hosts


def _format_search_results_text(hosts):
    if not hosts:
        return NO_RESULTS
    lines = []
    for i, h in enumerate(hosts, 1):
        name = str(h.get("host-name") or h.get("user") or "") or UNKNOWN_NAME
        ip = str(h.get("address") or "") or "—"
        mac = str(h.get("mac-address") or "") or "—"
        detail = f"{i}️⃣ 🏠 {name}\n    🌐 {ip}\n    🔗 {mac}"
        limit = h.get("_limit", "")
        uptime = h.get("_uptime", "")
        comment = h.get("_comment", "")
        if limit:
            detail += f"\n    📊 {format_bytes(limit)}"
        if uptime:
            detail += f" | ⏰ {uptime}"
        if comment:
            detail += f"\n    💬 {comment[:30]}"
        if str(h.get("_disabled", "false")).lower() == "true":
            detail += "\n    🔴 معطل"
        lines.append(detail)
    header = f"🔍 تم العثور على {len(hosts)}"
    if len(hosts) > MAX_SEARCH_RESULTS:
        header += f" — يعرض أول {MAX_SEARCH_RESULTS}:"
    return header + ":\n\n" + "\n\n".join(lines[:MAX_SEARCH_RESULTS])


@admin_only
async def hotspot_search_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    hosts = context.user_data.get("search_hosts")
    on_host_detail = context.user_data.get("kick_host_idx") is not None
    if on_host_detail and hosts is not None:
        context.user_data.pop("kick_host_idx", None)
        await edit_clean(query, context, _format_search_results_text(hosts), get_search_results_keyboard(hosts))
        return WAITING_HOTSPOT_SEARCH
    if hosts is not None:
        context.user_data.pop("search_hosts", None)
        context.user_data.pop("kick_host_idx", None)
        await edit_clean(query, context, SEARCH_PROMPT_ADV, get_cancel_keyboard())
        return WAITING_HOTSPOT_SEARCH
    await edit_clean(query, context, SEARCH_PROMPT_ADV, get_cancel_keyboard())
    return WAITING_HOTSPOT_SEARCH


@admin_only
async def hotspot_show_host(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    try:
        idx = int(query.data.split("_")[-1])
        hosts = context.user_data.get("search_hosts", [])
        if idx < 0 or idx >= len(hosts):
            await safe_edit_plain(query, context, INVALID_SELECTION, reply_markup=get_hotspot_keyboard())
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END
        host = hosts[idx]
        context.user_data["kick_host_idx"] = idx
        name = host.get("host-name") or host.get("user") or UNKNOWN_NAME
        ip = host.get("address") or "—"
        mac = host.get("mac-address") or "—"
        text = f"🏠 {name}\n🌐 {ip}\n🔗 {mac}"
        is_disabled = str(host.get("_disabled", "false")).lower() == "true"
        await safe_edit_plain(query, context, text, reply_markup=get_host_detail_keyboard(is_disabled=is_disabled, mac=mac if mac != "—" else ""))
    except Exception as e:
        await send_error(update, context, e, log_extra="hotspot_show_host", reply_markup=get_hotspot_keyboard())
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    return WAITING_HOTSPOT_SEARCH


@admin_only
async def hotspot_host_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = None
    try:
        idx = context.user_data.get("kick_host_idx")
        if idx is None:
            await safe_edit_plain(query, context, DEVICE_NOT_SELECTED, reply_markup=get_hotspot_keyboard())
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END
        hosts = context.user_data.get("search_hosts", [])
        if idx < 0 or idx >= len(hosts):
            await safe_edit_plain(query, context, DEVICE_NOT_FOUND, reply_markup=get_hotspot_keyboard())
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END
        host = hosts[idx]
        router_key = get_selected_router(query.from_user.id)
        if not router_key:
            await safe_edit_plain(query, context, NO_ROUTER_SELECTED, reply_markup=get_router_keyboard())
            cleanup_state(query.from_user.id, context.user_data)
            return ConversationHandler.END
        target = host.get("mac-address") or host.get("address") or ""
        success, host_name = await run_blocking(hotspot_manager.kick_host, router_key, target)
        if success:
            await safe_edit_plain(query, context, f"✅ تم طرد الجهاز «{host_name}» بنجاح", reply_markup=get_hotspot_keyboard())
        else:
            await safe_edit_plain(query, context, HOST_KICK_FAILED, reply_markup=get_hotspot_keyboard())
    except Exception as e:
        await send_error(update, context, e, router_key=router_key, log_extra="hotspot_host_action", reply_markup=get_hotspot_keyboard())
    cleanup_state(query.from_user.id, context.user_data)
    return ConversationHandler.END


@admin_only
async def block_mac_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حظر MAC دائم في address-list=hotspot_blocked على الراوتر."""
    from utils.callback_utils import is_duplicate_callback
    query = update.callback_query
    await safe_answer_callback(query)
    if is_duplicate_callback(query.data, update.effective_user.id):
        return WAITING_HOTSPOT_SEARCH
    router_key = get_selected_router(query.from_user.id)
    if not router_key:
        await safe_edit_plain(query, context, NO_ROUTER_SELECTED, reply_markup=get_router_keyboard())
        return ConversationHandler.END
    try:
        mac = query.data.split(":", 1)[1]
    except (IndexError, ValueError):
        await safe_edit_plain(query, context, "❌ بيانات الحظر غير صالحة", reply_markup=get_hotspot_keyboard())
        return WAITING_HOTSPOT_SEARCH
    success = await run_blocking(hotspot_manager.block_mac, router_key, mac)
    if success:
        await safe_edit_plain(query, context, BLOCK_MAC_SUCCESS.format(mac=mac), reply_markup=get_hotspot_keyboard())
    else:
        await safe_edit_plain(query, context, BLOCK_MAC_FAIL, reply_markup=get_hotspot_keyboard())
    cleanup_state(query.from_user.id, context.user_data)
    return ConversationHandler.END


@admin_only
async def unblock_mac_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع حظر MAC من address-list=hotspot_blocked."""
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    if not router_key:
        await safe_edit_plain(query, context, NO_ROUTER_SELECTED, reply_markup=get_router_keyboard())
        return ConversationHandler.END
    try:
        mac = query.data.split(":", 1)[1]
    except (IndexError, ValueError):
        await safe_edit_plain(query, context, "❌ بيانات رفع الحظر غير صالحة", reply_markup=get_hotspot_keyboard())
        return ConversationHandler.END
    success = await run_blocking(hotspot_manager.unblock_mac, router_key, mac)
    if success:
        await safe_edit_plain(query, context, UNBLOCK_MAC_SUCCESS.format(mac=mac), reply_markup=get_hotspot_keyboard())
    else:
        await safe_edit_plain(query, context, UNBLOCK_MAC_FAIL, reply_markup=get_hotspot_keyboard())
    return ConversationHandler.END


@admin_only
async def show_blocked_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة MACs المحظورة على الراوتر الحالي."""
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    if not router_key:
        await safe_edit_plain(query, context, NO_ROUTER_SELECTED, reply_markup=get_router_keyboard())
        return ConversationHandler.END
    blocked = await run_blocking(hotspot_manager.get_blocked_macs, router_key)
    if not blocked:
        await safe_edit_plain(query, context, BLOCKED_LIST_EMPTY, reply_markup=get_blocked_macs_keyboard([]))
    else:
        text = BLOCKED_LIST_HEADER.format(count=len(blocked))
        await safe_edit_plain(query, context, text, reply_markup=get_blocked_macs_keyboard(blocked))
    return WAITING_HOTSPOT_SEARCH

