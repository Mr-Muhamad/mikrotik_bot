"""Hotspot MAC blocking operations (firewall address-list management).

Extracted from ``core.hotspot_manager`` so that user/host lifecycle logic
stays separate from firewall address-list manipulation.
"""

import logging

from core.mikrotik_client import MikrotikClient, RouterOSRow

logger = logging.getLogger(__name__)


def block_mac(
    api: MikrotikClient,
    router_key: str,
    mac: str,
    comment: str = "blocked by bot",
) -> bool:
    """يضيف MAC إلى address-list باسم hotspot_blocked في /ip/firewall/address-list.

    يُعيد True عند النجاح وFalse عند الفشل.
    ملاحظة: يحتاج إلى firewall rule منفصلة لحظر الاتصال فعلياً.
    """
    from utils.validators import validate_mac

    is_valid, normalized_mac = validate_mac(mac)
    if not is_valid:
        logger.warning(f"Invalid MAC address format rejected in block_mac: {mac!r}")
        return False
    mac = normalized_mac

    # Sanitize comment string to avoid special characters injection
    safe_comment = comment.replace("\n", " ").replace("\r", "").strip()[:100]

    try:
        api.execute(
            router_key,
            "ip/firewall/address-list/add",
            address=mac,
            list="hotspot_blocked",
            comment=safe_comment,
        )
        logger.info(f"Blocked MAC {mac} on {router_key}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Failed to block MAC {mac} on {router_key} in block_mac "
            f"(error type: {type(e).__name__}): {e}",
            exc_info=True,
        )
        return False


def unblock_mac(api: MikrotikClient, router_key: str, mac: str) -> bool:
    """يحذف MAC من address-list=hotspot_blocked.

    يُعيد True عند النجاح وFalse عند الفشل أو عدم الوجود.
    """
    try:
        entries = api.execute(
            router_key,
            "ip/firewall/address-list/print",
            **{"?list": "hotspot_blocked", "?address": mac},
        )
        if not entries:
            logger.info(f"MAC {mac} not found in blocked list on {router_key}")
            return False
        entry_id = entries[0].get(".id")
        if not entry_id:
            return False
        api.execute(
            router_key,
            "ip/firewall/address-list/remove",
            **{".id": entry_id},
        )
        logger.info(f"Unblocked MAC {mac} on {router_key}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Failed to unblock MAC {mac} on {router_key} in unblock_mac "
            f"(error type: {type(e).__name__}): {e}",
            exc_info=True,
        )
        return False


def get_blocked_macs(api: MikrotikClient, router_key: str) -> list[RouterOSRow]:
    """يُعيد قائمة MACs في address-list=hotspot_blocked.

    يُعيد قائمة فارغة عند الفشل.
    """
    try:
        entries = api.execute(
            router_key,
            "ip/firewall/address-list/print",
            **{"?list": "hotspot_blocked"},
        )
        return [
            {
                "address": e.get("address", ""),
                "comment": e.get("comment", ""),
                "creation-time": e.get("creation-time", ""),
            }
            for e in entries
            if isinstance(e, dict)  # type: ignore[reportUnnecessaryIsInstance]
        ]
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"Failed to fetch blocked MACs on {router_key} in get_blocked_macs "
            f"(error type: {type(e).__name__}): {e}",
            exc_info=True,
        )
        return []
