import re
from functools import lru_cache
from typing import Any, cast

from core.mikrotik_client import RouterOSRow

SUFFIX_MULTIPLIER = {"k": 1000, "m": 1000000, "g": 1000000000, "t": 1000000000000}

# نمط الرموز العلمية مثل "1e10" أو "1.5E-3" — يجب رفضها لتجنب تفسيرها على أنها أرقام
_SCIENTIFIC_NOTATION_RE = re.compile(r"\d+\.?\d*[eE][+-]?\d+")


def parse_bytes(raw: str) -> str:
    """Convert human-readable byte strings (e.g. 1.5G, 500M) to raw numeric byte values.

    Raises ValueError for invalid input instead of returning the raw string.
    """
    if not raw:
        return ""
    # رفض الترميز العلمي فقط (ليس مجرد حرف "e" في كلمة مثل "guest")
    if _SCIENTIFIC_NOTATION_RE.search(raw):
        raise ValueError(
            f"❌ الصيغة العلمية غير مدعومة.\nأمثلة صحيحة: 1G بدلاً من {raw}, 500M بدلاً من 5e8"
        )
    try:
        float(raw)
        return raw
    except ValueError:
        pass
    parts = raw.lower().replace(" ", "").split("-")
    converted: list[str] = []
    for part in parts:
        try:
            float(part)
            converted.append(part)
            continue
        except ValueError:
            pass
        if len(part) < 2:
            raise ValueError(
                f"❌ الرمز «{part}» يحتاج رقماً قبله.\nأمثلة صحيحة: 1G, 500M, 2.5G, 10G-500M"
            )
        suffix = part[-1]
        num = part[:-1]
        if suffix in SUFFIX_MULTIPLIER:
            try:
                converted.append(str(int(float(num) * SUFFIX_MULTIPLIER[suffix])))
            except ValueError as _ve:
                raise ValueError(
                    f"❌ القيمة «{num}» ليست رقماً صالحاً.\nأمثلة صحيحة: 1G, 500M, 1.5G, 10G-500M"
                ) from _ve
        else:
            raise ValueError(
                f"❌ الرمز «{suffix}» غير صالح.\n"
                f"الرموز المدعومة: K (كيلو), M (ميغا), G (جيغا), T (تيرا)\n"
                f"أمثلة صحيحة: 500M, 1G, 2.5G, 10G-500M"
            )
    return "-".join(converted)


@lru_cache(maxsize=256)
def format_bytes(bytes_val: str | None) -> str:
    """Format a byte count into a human-readable string with appropriate units.

    Results are cached for frequently used values.
    """
    if bytes_val is None or bytes_val == "":
        return "غير محدود"
    try:
        val = int(bytes_val)
    except (ValueError, TypeError):
        return str(bytes_val)
    if val >= 1000000000:
        return f"{val / 1000000000:.2f} GB"
    elif val >= 1000000:
        return f"{val / 1000000:.2f} MB"
    elif val >= 1000:
        return f"{val / 1000:.2f} KB"
    return f"{val} B"


SENSITIVE_API_FIELDS = frozenset(
    {
        "password",
        "secret",
        "shared-users",
        "encryption-key",
    }
)

_SENSITIVE_LOG_KEYWORDS = frozenset(
    {
        "password",
        "secret",
        "token",
        "key",
        "credential",
        "auth",
        "bearer",
        "apikey",
    }
)


def sanitize_api_response(response: list[RouterOSRow]) -> list[RouterOSRow]:
    """Remove sensitive fields from MikroTik API responses for safe logging."""
    if not response:
        return response
    return [
        {k: ("***" if k in SENSITIVE_API_FIELDS else v) for k, v in item.items()}
        for item in response
    ]


def sanitize_log_data(data: Any, max_depth: int = 3) -> Any:
    """Recursively sanitize sensitive data from log context fields.

    Masks values for keys matching sensitive patterns to prevent credentials,
    tokens, and keys from leaking into structured logs.
    """
    if max_depth <= 0:
        return "***"
    if isinstance(data, dict):
        return {
            k: (
                "***"
                if any(kw in k.lower() for kw in _SENSITIVE_LOG_KEYWORDS)
                else sanitize_log_data(v, max_depth - 1)
            )
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [sanitize_log_data(item, max_depth - 1) for item in data]
    if isinstance(data, str) and len(data) > 200:
        return data[:200] + "..."
    return data


def format_user_list(users: list[RouterOSRow], max_items: int = 20) -> str:
    """Format a list of user dicts into a numbered Arabic display string."""
    if not users:
        return "📭 لا يوجد مستخدمين"

    lines = ["📋 قائمة المستخدمين:"]
    for i, user in enumerate(users[:max_items]):
        name = user.get("name", "N/A")
        comment = user.get("comment", "")
        profile = user.get("profile", "N/A")
        user_id = user.get(".id", "*0")
        line = f"{i + 1}. {name} ({profile})"
        if comment:
            line += f" - {comment}"
        line += f" [{user_id}]"
        lines.append(line)

    if len(users) > max_items:
        lines.append(f"... و {len(users) - max_items} مستخدمين آخرين")

    return "\n".join(lines)


def format_hotspot_user(user: RouterOSRow) -> str:
    """Format a hotspot user dict into a human-readable Arabic string."""
    bytes_in = user.get("bytes-in", "0")
    bytes_out = user.get("bytes-out", "0")
    try:
        total_consumed = int(cast(str | int, bytes_in)) + int(cast(str | int, bytes_out))
        total_text = format_bytes(str(total_consumed))
    except (ValueError, TypeError):
        total_text = "غير معروف"

    uptime_raw = user.get("limit-uptime", "")
    uptime_text = uptime_raw if uptime_raw else "غير محدود"

    lines = [
        f"\U0001f464 الاسم: {user.get('name', 'لا يوجد')}",
        f"\U0001f511 الباسورد: {'*' * 8 if user.get('password') else 'لا يوجد'}",
        f"\U0001f4cb البروفايل: {user.get('profile', 'لا يوجد')}",
        f"\U0001f4ca الحد: {format_bytes(user.get('limit-bytes-total', ''))}",
        f"\u23f0 المدة: {uptime_text}",
        f"\U0001f4ca المستهلك: {total_text}",
        f"\U0001f4ac التعليق: {user.get('comment', 'لا يوجد')}",
        f"\U0001f194 الرقم: {user.get('.id', 'لا يوجد')}",
    ]
    return "\n".join(lines)


def format_hotspot_stats(stats: RouterOSRow | None, router_name: str) -> str:
    """Format hotspot stats dict into an Arabic display string."""
    if not stats:
        return "❌ خطأ في جلب إحصائيات Hotspot"

    bytes_str = format_bytes(str(stats["total_bytes"]))

    return (
        f"📊 إحصائيات Hotspot - {router_name}\n\n"
        f"👥 إجمالي المستخدمين: {stats['total_users']}\n"
        f"🟢 نشط: {stats['active_users']}\n"
        f"🔴 غير نشط: {stats['inactive_users']}\n"
        f"📦 إجمالي البيانات: {bytes_str}"
    )


def format_userman_stats(stats: RouterOSRow | None, router_name: str) -> str:
    """Format User Manager stats dict into an Arabic display string."""
    if not stats:
        return "❌ خطأ في جلب إحصائيات User Manager"

    return (
        f"📊 إحصائيات User Manager - {router_name}\n\n"
        f"🎫 إجمالي الكروت: {stats['total_users']}\n"
        f"🟢 نشطة: {stats['enabled_users']}\n"
        f"🔴 منتهية/معطلة: {stats['disabled_users']}"
    )


def format_hotspot_usage_report(report: RouterOSRow, router_name: str) -> str:
    """Format a Hotspot usage report dict into an Arabic Telegram summary."""
    if not report or report.get("total", 0) == 0:
        return f"📊 تقرير استخدام Hotspot - {router_name}\n\n📭 لا يوجد مستخدمون لإنشاء تقرير."

    lines = [
        f"📊 تقرير استخدام Hotspot - {router_name}",
        "",
        f"👥 إجمالي المستخدمين: {report['total']}",
        f"🟢 نشط: {report['active']}",
        f"🔴 معطل: {report['disabled']}",
        f"📊 بحد بيانات: {report['with_limit']}",
        f"📦 إجمالي البيانات: {report['total_bytes_str']}",
        "",
        f"⏳ مقترب من الحد: {len(cast(list[RouterOSRow], report.get('near_limit', [])))}",
        f"⌛ منتهٍ (وصل الحد): {len(cast(list[RouterOSRow], report.get('expired', [])))}",
        f"💤 غير نشط: {len(cast(list[RouterOSRow], report.get('inactive', [])))}",
        "",
        "🔝 الأكثر استهلاكاً:",
    ]
    for r in cast(list[RouterOSRow], report.get("top_consumers", []))[:5]:
        lines.append(f"• {r['name']}: {r['total_str']} ({r['percent']:.0f}%)")
    return "\n".join(lines)


def format_trend_chart(snapshots: list[RouterOSRow]) -> str:
    """تنسيق آخر 7 أيام كـ ASCII bar chart نصي بسيط.

    كل سطر: التاريخ | شريط | عدد المستخدمين
    """
    if not snapshots:
        return ""
    max_active = (
        max((int(cast(int | float, s.get("active_users", 0))) for s in snapshots), default=1) or 1
    )
    lines = []
    for s in snapshots:
        day = str(s.get("snapshot_date", ""))[-5:]  # MM-DD فقط
        active = int(cast(int | float, s.get("active_users", 0)))
        bar_len = round((active / max_active) * 8)
        bar = "█" * bar_len
        lines.append(f"{day} | {bar:<8} {active}")
    return "\n".join(lines)


def format_vs_yesterday(current: RouterOSRow, yesterday: RouterOSRow | None) -> str:
    """مقارنة المستخدمين النشطين اليوم versus الأمس.

    يُعيد نص HTML مثل: ↑5 مقارنةً بالأمس (25 → 30)
    """
    if not yesterday:
        return ""
    prev = int(cast(int | float, yesterday.get("active_users", 0)))
    curr = int(cast(int | float, current.get("active_users", 0)))
    diff = curr - prev
    if diff > 0:
        arrow = "↑"
    elif diff < 0:
        arrow = "↓"
    else:
        arrow = "↔"
    return f"{arrow}{abs(diff)} مقارنةً بالأمس ({prev} → {curr})"
