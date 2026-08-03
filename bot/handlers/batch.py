import json
import logging
import os
from typing import cast

import telegram.error
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.constants import WAITING_BATCHES_SEARCH, WAITING_SHARE_RECIPIENT
from bot.handlers.handler_utils import get_query_message
from bot.keyboards import (
    get_back_keyboard,
    get_batch_detail_keyboard,
    get_batches_keyboard,
    get_cancel_keyboard,
)
from bot.messages import (
    BATCHES_SEARCH_PROMPT,
    MARK_PAID_FAIL,
    MARK_PAID_SUCCESS,
    PAYMENT_STATUS_LABELS,
    SALES_SUMMARY_HEADER,
    SALES_SUMMARY_ROW,
    SHARE_CARD_FAIL,
    SHARE_CARD_INVALID_ID,
    SHARE_CARD_NO_CARDS,
    SHARE_CARD_PROMPT,
    SHARE_CARD_SUCCESS,
    SHARE_CARD_TEMPLATE,
)
from bot.router_selector import cleanup_state, nav_set
from core.card_models import deserialize_cards
from core.mikrotik_client import RouterOSRow
from database.repositories.card_batches import (
    get_card_batch,
    get_card_batches_count,
    get_sales_summary,
    list_card_batches,
    search_card_batches,
    update_batch_payment,
)
from database.repositories.pdf_settings import get_pdf_settings
from pdf.card_generator import card_generator
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import is_duplicate_callback
from utils.chat_cleaner import send_step
from utils.formatters import format_bytes

logger = logging.getLogger(__name__)


def _batch_label(batch: RouterOSRow) -> str:
    btype = "هوت سبوت" if batch.get("batch_type") == "hotspot" else "User Manager"
    return f"#{batch['id']} • {batch['name']} • {btype} • {batch.get('count', 0)} كارت"


@admin_only
async def batches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show first page of saved card batches list.

    Args:
        update: Callback query from menu button.
        context: Conversation context with router_key.

    Returns:
        None.
    """
    query = update.callback_query
    if query:
        await query.answer()
    cleanup_state(update.effective_user.id, context.user_data)
    nav_set(context, "menu_reports")
    await _show_batches_page(update, context, page=0)


@admin_only
async def batches_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user for search term to filter card batches."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BATCHES_SEARCH_PROMPT, reply_markup=get_cancel_keyboard())
    return WAITING_BATCHES_SEARCH


@admin_only
async def batches_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search card batches by customer_name, comment_prefix, or name."""
    search_term = (update.message.text or "").strip()
    if not search_term:
        await send_step(update, context, BATCHES_SEARCH_PROMPT, get_cancel_keyboard())
        return WAITING_BATCHES_SEARCH

    router_key = context.user_data.get("router_key")
    try:
        results = await run_blocking(search_card_batches, search_term, router_key, 20, 0)
    except (ValueError, OSError) as e:
        logger.error("batches_search failed: %s", e)
        await send_step(update, context, "❌ فشل البحث: خطأ غير متوقع")
        return ConversationHandler.END

    if not results:
        await send_step(
            update, context,
            f"📭 لا توجد نتائج لـ \"{search_term}\"",
            get_cancel_keyboard(),
        )
        return WAITING_BATCHES_SEARCH

    text = f"🔍 نتائج البحث عن \"{search_term}\":\n\n" + "\n".join(
        f"• {_batch_label(b)} — {b.get('created_at', '')}" for b in results
    )
    keyboard = get_batches_keyboard(results, page=0, total=len(results), page_size=20)
    await send_step(update, context, text, keyboard)
    return ConversationHandler.END


async def _show_batches_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    router_key = context.user_data.get("router_key")
    if not router_key:
        return

    page_size = 10
    offset = page * page_size
    try:
        total = await run_blocking(get_card_batches_count, router_key)
        batches = await run_blocking(list_card_batches, router_key, page_size, offset)
    except (ValueError, OSError) as e:
        logger.error("Failed to list batches: %s", e)
        await send_step(update, context, "❌ فشل جلب الدفعات: خطأ غير متوقع")
        return

    if not batches and page == 0:
        await send_step(update, context, "📭 لا توجد دفعات كروت محفوظة بعد.")
        return

    text = "📦 الدفعات المحفوظة (الأحدث أولاً):\n\n" + "\n".join(
        f"• {_batch_label(b)} — {b.get('created_at', '')}" for b in batches
    )

    keyboard = get_batches_keyboard(batches, page=page, total=total, page_size=page_size)

    if update.callback_query and update.callback_query.data.startswith("batch_page:"):
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await send_step(update, context, text, keyboard)


async def batch_page_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pagination for the batches list.

    Args:
        update: Callback query with page index in callback_data.
        context: Conversation context with router_key.

    Returns:
        None.
    """
    query = update.callback_query
    await query.answer()
    try:
        page = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        page = 0
    await _show_batches_page(update, context, page=page)


async def batch_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Load and display details for a selected batch.

    Args:
        update: Callback query with batch_id in callback_data.
        context: Conversation context.

    Returns:
        None.
    """
    query = update.callback_query
    await query.answer()
    try:
        batch_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await query.answer("⚠️ رقم دفعة غير صالح", show_alert=True)
        return

    try:
        batch = await run_blocking(get_card_batch, batch_id)
    except (ValueError, OSError) as e:
        logger.error("Failed to load batch %s: %s", batch_id, e)
        await query.edit_message_text("❌ فشل تحميل الدفعة.", reply_markup=get_batches_keyboard([]))
        return

    if not batch:
        await query.edit_message_text(
            "⚠️ الدفعة غير موجودة.", reply_markup=get_batches_keyboard([])
        )
        return

    await query.edit_message_text(
        _format_batch_text(batch),
        reply_markup=get_batch_detail_keyboard(
            int(batch["id"] or 0),
            payment_status=str(batch.get("payment_status", "unpaid") or "unpaid"),
        ),
    )


def _format_batch_text(batch: RouterOSRow) -> str:
    cards_raw = batch.get("cards", [])
    cards = cards_raw if isinstance(cards_raw, list) else []
    total_bytes = 0
    for c in cards:
        if not isinstance(c, dict):
            continue
        try:
            limit = int(c.get("limit_bytes", 0) or 0)
        except (ValueError, TypeError):
            limit = 0
        total_bytes += limit

    btype = "هوت سبوت" if batch.get("batch_type") == "hotspot" else "User Manager"
    lines = [
        f"📦 تفاصيل الدفعة #{int(batch.get('id', 0) or 0)}",
        "",
        f"🏷️ الاسم: {batch.get('name', '')}",
        f"🔧 النوع: {btype}",
        f"📋 البروفايل: {batch.get('profile', '—')}",
        f"🔢 عدد الكروت: {int(batch.get('count', len(cards)) or len(cards))}",
        f"📊 إجمالي حد البيانات: {format_bytes(str(total_bytes)) if total_bytes else '—'}",
        f"🕒 الإنشاء: {batch.get('created_at', '')}",
    ]
    if batch.get("created_by"):
        lines.append(f"👤 المُنشئ: {batch['created_by']}")
    payment_status = str(batch.get("payment_status", "unpaid") or "unpaid")
    customer_name = str(batch.get("customer_name", "") or "")
    if customer_name:
        lines.append(f"🧑 العميل: {customer_name}")
    status_label = PAYMENT_STATUS_LABELS.get(payment_status, payment_status)
    lines.append(f"💰 حالة الدفع: {status_label}")
    if batch.get("sold_at"):
        lines.append(f"📅 تاريخ البيع: {batch['sold_at']}")
    return "\n".join(lines)


async def batch_regen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Regenerate and send the PDF for a batch from saved card data.

    Args:
        update: Callback query with batch_id in callback_data.
        context: Conversation context for sending documents.

    Returns:
        None.
    """
    query = update.callback_query
    try:
        batch_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await query.answer("⚠️ رقم دفعة غير صالح", show_alert=True)
        return

    try:
        batch = await run_blocking(get_card_batch, batch_id)
    except (ValueError, OSError) as e:
        logger.error("Failed to load batch %s: %s", batch_id, e)
        await query.answer("❌ فشل تحميل الدفعة", show_alert=True)
        return

    if not batch:
        await query.answer("⚠️ الدفعة غير موجودة", show_alert=True)
        return

    cards_raw = batch.get("cards", [])
    cards = deserialize_cards(_dump(cards_raw if isinstance(cards_raw, list) else []))
    if not cards:
        await query.answer("⚠️ لا توجد كروت في هذه الدفعة", show_alert=True)
        return

    try:
        pdf_path = await run_blocking(card_generator.generate_pdf, cards)
        msg = get_query_message(query)
        if msg is None:
            await query.answer("❌ فشل إرسال الملف", show_alert=True)
            return
        with open(pdf_path, "rb") as f:
            await context.bot.send_document(
                chat_id=msg.chat_id,
                document=f,
                filename=f"batch_{batch_id}.pdf",
                caption=f"📦 دفعة #{batch_id} — {batch['name']}",
            )
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        await query.answer("✅ تم إعادة توليد PDF", show_alert=False)
    except (OSError, ValueError) as e:
        logger.error("Failed to regenerate batch PDF %s: %s", batch_id, e)
        await query.answer("❌ فشل توليد PDF", show_alert=True)


def _dump(cards: list[RouterOSRow]):
    """Re-serialize a list of card dicts to JSON for deserialize_cards."""
    return json.dumps(cards, ensure_ascii=False)


@admin_only
async def mark_batch_paid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تغيير حالة الدفع لدفعة كروت (مدفوع/غير مدفوع/مرحّل)."""
    query = update.callback_query
    await query.answer()
    if is_duplicate_callback(query.data, query.from_user.id):
        return
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
                await query.edit_message_text(
                    text=_format_batch_text(batch),
                    reply_markup=get_batch_detail_keyboard(batch_id, payment_status=status),
                )
        except (ValueError, OSError, telegram.error.TelegramError):
            logger.debug("Failed to update batch %s payment UI", batch_id)
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
    except (ValueError, OSError) as e:
        logger.error("Failed to get sales summary: %s", e)
        summary = {
            "total_batches": 0,
            "paid_count": 0,
            "unpaid_count": 0,
            "deferred_count": 0,
            "total_revenue": 0.0,
        }
    text = SALES_SUMMARY_HEADER.format(days=days) + SALES_SUMMARY_ROW.format(**summary)
    await send_step(update, context, text, get_back_keyboard("menu_reports"))


@admin_only
async def share_card_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يبدأ تدفق مشاركة كرت WiFi — يحفظ batch_id ويطلب Telegram ID للعميل."""
    query = update.callback_query
    await query.answer()
    try:
        batch_id = int(query.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await query.answer("❌ بيانات غير صالحة", show_alert=True)
        return ConversationHandler.END
    # احفظ الـ batch_id في user_data للخطوة التالية
    context.user_data["share_batch_id"] = batch_id
    await query.edit_message_text(SHARE_CARD_PROMPT)
    return WAITING_SHARE_RECIPIENT


@admin_only
async def share_card_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل Telegram ID للعميل ويرسل له بيانات أول كرت في الدفعة."""
    recipient_text = (update.message.text or "").strip()
    try:
        recipient_id = int(recipient_text)
    except ValueError:
        await update.message.reply_text(SHARE_CARD_INVALID_ID)
        return WAITING_SHARE_RECIPIENT

    batch_id = context.user_data.pop("share_batch_id", None)
    if not batch_id:
        await update.message.reply_text("⚠️ انتهت صلاحية الجلسة، ابدأ من جديد.")
        return ConversationHandler.END

    try:
        batch = await run_blocking(get_card_batch, batch_id)
    except (ValueError, OSError) as e:
        logger.error("share_card_send: failed to load batch %s: %s", batch_id, e)
        await update.message.reply_text(SHARE_CARD_FAIL)
        return ConversationHandler.END

    if not batch:
        await update.message.reply_text(SHARE_CARD_NO_CARDS)
        return ConversationHandler.END

    cards = cast(list[dict[str, object]], batch.get("cards", []))
    if not cards:
        await update.message.reply_text(SHARE_CARD_NO_CARDS)
        return ConversationHandler.END

    # أول كرت في الدفعة
    first_card = cards[0]
    card = first_card
    username = card.get("username") or card.get("name") or "—"
    password = card.get("password") or ""
    profile = batch.get("profile") or card.get("profile") or "—"

    # جلب إعدادات PDF لاستخراج SSID/DNS
    try:
        pdf_settings = await run_blocking(get_pdf_settings)
        dns = pdf_settings.get("hotspot_dns", "")
        ssid = pdf_settings.get("brand_name", "")
    except (ValueError, OSError):
        dns = ssid = ""

    dns_line = f"\n🌐 DNS/رابط الدخول: <code>{dns}</code>" if dns else ""
    ssid_line = f"\n📶 اسم الشبكة: <b>{ssid}</b>" if ssid else ""
    pass_text = f"<code>{password}</code>" if password else "<i>بدون كلمة مرور</i>"

    msg = SHARE_CARD_TEMPLATE.format(
        username=username,
        password=pass_text,
        dns_line=dns_line,
        ssid_line=ssid_line,
        profile=profile,
    )

    try:
        await update.get_bot().send_message(
            chat_id=recipient_id,
            text=msg,
            parse_mode="HTML",
        )
        await update.message.reply_text(SHARE_CARD_SUCCESS)
    except telegram.error.TelegramError as e:
        logger.warning("share_card_send: failed to send to %s: %s", recipient_id, e)
        await update.message.reply_text(SHARE_CARD_FAIL)

    return ConversationHandler.END


__all__ = [
    "batch_page_handler",
    "batch_regen",
    "batch_select",
    "batches_command",
    "batches_search_query",
    "batches_search_start",
    "mark_batch_paid_handler",
    "share_card_send",
    "share_card_start",
    "show_sales_summary",
]
