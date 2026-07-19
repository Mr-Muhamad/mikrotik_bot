import re
from functools import lru_cache

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
            f"❌ الصيغة العلمية غير مدعومة.\n"
            f"أمثلة صحيحة: 1G بدلاً من {raw}, 500M بدلاً من 5e8"
        )
    try:
        float(raw)
        return raw
    except ValueError:
        pass
    parts = raw.lower().replace(" ", "").split("-")
    converted = []
    for part in parts:
        try:
            float(part)
            converted.append(part)
            continue
        except ValueError:
            pass
        if len(part) < 2:
            raise ValueError(
                f"❌ الرمز «{part}» يحتاج رقماً قبله.\n"
                f"أمثلة صحيحة: 1G, 500M, 2.5G, 10G-500M"
            )
        suffix = part[-1]
        num = part[:-1]
        if suffix in SUFFIX_MULTIPLIER:
            try:
                converted.append(str(int(float(num) * SUFFIX_MULTIPLIER[suffix])))
            except ValueError:
                raise ValueError(
                    f"❌ القيمة «{num}» ليست رقماً صالحاً.\n"
                    f"أمثلة صحيحة: 1G, 500M, 1.5G, 10G-500M"
                )
        else:
            raise ValueError(
                f"❌ الرمز «{suffix}» غير صالح.\n"
                f"الرموز المدعومة: K (كيلو), M (ميغا), G (جيغا), T (تيرا)\n"
                f"أمثلة صحيحة: 500M, 1G, 2.5G, 10G-500M"
            )
    return "-".join(converted)


@lru_cache(maxsize=256)
def format_bytes(bytes_val: str) -> str:
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


def sanitize_api_response(response: list[dict]) -> list[dict]:
    """Remove sensitive fields from MikroTik API responses for safe logging."""
    if not response:
        return response
    return [
        {k: ("***" if k in SENSITIVE_API_FIELDS else v) for k, v in item.items()}
        for item in response
    ]


def format_user_list(users: list[dict], max_items: int = 20) -> str:
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
