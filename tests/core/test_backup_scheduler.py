"""Unit tests for core/backup_scheduler.py — BackupScheduler class.

Lazy imports inside BackupScheduler methods (from database.models import ...
from core.backup_service import ...) mean we patch database.models.*
and core.backup_service.* instead of core.backup_scheduler.*.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.backup_scheduler import BackupScheduler


@pytest.fixture
def mock_job_queue():
    mq = MagicMock()
    mq.get_jobs_by_name.return_value = []
    return mq


class MockJob:
    def __init__(self):
        self.removed = False

    def schedule_removal(self):
        self.removed = True


@pytest.mark.asyncio
class TestBackupScheduler:
    async def test_start_daily_schedules_job(self, mock_job_queue):
        scheduler = BackupScheduler()
        scheduler.start_daily(mock_job_queue, hour=3, minute=0, persist=False)
        assert scheduler._running is True
        # run_daily يُستدعى 3 مرات: backup + expiry check + stats snapshot
        assert mock_job_queue.run_daily.call_count == 3

    async def test_start_daily_persists(self, mock_job_queue):
        with patch("database.models.save_backup_schedule") as mock_save:
            scheduler = BackupScheduler()
            scheduler.start_daily(mock_job_queue, hour=8, minute=15, persist=True)
            mock_save.assert_called_once_with(True, 8, 15)

    async def test_stop_removes_jobs(self, mock_job_queue):
        job = MockJob()
        mock_job_queue.get_jobs_by_name.return_value = [job]
        scheduler = BackupScheduler()
        scheduler._running = True
        scheduler.stop(mock_job_queue, persist=False)
        assert job.removed is True
        assert scheduler._running is False

    async def test_stop_persists_disabled(self, mock_job_queue):
        with (
            patch("database.models.get_backup_schedule") as mock_get,
            patch("database.models.save_backup_schedule") as mock_save,
        ):
            mock_get.return_value = {
                "schedule_enabled": True,
                "schedule_hour": 3,
                "schedule_minute": 0,
            }
            scheduler = BackupScheduler()
            scheduler.stop(mock_job_queue, persist=True)
            mock_save.assert_called_once_with(False, 3, 0)

    async def test_stop_without_job_queue(self):
        scheduler = BackupScheduler()
        scheduler._running = True
        scheduler.stop(None, persist=False)
        assert scheduler._running is False

    async def test_is_running_true_when_job_exists(self, mock_job_queue):
        mock_job_queue.get_jobs_by_name.return_value = [MagicMock()]
        scheduler = BackupScheduler()
        assert scheduler.is_running(mock_job_queue) is True

    async def test_is_running_false_when_no_job(self, mock_job_queue):
        mock_job_queue.get_jobs_by_name.return_value = []
        with patch("database.models.get_backup_schedule") as mock_get:
            mock_get.return_value = {
                "schedule_enabled": False,
                "schedule_hour": 3,
                "schedule_minute": 0,
            }
            scheduler = BackupScheduler()
            assert scheduler.is_running(mock_job_queue) is False

    async def test_is_running_fallback_to_db(self, mock_job_queue):
        mock_job_queue.get_jobs_by_name.return_value = []
        with patch("database.models.get_backup_schedule") as mock_get:
            mock_get.return_value = {
                "schedule_enabled": True,
                "schedule_hour": 3,
                "schedule_minute": 0,
            }
            scheduler = BackupScheduler()
            assert scheduler.is_running(None) is True

    async def test_restore_starts_when_enabled(self, mock_job_queue):
        with patch("database.models.get_backup_schedule") as mock_get:
            mock_get.return_value = {
                "schedule_enabled": True,
                "schedule_hour": 5,
                "schedule_minute": 30,
            }
            scheduler = BackupScheduler()
            scheduler.restore(mock_job_queue)
            # run_daily يُستدعى 3 مرات: backup + expiry check + stats snapshot
            assert mock_job_queue.run_daily.call_count == 3
            assert scheduler._running is True

    async def test_restore_skips_when_disabled(self, mock_job_queue):
        with patch("database.models.get_backup_schedule") as mock_get:
            mock_get.return_value = {
                "schedule_enabled": False,
                "schedule_hour": 3,
                "schedule_minute": 0,
            }
            scheduler = BackupScheduler()
            scheduler.restore(mock_job_queue)
            mock_job_queue.run_daily.assert_not_called()

    async def test_do_backup_calls_service_for_each_router(self, mock_job_queue):
        mock_context = MagicMock()
        mock_context.job_queue = mock_job_queue
        with (
            patch("database.models.get_saved_routers"),
            patch("core.backup_service.backup_service"),
            patch("core.mikrotik_api.mikrotik_api"),
            patch("core.backup_scheduler.run_blocking", new=AsyncMock()) as mock_run,
        ):
            routers_list = [
                {"id": 1, "username": "admin", "identity": "Router1"},
                {"id": 2, "username": "admin", "identity": "Router2"},
            ]
            mock_run.side_effect = [
                routers_list,
                (True, "healthy"),
                None,
                1,  # router1: health, userman_backup, record
                {"success": True},
                2,  # router1: full_backup, record
                (True, "healthy"),
                None,
                3,  # router2: health, userman_backup, record
                {"success": True},
                4,  # router2: full_backup, record
            ]
            scheduler = BackupScheduler()
            await scheduler._do_backup(mock_context)
            assert mock_run.call_count == 11

    async def test_do_backup_skips_routers_without_username(self, mock_job_queue):
        mock_context = MagicMock()
        mock_context.job_queue = mock_job_queue
        with (
            patch("database.models.get_saved_routers"),
            patch("core.backup_service.backup_service"),
            patch("core.mikrotik_api.mikrotik_api"),
            patch("core.backup_scheduler.run_blocking", new=AsyncMock()) as mock_run,
        ):
            mock_run.side_effect = [
                [
                    {"id": 1, "username": "", "identity": "R1"},
                    {"id": 2, "username": "admin", "identity": "R2"},
                ],
                (True, "healthy"),
                None,
                1,
                {"success": True},
                2,
            ]
            scheduler = BackupScheduler()
            await scheduler._do_backup(mock_context)
            assert mock_run.call_count == 6

    async def test_do_backup_handles_exception_gracefully(self, mock_job_queue):
        mock_context = MagicMock()
        mock_context.job_queue = mock_job_queue
        mock_context.bot.send_message = AsyncMock()
        with (
            patch("database.models.get_saved_routers"),
            patch("core.backup_service.backup_service"),
            patch("core.mikrotik_api.mikrotik_api"),
            patch("core.backup_scheduler.run_blocking", new=AsyncMock()) as mock_run,
        ):
            from librouteros.exceptions import LibRouterosError

            routers_list = [{"id": 1, "username": "admin", "identity": "R1"}]
            # health check ok, userman_backup raises, record failure, full_backup raises, record failure  # noqa: E501
            mock_run.side_effect = [
                routers_list,
                (True, "healthy"),
                LibRouterosError("error"),
                1,
                LibRouterosError("full error"),
                2,
            ]
            scheduler = BackupScheduler()
            await scheduler._do_backup(mock_context)
            assert mock_run.call_count == 6

    async def test_do_backup_runs_full_backup_when_flag_enabled(self, mock_job_queue):
        mock_context = MagicMock()
        mock_context.job_queue = mock_job_queue
        with (
            patch("database.models.get_saved_routers"),
            patch("core.backup_service.backup_service") as mock_svc,
            patch("core.mikrotik_api.mikrotik_api"),
            patch("core.backup_scheduler.run_blocking", new=AsyncMock()) as mock_run,
            patch("config.SCHEDULE_FULL_BACKUP", True),
        ):
            mock_run.side_effect = [
                [{"id": 1, "username": "admin", "identity": "R1"}],
                (True, "healthy"),
                None,
                1,
                {"success": True, "message": "ok"},
                None,
            ]
            scheduler = BackupScheduler()
            await scheduler._do_backup(mock_context)
            assert mock_run.call_count == 6
            mock_run.assert_any_call(mock_svc.full_backup, "discovered_1")
