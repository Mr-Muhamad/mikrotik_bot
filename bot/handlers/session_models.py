from dataclasses import dataclass, field

from core.mikrotik_client import RouterOSRow


@dataclass
class HotspotAddSession:
    username: str = ""
    password: str = ""
    profile: str = ""
    uptime_type: str = ""
    uptime_value: str = ""
    comment: str = ""
    bytes_total: str = ""


def get_hotspot_add_session(user_data: dict[str, object] | None) -> HotspotAddSession:
    if user_data is None:
        return HotspotAddSession()
    if "hotspot_add_session" not in user_data:  # type: ignore[operator]
        user_data["hotspot_add_session"] = HotspotAddSession()
    return user_data["hotspot_add_session"]  # type: ignore[return-value]


@dataclass
class HotspotEditSession:
    user_id: str = ""
    user_data: RouterOSRow = field(default_factory=dict)
    current_field: str = ""


def get_hotspot_edit_session(user_data: dict[str, object] | None) -> HotspotEditSession:
    if user_data is None:
        return HotspotEditSession()
    if "hotspot_edit_session" not in user_data:  # type: ignore[operator]
        user_data["hotspot_edit_session"] = HotspotEditSession()
    return user_data["hotspot_edit_session"]  # type: ignore[return-value]
