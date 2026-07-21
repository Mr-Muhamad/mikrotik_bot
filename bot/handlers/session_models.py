from dataclasses import dataclass, field
from typing import Any


@dataclass
class HotspotAddSession:
    username: str = ""
    password: str = ""
    profile: str = ""
    uptime_type: str = ""
    uptime_value: str = ""
    comment: str = ""
    bytes_total: str = ""

def get_hotspot_add_session(user_data: Any) -> HotspotAddSession:
    if "hotspot_add_session" not in user_data:
        user_data["hotspot_add_session"] = HotspotAddSession()
    return user_data["hotspot_add_session"]


@dataclass
class HotspotEditSession:
    user_id: str = ""
    user_data: dict[str, Any] = field(default_factory=dict)
    current_field: str = ""

def get_hotspot_edit_session(user_data: Any) -> HotspotEditSession:
    if "hotspot_edit_session" not in user_data:
        user_data["hotspot_edit_session"] = HotspotEditSession()
    return user_data["hotspot_edit_session"]
