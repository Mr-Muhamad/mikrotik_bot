import logging
import os
from telegram import Update
from telegram.ext import ContextTypes

from bot.keyboards import get_batches_keyboard, get_batch_detail_keyboard
from bot.messages import (
    MARK_PAID_FAIL,
    MARK_PAID_SUCCESS,
    PAYMENT_STATUS_LABELS,
    SALES_SUMMARY_HEADER,
    SALES_SUMMARY_ROW,
)
from bot.router_selector import cleanup_state, nav_set
from core.card_models import deserialize_cards
from database.models import list_card_batches, get_card_batch, update_batch_payment, get_sales_summary
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.chat_cleaner import send_step
from utils.formatters import format_bytes
from pdf.card_generator import card_generator
import json

logger = logging.getLogger(__name__)
def _batch_label(batch: dict) -> str:
    btype = "هوت سبوت" if batch.get("batch_type") == "hotspot" else "User Manager"
    return f"#{batch['id']} • {batch['name']} • {btype} • {batch.get('count', 0)} كارت"


@admin_only
async def batches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
    cleanup_state(update.effective_user.id, context.user_data)
    nav_set(context, "menu_hotspot")
    router_key = context.user_data["router_key"]
    try:
        batches = await run_blocking(list_card_batches, router_key)
    except Exception as e:
        logger.error(f"Failed to list batches: {e}")
        await send_step(update, context, f"❌ فشل جلب الدفعات: {str(e)[:120]}")
        return

    if not batches:
        await send_step(update, context, "📭 لا توجد دفعات كروت محفوظة بعد.")
        return

    text = "📦 الدفعات المحفوظة (الأحدث أولاً):\n\n" + "\n".join(
        f"• {_batch_label(b)} — {b.get('created_at', '')}" for b in batches
    )
    await send_step(update, context, text, get_batches_keyboard(batches))


async def batch_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        batch_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await query.answer("⚠️ رقم دفعة غير صالح", show_alert=True)
        return

    try:
        batch = await run_blocking(get_card_batch, batch_id)
    except Exception as e:
        logger.error(f"Failed to load batch {batch_id}: {e}")
        await query.edit_message_text("❌ فشل تحميل الدفعة.", reply_markup=get_batches_keyboard([]))
        return

    if not batch:
        await query.edit_message_text("⚠️ الدفعة غير موجودة.", reply_markup=get_batches_keyboard([]))
        return

    cards = batch.get("cards", [])
    total_bytes = 0
    for c in cards:
        try:
            limit = int(c.get("limit_bytes", 0) or 0)
        except (ValueError, TypeError):
            limit = 0
        total_bytes += limit

    btype = "هوت سبوت" if batch.get("batch_type") == "hotspot" else "User Manager"
    lines = [
        f"📦 تفاصيل الدفعة #{batch['id']}",
        "",
        f"🏷️ الاسم: {batch['name']}",
        f"🔧 النوع: {btype}",
        f"📋 البروفايل: {batch.get('profile', '—')}",
        f"🔢 عدد الكروت: {batch.get('count', len(cards))}",
        f"📊 إجمالي حد البيانات: {format_bytes(str(total_bytes)) if total_bytes else '—'}",
        f"🕒 الإنشاء: {batch.get('created_at', '')}",
    ]
    if batch.get("created_by"):
        lines.append(f"👤 المُنشئ: {batch['created_by']}")
    payment_status = batch.get("payment_status", "unpaid")
    customer_name = batch.get("customer_name", "")
    if customer_name:
        lines.append(f"🧑 العميل: {customer_name}")
    status_label = PAYMENT_STATUS_LABELS.get(payment_status, payment_status)
    lines.append(f"💰 حالة الدفع: {status_label}")
    if batch.get("sold_at"):
        lines.append(f"📅 تاريخ البيع: {batch['sold_at']}")
    await query.edit_message_text("\n".join(lines), reply_markup=get_batch_detail_keyboard(batch["id"], payment_status=payment_status))


async def batch_regen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        batch_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await query.answer("⚠️ رقم دفعة غير صالح", show_alert=True)
        return

    try:
        batch = await run_blocking(get_card_batch, batch_id)
    except Exception as e:
        logger.error(f"Failed to load batch {batch_id}: {e}")
        await query.answer("❌ فشل تحميل الدفعة", show_alert=True)
        return

    if not batch:
        await query.answer("⚠️ الدفعة غير موجودة", show_alert=True)
        return

    cards = deserialize_cards(_dump(batch.get("cards", [])))
    if not cards:
        await query.answer("⚠️ لا توجد كروت في هذه الدفعة", show_alert=True)
        return

    try:

        pdf_path = await run_blocking(card_generator.generate_pdf, cards)
        with open(pdf_path, "rb") as f:
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=f"batch_{batch_id}.pdf",
                caption=f"📦 دفعة #{batch_id} — {batch['name']}",
            )
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        await query.answer("✅ تم إعادة توليد PDF", show_alert=False)
    except Exception as e:
        logger.error(f"Failed to regenerate batch PDF {batch_id}: {e}")
        await query.answer("❌ فشل توليد PDF", show_alert=True)


def _dump(cards):
    """Re-serialize a list of card dicts to JSON for deserialize_cards."""
    return json.dumps(cards, ensure_ascii=False)


@admin_only
async def mark_batch_paid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير حالة الدفع لدفعة كروت (مدفوع/غير مدفوع/مرحّل)."""
    query = update.callback_query
    await query.answer()
    try:
        parts = query.data.split(":", 1)
        # query.data = mark_paid:5 | mark_unpaid:5 | mark_deferred:5
        status = parts[0].replace("mark_", "")
        batch_id = int(parts[1])
    except (IndexError, ValueError):
        await query.answer(MARK_PAID_FAIL, show_alert=True)
        return
    success = await run_blocking(update_batch_payment, batch_id, status)
    if success:
        status_label = PAYMENT_STATUS_LABELS.get(status, status)
        await query.answer(MARK_PAID_SUCCESS.format(status_label=status_label), show_alert=False)
        # أعد رسم keyboard بحالة الدفع الجديدة
        try:
            batch = await run_blocking(get_card_batch, batch_id)
            if batch:
                await query.edit_message_reply_markup(
                    reply_markup=get_batch_detail_keyboard(batch_id, payment_status=status)
                )
        except Exception:
            pass
    else:
        await query.answer(MARK_PAID_FAIL, show_alert=True)


@admin_only
async def show_sales_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض ملخص المبيعات لآخر 7 أيام."""
    query = update.callback_query
    if query:
        await query.answer()
    days = 7
    try:
        summary = await run_blocking(get_sales_summary, days)
    except Exception as e:
        logger.error(f"Failed to get sales summary: {e}")
        summary = {"total_batches": 0, "paid_count": 0, "unpaid_count": 0, "deferred_count": 0, "total_revenue": 0.0}
    text = (
        SALES_SUMMARY_HEADER.format(days=days)
        + SALES_SUMMARY_ROW.format(**summary)
    )
    await send_step(update, context, text)


__all__ = ["batches_command", "batch_select", "batch_regen", "mark_batch_paid_handler", "show_sales_summary"]
