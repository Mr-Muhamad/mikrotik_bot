"""Repository for operator-router permission assignments — Tenant Isolation."""

from __future__ import annotations

import logging
import sqlite3

from database.models import get_db

logger = logging.getLogger(__name__)


def assign_router_to_operator(operator_id: int, router_id: int, assigned_by: int) -> bool:
    """منح مشغّل صلاحية إدارة راوتر معين.

    يُعيد True إن تم الحفظ بنجاح (أو كان موجوداً مسبقاً).
    """
    try:
        with get_db() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO operator_router_permissions
                       (operator_id, router_id, assigned_by)
                   VALUES (?, ?, ?)""",
                (operator_id, router_id, assigned_by),
            )
        return True
    except sqlite3.Error as e:
        logger.warning("Failed to assign router %d to operator %d: %s", router_id, operator_id, e)
        return False


def revoke_router_from_operator(operator_id: int, router_id: int) -> bool:
    """سحب صلاحية مشغّل على راوتر معين.

    يُعيد True إن كان السجل موجوداً وحُذف.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM operator_router_permissions WHERE operator_id = ? AND router_id = ?",
                (operator_id, router_id),
            )
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.warning("Failed to revoke router %d from operator %d: %s", router_id, operator_id, e)
        return False


def get_operator_routers(operator_id: int) -> list[int]:
    """استرداد قائمة router_ids المسموح للمشغّل بإدارتها.

    يُعيد قائمة فارغة إن لم تكن له أي صلاحيات.
    """
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT router_id FROM operator_router_permissions WHERE operator_id = ?",
                (operator_id,),
            ).fetchall()
        return [row["router_id"] for row in rows]
    except sqlite3.Error as e:
        logger.warning("Failed to get routers for operator %d: %s", operator_id, e)
        return []


def is_operator_allowed(operator_id: int, router_id: int) -> bool:
    """فحص إذا كان المشغّل مسموح له بإدارة راوتر معين.

    ملاحظة: ADMIN_IDS لا يمرون من هنا — يُفحصون في decorator مباشرة.
    """
    try:
        with get_db() as conn:
            row = conn.execute(
                "SELECT 1 FROM operator_router_permissions WHERE operator_id = ? AND router_id = ?",
                (operator_id, router_id),
            ).fetchone()
        return row is not None
    except sqlite3.Error as e:
        logger.warning(
            "Failed to check permission for operator %d, router %d: %s",
            operator_id, router_id, e,
        )
        return False
