"""Typed key for identifying a router across the bot.

يستبدل الـ string الخام "discovered_<id>" بنوع آمن.
"""

from __future__ import annotations

from config import ROUTER_KEY_PREFIX


class RouterKey:
    """مفتاح راوتر قوي النوع.

    الأنماط المدعومة:
    - RouterKey.discovered(db_id)  → "discovered_5"
    - RouterKey.legacy("router1")  → "router1"

    مثال:
        key = RouterKey.discovered(5)
        db_id = key.db_id  # 5
        str(key)           # "discovered_5"
    """

    __slots__ = ("_raw", "_db_id")

    def __init__(self, raw: str) -> None:
        self._raw = raw
        self._db_id: int | None = None
        if raw.startswith(ROUTER_KEY_PREFIX):
            try:
                self._db_id = int(raw[len(ROUTER_KEY_PREFIX) :])
            except ValueError:
                pass  # parse: suffix is not numeric — db_id stays None for non-discovered keys

    @classmethod
    def discovered(cls, db_id: int) -> RouterKey:
        """إنشاء مفتاح لراوتم مكتشف في DB."""
        return cls(f"{ROUTER_KEY_PREFIX}{db_id}")

    @classmethod
    def parse(cls, raw: str) -> RouterKey:
        """تحليل string إلى RouterKey (يقبل أي قيمة)."""
        return cls(raw)

    @property
    def db_id(self) -> int | None:
        """معرّف DB للراوتر، أو None إذا لم يكن راوتر مكتشف."""
        return self._db_id

    @property
    def raw(self) -> str:
        """النص الخام (للتسجيل والعرض)."""
        return self._raw

    def is_discovered(self) -> bool:
        """هل المفتاح يشير لراوتر مكتشف في DB؟"""
        return self._db_id is not None

    def __str__(self) -> str:
        return self._raw

    def __repr__(self) -> str:
        return f"RouterKey({self._raw!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RouterKey):
            return self._raw == other._raw
        if isinstance(other, str):
            return self._raw == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._raw)
