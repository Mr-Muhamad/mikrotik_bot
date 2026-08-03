"""Fault-injection tests for sanitizing malformed RouterOS responses.

``sanitize_api_response`` must never crash the logging path when a router
returns unexpected row types (``None``, scalars) inside a non-empty list.
"""

import pytest

from utils.formatters import sanitize_api_response


class TestMalformedRows:
    @pytest.mark.parametrize(
        "payload",
        [
            [None],
            [123],
            ["plain-string"],
            [None, 123, "x"],
            [[], {}, 0],
        ],
    )
    def test_non_dict_rows_pass_through_unchanged(self, payload):  # type: ignore[reportMissingParameterType]
        assert sanitize_api_response(payload) == payload

    def test_mixed_rows_sanitize_only_dicts(self):
        payload = [{"password": "p", "name": "user1"}, None, 42]
        result = sanitize_api_response(payload)  # type: ignore[reportArgumentType]
        assert result[0] == {"password": "***", "name": "user1"}
        assert result[1] is None
        assert result[2] == 42

    def test_empty_list_returns_same_instance(self):
        payload = []
        assert sanitize_api_response(payload) is payload

    def test_sensitive_fields_only_masked(self):
        payload = [{"password": "p", "secret": "s", "shared-users": "3", "comment": "ok"}]
        result = sanitize_api_response(payload)[0]  # type: ignore[reportArgumentType]
        assert result["password"] == "***"
        assert result["secret"] == "***"
        assert result["shared-users"] == "***"
        assert result["comment"] == "ok"
