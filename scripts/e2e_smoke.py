"""End-to-end smoke test for the MikroTik Telegram bot.

This script drives the *real* handler stack (decorators, navigation guards,
ConversationHandler states) through ``Application.process_update`` against a
*real* MikroTik router (discovered_317 by default). It does not need a live
Telegram account: every Update is fabricated in-process and every outgoing
message is captured via a thin Bot shim.

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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import (
    Update,
    User,
    Chat,
    Message,
    CallbackQuery,
    MessageEntity,
)
from telegram.ext import Application, ContextTypes
from telegram._bot import Bot as _BotBase

import config
from database.models import save_user_session, init_db
from bot.registrations import build_all
from utils.admin_decorator import reset_rate_limit

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("e2e")

USER_ID = config.ADMIN_IDS[0]
CHAT_ID = USER_ID
ROUTER_KEY = "discovered_317"

sent_messages: list[dict[str, Any]] = []
captured_errors: list[str] = []


def _new_message(text):
    return Message(
        message_id=len(sent_messages) + 1,
        date=datetime.now(),
        chat=_make_chat(),
        from_user=_make_user(),
        text=text,
    )


class FakeBot(_BotBase):
    """A Bot that never hits Telegram; captures every outgoing message."""

    def __init__(self, token, **kwargs):
        super().__init__(token, **kwargs)
        # Seed the internal _bot so CommandHandler.username works without a
        # network round-trip to getMe. We reuse the bot itself as its own
        # identity source (Bot already exposes username via get_me).
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
        sent_messages.append({"type": "message", "chat_id": chat_id, "text": text, "kwargs": kwargs})
        return _new_message(text)

    async def edit_message_text(self, text=None, **kwargs):  # type: ignore[reportIncompatibleMethodOverride]
        sent_messages.append({"type": "edit", "text": text, "kwargs": kwargs})
        return _new_message(text)

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
        return _new_message(None)


def _make_user() -> User:
    return User(id=USER_ID, first_name="E2E Admin", is_bot=False, username="e2e")


def _make_chat() -> Chat:
    return Chat(id=CHAT_ID, type="private")


def _msg(text: str, bot=None) -> Message:
    kwargs: dict[str, Any] = dict(
        message_id=1,
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
        id="1",
        from_user=_make_user(),
        chat_instance="ci",
        message=msg,
        data=data,
    )
    if bot is not None:
        cq._bot = bot
        msg._bot = bot
    return cq


async def run_flow(app: Application, update: Update) -> None:
    # The bot enforces a per-user rate limit (RATE_LIMIT_WINDOW seconds). The
    # e2e suite drives commands immediately after one another, so we reset the
    # limiter before each flow to avoid silently dropping legitimately-fast
    # test commands (which would mask real failures).
    reset_rate_limit(USER_ID)
    update._bot = app.bot
    # Log which handler PTB selects, for diagnostics.
    for group in app.handlers.values():
        for handler in group:
            try:
                if handler.check_update(update):
                    logger.debug("MATCH handler=%s", type(handler).__name__)
                    break
            except Exception:
                pass
    try:
        await app.process_update(update)
    except Exception as e:  # never abort the whole suite on one failure
        captured_errors.append(f"{type(e).__name__}: {e}")
        logger.exception("Update raised: %s", e)


def last_texts(n: int = 3) -> list[str]:
    out = []
    for m in reversed(sent_messages):
        t = m.get("text")
        if t:
            out.append(str(t))
        if len(out) >= n:
            break
    return out


async def main() -> int:
    init_db()
    save_user_session(USER_ID, selected_router=ROUTER_KEY)

    application = (
        Application.builder()
        .bot(FakeBot(config.BOT_TOKEN))
        .concurrent_updates(False)
        .updater(None)
        .build()
    )
    build_all(application)
    await application.initialize()
    # Ensure the internal _bot is seeded (initialize should keep FakeBot, but
    # guard against any reset by pointing it back at the bot itself).
    application.bot._bot = application.bot

    results: list[tuple[str, bool, str]] = []

    def check(name: str, predicate) -> None:
        ok = bool(predicate)
        snippet = ""
        if sent_messages:
            snippet = (sent_messages[-1].get("text") or "")[:120]
        if not ok:
            logger.info("  >> sent count=%d texts=%s", len(sent_messages),
                        [ (m.get('text') or '')[:40] for m in sent_messages])
        results.append((name, ok, snippet))
        status = "PASS" if ok else "FAIL"
        logger.info("[%s] %s :: %s", status, name, snippet.replace("\n", " ")[:120])

    bot = application.bot

    # 1. /start with router pre-selected
    sent_messages.clear()
    await run_flow(application, Update(1, message=_msg("/start", bot=bot)))
    check("start_with_router", any("القائمة" in (m.get("text") or "") for m in sent_messages))

    # 2. /help
    sent_messages.clear()
    await run_flow(application, Update(2, message=_msg("/help", bot=bot)))
    check("help", any("مساعدة" in (m.get("text") or "") or "أمر" in (m.get("text") or "") for m in sent_messages))

    # 3. /metrics (router metadata, no router API needed)
    sent_messages.clear()
    await run_flow(application, Update(3, message=_msg("/metrics", bot=bot)))
    check("metrics", len(sent_messages) > 0)

    # 4. hotspot menu (callback)
    sent_messages.clear()
    await run_flow(application, Update(4, callback_query=_cb("menu_hotspot", bot=bot)))
    check("hotspot_menu", any("هوتسبوت" in (m.get("text") or "") for m in sent_messages))

    # 5. hotspot stats (real router query)
    sent_messages.clear()
    await run_flow(application, Update(5, callback_query=_cb("hotspot_stats", bot=bot)))
    check("hotspot_stats", len(sent_messages) > 0)

    # 6. hotspot search start
    sent_messages.clear()
    await run_flow(application, Update(6, callback_query=_cb("hotspot_search", bot=bot)))
    check("hotspot_search_start", any("بحث" in (m.get("text") or "") for m in sent_messages))

    # 7. hotspot add start
    sent_messages.clear()
    await run_flow(application, Update(7, callback_query=_cb("hotspot_add", bot=bot)))
    check("hotspot_add_start", any("اسم" in (m.get("text") or "") or "المستخدم" in (m.get("text") or "") for m in sent_messages))

    # 8. user manager menu
    sent_messages.clear()
    await run_flow(application, Update(8, callback_query=_cb("menu_userman", bot=bot)))
    check("userman_menu", len(sent_messages) > 0)

    # 9. stats menu
    sent_messages.clear()
    await run_flow(application, Update(9, callback_query=_cb("menu_stats", bot=bot)))
    check("stats_menu", len(sent_messages) > 0)

    # 10. backup menu
    sent_messages.clear()
    await run_flow(application, Update(10, callback_query=_cb("menu_backup", bot=bot)))
    check("backup_menu", any("نسخ" in (m.get("text") or "") for m in sent_messages))

    # 11. pdf settings menu
    sent_messages.clear()
    await run_flow(application, Update(11, callback_query=_cb("menu_pdf_settings", bot=bot)))
    check("pdf_settings_menu", len(sent_messages) > 0)

    # 12. /logs
    sent_messages.clear()
    await run_flow(application, Update(12, message=_msg("/logs", bot=bot)))
    check("logs", len(sent_messages) > 0)

    # 13. /usage
    sent_messages.clear()
    await run_flow(application, Update(13, message=_msg("/usage", bot=bot)))
    check("usage", len(sent_messages) > 0)

    # 14. /watchdog
    sent_messages.clear()
    await run_flow(application, Update(14, message=_msg("/watchdog", bot=bot)))
    check("watchdog", len(sent_messages) > 0)

    # 15. saved routers list
    sent_messages.clear()
    await run_flow(application, Update(15, callback_query=_cb("saved_routers", bot=bot)))
    check("saved_routers", len(sent_messages) > 0)

    await application.shutdown()

    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("\n" + "=" * 60)
    print(f"E2E RESULTS: {passed}/{len(results)} passed, {failed} failed, {len(captured_errors)} handler errors")
    for name, ok, snippet in results:
        mark = "OK " if ok else "ERR"
        print(f"  [{mark}] {name}")
    if captured_errors:
        print("\nHandler exceptions:")
        for e in captured_errors:
            print("  -", e)
    return 0 if failed == 0 and not captured_errors else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
