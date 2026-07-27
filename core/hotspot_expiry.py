"""Hotspot user expiry detection.

Extracted from ``core.hotspot_manager`` so that expiry/remaining-time
calculation stays separate from user CRUD. The function takes an API
handle and returns a plain list of dicts.
"""

import logging
import re

from core.mikrotik_client import MikrotikClient, RouterOSRow

logger = logging.getLogger(__name__)


def _parse_uptime_to_seconds(raw: str) -> int:
    """تحويل `1d02:30:00` أو `00:30:00` إلى ثوانٍ. يُعيد 0 عند الفشل."""
    if not raw or raw in ("0", "0s", ""):
        return 0
    try:
        # صيغة: [Nd]HH:MM:SS
        m = re.match(r"(?:(\d+)d)?(?:(\d+):)?(\d+):(\d+)", str(raw))
        if not m:
            return 0
        d = int(m.group(1) or 0)
        h = int(m.group(2) or 0)
        mn = int(m.group(3) or 0)
        s = int(m.group(4) or 0)
        return d * 86400 + h * 3600 + mn * 60 + s
    except Exception as e:  # noqa: BLE001
        logger.debug(
            f"Failed to parse uptime '{raw}' "
            f"(error type: {type(e).__name__}): {e}"
        )
        return 0


def get_expiring_users(api: MikrotikClient, router_key: str, days: int = 3) -> list[RouterOSRow]:
    """إعادة قائمة المستخدمين الذين ستنتهي صلاحيتهم خلال `days` أيام.

    يعتمد على `limit-uptime` في RouterOS:
    - RouterOS يحسب `limit-uptime` من لحظة أول اتصال ناجح للمستخدم
      (يُنقص منه `uptime` للجلسات النشطة).
    - نقارن `limit-uptime` بـ `uptime` المتراكمة من `ip/hotspot/active/print`
      لمعرفة كم تبقى.
    - إذا لم يكن للمستخدم جلسة نشطة نحسب بافتراض worst-case (استخدم كله).
    - المستخدمون ذوو `limit-uptime = 0` أو فارغ مُستثنَون.

    يُعيد قائمة دوال بـ: name, profile, uptime_limit, remaining_days, uptime_used
    """
    result: list[RouterOSRow] = []
    try:
        users = api.execute(
            router_key,
            "ip/hotspot/user/print",
            **{".proplist": "name,profile,limit-uptime,disabled"},
        )
        # جلب الجلسات النشطة لمعرفة وقت الاستخدام الفعلي
        try:
            active_sessions = api.execute(
                router_key,
                "ip/hotspot/active/print",
                **{".proplist": "user,uptime"},
            )
            active_map: dict[str, int] = {}
            for sess in active_sessions:
                uname = str(sess.get("user", ""))
                uptime_secs = _parse_uptime_to_seconds(str(sess.get("uptime", "")))
                active_map[uname] = active_map.get(uname, 0) + uptime_secs
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"Failed to fetch active sessions for {router_key} "
                f"(error type: {type(e).__name__}): {e}"
            )
            active_map = {}

        for user in users:
            # تخطي المستخدمين المعطلين
            if str(user.get("disabled", "false")).lower() == "true":
                continue
            limit_raw = str(user.get("limit-uptime", ""))
            limit_secs = _parse_uptime_to_seconds(limit_raw)
            if limit_secs <= 0:
                continue
            name = user.get("name", "")
            # uptime_used = ما استُهلك من حد المستخدم (من الجلسات النشطة)
            used_secs = active_map.get(str(name), 0)
            remaining_secs = max(0, limit_secs - used_secs)
            remaining_days = remaining_secs / 86400
            if remaining_days <= days:
                result.append(
                    {
                        "name": name,
                        "profile": user.get("profile", "—"),
                        "uptime_limit": limit_raw,
                        "remaining_days": round(remaining_days, 1),
                        "uptime_used_secs": used_secs,
                    }
                )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"get_expiring_users failed for {router_key} "
            f"(error type: {type(e).__name__}): {e}"
        )
    return sorted(result, key=lambda x: float(x["remaining_days"] or 0))


def parse_renewal_day_from_comment(comment: str) -> tuple[str, int | None]:
    """استخراج اسم المستخدم اليومي ويوم التجديد من حقل التعليق (مثل: `user/22` أو `أحمد-15`).

    يُعيد: (display_name, renewal_day)
    """
    if not comment:
        return "", None
    comment = comment.strip()
    match = re.search(r"(?:[/\-])\s*(\d{1,2})\b", comment)
    if not match:
        return comment, None
    try:
        renewal_day = int(match.group(1))
        if 1 <= renewal_day <= 31:
            name_part = comment[: match.start()].strip()
            return name_part or comment, renewal_day
    except ValueError:
        pass
    return comment, None


def get_custom_expiring_users(
    api: MikrotikClient,
    router_key: str,
    days_window: int = 3,
) -> list[RouterOSRow]:
    """إعادة قائمة المستخدمين الذين يقترب يوم تجديدهم المحدد في التعليق خلال `days_window` أيام."""
    import datetime

    result: list[RouterOSRow] = []
    try:
        users = api.execute(
            router_key,
            "ip/hotspot/user/print",
            **{".proplist": "name,profile,comment,disabled"},
        )
        today = datetime.datetime.now().day

        for user in users:
            if str(user.get("disabled", "false")).lower() == "true":
                continue
            comment = str(user.get("comment", ""))
            clean_name, renewal_day = parse_renewal_day_from_comment(comment)
            if renewal_day is None:
                continue

            days_left = (
                (renewal_day - today) if renewal_day >= today else (30 - today + renewal_day)
            )
            if 0 <= days_left <= days_window:
                result.append(
                    {
                        "username": user.get("name", ""),
                        "display_name": clean_name or user.get("name", ""),
                        "renewal_day": renewal_day,
                        "days_left": days_left,
                        "profile": user.get("profile", "—"),
                    }
                )
    except Exception as e:  # noqa: BLE001
        logger.warning(
            f"get_custom_expiring_users failed for {router_key} "
            f"(error type: {type(e).__name__}): {e}"
        )
    return sorted(result, key=lambda x: int(x.get("days_left", 0) or 0))
