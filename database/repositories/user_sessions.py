"""User session repository.

Stores per-user conversation/session state (selected router, current action).
Isolated from the former god-object ``database.models``.
"""
from __future__ import annotations


def get_user_session(user_id):
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_sessions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def save_user_session(user_id, selected_router=None, current_action=None, action_data=None):
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_sessions (user_id, selected_router, current_action, action_data)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   selected_router=CASE 
                       WHEN excluded.selected_router IS NOT NULL AND excluded.selected_router != '' 
                       THEN excluded.selected_router 
                       ELSE user_sessions.selected_router 
                   END,
                   current_action=excluded.current_action,
                   action_data=excluded.action_data""",
            (user_id, selected_router, current_action, action_data),
        )
