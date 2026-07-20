from dataclasses import dataclass, field
from typing import Any


@dataclass
class HotspotAddSession:
    """Strongly-typed session state for the hotspot_add flow."""

    username: str = ""
    password: str = ""
    profile: str = ""
    uptime_type: str = ""
    uptime_value: str = ""
    comment: str = ""
    bytes_total: str = ""


def get_hotspot_add_session(user_data: Any) -> HotspotAddSession:
    """Retrieve or initialize the HotspotAddSession from user_data."""
    if "hotspot_add_session" not in user_data:
        user_data["hotspot_add_session"] = HotspotAddSession()
    return user_data["hotspot_add_session"]


@dataclass
class HotspotEditSession:
    """Strongly-typed session state for the hotspot_edit flow."""

    user_id: str = ""
    user_data: dict = field(default_factory=dict)
    current_field: str = ""


def get_hotspot_edit_session(user_data: Any) -> HotspotEditSession:
    """Retrieve or initialize the HotspotEditSession from user_data."""
    if "hotspot_edit_session" not in user_data:
        user_data["hotspot_edit_session"] = HotspotEditSession()
    return user_data["hotspot_edit_session"]
