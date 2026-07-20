"""Run blocking sync calls off the asyncio event loop.

يضمن نقل ContextVars (مثل request_id) إلى الـ thread المنفذ،
بحيث تحمل السجلات نفس الـ context.
"""

import asyncio
import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, TypeVar

T = TypeVar("T")

# إنشاء مجمع خيوط مخصص (Custom ThreadPool) بحجم كبير لتجنب تجميد البوت (Starvation)
# عند وجود عدة روترات غير متصلة (Offline) تستنفد الخيوط الافتراضية
_executor = ThreadPoolExecutor(max_workers=50, thread_name_prefix="mikrotik_worker")


async def run_blocking[T](func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """تنفيذ دالة متزامنة في executor مع الحفاظ على ContextVars.

    يستخدم ``contextvars.copy_context()`` لضمان نقل الـ request_id
    وأي context آخر إلى الـ thread المنفذ، ثم يُعيد ضبطه محلياً.
    """
    loop = asyncio.get_running_loop()
    ctx = contextvars.copy_context()
    bound = partial(func, *args, **kwargs) if kwargs else partial(func, *args)
    return await loop.run_in_executor(_executor, ctx.run, bound)
