import logging
from collections.abc import Callable

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.keyboards import get_nav_back_keyboard
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
    """Show PDF text and branding settings submenu.

    Args:
        update: Callback query from PDF settings menu.
        context: Conversation context.

    Returns:
        None.
    """
    from bot.keyboards import get_pdf_text_keyboard

    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        "🔤 إعدادات النصوص والهوية",
        reply_markup=get_pdf_text_keyboard(),
    )


@admin_only
async def pdf_group_layout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF layout and dimensions settings submenu.

    Args:
        update: Callback query from PDF settings menu.
        context: Conversation context.

    Returns:
        None.
    """
    from bot.keyboards import get_pdf_layout_keyboard

    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        "📐 إعدادات الهيكل والمقاسات",
        reply_markup=get_pdf_layout_keyboard(),
    )


@admin_only
async def pdf_group_misc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show PDF QR code settings submenu.

    Args:
        update: Callback query from PDF settings menu.
        context: Conversation context.

    Returns:
        None.
    """
    from bot.keyboards import get_pdf_misc_keyboard

    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        "📱 إعدادات الباركود (QR Code)",
        reply_markup=get_pdf_misc_keyboard(),
    )


def _get_pdf_group_info(option: str):
    from bot.keyboards import (
        get_pdf_layout_keyboard,
        get_pdf_misc_keyboard,
        get_pdf_settings_keyboard,
        get_pdf_text_keyboard,
    )

    text_options = {"brand_name", "hotspot_dns", "footer", "value_font_size"}
    layout_options = {"margins", "spacing", "cards_per_row", "cards_per_page", "label_spacing"}
    misc_options = {"show_qr"}

    if option in text_options:
        return "pdf_group_text", "🔤 إعدادات النصوص والهوية", get_pdf_text_keyboard
    if option in layout_options:
        return "pdf_group_layout", "📐 إعدادات الهيكل والمقاسات", get_pdf_layout_keyboard
    if option in misc_options:
        return "pdf_group_misc", "📱 إعدادات الباركود (QR Code)", get_pdf_misc_keyboard

    return "menu_pdf_settings", "⚙️ إعدادات الطباعة", get_pdf_settings_keyboard


@admin_only
async def pdf_settings_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user for a new value for the selected PDF setting.

    Args:
        update: Callback query with option key in callback_data.
        context: Conversation context for storing selected option.

    Returns:
        WAITING_PDF_VALUE state constant.
    """
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

    parent_nav, _, _ = _get_pdf_group_info(option)
    context.user_data["pdf_option"] = option
    set_current_action(query.from_user.id, "pdf_settings")
    nav_set(context, parent_nav)

    await query.edit_message_text(
        prompts.get(option, PDF_UNKNOWN_OPTION),
        reply_markup=get_nav_back_keyboard(),
    )
    return WAITING_PDF_VALUE


def _update_margins(value: str) -> str | None:
    parts = list(map(float, value.split()))
    if len(parts) != 4:
        return PDF_SEND_4_VALUES
    pdf_settings.update(
        margin_top=parts[0],
        margin_bottom=parts[1],
        margin_left=parts[2],
        margin_right=parts[3],
    )
    return None


def _update_spacing(value: str) -> str | None:
    parts = list(map(float, value.split()))
    if len(parts) != 2:
        return PDF_SEND_2_VALUES
    pdf_settings.update(spacing_x=parts[0], spacing_y=parts[1])
    return None


def _update_label_spacing(value: str) -> str | None:
    parts = list(map(float, value.split()))
    if len(parts) != 2:
        return PDF_SEND_2_VALUES
    pdf_settings.update(label_spacing_single=parts[0], label_spacing_dual=parts[1])
    return None


def _update_value_font_size(value: str) -> str | None:
    parts = list(map(int, value.split()))
    if len(parts) == 2 and all(8 <= p <= 16 for p in parts):
        pdf_settings.update(value_max_font_single=parts[0], value_max_font_dual=parts[1])
        return None
    return PDF_SEND_2_VALUES


_PDF_OPTION_HANDLERS: dict[str, Callable[..., object]] = {
    "margins": _update_margins,
    "spacing": _update_spacing,
    "cards_per_row": lambda v: pdf_settings.update(cards_per_row=int(v)),
    "cards_per_page": lambda v: pdf_settings.update(cards_per_page=int(v)),
    "brand_name": lambda v: pdf_settings.update(brand_name=v.strip()),
    "hotspot_dns": lambda v: pdf_settings.update(hotspot_dns=v.strip()),
    "show_qr": lambda v: pdf_settings.update(show_qr=1 if v.strip() == "1" else 0),
    "footer": lambda v: pdf_settings.update(footer_text=v.strip()),
    "label_spacing": _update_label_spacing,
    "value_font_size": _update_value_font_size,
}


def _apply_pdf_option_update(option: str, value: str) -> str | None:
    """Apply PDF setting update for a given option and value."""
    handler = _PDF_OPTION_HANDLERS.get(option)
    if handler is None:
        return None
    result = handler(value)
    return result if isinstance(result, str) else None


@admin_only
async def pdf_settings_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Apply the user-provided value to the selected PDF setting.

    Args:
        update: Message with the new setting value.
        context: Conversation context with pdf_option in user_data.

    Returns:
        WAITING_PDF_VALUE on error, ConversationHandler.END on success.
    """
    option = context.user_data.get("pdf_option")
    value = update.message.text.strip()

    try:
        err_msg = _apply_pdf_option_update(str(option), value)
        if err_msg:
            await send_step(update, context, err_msg)
            return WAITING_PDF_VALUE

        _, group_title, keyboard_func = _get_pdf_group_info(str(option))
        await reply_final(update, context, PDF_SETTINGS_UPDATED)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"{group_title}\n\n{pdf_settings.format_settings()}",
            reply_markup=keyboard_func(),
        )
    except (ValueError, TypeError) as e:
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
