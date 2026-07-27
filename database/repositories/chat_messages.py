"""Repository for tracking messages sent by the bot for cleanup."""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def add_tracked_message(chat_id: int, message_id: int) -> None:
    """Track a newly sent bot message."""
    from database.models import get_db

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO tracked_messages (chat_id, message_id) VALUES (?, ?)",
                (chat_id, message_id),
            )
    except sqlite3.Error as e:
        logger.error(f"Failed to track message {message_id} in chat {chat_id}: {e}")


def get_tracked_messages(chat_id: int) -> list[int]:
    """Get all tracked message IDs for a chat."""
    from database.models import get_db

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT message_id FROM tracked_messages WHERE chat_id = ? ORDER BY tracked_at ASC",
                (chat_id,),
            )
            return [row["message_id"] for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"Failed to get tracked messages for chat {chat_id}: {e}")
        return []


def remove_tracked_messages(chat_id: int, message_ids: list[int]) -> None:
    """Remove successfully deleted or untrackable messages from tracking."""
    from database.models import get_db

    if not message_ids:
        return
    try:
        with get_db() as conn:
            # SQLite IN clause is limited, but for ~100 IDs it's completely safe.
            placeholders = ",".join("?" for _ in message_ids)
            conn.execute(
                f"DELETE FROM tracked_messages WHERE chat_id = ? AND message_id IN ({placeholders})",  # noqa: E501
                [chat_id] + message_ids,
            )
    except sqlite3.Error as e:
        logger.error(f"Failed to remove tracked messages {message_ids} in chat {chat_id}: {e}")


def delete_stale_records(cutoff_datetime: str) -> None:
    """Remove tracking records older than a cutoff datetime (UTC string)."""
    from database.models import get_db

    try:
        with get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM tracked_messages WHERE tracked_at < ?", (cutoff_datetime,)
            )
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.info(f"Purged {deleted_count} stale tracked messages from database.")
    except sqlite3.Error as e:
        logger.error(f"Failed to delete stale tracked messages: {e}")
