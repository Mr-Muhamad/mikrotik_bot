"""Tests for bot.handlers.watchdog – comprehensive coverage."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.handlers import watchdog as watchdog_module
from core.watchdog import ALERT_NONE, ALERT_RECOVERED, ALERT_WENT_OFFLINE
from utils import admin_decorator

ADMIN_ID = 724730774


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    admin_decorator._rate_limit_data.clear()
    yield
    admin_decorator._rate_limit_data.clear()


# ── helpers ────────────────────────────────────────────────────


def _cb_update(data: str = "watchdog_start"):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.from_user = MagicMock(id=ADMIN_ID)
    update.callback_query = query
    update.message = None
    return update


def _msg_update(text: str = "/watchdog"):
    update = MagicMock()
    update.effective_user = MagicMock(id=ADMIN_ID)
    update.effective_chat = MagicMock(id=1)
    update.callback_query = None
    msg = MagicMock()
    msg.text = text
    msg.reply_text = AsyncMock()
    update.message = msg
    return update


def _ctx():
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.job_queue = MagicMock()
    ctx.bot = MagicMock()
    ctx.bot.send_message = AsyncMock()
    return ctx


def _router(db_id=1, **extra):
    base = {"id": db_id, "ip_address": "10.0.0.1", "identity": "Router1"}
    base.update(extra)
    return base


# ── TestWatchdogStart ──────────────────────────────────────────


class TestWatchdogStart:
    @pytest.mark.asyncio
    async def test_no_job_queue(self):
        update = _cb_update()
        ctx = _ctx()
        ctx.job_queue = None
        with patch("bot.handlers.watchdog.send_step", new=AsyncMock()):
            await watchdog_module.watchdog_start(update, ctx)
        assert ctx.job_queue is None

    @pytest.mark.asyncio
    async def test_already_running(self):
        update = _cb_update()
        ctx = _ctx()
        ctx.job_queue.get_jobs_by_name.return_value = [MagicMock()]
        with patch("bot.handlers.watchdog.safe_edit_or_send", new=AsyncMock()):
            await watchdog_module.watchdog_start(update, ctx)
        ctx.job_queue.run_repeating.assert_not_called()

    @pytest.mark.asyncio
    async def test_created_successfully(self):
        update = _cb_update()
        ctx = _ctx()
        ctx.job_queue.get_jobs_by_name.return_value = []
        with patch("bot.handlers.watchdog.safe_edit_or_send", new=AsyncMock()):
            await watchdog_module.watchdog_start(update, ctx)
        ctx.job_queue.run_repeating.assert_called_once()
        call_kw = ctx.job_queue.run_repeating.call_args
        assert call_kw[1]["name"] == "router_watchdog"

    @pytest.mark.asyncio
    async def test_no_callback_answer_for_message(self):
        update = _msg_update()
        ctx = _ctx()
        ctx.job_queue.get_jobs_by_name.return_value = []
        with patch("bot.handlers.watchdog.send_step", new=AsyncMock()):
            await watchdog_module.watchdog_start(update, ctx)
        ctx.job_queue.run_repeating.assert_called_once()


# ── TestWatchdogStop ───────────────────────────────────────────


class TestWatchdogStop:
    @pytest.mark.asyncio
    async def test_no_job_queue(self):
        update = _cb_update()
        ctx = _ctx()
        ctx.job_queue = None
        await watchdog_module.watchdog_stop(update, ctx)

    @pytest.mark.asyncio
    async def test_no_jobs_found(self):
        update = _cb_update()
        ctx = _ctx()
        ctx.job_queue.get_jobs_by_name.return_value = []
        with patch("bot.handlers.watchdog.safe_edit_or_send", new=AsyncMock()):
            await watchdog_module.watchdog_stop(update, ctx)

    @pytest.mark.asyncio
    async def test_jobs_removed(self):
        update = _cb_update()
        ctx = _ctx()
        job1 = MagicMock()
        job2 = MagicMock()
        ctx.job_queue.get_jobs_by_name.return_value = [job1, job2]
        with patch("bot.handlers.watchdog.safe_edit_or_send", new=AsyncMock()):
            await watchdog_module.watchdog_stop(update, ctx)
        job1.schedule_removal.assert_called_once()
        job2.schedule_removal.assert_called_once()

    @pytest.mark.asyncio
    async def test_message_path(self):
        update = _msg_update()
        ctx = _ctx()
        ctx.job_queue.get_jobs_by_name.return_value = []
        with patch("bot.handlers.watchdog.send_step", new=AsyncMock()):
            await watchdog_module.watchdog_stop(update, ctx)


# ── TestWatchdogStatus ─────────────────────────────────────────


class TestWatchdogStatus:
    @pytest.mark.asyncio
    async def test_no_routers(self):
        update = _cb_update()
        ctx = _ctx()
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[]),
            patch("bot.handlers.watchdog.safe_edit_or_send", new=AsyncMock()),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_router_online_with_last_ok(self):
        update = _cb_update()
        ctx = _ctx()
        now = datetime.now()
        detail = {
            "online": True,
            "last_ok": now,
            "last_fail": None,
            "version": "7.14",
            "active_users": 5,
        }
        bk = {"status": "success", "backup_type": "full", "created_at": "2025-01-01"}
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[_router()]),
            patch(
                "bot.handlers.watchdog.run_blocking",
                new_callable=AsyncMock,
                side_effect=[detail, bk],
            ),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_last_backup"),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_router_online_no_last_ok(self):
        update = _cb_update()
        ctx = _ctx()
        detail = {
            "online": True,
            "last_ok": None,
            "last_fail": None,
            "version": None,
            "active_users": None,
        }
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[_router()]),
            patch(
                "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=detail
            ),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_last_backup", return_value=None),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_router_offline_with_last_fail(self):
        update = _cb_update()
        ctx = _ctx()
        now = datetime.now()
        detail = {
            "online": False,
            "last_ok": None,
            "last_fail": now,
            "version": "7.12",
            "active_users": 0,
        }
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[_router()]),
            patch(
                "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=detail
            ),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_last_backup", return_value=None),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_router_unchecked(self):
        update = _cb_update()
        ctx = _ctx()
        detail = {
            "online": False,
            "last_ok": None,
            "last_fail": None,
            "version": None,
            "active_users": None,
        }
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[_router()]),
            patch(
                "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=detail
            ),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_last_backup", return_value=None),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_router_with_alias(self):
        update = _cb_update()
        ctx = _ctx()
        detail = {
            "online": True,
            "last_ok": datetime.now(),
            "last_fail": None,
            "version": "7.14",
            "active_users": 3,
        }
        r = _router(name_alias="MyAlias")
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[r]),
            patch(
                "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=detail
            ),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_last_backup", return_value=None),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_backup_failed(self):
        update = _cb_update()
        ctx = _ctx()
        detail = {
            "online": True,
            "last_ok": datetime.now(),
            "last_fail": None,
            "version": "7.14",
            "active_users": None,
        }
        bk = {"status": "failed", "backup_type": "full", "created_at": "2025-06-01"}
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[_router()]),
            patch(
                "bot.handlers.watchdog.run_blocking",
                new_callable=AsyncMock,
                side_effect=[detail, bk],
            ),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_last_backup"),
        ):
            await watchdog_module.watchdog_status(update, ctx)

    @pytest.mark.asyncio
    async def test_message_path_no_callback(self):
        update = _msg_update()
        ctx = _ctx()
        detail = {
            "online": True,
            "last_ok": datetime.now(),
            "last_fail": None,
            "version": None,
            "active_users": None,
        }
        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[_router()]),
            patch(
                "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=detail
            ),
            patch("bot.handlers.watchdog.get_last_backup", return_value=None),
        ):
            await watchdog_module.watchdog_status(update, ctx)
        update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_routers(self):
        update = _cb_update()
        ctx = _ctx()
        r1 = _router(db_id=1)
        r2 = _router(db_id=2, identity="Router2")
        d1 = {
            "online": True,
            "last_ok": datetime.now(),
            "last_fail": None,
            "version": "7.14",
            "active_users": 2,
        }

        async def fake_blocking(fn, *args, **kwargs):
            from database.models import get_last_backup as _glb

            if fn is _glb:
                return None
            return d1

        with (
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[r1, r2]),
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
        ):
            await watchdog_module.watchdog_status(update, ctx)


# ── TestWatchdogRefresh ────────────────────────────────────────


class TestWatchdogRefresh:
    @pytest.mark.asyncio
    async def test_refresh_calls_check_then_status(self):
        update = _cb_update("watchdog_refresh")
        ctx = _ctx()
        with (
            patch("bot.handlers.watchdog.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.get_saved_routers", return_value=[]),
            patch("bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=[]),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
        ):
            await watchdog_module.watchdog_refresh(update, ctx)

    @pytest.mark.asyncio
    async def test_refresh_with_routers(self):
        update = _cb_update("watchdog_refresh")
        ctx = _ctx()
        router = _router(username="admin")
        detail = {
            "online": True,
            "last_ok": datetime.now(),
            "last_fail": None,
            "version": "7.14",
            "active_users": 1,
        }

        async def fake_blocking(fn, *args, **kwargs):
            from core.watchdog import get_router_status_detail as _grsd
            from database.models import get_last_backup as _glb
            from database.models import get_saved_routers as _gsr

            if fn is _gsr:
                return [router]
            if fn is _grsd:
                return detail
            if fn is _glb:
                return None
            return {"online": True}

        with (
            patch("bot.handlers.watchdog.safe_answer_callback", new_callable=AsyncMock),
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.record_check_result", return_value=ALERT_NONE),
            patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock),
        ):
            await watchdog_module.watchdog_refresh(update, ctx)


# ── TestCheckAllRouters ────────────────────────────────────────


class TestCheckAllRouters:
    @pytest.mark.asyncio
    async def test_no_routers(self):
        ctx = _ctx()
        with patch("bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=[]):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_router_online_no_alert(self):
        ctx = _ctx()
        router = _router(username="admin", identity="R1")

        async def fake_blocking(fn, *args, **kwargs):
            from database.models import get_saved_routers as _gsr

            if fn is _gsr:
                return [router]
            return {"online": True}

        with (
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.record_check_result", return_value=ALERT_NONE),
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_router_went_offline(self):
        ctx = _ctx()
        router = _router(username="admin", identity="R1")

        async def fake_blocking(fn, *args, **kwargs):
            from database.models import get_saved_routers as _gsr

            if fn is _gsr:
                return [router]
            return {"online": True}

        with (
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.record_check_result", return_value=ALERT_WENT_OFFLINE),
            patch("bot.handlers.watchdog._notify_admins", new_callable=AsyncMock),
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_router_recovered(self):
        ctx = _ctx()
        router = _router(username="admin", identity="R1")

        async def fake_blocking(fn, *args, **kwargs):
            from database.models import get_saved_routers as _gsr

            if fn is _gsr:
                return [router]
            return {"online": True}

        with (
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.record_check_result", return_value=ALERT_RECOVERED),
            patch("bot.handlers.watchdog._notify_admins", new_callable=AsyncMock),
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_router_exception_during_check(self):
        ctx = _ctx()
        router = _router(username="admin", identity="R1")
        call_count = 0

        async def fake_blocking(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [router]
            raise RuntimeError("connection failed")

        with (
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.record_check_result", return_value=ALERT_NONE),
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_router_no_username_skipped(self):
        ctx = _ctx()
        router = _router(username="")
        with patch(
            "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=[router]
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_router_none_username_skipped(self):
        ctx = _ctx()
        router = _router()
        router.pop("username", None)
        with patch(
            "bot.handlers.watchdog.run_blocking", new_callable=AsyncMock, return_value=[router]
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_multiple_routers_mixed(self):
        ctx = _ctx()
        r1 = _router(db_id=1, username="admin")
        r2 = _router(db_id=2, username="admin")

        async def fake_blocking(fn, *args, **kwargs):
            from database.models import get_saved_routers as _gsr

            if fn is _gsr:
                return [r1, r2]
            return {"online": True}

        with (
            patch("bot.handlers.watchdog.run_blocking", side_effect=fake_blocking),
            patch("bot.handlers.watchdog.record_check_result", return_value=ALERT_NONE),
        ):
            await watchdog_module._check_all_routers(ctx)

    @pytest.mark.asyncio
    async def test_public_alias(self):
        assert watchdog_module.check_all_routers is watchdog_module._check_all_routers


# ── TestNotifyAdmins ───────────────────────────────────────────


class TestNotifyAdmins:
    @pytest.mark.asyncio
    async def test_success(self):
        ctx = _ctx()
        with patch("bot.handlers.watchdog.ADMIN_IDS", [ADMIN_ID]):
            await watchdog_module._notify_admins(ctx, "<b>test</b>")
        ctx.bot.send_message.assert_called_once_with(ADMIN_ID, "<b>test</b>", parse_mode="HTML")

    @pytest.mark.asyncio
    async def test_retry_after_timedelta(self):
        from telegram.error import RetryAfter

        ctx = _ctx()
        call_count = 0

        def side_effect(uid, text, parse_mode=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RetryAfter(retry_after=timedelta(seconds=5))
            return AsyncMock()

        ctx.bot.send_message = AsyncMock(side_effect=side_effect)
        with (
            patch("bot.handlers.watchdog.ADMIN_IDS", [ADMIN_ID]),
            patch("bot.handlers.watchdog.asyncio.sleep", new_callable=AsyncMock),
        ):
            await watchdog_module._notify_admins(ctx, "test")
        assert ctx.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_after_int(self):
        from telegram.error import RetryAfter

        ctx = _ctx()
        call_count = 0

        def side_effect(uid, text, parse_mode=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RetryAfter(retry_after=3)
            return AsyncMock()

        ctx.bot.send_message = AsyncMock(side_effect=side_effect)
        with (
            patch("bot.handlers.watchdog.ADMIN_IDS", [ADMIN_ID]),
            patch("bot.handlers.watchdog.asyncio.sleep", new_callable=AsyncMock),
        ):
            await watchdog_module._notify_admins(ctx, "test")
        assert ctx.bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_after_second_retry_fails(self):
        from telegram.error import RetryAfter

        ctx = _ctx()
        call_count = 0

        def side_effect(uid, text, parse_mode=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RetryAfter(retry_after=timedelta(seconds=2))
            raise RuntimeError("still broken")

        ctx.bot.send_message = AsyncMock(side_effect=side_effect)
        with (
            patch("bot.handlers.watchdog.ADMIN_IDS", [ADMIN_ID]),
            patch("bot.handlers.watchdog.asyncio.sleep", new_callable=AsyncMock),
        ):
            await watchdog_module._notify_admins(ctx, "test")

    @pytest.mark.asyncio
    async def test_general_exception(self):
        ctx = _ctx()
        ctx.bot.send_message = AsyncMock(side_effect=RuntimeError("network"))
        with patch("bot.handlers.watchdog.ADMIN_IDS", [ADMIN_ID]):
            await watchdog_module._notify_admins(ctx, "test")

    @pytest.mark.asyncio
    async def test_multiple_admins(self):
        ctx = _ctx()
        with patch("bot.handlers.watchdog.ADMIN_IDS", [111, 222]):
            await watchdog_module._notify_admins(ctx, "hi")
        assert ctx.bot.send_message.call_count == 2


# ── TestReply ──────────────────────────────────────────────────


class TestReply:
    @pytest.mark.asyncio
    async def test_callback_path(self):
        update = _cb_update()
        ctx = _ctx()
        query = update.callback_query
        with patch("bot.handlers.watchdog.safe_edit_or_send", new_callable=AsyncMock) as mock_edit:
            await watchdog_module._reply(update, ctx, query, "hello")
        mock_edit.assert_called_once_with(query, ctx, "hello")

    @pytest.mark.asyncio
    async def test_message_path(self):
        update = _msg_update()
        ctx = _ctx()
        with patch("bot.handlers.watchdog.send_step", new_callable=AsyncMock) as mock_send:
            await watchdog_module._reply(update, ctx, None, "world")
        mock_send.assert_called_once_with(update, ctx, "world")
