"""Live User Manager card creation test against a saved router.

Creates a small number of real User Manager cards using each of the 3 card
systems (DIFFERENT_CREDENTIALS, SAME_CREDENTIALS, EMPTY_PASSWORD), verifies the
created users exist on the router, then deletes them to leave the router clean.

Usage:
    py -3.12 scripts/live_um_cards_test.py [router_key] [count_per_type]

Defaults to the currently selected router ("discovered_2") and 2 cards per type.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import logging

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

import config  # noqa: E402
from core.profile_sync import profile_sync  # noqa: E402
from core.userman_manager import userman_manager  # noqa: E402
from database.models import init_db  # noqa: E402

CARD_TYPES = ["card_type1", "card_type2", "card_type3"]
PREFIXES = {"card_type1": "LIVE1", "card_type2": "LIVE2", "card_type3": "LIVE3"}


def main() -> int:
    router_key = sys.argv[1] if len(sys.argv) > 1 else "discovered_2"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    init_db()
    print(f"Router: {router_key}")

    profiles = profile_sync.get_userman_profiles(router_key)
    if not profiles:
        print("ERROR: no User Manager profiles found. Is the UM package installed?")
        return 2
    profile = profiles[0]
    print(f"Profiles available: {profiles}")
    print(f"Using profile: {profile}")

    all_created: list[tuple[str, str, str]] = []
    exit_code = 0

    for card_type in CARD_TYPES:
        prefix = PREFIXES[card_type]
        try:
            cards = userman_manager.create_cards(
                router_key,
                count,
                card_type,
                profile,
                prefix=prefix,
            )
        except Exception as e:  # noqa: BLE001 - catch-all: report any failure and continue
            logging.exception("create_cards(%s) raised", card_type)
            print(f"[{card_type}] ERROR: {e}")
            exit_code = 1
            continue

        if not cards:
            print(f"[{card_type}] ERROR: no cards returned")
            exit_code = 1
            continue

        usernames = [str(c.get("username") or c.get("name") or "") for c in cards]
        created = [(card_type, u, profile) for u in usernames if u]
        all_created.extend(created)
        print(f"[{card_type}] created {len(created)}: {usernames}")

        for _, username, _ in created:
            user = userman_manager.get_user(router_key, username)
            status = "VERIFIED" if user is not None else "MISSING"
            if user is None:
                exit_code = 1
            print(f"    {username}: {status}")

    print("\nCleanup:")
    for card_type, username, _ in all_created:
        try:
            userman_manager.delete_user(router_key, username)
            print(f"    deleted {username} ({card_type})")
        except Exception as e:  # noqa: BLE001 - catch-all: report cleanup failure
            logging.exception("delete_user(%s) raised", username)
            print(f"    FAILED to delete {username}: {e}")
            exit_code = 1

    print(f"\n{'PASS' if exit_code == 0 else 'FAIL'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
