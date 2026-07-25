import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import get_stats_keyboard
from bot.messages import (
    STATS_NO_HISTORY,
    STATS_TREND_FOOTER,
    STATS_TREND_HEADER,
    STATS_VS_YESTERDAY,
)
from core.mikrotik_api import mikrotik_api
from core.stats import stats_manager
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.error_response import send_error

logger = logging.getLogger(__name__)


async def _show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, stat_type: str) -> None:
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]
    router_name = await run_blocking(mikrotik_api.get_router_name, router_key)
    try:
        if stat_type == "hotspot":
            stats = await run_blocking(stats_manager.get_hotspot_stats, router_key)
            text = stats_manager.format_hotspot_stats(stats, router_name)

            # إضافة المقارنة مع الأمس والـ trend الأسبوعي
            if stats:
                from database.repositories.stats_snapshots import (
                    get_week_snapshots,
                    get_yesterday_snapshot,
                )

                yesterday = await run_blocking(get_yesterday_snapshot, router_key)
                vs_yesterday = stats_manager.format_vs_yesterday(stats, yesterday)
                if vs_yesterday:
                    text += STATS_VS_YESTERDAY.format(comparison=vs_yesterday)

                snapshots = await run_blocking(get_week_snapshots, router_key)
                if snapshots:
                    chart = stats_manager.format_trend_chart(snapshots)
                    text += STATS_TREND_HEADER + chart + STATS_TREND_FOOTER
                else:
                    text += STATS_NO_HISTORY
        else:
            stats = await run_blocking(stats_manager.get_userman_stats, router_key)
            text = stats_manager.format_userman_stats(stats, router_name)

        await query.edit_message_text(text, reply_markup=get_stats_keyboard(), parse_mode="HTML")
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra=f"_show_stats({stat_type})",
            reply_markup=get_stats_keyboard(),
        )


@admin_only
async def stats_hotspot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_stats(update, context, "hotspot")


@admin_only
async def stats_userman(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _show_stats(update, context, "userman")


@admin_only
async def stats_chart_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send visual trend chart PNG to the user."""
    query = update.callback_query
    await safe_answer_callback(query)
    from bot.keyboards import get_router_keyboard
    from bot.messages import NO_ROUTER_SELECTED
    from bot.router_selector import get_selected_router
    from utils.chat_cleaner import safe_edit_or_send

    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        router_key = context.user_data.get("router_key")
    if not router_key:
        if query:
            await safe_edit_or_send(query, context, NO_ROUTER_SELECTED, get_router_keyboard())
        return

    try:
        from core.chart_generator import generate_trend_chart
        from database.repositories.stats_snapshots import get_week_snapshots

        snapshots = await run_blocking(get_week_snapshots, router_key)
        router_name = await run_blocking(mikrotik_api.get_router_name, router_key)
        chart_title = f"مخطط نشاط المستخدمين ({router_name})"
        img_bytes = await run_blocking(generate_trend_chart, snapshots, chart_title)

        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=img_bytes,
                caption="📈 الرسم البياني المصور لحركة نشاط وتدفق الشبكة للأسبوع الحالي",
                reply_markup=get_stats_keyboard(),
            )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="stats_chart_callback",
            reply_markup=get_stats_keyboard(),
        )
