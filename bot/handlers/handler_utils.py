"""Shared helpers for Telegram callback handlers.

تلخّص العمليات المتكررة في handlers دون تغيير السلوك:
- الإجابة الآمنة على callback query في بداية كل معالج.
- استخراج معرّف الراوتر الصحيح من بيانات callback مع معالجة خطأ موحّدة.
- make_back_step: factory لدوال "الرجوع" البسيطة المتكررة.

الهدف تقليل التكرار والحفاظ على سلوك Telegram الحالي بدقة.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from telegram import CallbackQuery, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from bot.keyboards import get_router_keyboard
from bot.messages import ERROR_OCCURRED
from utils.callback_utils import safe_answer_callback
from utils.tg_helpers import get_query_data


def get_user_id(update: Update) -> int | None:
    """أعد معرّف المستخدم من التحديث، أو None إن غاب ``effective_user``.

    تستبدل النمط المتكرر ``update.effective_user.id`` الذي يرفع
    ``reportOptionalMemberAccess`` لأن ``effective_user`` اختياري في نوع المكتبة.
    """
    user = update.effective_user
    return user.id if user is not None else None


def get_callback_data(update: Update) -> str | None:
    """أعد بيانات الـ callback query، أو None إن غاب الـ query."""
    query = update.callback_query
    return query.data if query is not None else None


def get_message_text(update: Update) -> str | None:
    """أعد نص الرسالة الفعّالة، أو None إن غابت الرسالة."""
    msg = update.effective_message
    return msg.text if msg is not None else None


def get_effective_message(update: Update) -> Message | None:
    """أعد الرسالة الفعّالة (لتجنّب الوصول المباشر الاختياري)."""
    return update.effective_message


def get_query_message(query: CallbackQuery | None) -> Message | None:
    """أعد رسالة الـ callback مضيّقةً إلى ``Message``، أو None.

    ``query.message`` من نوع ``Message | MaybeInaccessibleMessage`` ولا يمكن
    الوصول إلى ``chat_id``/``message_id`` عليه مباشرة؛ نضيّقه هنا. نستخدم
    ``cast`` بدل ``isinstance`` ليتوافق مع الـ mocks في الاختبارات (التي تكون
    من نوع MagicMock لا ترث من ``Message``).
    """
    if query is None or query.message is None:
        return None
    return cast("Message", query.message)


def get_query_chat_id(query: CallbackQuery | None) -> int | None:
    """أعد معرّف المحادثة لرسالة الـ callback، أو None."""
    msg = get_query_message(query)
    return msg.chat_id if msg is not None else None


async def ack_callback(update: Update) -> CallbackQuery | None:
    """أجب على callback query بأمان وأعده، أو None إن لم يوجد query.

    يستبدل النمط المتكرر:
        query = update.callback_query
        await safe_answer_callback(query)

    يتجاهل حالة غياب الـ query (مثل تحديثات الرسائل النصية) كما في
    المعالجات التي تدعم كلا المدخلين.
    """
    query = update.callback_query
    if query is not None:
        await safe_answer_callback(query)
    return query


async def parse_router_id(
    query: CallbackQuery | None,
    prefix: str,
    *,
    error_markup: InlineKeyboardMarkup | None = None,
) -> int | None:
    """استخرج معرّف الراوتر الصحيح من بيانات الـ callback.

    عند الفشل يرسل ``ERROR_OCCURRED`` ويعيد ``None`` ليتمكن المستدعي
    من الإنهاء مبكراً. يطابق النمط المتكرر في ``saved``/``discovery``/``reboot``:

        try:
            router_id = int(query.data.replace(prefix, ""))
        except (ValueError, IndexError):
            await query.edit_message_text(
                ERROR_OCCURRED.format(""), reply_markup=get_router_keyboard()
            )
            return
    """
    if error_markup is None:
        error_markup = get_router_keyboard()
    if query is None:
        return None
    try:
        return int(get_query_data(query).replace(prefix, ""))
    except (ValueError, IndexError):
        await query.edit_message_text(ERROR_OCCURRED.format(""), reply_markup=error_markup)
        return None


def make_back_step(message: str, keyboard_fn: Callable[..., Any], next_state: int):
    """Factory لدوال "الرجوع" البسيطة المتكررة.

    تُنشئ دالة async تستقبل (update, context)، تجيب على الـ callback query،
    تعرض رسالة بـ keyboard محدد، وتعيد next_state.

    تُستخدم فقط للدوال التي لا تحتوي منطقاً إضافياً (profile fetch، error handling، إلخ).

    مثال:
        add_back_to_username = make_back_step(
            ADD_USER_PROMPT, get_cancel_keyboard, WAITING_USERNAME
        )
    """
    from utils.admin_decorator import admin_only

    @admin_only
    async def _back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = await ack_callback(update)
        if query is not None:
            await query.edit_message_text(message, reply_markup=keyboard_fn())
        return next_state

    return _back_handler
