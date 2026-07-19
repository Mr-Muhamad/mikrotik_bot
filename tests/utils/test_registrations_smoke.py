"""Smoke tests for the registrations module — verify constants import cleanly.

Note: handler registration is validated by scripts/validate_handlers.py at runtime,
not via these unit tests, because the singleton patching in conftest makes
import-time side effects fragile in cross-test scenarios.
"""

from bot.handlers import (
    WAITING_USERNAME,
    WAITING_PASSWORD,
    WAITING_PROFILE,
    WAITING_BYTES_TOTAL,
    WAITING_COMMENT,
    WAITING_DELETE_ID,
    WAITING_DELETE_SELECT,
    WAITING_HOTSPOT_SEARCH,
    WAITING_USERMAN_SEARCH,
    WAITING_CARD_COUNT,
    WAITING_CARD_TYPE,
    WAITING_CARD_PROFILE,
    WAITING_PDF_VALUE,
    WAITING_INPUT,
    WAITING_DISC_USERNAME,
    WAITING_DISC_PASSWORD,
    WAITING_SCHEDULE_TIME,
    WAITING_EDIT_FIELD,
    WAITING_EDIT_VALUE,
    WAITING_RENAME,
    WAITING_UPTIME_TYPE,
    WAITING_UPTIME_VALUE,
    WAITING_HOTSPOT_CARD_COUNT,
    WAITING_HOTSPOT_CARD_LENGTH,
    WAITING_HOTSPOT_CARD_PREFIX,
    WAITING_HOTSPOT_CARD_TYPE,
    WAITING_HOTSPOT_CARD_PROFILE,
    WAITING_HOTSPOT_CARD_UPTIME,
    WAITING_HOTSPOT_CARD_BYTES,
    WAITING_USAGE_QUERY,
)


def test_all_30_state_constants_are_ints():
    constants = [
        WAITING_USERNAME,
        WAITING_PASSWORD,
        WAITING_PROFILE,
        WAITING_BYTES_TOTAL,
        WAITING_COMMENT,
        WAITING_DELETE_ID,
        WAITING_DELETE_SELECT,
        WAITING_HOTSPOT_SEARCH,
        WAITING_USERMAN_SEARCH,
        WAITING_CARD_COUNT,
        WAITING_CARD_TYPE,
        WAITING_CARD_PROFILE,
        WAITING_PDF_VALUE,
        WAITING_INPUT,
        WAITING_DISC_USERNAME,
        WAITING_DISC_PASSWORD,
        WAITING_SCHEDULE_TIME,
        WAITING_EDIT_FIELD,
        WAITING_EDIT_VALUE,
        WAITING_RENAME,
        WAITING_UPTIME_TYPE,
        WAITING_UPTIME_VALUE,
        WAITING_HOTSPOT_CARD_COUNT,
        WAITING_HOTSPOT_CARD_LENGTH,
        WAITING_HOTSPOT_CARD_PREFIX,
        WAITING_HOTSPOT_CARD_TYPE,
        WAITING_HOTSPOT_CARD_PROFILE,
        WAITING_HOTSPOT_CARD_UPTIME,
        WAITING_HOTSPOT_CARD_BYTES,
        WAITING_USAGE_QUERY,
    ]
    assert len(constants) == 30
    assert all(isinstance(v, int) for v in constants)
    assert len(set(constants)) == 30
