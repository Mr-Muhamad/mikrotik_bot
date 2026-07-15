import logging
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import (
    get_cancel_keyboard,
    get_search_results_keyboard,
    get_userman_detail_keyboard,
    get_router_keyboard,
)
from bot.messages import (
    USERMAN_SEARCH_PROMPT,
    NO_ROUTER_SELECTED,
    INVALID_SELECTION,
    UNKNOWN_NAME,
    NO_RESULTS,
)
from bot.router_selector import get_selected_router, set_current_action, nav_set, cleanup_state
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from core.userman_manager import userman_manager
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import delete_now, edit_clean, reply_final, safe_edit_plain, send_loading, send_step
from bot.handlers.constants import WAITING_USERMAN_SEARCH

logger = logging.getLogger(__name__)
MAX_SEARCH_RESULTS = 50

def _format_userman_search_results(users):
    if not users:
        return NO_RESULTS
    lines = []
    for i, u in enumerate(users, 1):
        name = u.get("name") or u.get("username") or UNKNOWN_NAME
        profile = u.get("profile", "—")
        detail = f"{i}️⃣ 👤 {name} | 📋 {profile}"
        if str(u.get("disabled", "false")).lower() == "true":
            detail += " [🔴 معطل]"
        lines.append(detail)
    header = f"🔍 تم العثور على {len(users)}"
    if len(users) > MAX_SEARCH_RESULTS:
        header += f" — يعرض أول {MAX_SEARCH_RESULTS}:"
    return header + ":\n\n" + "\n".join(lines[:MAX_SEARCH_RESULTS])

def _format_userman_detail(user):
    name = user.get("name") or user.get("username") or UNKNOWN_NAME
    pwd = user.get("password") or "—"
    profile = user.get("profile") or "—"
    is_disabled = str(user.get("disabled", "false")).lower() == "true"
    status = "🔴 معطل" if is_disabled else "🟢 نشط"
    return f"👤 مستخدم User Manager:\n📛 الاسم: {name}\n🔑 الرمز: {pwd}\n📋 البروفايل: {profile}\nوضع الحساب: {status}"

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
    loading = await send_loading(update, context, "جاري البحث...")

    try:
        hosts = await run_blocking(userman_manager.search_users, router_key, text)
    except Exception:
        hosts = []

    if len(hosts) > MAX_SEARCH_RESULTS:
        hosts = hosts[:MAX_SEARCH_RESULTS]
    context.user_data["search_um_hosts"] = hosts
    await delete_now(context, update.effective_chat.id, loading.message_id)
    
    res_text = _format_userman_search_results(hosts)
    await send_step(update, context, res_text, get_search_results_keyboard(hosts, is_userman=True))
    return WAITING_USERMAN_SEARCH

@admin_only
async def userman_search_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    
    idx = int(query.data.split("_")[-1])
    hosts = context.user_data.get("search_um_hosts")
    if not hosts or idx >= len(hosts):
        await safe_edit_plain(query, INVALID_SELECTION, get_cancel_keyboard())
        return WAITING_USERMAN_SEARCH

    context.user_data["kick_um_idx"] = idx
    h = hosts[idx]
    
    msg = _format_userman_detail(h)
    is_disabled = str(h.get("disabled", "false")).lower() == "true"
    await edit_clean(query, context, msg, get_userman_detail_keyboard(is_disabled))
        
    return WAITING_USERMAN_SEARCH

@admin_only
async def userman_search_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    action = query.data
    
    idx = context.user_data.get("kick_um_idx")
    hosts = context.user_data.get("search_um_hosts")
    router_key = context.user_data.get("router_key")
    if idx is None or not hosts or not router_key:
        return ConversationHandler.END

    h = hosts[idx]
    username = h.get("name") or h.get("username")
    
    try:
        if action == "um_kick_execute":
            sessions = await run_blocking(userman_manager.get_active_sessions, router_key)
            killed = 0
            for s in sessions:
                if str(s.get("user")) == str(username):
                    await run_blocking(userman_manager.terminate_session, router_key, s.get(".id"))
                    killed += 1
            msg = f"✅ تم طرد {killed} جلسة للمستخدم {username}."
        elif action == "um_reset_counters":
            await run_blocking(userman_manager.reset_user_counters, router_key, username)
            msg = f"✅ تم تصفير عداد المستخدم {username}."
        elif action == "um_toggle_disabled":
            is_disabled = str(h.get("disabled", "false")).lower() == "true"
            if is_disabled:
                await run_blocking(userman_manager.enable_user, router_key, username)
                h["disabled"] = "false"
                msg = f"✅ تم تفعيل المستخدم {username}."
            else:
                await run_blocking(userman_manager.disable_user, router_key, username)
                h["disabled"] = "true"
                msg = f"🔴 تم تعطيل المستخدم {username}."
        elif action == "um_delete":
            await run_blocking(userman_manager.delete_user, router_key, username)
            msg = f"🗑️ تم حذف المستخدم {username}."
            hosts.pop(idx)
            context.user_data.pop("kick_um_idx", None)
            await edit_clean(query, context, msg + "\n\n" + _format_userman_search_results(hosts), get_search_results_keyboard(hosts, is_userman=True))
            return WAITING_USERMAN_SEARCH
            
        is_disabled = str(h.get("disabled", "false")).lower() == "true"
        await query.edit_message_text(f"{msg}\n\n" + _format_userman_detail(h), reply_markup=get_userman_detail_keyboard(is_disabled))
    except Exception as e:
        await safe_edit_plain(query, f"❌ خطأ: {e}", get_userman_detail_keyboard(str(h.get("disabled", "false")).lower() == "true"))

    return WAITING_USERMAN_SEARCH

@admin_only
async def userman_search_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    hosts = context.user_data.get("search_um_hosts")
    
    if hosts:
        context.user_data.pop("kick_um_idx", None)
        res_text = _format_userman_search_results(hosts)
        await edit_clean(query, context, res_text, get_search_results_keyboard(hosts, is_userman=True))
    else:
        await edit_clean(query, context, SEARCH_PROMPT, get_cancel_keyboard())
    return WAITING_USERMAN_SEARCH
