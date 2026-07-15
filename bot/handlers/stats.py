import logging
from telegram import Update
from utils.async_blocking import run_blocking
from telegram.ext import ContextTypes
from bot.keyboards import get_stats_keyboard
from core.stats import stats_manager
from core.mikrotik_api import mikrotik_api
from utils.admin_decorator import admin_only
from bot.router_selector import require_router
from utils.error_response import send_error
from utils.callback_utils import safe_answer_callback

logger = logging.getLogger(__name__)


async def _show_stats(update, context, stat_type):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]
    router_name = await run_blocking(mikrotik_api.get_router_name, router_key)
    try:
        if stat_type == "hotspot":
            stats = await run_blocking(stats_manager.get_hotspot_stats, router_key)
            text = stats_manager.format_hotspot_stats(stats, router_name)
        else:
            stats = await run_blocking(stats_manager.get_userman_stats, router_key)
            text = stats_manager.format_userman_stats(stats, router_name)
        await query.edit_message_text(text, reply_markup=get_stats_keyboard())
    except Exception as e:
        await send_error(
            update, context, e,
            router_key=router_key,
            log_extra=f"_show_stats({stat_type})",
            reply_markup=get_stats_keyboard(),
        )


@admin_only
@require_router
async def stats_hotspot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_stats(update, context, "hotspot")


@admin_only
@require_router
async def stats_userman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_stats(update, context, "userman")
