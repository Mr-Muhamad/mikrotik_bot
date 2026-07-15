"""Shared helpers for Telegram callback handlers.

تلخّص العمليات المتكررة في handlers دون تغيير السلوك:
- الإجابة الآمنة على callback query في بداية كل معالج.
- استخراج معرّف الراوتر الصحيح من بيانات callback مع معالجة خطأ موحّدة.

الهدف تقليل التكرار والحفاظ على سلوك Telegram الحالي بدقة.
"""
from telegram import CallbackQuery, Update

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
