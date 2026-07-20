import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.handler_utils import ack_callback, get_query_message, parse_router_id
from bot.keyboards import get_main_keyboard, get_reboot_keyboard, get_router_keyboard
from bot.messages import (
    NO_REBOOT_ROUTER,
    REBOOT_CANCELLED,
    REBOOT_CONFIRM,
    REBOOT_IN_PROGRESS,
    ROUTER_NOT_FOUND,
)
from bot.router_selector import get_selected_router
from config import ROUTER_KEY_PREFIX
from core.mikrotik_api import mikrotik_api
from database.models import get_router_by_id, log_action
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import is_duplicate_callback, safe_answer_callback
from utils.chat_cleaner import clean_command, schedule_delete, send_and_track

logger = logging.getLogger(__name__)


@require_role("admin")
@admin_only
async def reboot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await clean_command(update, context)
    chat_id = update.effective_chat.id
    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        await send_and_track(
            context,
            chat_id,
            NO_REBOOT_ROUTER,
            get_router_keyboard(),
        )
        return
    router_name = await run_blocking(mikrotik_api.get_router_name, router_key)
    await send_and_track(
        context,
        chat_id,
        REBOOT_CONFIRM.format(router_name),
        get_reboot_keyboard(router_key),
    )


@require_role("admin")
@admin_only
async def reboot_router_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query is None:
        return
    if is_duplicate_callback(query.data, update.effective_user.id):
        return
    await safe_answer_callback(query)
    if query.data.startswith("reboot_yes_"):
        router_key = query.data.replace("reboot_yes_", "")
        if not router_key:
            await query.edit_message_text(NO_REBOOT_ROUTER, reply_markup=get_router_keyboard())
            return
        router_name = await run_blocking(mikrotik_api.get_router_name, router_key)
        await query.edit_message_text(REBOOT_IN_PROGRESS)
        try:
            mikrotik_api.execute_non_blocking(router_key, "system/reboot")
            await run_blocking(log_action, "reboot", router_name, router_key, query.from_user.id)
            await query.edit_message_text(
                f"✅ تم بدء إعادة تشغيل {router_name}\n\n⏳ قد يستغرق الأمر 10-30 ثانية حتى يعود الراوتر متاحاً",  # noqa: E501
                reply_markup=get_main_keyboard(),
            )
            msg = get_query_message(query)
            if msg is not None:
                await schedule_delete(context, msg.chat_id, msg.message_id)
        except Exception as e:
            logger.info(f"Reboot command sent (connection may be lost): {e}")
            await query.edit_message_text(
                f"✅ تم بدء إعادة تشغيل {router_name}\n\n⏳ قد يستغرق الأمر 10-30 ثانية حتى يعود الراوتر متاحاً",  # noqa: E501
                reply_markup=get_main_keyboard(),
            )
            msg = get_query_message(query)
            if msg is not None:
                await schedule_delete(context, msg.chat_id, msg.message_id)
    elif query.data == "reboot_no":
        await query.edit_message_text(REBOOT_CANCELLED, reply_markup=get_main_keyboard())


@require_role("admin")
@admin_only
async def reboot_saved_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = await ack_callback(update)
    router_id = await parse_router_id(query, "reboot_router_")
    if router_id is None:
        return
    router = await run_blocking(get_router_by_id, router_id, decrypt=False)
    if not router:
        await query.edit_message_text(ROUTER_NOT_FOUND)
        return
    router_name = router.get("identity", router["ip_address"])
    await query.edit_message_text(
        REBOOT_CONFIRM.format(router_name),
        reply_markup=get_reboot_keyboard(f"{ROUTER_KEY_PREFIX}{router_id}"),
    )
