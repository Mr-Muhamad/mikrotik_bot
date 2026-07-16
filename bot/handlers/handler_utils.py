"""Shared helpers for Telegram callback handlers.

تلخّص العمليات المتكررة في handlers دون تغيير السلوك:
- الإجابة الآمنة على callback query في بداية كل معالج.
- استخراج معرّف الراوتر الصحيح من بيانات callback مع معالجة خطأ موحّدة.
- make_back_step: factory لدوال "الرجوع" البسيطة المتكررة.

الهدف تقليل التكرار والحفاظ على سلوك Telegram الحالي بدقة.
"""
from __future__ import annotations
from typing import Callable

from telegram import CallbackQuery, Update
from telegram.ext import ContextTypes

from bot.keyboards import get_router_keyboard
from bot.messages import ERROR_OCCURRED
from utils.callback_utils import safe_answer_callback


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
    query: CallbackQuery,
    prefix: str,
    *,
    error_markup=None,
) -> int | None:
    """استخرج معرّف الراوتر الصحيح من بيانات الـ callback.

    عند الفشل يرسل ``ERROR_OCCURRED`` ويعيد ``None`` ليتمكن المستدعي
    من الإنهاء مبكراً. يطابق النمط المتكرر في ``saved``/``discovery``/``reboot``:

        try:
            router_id = int(query.data.replace(prefix, ""))
        except (ValueError, IndexError):
            await query.edit_message_text(ERROR_OCCURRED.format(""), reply_markup=get_router_keyboard())
            return
    """
    if error_markup is None:
        error_markup = get_router_keyboard()
    try:
        return int(query.data.replace(prefix, ""))
    except (ValueError, IndexError):
        await query.edit_message_text(ERROR_OCCURRED.format(""), reply_markup=error_markup)
        return None


def make_back_step(message: str, keyboard_fn: Callable, next_state: int):
    """Factory لدوال "الرجوع" البسيطة المتكررة.

    تُنشئ دالة async تستقبل (update, context)، تجيب على الـ callback query،
    تعرض رسالة بـ keyboard محدد، وتعيد next_state.

    تُستخدم فقط للدوال التي لا تحتوي منطقاً إضافياً (profile fetch، error handling، إلخ).

    مثال:
        add_back_to_username = make_back_step(ADD_USER_PROMPT, get_cancel_keyboard, WAITING_USERNAME)
    """
    from utils.admin_decorator import admin_only

    @admin_only
    async def _back_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await safe_answer_callback(query)
        await query.edit_message_text(message, reply_markup=keyboard_fn())
        return next_state

    return _back_handler
