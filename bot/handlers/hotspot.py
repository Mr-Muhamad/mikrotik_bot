import html
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.constants import WAITING_STATS_DAY
from bot.keyboards import get_back_keyboard, get_hotspot_keyboard
from bot.messages import (
    HOTSPOT_STATS,
    HOTSPOT_STATS_DAY_INVALID,
    HOTSPOT_STATS_DAY_NOT_FOUND,
    HOTSPOT_STATS_NO_RESET,
    HOTSPOT_STATS_PROMPT,
    HOTSPOT_STATS_RESET_BLOCK,
)
from bot.router_selector import cleanup_state, nav_set
from core.hotspot_manager import hotspot_manager
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.error_response import send_error

logger = logging.getLogger(__name__)


def _categories_kwargs(stats: dict) -> dict:
    cats = stats["categories"]
    return {
        "cat_10": cats["10 GB"],
        "cat_20": cats["20 GB"],
        "cat_30": cats["30 GB"],
        "cat_40": cats["40 GB"],
        "cat_50": cats["50 GB"],
        "cat_other": cats["أخرى"],
    }


def _summary_text(stats: dict) -> str:
    return HOTSPOT_STATS.format(
        total=stats["total"],
        active=stats["active"],
        inactive=stats["inactive"],
        **_categories_kwargs(stats),
    )


def _reset_block_text(stats: dict) -> str:
    reset_list = (
        "\n".join(
            [
                f"  • {html.escape(comment)} - {html.escape(limit)}"
                for comment, limit in stats["reset_list"]
            ]
        )
        or "  لا يوجد"
    )
    return HOTSPOT_STATS_RESET_BLOCK.format(
        selected_day=stats["selected_day"],
        reset_count=len(stats["reset_list"]),
        reset_list=reset_list,
    )


@admin_only
async def hotspot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show hotspot statistics summary and ask for the reset day as text input."""
    query = update.callback_query
    await safe_answer_callback(query)
    cleanup_state(update.effective_user.id, context.user_data)
    nav_set(context, "menu_hotspot")
    router_key = context.user_data["router_key"]
    try:
        stats = await run_blocking(hotspot_manager.get_hotspot_stats, router_key)
        if not stats:
            await query.edit_message_text(
                "❌ خطأ في جلب إحصائيات Hotspot",
                reply_markup=get_hotspot_keyboard(),
            )
            return

        text = _summary_text(stats)
        reset_days = stats["reset_days"]
        if reset_days:
            text += "\n\n" + HOTSPOT_STATS_PROMPT.format(days=", ".join(map(str, reset_days)))
            await query.edit_message_text(
                text,
                reply_markup=get_back_keyboard("menu_hotspot"),
                parse_mode="HTML",
            )
            return WAITING_STATS_DAY
        else:
            text += "\n\n" + HOTSPOT_STATS_NO_RESET
            await query.edit_message_text(
                text, reply_markup=get_hotspot_keyboard(), parse_mode="HTML"
            )
            return ConversationHandler.END
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_stats",
            reply_markup=get_hotspot_keyboard(),
        )


@admin_only
async def hotspot_stats_day_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a day number typed by the user and show that day's reset list."""
    router_key = context.user_data["router_key"]
    day_text = update.message.text.strip()
    try:
        day = int(day_text)
    except (ValueError, TypeError):
        await update.message.reply_text(
            HOTSPOT_STATS_DAY_INVALID,
            reply_markup=get_back_keyboard("menu_hotspot"),
        )
        return WAITING_STATS_DAY

    if day < 1 or day > 31:
        await update.message.reply_text(
            HOTSPOT_STATS_DAY_INVALID,
            reply_markup=get_back_keyboard("menu_hotspot"),
        )
        return WAITING_STATS_DAY

    try:
        stats = await run_blocking(hotspot_manager.get_hotspot_stats, router_key, day)
        if not stats:
            await update.message.reply_text(
                "❌ خطأ في جلب إحصائيات Hotspot",
                reply_markup=get_back_keyboard("menu_hotspot"),
            )
            return WAITING_STATS_DAY

        if day not in stats["reset_days"]:
            await update.message.reply_text(
                HOTSPOT_STATS_DAY_NOT_FOUND.format(
                    day=day,
                    days=", ".join(map(str, stats["reset_days"])),
                ),
                reply_markup=get_back_keyboard("menu_hotspot"),
                parse_mode="HTML",
            )
            return WAITING_STATS_DAY

        text = _summary_text(stats) + "\n\n" + _reset_block_text(stats)
        await update.message.reply_text(
            text,
            reply_markup=get_back_keyboard("menu_hotspot"),
            parse_mode="HTML",
        )
        return WAITING_STATS_DAY
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_stats_day_input",
            reply_markup=get_back_keyboard("menu_hotspot"),
        )


__all__ = ["hotspot_stats", "hotspot_stats_day_input"]
