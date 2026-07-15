from dataclasses import dataclass, asdict
from enum import Enum
import json


class CardSystem(Enum):
    """أنظمة إنشاء الكروت الثلاثة."""
    DIFFERENT_CREDENTIALS = 1    # اسم + سر مختلفين
    SAME_CREDENTIALS = 2         # اسم + سر متشابهين
    EMPTY_PASSWORD = 3           # اسم + سر فارغة


@dataclass
class CardData:
    """هيكل بيانات الكارت المشترك بين User Manager و Hotspot."""
    username: str
    password: str
    card_number: int
    profile: str = ""
    caller_id: str = ""
    limit_uptime: str = ""
    limit_bytes: str = ""
    comment: str = ""
    created_at: str = ""
    payment: str = ""

    @property
    def show_password(self) -> bool:
        """إظهار الباسورد فقط إذا كان مختلفاً عن اليوزر."""
        return bool(self.password and self.password != self.username)


def serialize_cards(cards: list["CardData"]) -> str:
    """Serialize a list of CardData into a JSON string."""
    return json.dumps([asdict(c) for c in cards], ensure_ascii=False)


def deserialize_cards(data: str) -> list["CardData"]:
    """Reconstruct a list of CardData from a serialized JSON string."""
    if not data:
        return []
    try:
        raw = json.loads(data)
    except (ValueError, TypeError):
        return []
    if not isinstance(raw, list):
        return []
    cards = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        cards.append(CardData(
            username=item.get("username", ""),
            password=item.get("password", ""),
            card_number=item.get("card_number", 0),
            profile=item.get("profile", ""),
            caller_id=item.get("caller_id", ""),
            limit_uptime=item.get("limit_uptime", ""),
            limit_bytes=item.get("limit_bytes", ""),
            comment=item.get("comment", ""),
            created_at=item.get("created_at", ""),
            payment=item.get("payment", ""),
        ))
    return cards
