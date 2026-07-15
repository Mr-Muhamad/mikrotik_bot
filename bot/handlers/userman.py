import logging
import os
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from bot.keyboards import (
    get_card_type_keyboard,
    get_profile_keyboard,
    get_card_payment_keyboard,
    get_card_mac_keyboard,
    get_userman_keyboard,
    get_back_keyboard,
    get_skip_keyboard,
)
from bot.messages import (
    CARDS_PROMPT, ERROR_OCCURRED, CHOOSE_PROFILE, INVALID_PROFILE,
    NO_PROFILES_AVAILABLE, SEND_CARD_COUNT, MAX_CARDS_EXCEEDED,
    CREATING_CARDS, CARDS_CREATED_DETAIL, PDF_FILE_CAPTION,
    PROFILES_HEADER, NO_PROFILES, CHOOSE_PAYMENT, PAYMENT_PAID, PAYMENT_UNPAID,
    CHOOSE_MAC_BIND, ENTER_CARD_PREFIX,
)
from bot.router_selector import get_selected_router, cleanup_state, nav_set, set_current_action, require_router
from bot.helpers.profiles import fetch_and_cache_profiles, PROFILE_SOURCE_USERMAN
from core.userman_manager import userman_manager
from core.profile_sync import profile_sync
from core.card_models import CardData, serialize_cards
from database.models import log_action,save_card_batch
from utils.formatters import format_user_list
from utils.validators import validate_positive_int
from utils.chat_cleaner import send_and_track, send_step, edit_clean, track_message
from pdf.card_generator import card_generator
from .constants import (
    WAITING_CARD_TYPE,
    WAITING_CARD_PROFILE,
    WAITING_CARD_COUNT,
    WAITING_CARD_PAYMENT,
    WAITING_CARD_MAC,
    WAITING_CARD_PREFIX,
)
from utils.admin_decorator import admin_only
from utils.async_blocking import run_blocking
from utils.callback_utils import safe_answer_callback
from utils.error_response import send_error
from bot.profile_callbacks import resolve_profile_from_callback

logger = logging.getLogger(__name__)


# ─── CARD GENERATION ──────────────────────────────────────────


@admin_only
@require_router
async def userman_cards_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cleanup_state(update.effective_user.id, context.user_data)
    query = update.callback_query
    if query:
        await safe_answer_callback(query)
        await edit_clean(query, context, CARDS_PROMPT, get_card_type_keyboard())
    else:
        await send_step(update, context, CARDS_PROMPT, get_card_type_keyboard())
    set_current_action(update.effective_user.id, "userman_cards")
    nav_set(context, "menu_userman")
    return WAITING_CARD_TYPE


@admin_only
async def userman_card_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    card_type = query.data.replace("card_", "")
    context.user_data["card_type"] = card_type

    router_key = get_selected_router(query.from_user.id)
    profile_names = await fetch_and_cache_profiles(
        context, router_key, source=PROFILE_SOURCE_USERMAN,
    )
    if profile_names:
        await query.edit_message_text(
            CHOOSE_PROFILE,
            reply_markup=get_profile_keyboard(
                profile_names, "card_profile", "card_back_to_type"
            ),
        )
        return WAITING_CARD_PROFILE
    else:
        await query.edit_message_text(NO_PROFILES_AVAILABLE)
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END


@admin_only
async def userman_card_profile_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    profile = resolve_profile_from_callback(context, query.data, "card_profile_")
    if not profile:
        await query.edit_message_text(ERROR_OCCURRED.format(INVALID_PROFILE))
        cleanup_state(query.from_user.id, context.user_data)
        return ConversationHandler.END
    context.user_data["card_profile"] = profile

    await query.edit_message_text(CHOOSE_PAYMENT, reply_markup=get_card_payment_keyboard())
    return WAITING_CARD_PAYMENT


@admin_only
async def userman_card_payment_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    payment = PAYMENT_PAID if query.data == "card_paid" else PAYMENT_UNPAID
    context.user_data["card_payment"] = payment

    await query.edit_message_text(CHOOSE_MAC_BIND, reply_markup=get_card_mac_keyboard())
    return WAITING_CARD_MAC


@admin_only
async def userman_card_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valid, msg = validate_positive_int(update.message.text)
    if not valid:
        await send_step(update, context, msg)
        return WAITING_CARD_COUNT

    count = int(update.message.text)
    if count > 100:
        await send_step(update, context, MAX_CARDS_EXCEEDED)
        return WAITING_CARD_COUNT

    router_key = get_selected_router(update.effective_user.id)
    chat_id = update.effective_chat.id

    status_msg = await send_step(update, context, CREATING_CARDS)

    card_type = context.user_data.get("card_type")
    profile = context.user_data.get("card_profile")
    caller_id = context.user_data.get("card_caller_id", "")
    prefix = context.user_data.get("card_prefix", "")

    try:
        cards = await run_blocking(
            userman_manager.create_cards,
            router_key,
            count,
            card_type,
            profile,
            prefix=prefix,
        )

        if caller_id:
            for c in cards:
                await run_blocking(
                    userman_manager.set_user_caller_id,
                    router_key=router_key,
                    username=c["username"],
                    caller_id=caller_id,
                )

        await run_blocking(log_action, "create_cards", f"{count} cards", router_key, update.effective_user.id)

        if status_msg:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
            except Exception as e:
                logger.debug(f"Failed to delete status message: {e}")

        # لا نعرض بيانات الدخول (يوزر/باسورد) في الدردشة؛ الملف PDF هو المخرج الرسمي.
        payment = context.user_data.get("card_payment", "")
        created_at = datetime.now()
        batch_comment = f"{prefix}_{created_at.strftime('%Y-%m-%d_%H:%M')}" if prefix else created_at.strftime('%Y-%m-%d_%H:%M')
        linked_count = sum(1 for c in cards if c.get("profile_linked"))
        unlinked_count = len(cards) - linked_count
        cards_data = [
            CardData(
                username=c["username"],
                password=c["password"],
                card_number=i + 1,
                profile=context.user_data.get("card_profile", ""),
                caller_id=caller_id,
                created_at=created_at.isoformat(timespec="seconds"),
                payment=payment,
                comment=(
                    " | ".join(
                        ([batch_comment] if batch_comment else [])
                        + ([f"payment:{payment}"] if payment else [])
                        + ([f"unlinked:{c.get('link_error') or 'link failed'}"]
                           if not c.get("profile_linked") else [])
                    )
                ),
            )
            for i, c in enumerate(cards)
        ]

        detail = CARDS_CREATED_DETAIL.format(
            count=len(cards),
            created_at=created_at.strftime("%Y-%m-%d %H:%M"),
            payment=payment or "غير محدد",
        )
        if unlinked_count:
            first_err = next(
                (c.get("link_error") for c in cards
                 if not c.get("profile_linked") and c.get("link_error")),
                "",
            )
            detail += (
                f"\n\n⚠️ {unlinked_count} من {len(cards)} كارتاً لم يُربط بها البروفايل "
                f"«{context.user_data.get('card_profile', '')}»"
                + (f":\n{first_err}" if first_err else "")
            )
        await send_and_track(context, chat_id, detail)

        pdf_path = await run_blocking(card_generator.generate_pdf, cards_data)
        try:
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    doc_msg = await context.bot.send_document(
                        chat_id=chat_id,
                        document=f,
                        filename="cards.pdf",
                        caption=PDF_FILE_CAPTION,
                    )
                track_message(context, chat_id, doc_msg.message_id)
        finally:
            if os.path.exists(pdf_path):
                os.remove(pdf_path)


        batch_name = f"userman_{created_at:%Y%m%d_%H%M}"
        comment_prefix = (
            f"pay:{payment} | {created_at:%Y-%m-%d %H:%M}"
            if payment else created_at.strftime("%Y-%m-%d %H:%M")
        )
        try:
            await run_blocking(
                save_card_batch,
                router_key=router_key,
                name=batch_name,
                batch_type="userman",
                profile=context.user_data.get("card_profile", ""),
                comment_prefix=comment_prefix,
                cards=serialize_cards(cards_data),
                created_by=update.effective_user.id if update.effective_user else None,
            )
        except Exception as e:
            logger.warning(f"Failed to persist userman card batch: {e}")

    except Exception as e:
        await send_error(
            update, context, e,
            router_key=router_key,
            log_extra="userman_card_count",
        )
        cleanup_state(update.effective_user.id, context.user_data)
        return ConversationHandler.END

    cleanup_state(update.effective_user.id, context.user_data)
    return ConversationHandler.END


@admin_only
async def userman_card_mac_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)

    if query.data == "card_bind_known":
        context.user_data["card_caller_id"] = "bind"
    else:
        # card_no_bind: بدون ربط (caller-id فارغ).
        context.user_data["card_caller_id"] = ""

    await query.edit_message_text(
        ENTER_CARD_PREFIX,
        reply_markup=get_skip_keyboard("card_skip_prefix", "card_back_to_mac")
    )
    return WAITING_CARD_PREFIX


@admin_only
async def userman_card_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["card_prefix"] = update.message.text.strip()
    await send_step(update, context, SEND_CARD_COUNT, get_back_keyboard("card_back_to_prefix"))
    return WAITING_CARD_COUNT


@admin_only
async def userman_card_skip_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    context.user_data["card_prefix"] = ""
    await query.edit_message_text(SEND_CARD_COUNT, reply_markup=get_back_keyboard("card_back_to_prefix"))
    return WAITING_CARD_COUNT


# ─── USERMAN BACK HANDLERS ────────────────────────────────────


@admin_only
async def userman_back_to_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(CARDS_PROMPT, reply_markup=get_card_type_keyboard())
    return WAITING_CARD_TYPE


@admin_only
async def userman_back_to_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = get_selected_router(query.from_user.id)
    profile_names = await fetch_and_cache_profiles(
        context, router_key, source=PROFILE_SOURCE_USERMAN,
    )
    await query.edit_message_text(
        CHOOSE_PROFILE,
        reply_markup=get_profile_keyboard(
            profile_names, "card_profile", "card_back_to_type"
        ),
    )
    return WAITING_CARD_PROFILE


@admin_only
async def userman_back_to_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(CHOOSE_PAYMENT, reply_markup=get_card_payment_keyboard())
    return WAITING_CARD_PAYMENT


@admin_only
async def userman_back_to_mac(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(CHOOSE_MAC_BIND, reply_markup=get_card_mac_keyboard())
    return WAITING_CARD_MAC


@admin_only
async def userman_back_to_prefix(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    await query.edit_message_text(
        ENTER_CARD_PREFIX,
        reply_markup=get_skip_keyboard("card_skip_prefix", "card_back_to_mac")
    )
    return WAITING_CARD_PREFIX


# ─── USERMAN LIST ─────────────────────────────────────────────


@admin_only
@require_router
async def userman_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]

    try:
        users = await run_blocking(userman_manager.list_users, router_key)
        text = format_user_list(users)
        await query.edit_message_text(text, reply_markup=get_userman_keyboard())
    except Exception as e:
        await send_error(
            update, context, e,
            router_key=router_key,
            log_extra="userman_list",
            reply_markup=get_userman_keyboard(),
        )


# ─── PROFILES ─────────────────────────────────────────────────


@admin_only
@require_router
async def userman_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await safe_answer_callback(query)
    router_key = context.user_data["router_key"]

    try:
        profiles = await run_blocking(profile_sync.get_userman_profiles, router_key)
        if profiles:
            text = PROFILES_HEADER + "\n".join(f"• {p}" for p in profiles)
        else:
            text = NO_PROFILES
        await query.edit_message_text(text, reply_markup=get_userman_keyboard())
    except Exception as e:
        await send_error(
            update, context, e,
            router_key=router_key,
            log_extra="userman_profiles",
            reply_markup=get_userman_keyboard(),
        )
