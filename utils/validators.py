import ipaddress
from utils.formatters import parse_bytes


def validate_bytes_input(raw: str) -> str:
    """Validate and convert MikroTik byte input to raw byte value.

    Converts human-readable formats (1G, 500M, 1.5G, 1G-500M) to raw bytes
    so the MikroTik API receives an integer (e.g. '1073741824'), not '1G'.
    Raises ValueError with Arabic message on invalid input.
    """
    if not raw:
        return ""
    return parse_bytes(raw)


def validate_ip(ip: str) -> tuple[bool, str]:
    """Validate an IPv4 or IPv6 address."""
    if not ip:
        return False, "عنوان IP مطلوب"
    try:
        ipaddress.ip_address(ip)
        return True, ""
    except ValueError:
        return False, f"عنوان IP غير صالح: '{ip}'"


def validate_port(port: str) -> tuple[bool, str]:
    """Validate a network port number (1–65535)."""
    if not port:
        return False, "رقم المنفذ مطلوب"
    try:
        p = int(port)
        if 1 <= p <= 65535:
            return True, ""
        return False, "رقم المنفذ يجب أن يكون بين 1 و 65535"
    except (ValueError, TypeError):
        return False, "رقم المنفذ يجب أن يكون رقماً"


def validate_username(username: str) -> tuple[bool, str]:
    """Validate a hotspot username for length and allowed characters."""
    if not username or len(username) < 3:
        return False, "اسم المستخدم يجب أن يكون 3 أحرف على الأقل"
    if len(username) > 64:
        return False, "اسم المستخدم طويل جداً"
    if (
        not username.replace("_", "")
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .isalnum()
    ):
        return False, "اسم المستخدم يجب أن يحتوي على أحرف وأرقام فقط"
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate a hotspot password for length and disallowed whitespace characters."""
    if not password or len(password) < 4:
        return False, "الباسورد يجب أن يكون 4 أحرف على الأقل"
    if len(password) > 64:
        return False, "الباسورد طويل جداً"
    if any(c in password for c in "\n\r\t"):
        return False, "الباسورد يحتوي على أحرف غير مسموحة"
    return True, ""


def validate_positive_int(value: str) -> tuple[bool, str]:
    """Validate that a value is a positive integer."""
    try:
        val = int(value)
        if val > 0:
            return True, ""
        return False, "القيمة يجب أن تكون رقم موجب"
    except (ValueError, TypeError):
        return False, "القيمة يجب أن تكون رقم صحيح"


def validate_mac(mac: str) -> tuple[bool, str]:
    """Validate and normalize a MAC address for User Manager caller-id binding.

    Accepts colon, hyphen, or dot separators and returns the canonical
    colon-separated uppercase form. Returns ``(True, normalized)`` on success
    or ``(False, reason)`` when the value is not a valid 48-bit MAC.
    """
    import re

    if not mac or not mac.strip():
        return False, "MAC address is empty"
    raw = mac.strip().upper()
    cleaned = re.sub(r"[-:.]", "", raw)
    if len(cleaned) != 12 or not re.fullmatch(r"[0-9A-F]{12}", cleaned):
        return False, "MAC must be 12 hex digits (e.g. AA:BB:CC:DD:EE:FF)"
    groups = [cleaned[i : i + 2] for i in range(0, 12, 2)]
    return True, ":".join(groups)
