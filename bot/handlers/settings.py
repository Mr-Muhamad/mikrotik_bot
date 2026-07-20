import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import get_nav_back_keyboard, get_pdf_settings_keyboard
from bot.messages import (
    PDF_BRAND_NAME_PROMPT,
    PDF_CARDS_PER_PAGE_PROMPT,
    PDF_CARDS_PER_ROW_PROMPT,
    PDF_FOOTER_PROMPT,
    PDF_HOTSPOT_DNS_PROMPT,
    PDF_LABEL_SPACING_PROMPT,
    PDF_MARGINS_PROMPT,
    PDF_SEND_2_VALUES,
    PDF_SEND_4_VALUES,
    PDF_SETTINGS_UPDATED,
    PDF_SHOW_QR_PROMPT,
    PDF_SPACING_PROMPT,
    PDF_UNKNOWN_OPTION,
    PDF_VALUE_FONT_SIZE_PROMPT,
)
from bot.router_selector import cleanup_state, nav_set, set_current_action
from pdf.pdf_settings import pdf_settings
from utils.admin_decorator import admin_only
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import reply_final, send_step
from utils.error_response import send_error

from .constants import WAITING_PDF_VALUE

logger = logging.getLogger(__name__)


@admin_only
async def pdf_group_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.keyboards import get_pdf_text_keyboard

    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        "🔤 إعدادات النصوص والهوية",
        reply_markup=get_pdf_text_keyboard(),
    )


@admin_only
async def pdf_group_layout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.keyboards import get_pdf_layout_keyboard

    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        "📐 إعدادات الهيكل والمقاسات",
        reply_markup=get_pdf_layout_keyboard(),
    )


@admin_only
async def pdf_group_misc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from bot.keyboards import get_pdf_misc_keyboard

    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        "📱 إعدادات الباركود (QR Code)",
        reply_markup=get_pdf_misc_keyboard(),
    )


@admin_only
async def pdf_settings_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    cleanup_state(query.from_user.id, context.user_data)

    option = query.data.replace("pdf_", "")
    settings = pdf_settings.get_settings()

    prompts = {
        "margins": PDF_MARGINS_PROMPT.format(
            top=settings.get("margin_top", 10),
            bottom=settings.get("margin_bottom", 10),
            left=settings.get("margin_left", 10),
            right=settings.get("margin_right", 10),
        ),
        "spacing": PDF_SPACING_PROMPT.format(
            x=settings.get("spacing_x", 5), y=settings.get("spacing_y", 5)
        ),
        "cards_per_row": PDF_CARDS_PER_ROW_PROMPT.format(value=settings.get("cards_per_row", 4)),
        "cards_per_page": PDF_CARDS_PER_PAGE_PROMPT.format(
            value=settings.get("cards_per_page", 40)
        ),
        "brand_name": PDF_BRAND_NAME_PROMPT.format(
            value=settings.get("brand_name", "") or "(فارغ)"
        ),
        "hotspot_dns": PDF_HOTSPOT_DNS_PROMPT.format(
            value=settings.get("hotspot_dns", "") or "(فارغ)"
        ),
        "show_qr": PDF_SHOW_QR_PROMPT.format(
            value="✅ مفعّل" if settings.get("show_qr", 1) else "❌ معطّل"
        ),
        "footer": PDF_FOOTER_PROMPT.format(value=settings.get("footer_text", "") or "(فارغ)"),
        "label_spacing": PDF_LABEL_SPACING_PROMPT.format(
            single=settings.get("label_spacing_single", 1.0),
            dual=settings.get("label_spacing_dual", 1.0),
        ),
        "value_font_size": PDF_VALUE_FONT_SIZE_PROMPT.format(
            single=settings.get("value_max_font_single", 12),
            dual=settings.get("value_max_font_dual", 11),
        ),
    }

    context.user_data["pdf_option"] = option
    set_current_action(query.from_user.id, "pdf_settings")
    nav_set(context, "menu_pdf_settings")

    await query.edit_message_text(
        prompts.get(option, PDF_UNKNOWN_OPTION),
        reply_markup=get_nav_back_keyboard(),
    )
    return WAITING_PDF_VALUE


@admin_only
async def pdf_settings_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    option = context.user_data.get("pdf_option")
    value = update.message.text.strip()

    try:
        if option == "margins":
            parts = list(map(float, value.split()))
            if len(parts) == 4:
                pdf_settings.update(
                    margin_top=parts[0],
                    margin_bottom=parts[1],
                    margin_left=parts[2],
                    margin_right=parts[3],
                )
            else:
                await send_step(update, context, PDF_SEND_4_VALUES)
                return WAITING_PDF_VALUE
        elif option == "spacing":
            parts = list(map(float, value.split()))
            if len(parts) == 2:
                pdf_settings.update(spacing_x=parts[0], spacing_y=parts[1])
            else:
                await send_step(update, context, PDF_SEND_2_VALUES)
                return WAITING_PDF_VALUE
        elif option == "cards_per_row":
            pdf_settings.update(cards_per_row=int(value))
        elif option == "cards_per_page":
            pdf_settings.update(cards_per_page=int(value))
        elif option == "brand_name":
            pdf_settings.update(brand_name=value.strip())
        elif option == "hotspot_dns":
            pdf_settings.update(hotspot_dns=value.strip())
        elif option == "show_qr":
            show = 1 if value.strip() == "1" else 0
            pdf_settings.update(show_qr=show)
        elif option == "footer":
            pdf_settings.update(footer_text=value.strip())
        elif option == "label_spacing":
            parts = list(map(float, value.split()))
            if len(parts) == 2:
                pdf_settings.update(label_spacing_single=parts[0], label_spacing_dual=parts[1])
            else:
                await send_step(update, context, PDF_SEND_2_VALUES)
                return WAITING_PDF_VALUE
        elif option == "value_font_size":
            try:
                parts = list(map(int, value.split()))
            except ValueError:
                await send_step(update, context, PDF_SEND_2_VALUES)
                return WAITING_PDF_VALUE
            if len(parts) == 2 and all(8 <= p <= 16 for p in parts):
                pdf_settings.update(value_max_font_single=parts[0], value_max_font_dual=parts[1])
            else:
                await send_step(update, context, PDF_SEND_2_VALUES)
                return WAITING_PDF_VALUE

        await reply_final(update, context, PDF_SETTINGS_UPDATED)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=pdf_settings.format_settings(),
            reply_markup=get_pdf_settings_keyboard(),
        )
    except Exception as e:
        await send_error(
            update,
            context,
            e,
            log_extra="pdf_settings_value",
        )
        # ابق في حالة الانتظار للسماح بإعادة المحاولة
        return WAITING_PDF_VALUE

    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END
