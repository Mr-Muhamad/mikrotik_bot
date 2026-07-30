"""Tests for database.repositories.chat_messages — CRUD operations."""

from unittest.mock import MagicMock, patch


class SQLiteError(Exception):
    pass


class TestAddTrackedMessage:
    def test_inserts_record(self):
        from database.models import get_db
        from database.repositories.chat_messages import add_tracked_message

        add_tracked_message(100, 1)
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM tracked_messages").fetchall()
        assert len(rows) == 1
        assert rows[0]["chat_id"] == 100
        assert rows[0]["message_id"] == 1

    def test_multiple_inserts(self):
        from database.models import get_db
        from database.repositories.chat_messages import add_tracked_message

        add_tracked_message(100, 1)
        add_tracked_message(100, 2)
        add_tracked_message(200, 3)
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM tracked_messages ORDER BY rowid").fetchall()
        assert len(rows) == 3

    def test_logs_error_on_failure(self):
        from database.repositories.chat_messages import add_tracked_message

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = SQLiteError("disk full")
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("database.models.get_db", return_value=mock_conn):
            with patch("database.repositories.chat_messages.logger") as mock_log:
                add_tracked_message(100, 1)
        mock_log.error.assert_called_once()
        assert "Failed to track message" in mock_log.error.call_args[0][0]


class TestGetTrackedMessages:
    def test_returns_empty_for_unknown_chat(self):
        from database.repositories.chat_messages import get_tracked_messages

        result = get_tracked_messages(999)
        assert result == []

    def test_returns_message_ids_ordered(self):
        from database.repositories.chat_messages import add_tracked_message, get_tracked_messages

        add_tracked_message(100, 5)
        add_tracked_message(100, 1)
        add_tracked_message(100, 3)
        result = get_tracked_messages(100)
        assert result == [5, 1, 3]

    def test_filters_by_chat_id(self):
        from database.repositories.chat_messages import add_tracked_message, get_tracked_messages

        add_tracked_message(100, 1)
        add_tracked_message(200, 2)
        assert get_tracked_messages(100) == [1]
        assert get_tracked_messages(200) == [2]

    def test_returns_empty_list_on_error(self):
        from database.repositories.chat_messages import get_tracked_messages

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = SQLiteError("corrupt")
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("database.models.get_db", return_value=mock_conn):
            with patch("database.repositories.chat_messages.logger") as mock_log:
                result = get_tracked_messages(100)
        assert result == []
        mock_log.error.assert_called_once()
        assert "Failed to get tracked messages" in mock_log.error.call_args[0][0]


class TestRemoveTrackedMessages:
    def test_noop_when_empty_list(self):
        from database.models import get_db
        from database.repositories.chat_messages import add_tracked_message, remove_tracked_messages

        add_tracked_message(100, 1)
        remove_tracked_messages(100, [])
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) c FROM tracked_messages").fetchone()["c"]
        assert count == 1

    def test_removes_specified_ids(self):
        from database.repositories.chat_messages import (
            add_tracked_message,
            get_tracked_messages,
            remove_tracked_messages,
        )

        add_tracked_message(100, 1)
        add_tracked_message(100, 2)
        add_tracked_message(100, 3)
        remove_tracked_messages(100, [1, 3])
        result = get_tracked_messages(100)
        assert result == [2]

    def test_only_removes_for_specified_chat(self):
        from database.repositories.chat_messages import (
            add_tracked_message,
            get_tracked_messages,
            remove_tracked_messages,
        )

        add_tracked_message(100, 1)
        add_tracked_message(200, 1)
        remove_tracked_messages(100, [1])
        assert get_tracked_messages(100) == []
        assert get_tracked_messages(200) == [1]

    def test_logs_error_on_failure(self):
        from database.repositories.chat_messages import remove_tracked_messages

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = SQLiteError("locked")
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("database.models.get_db", return_value=mock_conn):
            with patch("database.repositories.chat_messages.logger") as mock_log:
                remove_tracked_messages(100, [1, 2])
        mock_log.error.assert_called_once()
        assert "Failed to remove tracked messages" in mock_log.error.call_args[0][0]


class TestDeleteStaleRecords:
    def test_deletes_old_records(self):
        from database.models import get_db
        from database.repositories.chat_messages import add_tracked_message, delete_stale_records

        add_tracked_message(100, 1)
        add_tracked_message(100, 2)
        with get_db() as conn:
            conn.execute(
                "UPDATE tracked_messages SET tracked_at = ? WHERE message_id = 1",
                ("2020-01-01 00:00:00",),
            )
        delete_stale_records("2021-01-01 00:00:00")
        with get_db() as conn:
            rows = conn.execute("SELECT message_id FROM tracked_messages").fetchall()
        assert [r["message_id"] for r in rows] == [2]

    def test_deletes_nothing_when_no_stale(self):
        from database.models import get_db
        from database.repositories.chat_messages import add_tracked_message, delete_stale_records

        add_tracked_message(100, 1)
        delete_stale_records("2020-01-01 00:00:00")
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) c FROM tracked_messages").fetchone()["c"]
        assert count == 1

    def test_logs_purge_count(self):
        from database.repositories.chat_messages import add_tracked_message, delete_stale_records

        add_tracked_message(100, 1)
        add_tracked_message(100, 2)
        from database.models import get_db

        with get_db() as conn:
            conn.execute("UPDATE tracked_messages SET tracked_at = '2020-01-01 00:00:00'")
        with patch("database.repositories.chat_messages.logger") as mock_log:
            delete_stale_records("2021-01-01 00:00:00")
        mock_log.info.assert_called_once()
        assert mock_log.info.call_args[0][0] == "Purged %d stale tracked messages from database."
        assert mock_log.info.call_args[0][1] == 2

    def test_logs_error_on_failure(self):
        from database.repositories.chat_messages import delete_stale_records

        mock_conn = MagicMock()
        mock_conn.execute.side_effect = SQLiteError("io error")
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("database.models.get_db", return_value=mock_conn):
            with patch("database.repositories.chat_messages.logger") as mock_log:
                delete_stale_records("2021-01-01 00:00:00")
        mock_log.error.assert_called_once()
        assert "Failed to delete stale" in mock_log.error.call_args[0][0]
