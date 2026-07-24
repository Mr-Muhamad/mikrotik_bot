"""Helpers for fetching and caching MikroTik profile names.

يحلّ 7 نسخ مكررة من نفس المنطق في handlers مختلفة، ويستخدم TTL cache
لتقليل طلبات API المتكررة.
"""

import logging

from telegram.ext import ContextTypes

from bot.profile_callbacks import cache_profile_names
from core.hotspot_manager import hotspot_manager
from core.profile_cache import profile_cache
from core.profile_sync import profile_sync
from utils.async_blocking import run_blocking

logger = logging.getLogger(__name__)


# نوع مصدر البروفايلات: hotspot أو userman
PROFILE_SOURCE_HOTSPOT = "hotspot"
PROFILE_SOURCE_USERMAN = "userman"


async def fetch_profiles(
    router_key: str,
    source: str = PROFILE_SOURCE_HOTSPOT,
    use_cache: bool = True,
) -> list[str]:
    """جلب أسماء البروفايلات من الراوتر (مع TTL cache).

    Args:
        router_key: مفتاح الراوتر.
        source: مصدر البروفايلات (hotspot أو userman).
        use_cache: استخدام الكاش (افتراضي True).

    Returns:
        قائمة بأسماء البروفايلات. فارغة عند الفشل.
    """
    cache_key = f"{source}:{router_key}"

    if use_cache:
        cached = profile_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Profile cache hit for {cache_key}")
            return cached

    try:
        if source == PROFILE_SOURCE_USERMAN:
            raw = await run_blocking(profile_sync.get_userman_profiles, router_key)
        else:
            raw = await run_blocking(hotspot_manager.get_profiles, router_key)
    except Exception as e:
        logger.warning(f"fetch_profiles({source}) failed for {router_key}: {e}")
        return []

    # توحيد الشكل: list[str]
    names: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            names.append(entry)
        elif hasattr(entry, "get"):
            name = entry.get("name", "")
            if name:
                names.append(str(name))

    if use_cache:
        profile_cache.set(cache_key, names)
    return names


async def fetch_and_cache_profiles(
    context: ContextTypes.DEFAULT_TYPE,
    router_key: str | None,
    source: str = PROFILE_SOURCE_HOTSPOT,
) -> list[str]:
    """جلب البروفايلات وتخزينها في ``context.user_data`` لربط الـ callback.

    Args:
        context: Telegram context.
        router_key: مفتاح الراوتر.
        source: hotspot أو userman.

    Returns:
        قائمة بأسماء البروفايلات.
    """
    if not router_key:
        return []
    names = await fetch_profiles(router_key, source=source)
    cache_profile_names(context, names)
    return names


def invalidate_profile_cache(router_key: str | None = None) -> None:
    """إبطال الكاش لراوتر محدد أو مسحه بالكامل.

    يُستدعى بعد edit_profile_* أو add/delete users للحفاظ على البيانات محدّثة.
    """
    if router_key is None:
        profile_cache.clear()
    else:
        profile_cache.invalidate(f"hotspot:{router_key}")
        profile_cache.invalidate(f"userman:{router_key}")
