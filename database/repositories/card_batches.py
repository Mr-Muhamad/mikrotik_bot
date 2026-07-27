"""Card batch repository.

Stores generated hotspot/User Manager card batches with Fernet-encrypted
payloads. Isolated from the former god-object ``database.models``.
"""

from __future__ import annotations

import json
from datetime import UTC

from core.mikrotik_client import RouterOSRow
from utils.crypto import decrypt_data, encrypt_data


def now_utc() -> str:
    from datetime import datetime

    from database.models import UTC_TIMESTAMP_FORMAT

    return datetime.now(UTC).strftime(UTC_TIMESTAMP_FORMAT)


def save_card_batch(
    router_key: str,
    name: str,
    batch_type: str,
    profile: str = "",
    comment_prefix: str = "",
    cards: list[object] | None = None,
    created_by: int | None = None,
    unit_price: float = 0.0,
) -> int | None:
    """Persist a generated card batch with optional unit price calculation.

    ``cards`` is a JSON-serializable list (list of dicts or CardData). The payload
    is stored encrypted with Fernet so card credentials are not saved in plaintext.
    Returns the new batch id.
    """
    from database.models import get_db

    if cards is None:
        cards = []
    if isinstance(cards, str):
        # Already-serialized JSON payload (e.g. from serialize_cards()).
        payload = cards
        try:
            parsed = json.loads(cards)
            count = len(parsed) if isinstance(parsed, list) else 0
        except (ValueError, TypeError):
            count = 0
    else:
        payload = json.dumps(cards, ensure_ascii=False)
        count = len(cards)
    encrypted = encrypt_data(payload)
    total_price = round(count * unit_price, 2)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO card_batches
               (router_key, name, batch_type, profile, comment_prefix,
               count, cards_json, created_by, created_at, sale_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                router_key,
                name,
                batch_type,
                profile,
                comment_prefix,
                count,
                encrypted,
                created_by,
                now_utc(),
                total_price,
            ),
        )
        return cursor.lastrowid


def list_card_batches(
    router_key: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[RouterOSRow]:
    """Return batch rows (without the encrypted payload) ordered by created_at desc."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        if router_key:
            cursor.execute(
                "SELECT id, router_key, name, batch_type, profile, comment_prefix, count, created_by, created_at "  # noqa: E501
                "FROM card_batches WHERE router_key = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (router_key, limit, offset),
            )
        else:
            cursor.execute(
                "SELECT id, router_key, name, batch_type, profile, comment_prefix, count, created_by, created_at "  # noqa: E501
                "FROM card_batches ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [dict(row) for row in cursor.fetchall()]


def get_card_batches_count(router_key: str | None = None) -> int:
    """Return the total number of card batches for the given router (or all)."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        if router_key:
            cursor.execute(
                "SELECT COUNT(*) as c FROM card_batches WHERE router_key = ?", (router_key,)
            )
        else:
            cursor.execute("SELECT COUNT(*) as c FROM card_batches")
        row = cursor.fetchone()
        return row["c"] if row else 0


def _decode_batch_cards(cards_json: str) -> list[object]:
    """Decrypt and parse a stored batch payload into a list of card dicts."""
    if not cards_json:
        return []
    try:
        decrypted = decrypt_data(cards_json)
    except (ValueError, TypeError):
        return []
    if not decrypted:
        return []
    try:
        raw = json.loads(decrypted)
    except (ValueError, TypeError):
        return []
    return raw if isinstance(raw, list) else []


def get_card_batch(batch_id: int) -> RouterOSRow | None:
    """Return a single batch row including decrypted ``cards`` (list of dicts)."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, router_key, name, batch_type, profile, comment_prefix, count, cards_json, created_by, created_at "  # noqa: E501
            "FROM card_batches WHERE id = ?",
            (batch_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["cards"] = _decode_batch_cards(data.get("cards_json", ""))
        data.pop("cards_json", None)
        return data


def delete_card_batch(batch_id: int) -> int:
    """Delete a stored batch by id. Returns number of deleted rows."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM card_batches WHERE id = ?", (batch_id,))
        return cursor.rowcount


def update_batch_payment(
    batch_id: int, status: str, customer_name: str = "", price: float = 0.0
) -> bool:
    """تحديث حالة الدفع والبيانات التجارية لدفعة كروت.

    status: 'paid' | 'unpaid' | 'deferred'
    يُعيد True عند النجاح.
    """
    from database.models import get_db, now_utc

    valid_statuses = ("paid", "unpaid", "deferred")
    if status not in valid_statuses:
        return False
    sold_at = now_utc() if status == "paid" else None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE card_batches
               SET payment_status = ?, customer_name = ?, sale_price = ?, sold_at = ?
               WHERE id = ?""",
            (status, customer_name or "", price or 0.0, sold_at, batch_id),
        )
        return cursor.rowcount > 0


def get_sales_summary(days: int = 7) -> RouterOSRow:
    """ملخص المبيعات خلال الـ `days` الماضية.

    يُعيد: total_batches, paid_count, total_revenue, unpaid_count, deferred_count
    """
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        if days:
            cursor.execute(
                """SELECT
                       COUNT(*) AS total_batches,
                       SUM(CASE WHEN payment_status='paid' THEN 1 ELSE 0 END) AS paid_count,
                       SUM(CASE WHEN payment_status='unpaid' THEN 1 ELSE 0 END) AS unpaid_count,
                       SUM(CASE WHEN payment_status='deferred' THEN 1 ELSE 0 END) AS deferred_count,
                       SUM(CASE WHEN payment_status='paid'
                       THEN sale_price ELSE 0 END) AS total_revenue
                   FROM card_batches
                   WHERE created_at >= datetime('now', ?)""",
                (f"-{days} days",),
            )
        else:
            cursor.execute("""SELECT
                       COUNT(*) AS total_batches,
                       SUM(CASE WHEN payment_status='paid' THEN 1 ELSE 0 END) AS paid_count,
                       SUM(CASE WHEN payment_status='unpaid' THEN 1 ELSE 0 END) AS unpaid_count,
                       SUM(CASE WHEN payment_status='deferred' THEN 1 ELSE 0 END) AS deferred_count,
                       SUM(CASE WHEN payment_status='paid'
                       THEN sale_price ELSE 0 END) AS total_revenue
                   FROM card_batches""")
        row = cursor.fetchone()
        if not row:
            return {
                "total_batches": 0,
                "paid_count": 0,
                "unpaid_count": 0,
                "deferred_count": 0,
                "total_revenue": 0.0,
            }
        return {
            "total_batches": row["total_batches"] or 0,
            "paid_count": row["paid_count"] or 0,
            "unpaid_count": row["unpaid_count"] or 0,
            "deferred_count": row["deferred_count"] or 0,
            "total_revenue": row["total_revenue"] or 0.0,
        }
