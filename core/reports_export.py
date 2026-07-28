"""CSV report generator for MikroTik Hotspot users.

Generates structured CSV files for export in Telegram.
"""

import csv
import io
import logging

from core.hotspot_expiry import parse_renewal_day_from_comment
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow
from utils.formatters import format_bytes

logger = logging.getLogger(__name__)


def generate_hotspot_users_csv(router_key: str) -> str:
    """Generate CSV text containing all hotspot users on a router."""
    try:
        users: list[RouterOSRow] = mikrotik_api.execute_long(
            router_key,
            "ip/hotspot/user/print",
            **{
                ".proplist": (
                    ".id,name,profile,limit-bytes-total,bytes-out,bytes-in,"
                    "limit-uptime,uptime,comment,disabled"
                )
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Failed to fetch hotspot users for CSV export on {router_key} in export_hotspot_users_csv "
            f"(error type: {type(e).__name__}): {e}",
            exc_info=True,
        )
        return ""

    output = io.StringIO()
    writer = csv.writer(output)
    # Write Header
    writer.writerow(
        [
            "اسم المستخدم (Username)",
            "الاسم/التعليق (Display Name)",
            "يوم التجديد (Renewal Day)",
            "البروفايل (Profile)",
            "الحد الكلي (Limit Bytes)",
            "المستهلك (Bytes Used)",
            "الحالة (Status)",
        ]
    )

    for u in users:
        username = str(u.get("name", ""))
        comment = str(u.get("comment", ""))
        clean_name, renewal_day = parse_renewal_day_from_comment(comment)

        limit_bytes = int(u.get("limit-bytes-total", 0) or 0)
        bytes_used = int(u.get("bytes-out", 0) or 0) + int(u.get("bytes-in", 0) or 0)

        is_disabled = str(u.get("disabled", "false")).lower() == "true"
        status_str = "معطل (Disabled)" if is_disabled else "نشط (Active)"

        writer.writerow(
            [
                username,
                clean_name or comment or username,
                renewal_day if renewal_day else "—",
                str(u.get("profile", "—")),
                format_bytes(limit_bytes) if limit_bytes > 0 else "غير محدد",
                format_bytes(bytes_used),
                status_str,
            ]
        )

    return output.getvalue()
