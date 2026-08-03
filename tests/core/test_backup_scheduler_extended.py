"""Extended tests for core/backup_scheduler.py — cover _backup_single_router
branches, _do_expiry_check, _do_stats_snapshot, admin notification paths."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.backup_scheduler import BackupScheduler


@pytest.fixture
def mock_job_queue():
    mq = MagicMock()
    mq.get_jobs_by_name.return_value = []
    return mq


class TestBackupSingleRouter:
    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_unhealthy_router_skipped(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_run.return_value = (False, "offline")
        scheduler = BackupScheduler()
        failed = []
        successful = []
        await scheduler._backup_single_router(  # type: ignore[reportPrivateUsage]
            {"id": 1, "identity": "R1", "username": "admin"},
            "discovered_1",
            failed,
            successful,
        )
        assert len(failed) == 1
        assert "غير متصل" in failed[0]
        assert len(successful) == 0

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_userman_error_records_failure(self, mock_run):  # type: ignore[reportMissingParameterType]
        from librouteros.exceptions import LibRouterosError

        mock_run.side_effect = [
            (True, "ok"),  # health check
            LibRouterosError("um fail"),  # userman_backup raises
            None,  # record_backup_result
            {"success": True},  # full_backup
            None,  # record_backup_result
        ]
        scheduler = BackupScheduler()
        failed = []
        successful = []
        await scheduler._backup_single_router(  # type: ignore[reportPrivateUsage]
            {"id": 1, "identity": "R1", "username": "admin"},
            "discovered_1",
            failed,
            successful,
        )
        assert "R1" in failed[0]

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_full_backup_fails(self, mock_run):  # type: ignore[reportMissingParameterType]
        from librouteros.exceptions import LibRouterosError

        mock_run.side_effect = [
            (True, "ok"),  # health check
            {"success": True},  # userman_backup ok
            None,  # record_backup_result
            LibRouterosError("full fail"),  # full_backup raises
            None,  # record_backup_result
        ]
        scheduler = BackupScheduler()
        failed = []
        successful = []
        await scheduler._backup_single_router(  # type: ignore[reportPrivateUsage]
            {"id": 1, "identity": "R1", "username": "admin"},
            "discovered_1",
            failed,
            successful,
        )
        assert any("باكوب كامل" in f for f in failed)

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_full_backup_success_false(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_run.side_effect = [
            (True, "ok"),
            {"success": True},
            None,
            {"success": False, "message": "disk full"},
            None,
        ]
        scheduler = BackupScheduler()
        failed = []
        successful = []
        await scheduler._backup_single_router(  # type: ignore[reportPrivateUsage]
            {"id": 1, "identity": "R1", "username": "admin"},
            "discovered_1",
            failed,
            successful,
        )
        assert any("باكوب كامل" in f for f in failed)

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_full_backup_success_true(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_run.side_effect = [
            (True, "ok"),
            {"success": True},
            None,
            {"success": True, "message": "ok"},
            None,
        ]
        scheduler = BackupScheduler()
        failed = []
        successful = []
        await scheduler._backup_single_router(  # type: ignore[reportPrivateUsage]
            {"id": 1, "identity": "R1", "username": "admin"},
            "discovered_1",
            failed,
            successful,
        )
        assert "R1" in successful
        assert len(failed) == 0


class TestDoExpiryCheck:
    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_sends_expiry_alerts(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            [{"name": "user1", "profile": "10GB", "remaining_days": 1}],
        ]
        scheduler = BackupScheduler()
        await scheduler._do_expiry_check(mock_context)  # type: ignore[reportPrivateUsage]
        mock_context.bot.send_message.assert_called()

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_skips_when_no_expiring(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            [],
        ]
        scheduler = BackupScheduler()
        await scheduler._do_expiry_check(mock_context)  # type: ignore[reportPrivateUsage]
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_skips_router_without_username(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "", "identity": "R1"}],
        ]
        scheduler = BackupScheduler()
        await scheduler._do_expiry_check(mock_context)  # type: ignore[reportPrivateUsage]
        assert mock_run.call_count == 1

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_exception_in_get_expiring(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            Exception("connection lost"),
        ]
        scheduler = BackupScheduler()
        await scheduler._do_expiry_check(mock_context)  # type: ignore[reportPrivateUsage]
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_admin_send_fails(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_context.bot.send_message.side_effect = OSError("tg down")
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            [{"name": "u1", "profile": "p", "remaining_days": 1}],
        ]
        scheduler = BackupScheduler()
        await scheduler._do_expiry_check(mock_context)  # type: ignore[reportPrivateUsage]
        mock_context.bot.send_message.assert_called_once()


class TestDoStatsSnapshot:
    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_saves_snapshot(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            {"active_users": 5, "total_users": 20, "bytes_in": 100, "bytes_out": 200},
            None,
        ]
        scheduler = BackupScheduler()
        await scheduler._do_stats_snapshot(mock_context)  # type: ignore[reportPrivateUsage]
        assert mock_run.call_count == 3

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_skips_when_no_stats(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            None,
        ]
        scheduler = BackupScheduler()
        await scheduler._do_stats_snapshot(mock_context)  # type: ignore[reportPrivateUsage]
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_exception_in_stats(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            Exception("timeout"),
        ]
        scheduler = BackupScheduler()
        await scheduler._do_stats_snapshot(mock_context)  # type: ignore[reportPrivateUsage]
        assert mock_run.call_count == 2

    @pytest.mark.asyncio
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_skips_router_without_username(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "", "identity": "R1"}],
        ]
        scheduler = BackupScheduler()
        await scheduler._do_stats_snapshot(mock_context)  # type: ignore[reportPrivateUsage]
        assert mock_run.call_count == 1


class TestDoBackupNotifications:
    @pytest.mark.asyncio
    @patch("config.ADMIN_IDS", [724730774])
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_sends_failure_notification(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            (False, "offline"),
        ]
        scheduler = BackupScheduler()
        await scheduler._do_backup(mock_context)  # type: ignore[reportPrivateUsage]
        mock_context.bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    @patch("config.ADMIN_IDS", [724730774])
    @patch("core.backup_scheduler.run_blocking", new_callable=AsyncMock)
    async def test_admin_send_failure_graceful(self, mock_run):  # type: ignore[reportMissingParameterType]
        mock_context = MagicMock()
        mock_context.bot = AsyncMock()
        mock_context.bot.send_message.side_effect = OSError("tg down")
        mock_run.side_effect = [
            [{"id": 1, "username": "admin", "identity": "R1"}],
            (False, "offline"),
        ]
        scheduler = BackupScheduler()
        await scheduler._do_backup(mock_context)  # type: ignore[reportPrivateUsage]
        mock_context.bot.send_message.assert_called_once()


class TestStopRemovesAllJobs:
    def test_stop_removes_expiry_and_snapshot_jobs(self, mock_job_queue):  # type: ignore[reportMissingParameterType]
        from tests.core.test_backup_scheduler import MockJob

        backup_job = MockJob()
        expiry_job = MockJob()
        snapshot_job = MockJob()

        def get_jobs(name):  # type: ignore[reportMissingParameterType]
            return {
                "scheduled_backup": [backup_job],
                "scheduled_backup_expiry": [expiry_job],
                "scheduled_backup_snapshot": [snapshot_job],
            }.get(name, [])

        mock_job_queue.get_jobs_by_name.side_effect = get_jobs
        scheduler = BackupScheduler()
        scheduler._running = True  # type: ignore[reportPrivateUsage]
        scheduler.stop(mock_job_queue, persist=False)
        assert backup_job.removed is True
        assert expiry_job.removed is True
        assert snapshot_job.removed is True
