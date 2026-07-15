"""Router (discovered/saved) repository.

Manages the ``discovered_routers`` table: discovery persistence, credential
encryption, and metadata helpers. Isolated from the former god-object
``database.models``.
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import DEFAULT_API_PORT


def _utc_now():
    from database.models import UTC_TIMESTAMP_FORMAT

    return datetime.now(timezone.utc).strftime(UTC_TIMESTAMP_FORMAT)


def save_discovered_router(ip, mac="", identity="Unknown", version="", board="",
                           software_id="", platform="MikroTik", uptime="",
                           port=DEFAULT_API_PORT, username="", password="", last_seen=""):
    from database.models import get_db, encrypt_password

    with get_db() as conn:
        cursor = conn.cursor()
        encrypted_password = encrypt_password(password)
        cursor.execute("""
            INSERT INTO discovered_routers
                (ip_address, mac_address, identity, version, board, software_id,
                 platform, uptime, port, username, password, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip_address) DO UPDATE SET
                mac_address=excluded.mac_address,
                identity=excluded.identity,
                version=excluded.version,
                board=excluded.board,
                software_id=excluded.software_id,
                platform=excluded.platform,
                uptime=excluded.uptime,
                port=excluded.port,
                username=CASE WHEN excluded.username != '' THEN excluded.username ELSE username END,
                password=CASE WHEN excluded.password != '' THEN excluded.password ELSE password END,
                last_seen=excluded.last_seen,
                is_active=1
        """, (ip, mac, identity, version, board, software_id, platform, uptime, port, username, encrypted_password, last_seen))
        cursor.execute("SELECT id FROM discovered_routers WHERE ip_address = ?", (ip,))
        result = cursor.fetchone()
        router_id = result["id"] if result else None
        return router_id


def save_manual_router(ip, port=DEFAULT_API_PORT, username="", password="", alias=""):
    """Insert a manually-entered router.

    Encrypts the password before storage. Raises ``sqlite3.IntegrityError``
    if ``ip_address`` already exists (the column is UNIQUE).
    """
    from database.models import get_db, encrypt_password

    with get_db() as conn:
        cursor = conn.cursor()
        encrypted_password = encrypt_password(password)
        cursor.execute(
            """INSERT INTO discovered_routers
                   (ip_address, identity, port, username, password, name_alias, is_active)
               VALUES (?, 'Unknown', ?, ?, ?, ?, 1)""",
            (ip, port, username, encrypted_password, alias),
        )
        return cursor.lastrowid


def get_saved_routers(active_only=True, decrypt: bool = False):
    """جلب الروترات المحفوظة من قاعدة البيانات.

    Args:
        active_only: تصفية الروترات النشطة فقط.
        decrypt: فك تشفير كلمات المرور. افتراضي False لتجنب CPU overhead
                 عندما لا يحتاج المستدعي كلمة المرور (مثل عرض القائمة).
                 استدعِ مع decrypt=True فقط عند الحاجة للاتصال بالراوتر.
    """
    from database.models import get_db, decrypt_password

    with get_db() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("SELECT * FROM discovered_routers WHERE is_active = 1 ORDER BY added_at DESC")
        else:
            cursor.execute("SELECT * FROM discovered_routers ORDER BY added_at DESC")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if decrypt:
                d["password"] = decrypt_password(d.get("password", ""))
            result.append(d)
        return result


def get_router_by_id(router_id, decrypt=True):
    from database.models import get_db, decrypt_password

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discovered_routers WHERE id = ?", (router_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            if decrypt:
                d["password"] = decrypt_password(d.get("password", ""))
            return d
        return None


def get_router_by_ip(ip_address):
    from database.models import get_db, decrypt_password

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discovered_routers WHERE ip_address = ?", (ip_address,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            d["password"] = decrypt_password(d.get("password", ""))
            return d
        return None


def update_router_credentials(router_id, username, password):
    from database.models import get_db, encrypt_password

    with get_db() as conn:
        cursor = conn.cursor()
        encrypted_password = encrypt_password(password)
        cursor.execute(
            "UPDATE discovered_routers SET username = ?, password = ? WHERE id = ?",
            (username, encrypted_password, router_id)
        )


def update_router_last_seen(router_id):
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE discovered_routers SET last_seen = ? WHERE id = ?",
            (_utc_now(), router_id)
        )


def update_router_identity(router_id, identity):
    """Update the identity (name) of a router in the database."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE discovered_routers SET identity = ? WHERE id = ?",
            (identity, router_id)
        )


def delete_router(router_id):
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM discovered_routers WHERE id = ?", (router_id,))


def update_router_alias(router_id, alias):
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE discovered_routers SET name_alias = ? WHERE id = ?", (alias, router_id))


def get_router_display_name(router):
    alias = router.get("name_alias", "") or ""
    if alias:
        return alias
    identity = router.get("identity", "Unknown")
    if identity and identity != "Unknown":
        return identity
    return router.get("ip_address", "Unknown")
