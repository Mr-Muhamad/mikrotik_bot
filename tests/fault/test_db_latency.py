"""Fault-injection tests for timed database execution.

Verifies that ``timed_execute`` records both success and failure into the
metrics system and always re-raises the original cursor error.
"""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from database.execute import timed_execute


class TestTimedExecute:
    def test_success_records_metrics(self):
        cursor = MagicMock()
        with patch("database.execute.record_db_query") as mock_record:
            timed_execute(cursor, "SELECT 1", None, "read", "routers")
        mock_record.assert_called_once()
        args, kwargs = mock_record.call_args
        assert kwargs == {}
        assert args[0] == "read"
        assert args[1] == "routers"
        assert args[2] is True
        assert isinstance(args[3], float)

    def test_success_passes_params(self):
        cursor = MagicMock()
        with patch("database.execute.record_db_query"):
            timed_execute(cursor, "SELECT ?", (1,), "read", "routers")
        cursor.execute.assert_called_once_with("SELECT ?", (1,))

    def test_success_defaults_empty_params(self):
        cursor = MagicMock()
        with patch("database.execute.record_db_query"):
            timed_execute(cursor, "SELECT 1")
        cursor.execute.assert_called_once_with("SELECT 1", ())

    def test_failure_records_failure_and_reraises(self):
        cursor = MagicMock()
        cursor.execute.side_effect = sqlite3.OperationalError("no such table")
        with (
            patch("database.execute.record_db_query") as mock_record,
            pytest.raises(Exception, match="no such table"),
        ):
            timed_execute(cursor, "SELECT * FROM missing", None, "read", "routers")
        mock_record.assert_called_once()
        args, kwargs = mock_record.call_args
        assert kwargs == {}
        assert args[0] == "read"
        assert args[1] == "routers"
        assert args[2] is False
        assert isinstance(args[3], float)

    def test_failure_does_not_swallow_error_type(self):
        cursor = MagicMock()
        cursor.execute.side_effect = ValueError("bad sql")
        with (
            patch("database.execute.record_db_query"),
            pytest.raises(ValueError, match="bad sql"),
        ):
            timed_execute(cursor, "garbage")
