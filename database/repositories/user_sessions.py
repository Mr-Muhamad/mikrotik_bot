"""User session repository.

Stores per-user conversation/session state (selected router, current action).
Isolated from the former god-object ``database.models``.
"""

from __future__ import annotations


def get_user_session(user_id: int) -> dict[str, object] | None:
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_sessions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None


def save_user_session(
    user_id: int,
    selected_router: str | None = None,
    current_action: str | None = None,
    action_data: str | None = None,
) -> None:
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_sessions
            (user_id, selected_router, current_action, action_data, last_activity)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET
                   selected_router=CASE
                       WHEN excluded.selected_router IS NOT NULL AND excluded.selected_router != ''
                       THEN excluded.selected_router
                       ELSE user_sessions.selected_router
                   END,
                   current_action=excluded.current_action,
                   action_data=excluded.action_data,
                   last_activity=CURRENT_TIMESTAMP""",
            (user_id, selected_router, current_action, action_data),
        )


def update_activity(user_id: int):
    """Update the last_activity timestamp for a user."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_sessions (user_id, last_activity)
               VALUES (?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET last_activity=CURRENT_TIMESTAMP""",
            (user_id,),
        )


def set_session_timeout(user_id: int, timeout_minutes: int):
    """Set the session timeout duration for a user."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO user_sessions (user_id, session_timeout, last_activity)
               VALUES (?, ?, CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET session_timeout=excluded.session_timeout""",
            (user_id, timeout_minutes),
        )


def clear_router_session(user_id: int):
    """Clear the selected router from the user's session (used on timeout)."""
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE user_sessions SET selected_router='' WHERE user_id=?", (user_id,))
