"""Hotspot user expiry detection.

Extracted from ``core.hotspot_manager`` so that expiry/remaining-time
calculation stays separate from user CRUD. The function takes an API
handle and returns a plain list of dicts.
"""

import re
import logging

from librouteros.exceptions import LibRouterosError

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
    except Exception:
        return 0


def get_expiring_users(api, router_key: str, days: int = 3) -> list[dict]:
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
    result: list[dict] = []
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
                if isinstance(sess, dict):
                    uname = sess.get("user", "")
                    uptime_secs = _parse_uptime_to_seconds(sess.get("uptime", ""))
                    active_map[uname] = active_map.get(uname, 0) + uptime_secs
        except Exception:
            active_map = {}

        for user in users:
            if not isinstance(user, dict):
                continue
            # تخطي المستخدمين المعطلين
            if str(user.get("disabled", "false")).lower() == "true":
                continue
            limit_raw = user.get("limit-uptime", "")
            limit_secs = _parse_uptime_to_seconds(limit_raw)
            if limit_secs <= 0:
                continue
            name = user.get("name", "")
            # uptime_used = ما استُهلك من حد المستخدم (من الجلسات النشطة)
            used_secs = active_map.get(name, 0)
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
    except (LibRouterosError, ConnectionError, OSError) as e:
        logger.warning(f"get_expiring_users failed for {router_key}: {e}")
    return sorted(result, key=lambda x: x["remaining_days"])