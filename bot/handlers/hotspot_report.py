import csv
import io
import logging
import os
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.handler_utils import get_query_message
from bot.keyboards import get_report_keyboard
from bot.router_selector import cleanup_state, nav_set
from core.hotspot_manager import hotspot_manager
from core.mikrotik_api import mikrotik_api
from core.stats import stats_manager
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.chat_cleaner import send_step

logger = logging.getLogger(__name__)


def build_csv(report: dict) -> str:
    """Build a UTF-8-sig CSV string from a usage report's rows."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "name",
            "profile",
            "status",
            "bytes_in",
            "bytes_out",
            "total_bytes",
            "total_str",
            "limit_str",
            "percent",
            "comment",
        ]
    )
    for r in report.get("rows", []):
        writer.writerow(
            [
                r.get("name", ""),
                r.get("profile", ""),
                r.get("status", ""),
                r.get("bytes_in", 0),
                r.get("bytes_out", 0),
                r.get("total_bytes", 0),
                r.get("total_str", ""),
                r.get("limit_str", ""),
                f"{r.get('percent', 0.0):.1f}",
                r.get("comment", ""),
            ]
        )
    return output.getvalue()


@admin_only
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    cleanup_state(update.effective_user.id, context.user_data)
    nav_set(context, "menu_stats")
    router_key = context.user_data["router_key"]
    try:
        report = await run_blocking(hotspot_manager.build_usage_report, router_key)
        router_name = await run_blocking(mikrotik_api.get_router_name, router_key)
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        await send_step(update, context, f"❌ فشل إنشاء التقرير: {str(e)[:120]}")
        return

    context.user_data["report"] = report
    text = stats_manager.format_hotspot_usage_report(report, router_name)
    await send_step(update, context, text, get_report_keyboard())


async def report_export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report = context.user_data.get("report")
    if not report:
        await query.edit_message_text(
            "⚠️ لا يوجد تقرير محمّل. شغّل أمر /report أولاً.",
            reply_markup=get_report_keyboard(),
        )
        return

    csv_text = build_csv(report)
    filename = f"hotspot_report_{report.get('router_key', 'router')}.csv"
    fd, path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(csv_text.encode("utf-8-sig"))
        with open(path, "rb") as f:
            msg = get_query_message(query)
            if msg is None:
                await query.answer("❌ فشل إرسال الملف", show_alert=True)
                return
            await context.bot.send_document(
                chat_id=msg.chat_id,
                document=f,
                filename=filename,
                caption="📊 تقرير استخدام Hotspot (CSV)",
            )
        await query.answer("✅ تم إرسال ملف CSV", show_alert=False)
    except Exception as e:
        logger.error(f"CSV export failed: {e}")
        await query.answer("❌ فشل تصدير CSV", show_alert=True)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


__all__ = ["report_command", "report_export_csv", "build_csv"]
