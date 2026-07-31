"""End-to-end smoke test for the MikroTik Telegram bot.

This script drives the *real* handler stack through ``Application.process_update``
against fabricated Updates for all 31 mapped main and sub-flows.

Run:
    py -3.12 scripts/e2e_smoke.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from telegram import (
    CallbackQuery,
    Chat,
    Message,
    MessageEntity,
    Update,
    User,
)
from telegram._bot import Bot as _BotBase
from telegram.ext import Application, ConversationHandler

import config
from bot.registrations import build_all
from database.models import init_db, save_user_session
from database.repositories.routers import save_discovered_router
from utils.admin_decorator import reset_rate_limit

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("e2e")

USER_ID = config.ADMIN_IDS[0]
CHAT_ID = USER_ID

sent_messages: list[dict[str, Any]] = []
captured_errors: list[str] = []


def _new_message(text, bot=None):
    m = Message(
        message_id=len(sent_messages) + 1,
        date=datetime.now(),
        chat=_make_chat(),
        from_user=_make_user(),
        text=text,
    )
    if bot is not None:
        m._bot = bot
    return m


class FakeBot(_BotBase):
    """A Bot that captures every outgoing message without network activity."""

    def __init__(self, token, **kwargs):
        super().__init__(token, **kwargs)
        self._bot = self

    @property
    def username(self):
        return "e2e_bot"

    async def send_message(self, *args, chat_id=None, text=None, **kwargs):
        if args:
            chat_id = args[0]
            if len(args) > 1:
                text = args[1]
        logger.debug("FakeBot.send_message called chat=%s text=%r", chat_id, (text or "")[:60])
        sent_messages.append(
            {"type": "message", "chat_id": chat_id, "text": text, "kwargs": kwargs}
        )
        return _new_message(text, bot=self)

    async def edit_message_text(self, text=None, **kwargs):  # type: ignore[reportIncompatibleMethodOverride]
        sent_messages.append({"type": "edit", "text": text, "kwargs": kwargs})
        return _new_message(text, bot=self)

    async def answer_callback_query(self, *a, **k):
        return True

    async def delete_message(self, *a, **k):
        return True

    async def get_me(self):  # type: ignore[reportIncompatibleMethodOverride]
        return User(id=USER_ID, first_name="E2E Admin", is_bot=True, username="e2e_bot")

    async def set_my_commands(self, *a, **k):
        return True

    async def send_document(self, *a, **k):
        sent_messages.append({"type": "document", "kwargs": k})
        return _new_message(None, bot=self)


def _make_user() -> User:
    return User(id=USER_ID, first_name="E2E Admin", is_bot=False, username="e2e")


def _make_chat() -> Chat:
    return Chat(id=CHAT_ID, type="private")


def _msg(text: str, bot=None) -> Message:
    kwargs: dict[str, Any] = dict(
        message_id=len(sent_messages) + 1,
        date=datetime.now(),
        chat=_make_chat(),
        from_user=_make_user(),
        text=text,
    )
    if text.startswith("/"):
        kwargs["entities"] = [
            MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len(text.split()[0]))
        ]
    m = Message(**kwargs)
    if bot is not None:
        m._bot = bot
    return m


def _cb(data: str, bot=None, message: Message | None = None) -> CallbackQuery:
    msg = message or _msg("menu", bot=bot)
    cq = CallbackQuery(
        id=str(len(sent_messages) + 1),
        from_user=_make_user(),
        chat_instance="ci",
        message=msg,
        data=data,
    )
    if bot is not None:
        cq._bot = bot
        msg._bot = bot
    return cq


def clear_ptb_conversations(app: Application):
    """Clear PTB conversation states across all groups."""
    for group in app.handlers.values():
        for handler in group:
            if isinstance(handler, ConversationHandler):
                if hasattr(handler, "_conversations"):
                    handler._conversations.clear()


async def run_flow(app: Application, update: Update) -> None:
    reset_rate_limit(USER_ID)
    update._bot = app.bot
    try:
        await app.process_update(update)
    except Exception as e:  # noqa: BLE001
        captured_errors.append(f"{type(e).__name__}: {e}")
        logger.exception("Update raised: %s", e)


async def main() -> int:
    init_db()
    router_id = save_discovered_router(
        ip="192.0.1.87",
        identity="discovered_317",
        username="admin",
        password="encrypted_pass",
        port=8728,
    )
    router_key = f"discovered_{router_id}" if router_id else "discovered_317"
    save_user_session(USER_ID, selected_router=router_key)

    import bot.router_selector as rs
    from core.hotspot_manager import hotspot_manager
    from core.mikrotik_api import mikrotik_api

    async def _fake_reachability(rk: str) -> bool:
        return True

    rs._fast_reachability_check = _fake_reachability

    # Mock RouterOS API calls so E2E test suite runs offline without real network credentials
    mikrotik_api.execute = MagicMock(return_value=[{"name": "default", "users": "10"}])
    mikrotik_api.execute_long = MagicMock(return_value=[{"name": "default", "users": "10"}])
    hotspot_manager.get_active_users = MagicMock(return_value=[])
    hotspot_manager.get_users = MagicMock(return_value=[])
    hotspot_manager.get_profiles = MagicMock(return_value=["default", "10MB"])
    hotspot_manager.user_exists = MagicMock(return_value=False)

    # Keep the smoke run side-effect-free: skip persisting card batches to the dev DB
    import bot.handlers.hotspot_cards as hotspot_cards_module

    hotspot_cards_module.save_card_batch = MagicMock(return_value=1)

    application = (
        Application.builder()
        .bot(FakeBot(config.BOT_TOKEN))
        .concurrent_updates(False)
        .updater(None)
        .build()
    )
    build_all(application)
    await application.initialize()
    application.bot._bot = application.bot

    results: list[tuple[str, bool, str]] = []

    def check(name: str, predicate) -> None:
        ok = bool(predicate)
        snippet = ""
        if sent_messages:
            snippet = (sent_messages[-1].get("text") or "")[:120]
        else:
            snippet = f"ERRORS: {captured_errors[-1] if captured_errors else 'no sent msgs'}"
        results.append((name, ok, snippet))
        status = "PASS" if ok else "FAIL"
        logger.info("[%s] %s :: %s", status, name, snippet.replace("\n", " ")[:120])

    bot = application.bot
    up_id = 100

    async def step_msg(text: str, reset_conv: bool = False):
        nonlocal up_id
        if reset_conv:
            clear_ptb_conversations(application)
        up_id += 1
        await run_flow(application, Update(up_id, message=_msg(text, bot=bot)))

    async def step_cb(data: str, reset_conv: bool = False):
        nonlocal up_id
        if reset_conv:
            clear_ptb_conversations(application)
        up_id += 1
        await run_flow(application, Update(up_id, callback_query=_cb(data, bot=bot)))

    # Reset initial state
    await step_msg("/cancel", reset_conv=True)

    # --- 1. Basic & Menu Flows ---
    sent_messages.clear()
    await step_msg("/start", reset_conv=True)
    check("1. start_with_router", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/help", reset_conv=True)
    check("2. help", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/metrics", reset_conv=True)
    check("3. metrics", len(sent_messages) > 0)

    # --- 2. Hotspot Full & Sub-Flows ---
    sent_messages.clear()
    await step_cb("menu_hotspot", reset_conv=True)
    check("4. hotspot_menu", len(sent_messages) > 0)

    sent_messages.clear()
    await step_cb("hotspot_stats", reset_conv=True)
    check("5. hotspot_stats", len(sent_messages) > 0)

    # H7: Hotspot Search Flow
    sent_messages.clear()
    await step_cb("hotspot_search", reset_conv=True)
    check("6. hotspot_search_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    # H1: Hotspot Add User Start
    sent_messages.clear()
    await step_cb("hotspot_add", reset_conv=True)
    check("7. hotspot_add_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)
    
    # H2: Hotspot Add Cancel
    sent_messages.clear()
    await step_msg("/cancel", reset_conv=True)
    check("8. hotspot_add_cancel", len(sent_messages) > 0)

    # H4: Hotspot Edit Start
    sent_messages.clear()
    await step_cb("hotspot_edit", reset_conv=True)
    check("9. hotspot_edit_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    # H5: Hotspot Delete Start
    sent_messages.clear()
    await step_cb("hotspot_delete", reset_conv=True)
    check("10. hotspot_delete_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    # H6: Hotspot Cards Start
    sent_messages.clear()
    await step_cb("hotspot_cards", reset_conv=True)
    check("11. hotspot_cards_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    # H6b: Full cards flow with EMPTY_PASSWORD (no password) must produce a PDF end-to-end
    sent_messages.clear()
    await step_cb("hotspot_cards", reset_conv=True)
    await step_msg("1")
    await step_msg("4")
    await step_cb("hs_skip_prefix")
    await step_cb("hs_skip_price")
    await step_cb("hs_card_type3")
    await step_cb("hs_card_profile_0")
    await step_cb("uptime_days")
    await step_msg("1")
    await step_cb("hs_skip_bytes")
    check(
        "11b. hotspot_cards_empty_password_pdf",
        any(m.get("type") == "document" for m in sent_messages),
    )
    await step_msg("/cancel", reset_conv=True)

    # H8: Blocked MAC List (button lives inside the search flow state)
    sent_messages.clear()
    await step_cb("hotspot_search", reset_conv=True)
    await step_msg("mac:aa:bb:cc:dd:ee:ff")
    await step_cb("blocked_list")
    check("12. hotspot_blocked_mac_list", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    # --- 3. User Manager Flows ---
    sent_messages.clear()
    await step_cb("menu_userman", reset_conv=True)
    check("13. userman_menu", len(sent_messages) > 0)

    sent_messages.clear()
    await step_cb("userman_cards", reset_conv=True)
    check("14. userman_cards_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    sent_messages.clear()
    await step_cb("userman_search", reset_conv=True)
    check("15. userman_search_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    sent_messages.clear()
    await step_cb("batches_search", reset_conv=True)
    check("16. batches_search_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    # --- 4. Stats & System Flows ---
    sent_messages.clear()
    await step_cb("menu_stats", reset_conv=True)
    check("17. stats_menu", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/usage", reset_conv=True)
    check("18. usage_report", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/watchdog", reset_conv=True)
    check("19. watchdog_status", len(sent_messages) > 0)

    # --- 5. Backup & Restore Flows ---
    sent_messages.clear()
    await step_cb("menu_backup", reset_conv=True)
    check("20. backup_menu", len(sent_messages) > 0)

    sent_messages.clear()
    await step_cb("menu_schedule", reset_conv=True)
    check("21. schedule_backup_menu", len(sent_messages) > 0)

    # --- 6. Router Management Flows ---
    sent_messages.clear()
    await step_cb("saved_routers", reset_conv=True)
    check("22. saved_routers_list", len(sent_messages) > 0)

    sent_messages.clear()
    await step_cb("manual_add_router", reset_conv=True)
    check("23. router_manual_add_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    sent_messages.clear()
    await step_cb(f"rename_router_{router_id}", reset_conv=True)
    check("24. router_rename_start", len(sent_messages) > 0)
    await step_msg("/cancel", reset_conv=True)

    sent_messages.clear()
    await step_cb(f"reboot_router_{router_id}", reset_conv=True)
    check("25. router_reboot_prompt", len(sent_messages) > 0)

    # --- 7. Settings, Roles & Audit Flows ---
    sent_messages.clear()
    await step_cb("menu_pdf_settings", reset_conv=True)
    check("26. pdf_settings_menu", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/logs", reset_conv=True)
    check("27. logs_audit_view", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/roles", reset_conv=True)
    check("28. roles_admin_view", len(sent_messages) > 0)

    sent_messages.clear()
    await step_cb("go_back", reset_conv=True)
    check("29. menu_go_back_navigation", len(sent_messages) > 0)

    # --- 8. Standalone Clean & Sync Commands ---
    sent_messages.clear()
    await step_msg("/clean", reset_conv=True)
    check("30. clean_chat_command", len(sent_messages) > 0)

    sent_messages.clear()
    await step_msg("/sync", reset_conv=True)
    check("31. sync_profiles_command", len(sent_messages) > 0)

    await application.shutdown()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("\n" + "=" * 60)
    print(
        f"E2E RESULTS: {passed}/{len(results)} passed, {failed} failed, {len(captured_errors)} handler errors"
    )
    for name, ok, snippet in results:
        mark = "OK " if ok else "ERR"
        print(f"  [{mark}] {name} :: {snippet[:60]}")
    if captured_errors:
        print("\nHandler exceptions:")
        for e in captured_errors:
            print("  -", e)
    return 0 if failed == 0 and not captured_errors else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
