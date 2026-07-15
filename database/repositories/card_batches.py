"""Card batch repository.

Stores generated hotspot/User Manager card batches with Fernet-encrypted
payloads. Isolated from the former god-object ``database.models``.
"""
from __future__ import annotations

import json

from utils.crypto import decrypt_data, encrypt_data


def _now_utc():
    from datetime import datetime, timezone

    from database.models import UTC_TIMESTAMP_FORMAT

    return datetime.now(timezone.utc).strftime(UTC_TIMESTAMP_FORMAT)


def save_card_batch(router_key, name, batch_type, profile="", comment_prefix="", cards=None, created_by=None):
    """Persist a generated card batch.

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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO card_batches
               (router_key, name, batch_type, profile, comment_prefix, count, cards_json, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                router_key, name, batch_type, profile, comment_prefix, count,
                encrypted, created_by,
                _now_utc(),
            ),
        )
        return cursor.lastrowid


def list_card_batches(router_key=None):
    """Return batch rows (without the encrypted payload) ordered by created_at desc."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        if router_key:
            cursor.execute(
                "SELECT id, router_key, name, batch_type, profile, comment_prefix, count, created_by, created_at "
                "FROM card_batches WHERE router_key = ? ORDER BY created_at DESC",
                (router_key,),
            )
        else:
            cursor.execute(
                "SELECT id, router_key, name, batch_type, profile, comment_prefix, count, created_by, created_at "
                "FROM card_batches ORDER BY created_at DESC"
            )
        return [dict(row) for row in cursor.fetchall()]


def _decode_batch_cards(cards_json):
    """Decrypt and parse a stored batch payload into a list of card dicts."""
    if not cards_json:
        return []
    try:
        decrypted = decrypt_data(cards_json)
    except Exception:
        return []
    if not decrypted:
        return []
    try:
        raw = json.loads(decrypted)
    except (ValueError, TypeError):
        return []
    return raw if isinstance(raw, list) else []


def get_card_batch(batch_id):
    """Return a single batch row including decrypted ``cards`` (list of dicts)."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, router_key, name, batch_type, profile, comment_prefix, count, cards_json, created_by, created_at "
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


def delete_card_batch(batch_id):
    """Delete a stored batch by id. Returns number of deleted rows."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM card_batches WHERE id = ?", (batch_id,))
        return cursor.rowcount
