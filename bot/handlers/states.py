from enum import IntEnum


class WaitingState(IntEnum):
    """ConversationHandler state constants grouped by feature domain.

    All values are integers 0-27, matching PTB ConversationHandler requirements.
    """

    # Base states (0-14)
    INPUT = 0
    USERNAME = 1
    PASSWORD = 2
    PROFILE = 3
    BYTES_TOTAL = 4
    COMMENT = 5
    EDIT_FIELD = 6
    EDIT_VALUE = 7
    DELETE_ID = 8
    HOTSPOT_SEARCH = 9
    CARD_COUNT = 10
    PDF_VALUE = 11
    DISC_USERNAME = 12
    DISC_PASSWORD = 13
    SCHEDULE_TIME = 14

    # Extended single states (15-18)
    CARD_TYPE = 15
    CARD_PROFILE = 16
    DELETE_SELECT = 17
    RENAME = 18

    # Hotspot add uptime sub-flow (19-20)
    UPTIME_TYPE = 19
    UPTIME_VALUE = 20

    # Hotspot card creation sub-flow (21-27)
    HOTSPOT_CARD_COUNT = 21
    HOTSPOT_CARD_LENGTH = 22
    HOTSPOT_CARD_PREFIX = 23
    HOTSPOT_CARD_TYPE = 24
    HOTSPOT_CARD_PROFILE = 25
    HOTSPOT_CARD_UPTIME = 26
    HOTSPOT_CARD_BYTES = 27

    # Phase 1: Usage query (34)
    USAGE_QUERY = 34

    # Manual router add flow (35-40)
    MANUAL_IP = 35
    MANUAL_PORT = 36
    MANUAL_USER = 37
    MANUAL_PASS = 38
    MANUAL_ALIAS = 39
    MANUAL_CONFIRM = 40

    # Hotspot stats day text input (41)
    STATS_DAY = 41

    # User Manager card payment distinction step (42)
    CARD_PAYMENT = 42

    # User Manager card MAC binding step (50)
    CARD_MAC = 50

    # User Manager card prefix step (51)
    CARD_PREFIX = 51

    # User Manager search (52)
    USERMAN_SEARCH = 52

    # مشاركة كرت WiFi للعميل (53)
    SHARE_RECIPIENT = 53
