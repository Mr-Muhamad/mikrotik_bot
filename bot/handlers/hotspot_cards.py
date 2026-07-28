import logging
import os
import sqlite3
from datetime import datetime

from librouteros.exceptions import LibRouterosError
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.handlers.handler_utils import make_back_step
from bot.helpers.profiles import PROFILE_SOURCE_HOTSPOT, fetch_and_cache_profiles
from bot.keyboards import (
    get_cancel_keyboard,
    get_hotspot_keyboard,
    get_profile_keyboard,
    get_skip_keyboard,
)
from bot.messages import (
    CARD_BYTES_PROMPT,
    CARDS_CREATED,
    CHOOSE_CARD_PROFILE,
    CHOOSE_CARD_SYSTEM,
    ENTER_CARD_COUNT,
    ENTER_CARD_LENGTH,
    ENTER_CARD_PREFIX,
    ERROR_OCCURRED,
    SEND_UPTIME_TYPE,
)
from bot.profile_callbacks import resolve_profile_from_callback
from bot.router_selector import (
    cleanup_state,
    get_selected_router,
    nav_set,
    set_current_action,
)
from core.card_models import CardSystem, serialize_cards
from core.exceptions import MikrotikBotError
from core.hotspot_manager import hotspot_manager
from database.models import save_card_batch
from pdf.card_generator import card_generator
from utils.admin_decorator import admin_only, require_role
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.chat_cleaner import edit_clean, reply_final, send_step
from utils.error_response import send_error

from .constants import (
    WAITING_HOTSPOT_CARD_BYTES,
    WAITING_HOTSPOT_CARD_COUNT,
    WAITING_HOTSPOT_CARD_LENGTH,
    WAITING_HOTSPOT_CARD_PREFIX,
    WAITING_HOTSPOT_CARD_PRICE,
    WAITING_HOTSPOT_CARD_PROFILE,
    WAITING_HOTSPOT_CARD_TYPE,
    WAITING_HOTSPOT_CARD_UPTIME,
)
from .hotspot_flow_utils import (
    convert_uptime_value,
    set_uptime_unit,
)

logger = logging.getLogger(__name__)


def get_card_type_keyboard():
    """Return keyboard for card system selection."""
    keyboard = [
        [InlineKeyboardButton("1️⃣ اسم + سر مختلفين", callback_data="hs_card_type1")],
        [InlineKeyboardButton("2️⃣ اسم + سر متشابهين", callback_data="hs_card_type2")],
        [InlineKeyboardButton("3️⃣ اسم + سر فارغة", callback_data="hs_card_type3")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_hotspot")],
    ]
    return InlineKeyboardMarkup(keyboard)


CARD_PRICE_PROMPT = "💰 أدخل سعر الكارت الواحد (بالدولار مثلاً 5):\nأو اضغط تخطي إذا لا يوجد سعر."


@require_role("operator")
@admin_only
async def hotspot_cards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the card-creation flow and prompt for the card count.

    Args:
        update: Telegram update from callback or command.
        context: Conversation context; clears previous state.

    Returns:
        WAITING_HOTSPOT_CARD_COUNT state.
    """
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, ENTER_CARD_COUNT, get_cancel_keyboard())
    else:
        await send_step(update, context, ENTER_CARD_COUNT, get_cancel_keyboard())
    set_current_action(update.effective_user.id, "hotspot_cards")
    nav_set(context, "menu_hotspot")
    return WAITING_HOTSPOT_CARD_COUNT


MAX_HOTSPOT_CARDS = 500  # حد أعلى لتجنب إغراق الراوتر


@admin_only
async def hotspot_cards_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and store the card count, then prompt for card length.

    Args:
        update: Message update with the count number.
        context: Conversation context; stores hs_card_count.

    Returns:
        WAITING_HOTSPOT_CARD_LENGTH or WAITING_HOTSPOT_CARD_COUNT on error.
    """
    count_text = update.message.text.strip()
    if not count_text.isdigit() or int(count_text) < 1:
        await send_step(update, context, "❌ الرجاء إدخال رقم صحيح أكبر من 0.")
        return WAITING_HOTSPOT_CARD_COUNT
    count = int(count_text)
    if count > MAX_HOTSPOT_CARDS:
        await send_step(
            update,
            context,
            f"❌ الحد الأقصى {MAX_HOTSPOT_CARDS} كارت في المرة الواحدة. أدخل عدداً أقل.",
        )
        return WAITING_HOTSPOT_CARD_COUNT
    context.user_data["hs_card_count"] = count
    await send_step(update, context, ENTER_CARD_LENGTH, get_cancel_keyboard())
    return WAITING_HOTSPOT_CARD_LENGTH


@admin_only
async def hotspot_cards_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and store the card length, then prompt for an optional prefix.

    Args:
        update: Message update with the length number.
        context: Conversation context; stores hs_card_length.

    Returns:
        WAITING_HOTSPOT_CARD_PREFIX or WAITING_HOTSPOT_CARD_LENGTH on error.
    """
    length_text = update.message.text.strip()
    if not length_text.isdigit() or int(length_text) < 1:
        await send_step(update, context, "❌ الرجاء إدخال رقم صحيح أكبر من 0.")
        return WAITING_HOTSPOT_CARD_LENGTH
    context.user_data["hs_card_length"] = int(length_text)
    await send_step(
        update,
        context,
        ENTER_CARD_PREFIX,
        get_skip_keyboard("hs_skip_prefix", "hs_back_to_length"),
    )
    return WAITING_HOTSPOT_CARD_PREFIX


@admin_only
async def hotspot_cards_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the typed prefix and show the card type selection keyboard.

    Args:
        update: Message update with the prefix text.
        context: Conversation context; stores hs_card_prefix.

    Returns:
        WAITING_HOTSPOT_CARD_TYPE state.
    """
    context.user_data["hs_card_prefix"] = update.message.text.strip()
    await send_step(
        update,
        context,
        CARD_PRICE_PROMPT,
        get_skip_keyboard("hs_skip_price", "hs_back_to_length"),
    )
    return WAITING_HOTSPOT_CARD_PRICE


@admin_only
async def hotspot_cards_skip_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip prefix entry and proceed to card type selection.

    Args:
        update: Callback update from the skip button.
        context: Conversation context; sets hs_card_prefix to empty.

    Returns:
        WAITING_HOTSPOT_CARD_TYPE state.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["hs_card_prefix"] = ""
    await query.edit_message_text(
        CARD_PRICE_PROMPT,
        reply_markup=get_skip_keyboard("hs_skip_price", "hs_back_to_length"),
    )
    return WAITING_HOTSPOT_CARD_PRICE


@admin_only
async def hotspot_cards_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price_text = update.message.text.strip()
    try:
        price = float(price_text)
        if price < 0:
            raise ValueError
    except (ValueError, TypeError):
        await send_step(
            update,
            context,
            "❌ الرجاء إدخال رقم صحيح (مثل 5 أو 2.50).",
            get_skip_keyboard("hs_skip_price", "hs_back_to_length"),
        )
        return WAITING_HOTSPOT_CARD_PRICE
    context.user_data["hs_card_price"] = price_text
    await send_step(update, context, CHOOSE_CARD_SYSTEM, get_card_type_keyboard())
    return WAITING_HOTSPOT_CARD_TYPE


@admin_only
async def hotspot_cards_skip_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["hs_card_price"] = "0"
    await query.edit_message_text(CHOOSE_CARD_SYSTEM, reply_markup=get_card_type_keyboard())
    return WAITING_HOTSPOT_CARD_TYPE


hs_back_to_prefix = make_back_step(
    ENTER_CARD_PREFIX,
    lambda: get_skip_keyboard("hs_skip_prefix", "hs_back_to_length"),
    WAITING_HOTSPOT_CARD_PREFIX,
)


@admin_only
async def hotspot_cards_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the selected card system and show the profile picker.

    Args:
        update: Callback update with hs_card_type<N> data.
        context: Conversation context; stores hs_card_system.

    Returns:
        WAITING_HOTSPOT_CARD_PROFILE or ConversationHandler.END on error.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    callback_data = query.data

    if callback_data == "hs_card_type1":
        context.user_data["hs_card_system"] = CardSystem.DIFFERENT_CREDENTIALS
    elif callback_data == "hs_card_type2":
        context.user_data["hs_card_system"] = CardSystem.SAME_CREDENTIALS
    elif callback_data == "hs_card_type3":
        context.user_data["hs_card_system"] = CardSystem.EMPTY_PASSWORD
    else:
        return WAITING_HOTSPOT_CARD_TYPE

    router_key = get_selected_router(query.from_user.id)
    try:
        profile_names = await fetch_and_cache_profiles(
            context,
            router_key,
            source=PROFILE_SOURCE_HOTSPOT,
        )
        await query.edit_message_text(
            CHOOSE_CARD_PROFILE,
            reply_markup=get_profile_keyboard(profile_names, "hs_card_profile", "hs_back_to_type"),
        )
    except (LibRouterosError, OSError, MikrotikBotError) as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hotspot_cards_type_selected",
            reply_markup=get_hotspot_keyboard(),
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END

    return WAITING_HOTSPOT_CARD_PROFILE


@admin_only
async def hotspot_cards_profile_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store the chosen profile and prompt for uptime type selection.

    Args:
        update: Callback update with hs_card_profile_<name> data.
        context: Conversation context; stores hs_card_profile.

    Returns:
        WAITING_HOTSPOT_CARD_UPTIME or ConversationHandler.END on error.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    profile = resolve_profile_from_callback(context, query.data, "hs_card_profile_")
    if not profile:
        await query.edit_message_text(ERROR_OCCURRED.format(""))
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    context.user_data["hs_card_profile"] = profile
    await query.edit_message_text(
        SEND_UPTIME_TYPE,
        reply_markup=get_skip_keyboard("hs_skip_uptime", "hs_back_to_type"),
    )
    return WAITING_HOTSPOT_CARD_UPTIME


@admin_only
async def hotspot_cards_uptime_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uptime type button: hours or days, then prompt for value.

    Args:
        update: Callback update with uptime_hours/days data.
        context: Conversation context; stores hs_uptime_unit.

    Returns:
        WAITING_HOTSPOT_CARD_UPTIME state.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    query_data = query.data

    if query_data == "uptime_hours":
        prompt, _ = set_uptime_unit(context.user_data, "hs_uptime_unit", "hours")
        await query.edit_message_text(
            prompt,
            reply_markup=get_skip_keyboard("hs_skip_uptime", "hs_back_to_profile"),
        )
        return WAITING_HOTSPOT_CARD_UPTIME
    elif query_data == "uptime_days":
        prompt, _ = set_uptime_unit(context.user_data, "hs_uptime_unit", "days")
        await query.edit_message_text(
            prompt,
            reply_markup=get_skip_keyboard("hs_skip_uptime", "hs_back_to_profile"),
        )
        return WAITING_HOTSPOT_CARD_UPTIME
    return WAITING_HOTSPOT_CARD_UPTIME


@admin_only
async def hotspot_cards_skip_uptime_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip uptime type selection and clear any previous uptime value.

    Args:
        update: Callback update from the skip button.
        context: Conversation context; sets hs_card_uptime to empty.

    Returns:
        WAITING_HOTSPOT_CARD_UPTIME state.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["hs_card_uptime"] = ""
    await query.edit_message_text(
        SEND_UPTIME_TYPE,
        reply_markup=get_skip_keyboard("hs_skip_uptime", "hs_back_to_profile"),
    )
    return WAITING_HOTSPOT_CARD_UPTIME


@admin_only
async def hotspot_cards_uptime_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and convert the uptime value, then prompt for bytes limit.

    Args:
        update: Message update with the numeric uptime value.
        context: Conversation context; stores hs_card_uptime.

    Returns:
        WAITING_HOTSPOT_CARD_BYTES or WAITING_HOTSPOT_CARD_UPTIME on error.
    """
    value = update.message.text.strip()
    unit = context.user_data.get("hs_uptime_unit", "hours")
    uptime = convert_uptime_value(value, unit)

    if not uptime:
        await send_step(
            update,
            context,
            "❌ قيمة غير صالحة. الرجاء إدخال رقم صحيح.",
            get_skip_keyboard("hs_skip_uptime", "hs_back_to_profile"),
        )
        return WAITING_HOTSPOT_CARD_UPTIME

    context.user_data["hs_card_uptime"] = uptime
    await send_step(
        update,
        context,
        CARD_BYTES_PROMPT,
        get_skip_keyboard("hs_skip_bytes", "hs_back_to_uptime"),
    )
    return WAITING_HOTSPOT_CARD_BYTES


@admin_only
async def hotspot_cards_skip_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip uptime value entry and proceed to bytes limit prompt.

    Args:
        update: Callback update from the skip button.
        context: Conversation context; sets hs_card_uptime to empty.

    Returns:
        WAITING_HOTSPOT_CARD_BYTES state.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["hs_card_uptime"] = ""
    await query.edit_message_text(
        CARD_BYTES_PROMPT,
        reply_markup=get_skip_keyboard("hs_skip_bytes", "hs_back_to_uptime"),
    )
    return WAITING_HOTSPOT_CARD_BYTES


@admin_only
async def hotspot_cards_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Validate and store the bytes limit, then create the card batch.

    Args:
        update: Message update with the bytes limit text.
        context: Conversation context; stores hs_card_bytes.

    Returns:
        ConversationHandler.END after card creation.
    """
    bytes_input = update.message.text.strip()
    try:
        from utils.validators import validate_bytes_input

        context.user_data["hs_card_bytes"] = validate_bytes_input(bytes_input)
    except ValueError as e:
        await send_step(
            update,
            context,
            f"❌ {e}",
            get_skip_keyboard("hs_skip_bytes", "hs_back_to_uptime"),
        )
        return WAITING_HOTSPOT_CARD_BYTES

    return await _create_cards(update, context)


@admin_only
async def hotspot_cards_skip_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Skip bytes limit entry and create the card batch without a limit.

    Args:
        update: Callback update from the skip button.
        context: Conversation context; sets hs_card_bytes to empty.

    Returns:
        ConversationHandler.END after card creation.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["hs_card_bytes"] = ""
    return await _create_cards(update, context, query=query)


async def _create_cards(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    query: CallbackQuery | None = None,
):
    router_key = get_selected_router(update.effective_user.id)
    if not router_key:
        await reply_final(update, context, "❌ لم يتم اختيار روتر.", get_hotspot_keyboard())
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    count = context.user_data.get("hs_card_count", 1)
    length = context.user_data.get("hs_card_length", 3)
    prefix = context.user_data.get("hs_card_prefix", "")
    card_system = context.user_data.get("hs_card_system", CardSystem.DIFFERENT_CREDENTIALS)
    profile = context.user_data.get("hs_card_profile", "default")
    uptime = context.user_data.get("hs_card_uptime", "")
    bytes_limit = context.user_data.get("hs_card_bytes", "")
    unit_price = float(context.user_data.get("hs_card_price", "0") or "0")
    try:
        cards = await run_blocking(
            hotspot_manager.create_cards,
            router_key=router_key,
            count=count,
            length=length,
            card_system=card_system,
            profile=profile,
            prefix=prefix,
            limit_uptime=uptime,
            limit_bytes=bytes_limit,
        )

        if not cards:
            msg = "❌ فشل إنشاء الكروت."
            if query:
                await query.edit_message_text(msg, reply_markup=get_hotspot_keyboard())
            else:
                await reply_final(update, context, msg, get_hotspot_keyboard())
            cleanup_state(update.effective_user.id, context.user_data)
            return ConversationHandler.END

        batch_name = (
            f"hotspot_{prefix}_{datetime.now():%Y%m%d_%H%M}"
            if prefix
            else f"hotspot_{datetime.now():%Y%m%d_%H%M}"
        )
        try:
            await run_blocking(
                save_card_batch,
                router_key=router_key,
                name=batch_name,
                batch_type="hotspot",
                profile=profile,
                comment_prefix=prefix,
                cards=serialize_cards(cards),
                created_by=update.effective_user.id if update.effective_user else None,
                unit_price=unit_price,
            )
        except sqlite3.Error as e:
            logger.warning(f"Failed to persist card batch: {e}")

        pdf_path = await run_blocking(card_generator.generate_pdf, cards)

        chat_id = update.effective_chat.id
        with open(pdf_path, "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id,
                document=f,
                filename="hotspot_cards.pdf",
                caption=CARDS_CREATED.format(count=len(cards)),
            )

        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        if query:
            await query.edit_message_text(
                "🏠 القائمة الرئيسية", reply_markup=get_hotspot_keyboard()
            )
        else:
            await reply_final(update, context, "🏠 القائمة الرئيسية", get_hotspot_keyboard())

    except (LibRouterosError, OSError, MikrotikBotError) as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="_create_cards",
            reply_markup=get_hotspot_keyboard(),
        )

    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END


hs_back_to_length = make_back_step(
    ENTER_CARD_LENGTH, get_cancel_keyboard, WAITING_HOTSPOT_CARD_LENGTH
)
hs_back_to_type = make_back_step(
    CHOOSE_CARD_SYSTEM, get_card_type_keyboard, WAITING_HOTSPOT_CARD_TYPE
)


@admin_only
async def hs_back_to_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Navigate back from uptime step to the profile picker.

    Args:
        update: Callback update from the back button.
        context: Conversation context.

    Returns:
        WAITING_HOTSPOT_CARD_PROFILE or ConversationHandler.END on error.
    """
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    try:
        profile_names = await fetch_and_cache_profiles(
            context,
            router_key,
            source=PROFILE_SOURCE_HOTSPOT,
        )
        await query.edit_message_text(
            CHOOSE_CARD_PROFILE,
            reply_markup=get_profile_keyboard(profile_names, "hs_card_profile", "hs_back_to_type"),
        )
    except (LibRouterosError, OSError, MikrotikBotError) as e:
        await send_error(
            update,
            context,
            e,
            router_key=router_key,
            log_extra="hs_back_to_profile",
            reply_markup=get_hotspot_keyboard(),
        )
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    return WAITING_HOTSPOT_CARD_PROFILE


hs_back_to_uptime = make_back_step(
    SEND_UPTIME_TYPE,
    lambda: get_skip_keyboard("hs_skip_uptime", "hs_back_to_profile"),
    WAITING_HOTSPOT_CARD_UPTIME,
)
