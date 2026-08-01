import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

from core.metrics import record_action, record_backup_duration
from core.mikrotik_api import mikrotik_api
from core.mikrotik_client import RouterOSRow
from database.models import record_backup_result
from utils.async_blocking import run_blocking
from utils.formatters import sanitize_log_data
from utils.logging_setup import COMPONENT_BACKUP, bind_component, new_request_id
from utils.request_id import bind_request_id, bind_trace_id

logger = logging.getLogger(__name__)

JOB_NAME = "scheduled_backup"

_JOB_QUEUE_DOC = """JobQueue-like object from telegram.ext (passed from Application.job_queue).
                   Typed as Any to avoid a direct telegram.ext dependency in core/ layer."""
_JOB_CONTEXT_DOC = """CallbackContext-like object from telegram.ext.
                      Typed as Any to avoid a direct telegram.ext dependency in core/ layer."""


class BackupScheduler:
    def __init__(self) -> None:
        self._running = False

    async def _run_backup_operation(
        self,
        router_key: str,
        router_name: str,
        backup_type: str,
        service_method: Callable[..., RouterOSRow],
        action_name: str,
        failure_log_level: int,  # logging.WARNING or logging.ERROR
        record_duration: bool = False
    ) -> bool:
        """Run a backup operation and record results. Returns True on success."""
        t1 = time.monotonic()
        ok = False
        msg = ""
        try:
            result = await run_blocking(service_method, router_key)
            ok = bool(result.get("success"))
            msg = str(result.get("message", f"scheduled {backup_type} backup failed"))
        except Exception as e:  # noqa: BLE001 - catch-all: backup_service may raise unexpected errors
            msg = sanitize_log_data(str(e))
            logger.exception(
                f"Scheduled {backup_type} backup raised for %s",
                router_key,
                exc_info=True,
                extra={"component": COMPONENT_BACKUP},
            )
        elapsed_ms = (time.monotonic() - t1) * 1000

        # DB writes are best-effort: a DB failure must not flip the backup status
        try:
            record_action(router_key, action_name, ok, elapsed_ms)
        except Exception:  # noqa: BLE001 - best-effort: DB write failure should not mask backup outcome
            logger.warning(
                "DB write failed after %s backup for %s",
                backup_type,
                router_key,
                exc_info=True,
                extra={"component": COMPONENT_BACKUP},
            )
        try:
            await run_blocking(
                record_backup_result,
                router_key,
                backup_type,
                ok,
                msg,
                router_name=router_name,
            )
        except Exception:  # noqa: BLE001 - best-effort: DB write failure should not mask backup outcome
            logger.warning(
                "record_backup_result failed after %s backup for %s",
                backup_type,
                router_key,
                exc_info=True,
                extra={"component": COMPONENT_BACKUP},
            )

        if not ok:
            log_func = logger.warning if failure_log_level == logging.WARNING else logger.error
            log_func(
                f"Scheduled {backup_type} backup failed for %s: %s",
                router_key,
                msg,
                extra={"component": COMPONENT_BACKUP},
            )

        # Record duration for full backups only
        if ok and record_duration:
            try:
                record_backup_duration(backup_type, elapsed_ms / 1000)
            except Exception:  # noqa: BLE001 - best-effort: DB write failure should not mask backup outcome
                logger.warning(
                    "Failed to record %s backup duration for %s",
                    backup_type,
                    router_key,
                    exc_info=True,
                    extra={"component": COMPONENT_BACKUP},
                )

        return bool(ok)

    async def _backup_single_router(
        self,
        r: RouterOSRow,
        router_key: str,
        failed_routers: list[str],
        successful_routers: list[str],
    ) -> None:
        trace_id = new_request_id()
        with bind_trace_id(trace_id):
            with bind_component(COMPONENT_BACKUP):
                is_healthy, health_msg = await run_blocking(
                    mikrotik_api.check_connection_health, router_key
                )
                if not is_healthy:
                    logger.warning(
                        "Router %s is not healthy (%s), skipping backup",
                        router_key,
                        health_msg,
                    )
                    failed_routers.append(str(r.get("identity", router_key)) + " (غير متصل)")
                    return

                router_name = str(r.get("identity", router_key))

                userman_ok = await self._run_userman_backup(router_key, router_name)
                if userman_ok:
                    successful_routers.append(router_name)
                    logger.info("Scheduled userman backup done for %s", router_key)
                else:
                    failed_routers.append(str(router_name))

                full_ok = await self._run_full_backup(router_key, router_name)
                if full_ok:
                    logger.info("Scheduled full backup done for %s", router_key)
                else:
                    failed_routers.append(f"{router_name} (باكوب كامل)")

    async def _run_userman_backup(self, router_key: str, router_name: str) -> bool:
        """Run User Manager backup and record results. Returns True on success."""
        from core.backup_service import backup_service

        return await self._run_backup_operation(
            router_key,
            router_name,
            backup_type="userman",
            service_method=backup_service.userman_backup,
            action_name="backup_userman",
            failure_log_level=logging.WARNING,
            record_duration=False,
        )

    async def _run_full_backup(self, router_key: str, router_name: str) -> bool:
        """Run full system backup and record results. Returns True on success."""
        from core.backup_service import backup_service

        return await self._run_backup_operation(
            router_key,
            router_name,
            backup_type="full",
            service_method=backup_service.full_backup,
            action_name="backup_full",
            failure_log_level=logging.ERROR,
            record_duration=True,
        )

    async def _do_backup(self, context: Any) -> None:
        from config import ADMIN_IDS, ROUTER_KEY_PREFIX
        from database.models import get_saved_routers

        trace_id = new_request_id()
        with bind_trace_id(trace_id):
            with bind_component(COMPONENT_BACKUP):
                rid = new_request_id()
                with bind_request_id(rid):
                    failed_routers: list[str] = []
                    successful_routers: list[str] = []
                    routers: list[RouterOSRow] = await run_blocking(get_saved_routers, active_only=True)

                    logger.info("Scheduled backup starting for %d routers...", len(routers))

                    for r in routers:
                        if not r.get("username"):
                            continue
                        router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
                        await self._backup_single_router(r, router_key, failed_routers, successful_routers)

                    if successful_routers:
                        logger.info("Backup completed successfully for %d routers", len(successful_routers))

                    if failed_routers and context.bot:
                        for admin_id in ADMIN_IDS:
                            try:
                                await context.bot.send_message(
                                    admin_id,
                                    f"\u26a0\uFE0F فشل الباكوب الآلي لـ {len(failed_routers)} روتر:\n"
                                    + "\n".join(f"\u2022 {r}" for r in failed_routers),
                                )
                            except (OSError, ConnectionError) as e:
                                logger.warning(
                                    "Failed to notify admin %s about backup failures: %s",
                                    admin_id,
                                    e,
                                    extra={"component": COMPONENT_BACKUP},
                                )

    async def _do_expiry_check(self, context: Any) -> None:
        """فحص يومي لاشتراكات Hotspot المشارفة على الانتهاء وإرسال تنبيه للمشرفين."""
        from config import ADMIN_IDS, ROUTER_KEY_PREFIX
        from core.hotspot_manager import hotspot_manager
        from core.messages_expiry import EXPIRY_ALERT_HEADER, EXPIRY_ALERT_USER_ROW
        from database.models import get_saved_routers, log_action

        trace_id = new_request_id()
        with bind_trace_id(trace_id):
            with bind_component(COMPONENT_BACKUP):
                rid = new_request_id()
                with bind_request_id(rid):
                    routers: list[RouterOSRow] = await run_blocking(get_saved_routers, active_only=True)
                    days = 3

                    for r in routers:
                        if not r.get("username"):
                            continue
                        router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
                        router_name = str(r.get("identity", router_key))
                        t0 = time.monotonic()
                        try:
                            expiring = await run_blocking(hotspot_manager.get_expiring_users, router_key, days)
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            record_action(router_key, "expiry_check", True, elapsed_ms)
                        except Exception as e:  # noqa: BLE001 - catch-all: background scheduler task must not crash on unexpected errors
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            record_action(router_key, "expiry_check", False, elapsed_ms)
                            logger.warning(
                                "Expiry check failed for %s "
                                "(error type: %s): %s",
                                router_key,
                                type(e).__name__,
                                e,
                                extra={"component": COMPONENT_BACKUP},
                                exc_info=True,
                            )
                            continue

                        if not expiring:
                            continue

                        header = EXPIRY_ALERT_HEADER.format(router_name=router_name, days=days)
                        rows = [
                            EXPIRY_ALERT_USER_ROW.format(
                                name=u["name"],
                                profile=u["profile"],
                                remaining_days=u["remaining_days"],
                            )
                            for u in expiring
                        ]
                        message = header + "\n".join(rows)
                        for admin_id in ADMIN_IDS:
                            try:
                                await context.bot.send_message(admin_id, message, parse_mode="HTML")
                            except Exception as e:  # noqa: BLE001 - catch-all: notification failure should not block other admin alerts
                                logger.warning(
                                    "Failed to notify admin %s about expiry "
                                    "(error type: %s): %s",
                                    admin_id,
                                    type(e).__name__,
                                    e,
                                    extra={"component": COMPONENT_BACKUP},
                                    exc_info=True,
                                )
                        try:
                            log_action("expiry_check_alert", "", router_name, 0)
                        except Exception as e:  # noqa: BLE001 - best-effort: log_action failure should not block backup workflow
                            logger.warning(
                                "Failed to log expiry check alert for %s: %s",
                                router_key,
                                e,
                                extra={"component": COMPONENT_BACKUP},
                                exc_info=True,
                            )

    async def _do_stats_snapshot(self, context: Any) -> None:
        """حفظ snapshot يومي لإحصائيات كل راوتر في قاعدة البيانات."""
        from config import ROUTER_KEY_PREFIX
        from core.stats import stats_manager
        from database.models import get_saved_routers, log_action
        from database.repositories.stats_snapshots import save_snapshot

        trace_id = new_request_id()
        with bind_trace_id(trace_id):
            with bind_component(COMPONENT_BACKUP):
                rid = new_request_id()
                with bind_request_id(rid):
                    routers: list[RouterOSRow] = await run_blocking(get_saved_routers, active_only=True)
                    for r in routers:
                        if not r.get("username"):
                            continue
                        router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
                        router_name = str(r.get("identity", router_key))
                        t0 = time.monotonic()
                        try:
                            raw = await run_blocking(stats_manager.get_hotspot_stats, router_key)
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            if not raw:
                                record_action(router_key, "stats_snapshot", True, elapsed_ms)
                                continue
                            snapshot_data: dict[str, int] = {
                                "active_users": int(raw.get("active_users", 0) or 0),
                                "total_users": int(raw.get("total_users", 0) or 0),
                                "bytes_in": 0,
                                "bytes_out": 0,
                            }
                            await run_blocking(save_snapshot, router_key, snapshot_data)
                            record_action(router_key, "stats_snapshot", True, elapsed_ms)
                            logger.info("Stats snapshot saved for %s", router_key)
                            try:
                                log_action("stats_snapshot", "", router_name, 0)
                            except Exception as e:  # noqa: BLE001 - best-effort: log_action failure should not block stats snapshot workflow
                                logger.warning(
                                    "Failed to log stats snapshot for %s: %s",
                                    router_key,
                                    e,
                                    extra={"component": COMPONENT_BACKUP},
                                    exc_info=True,
                                )
                        except Exception as e:  # noqa: BLE001 - catch-all: background scheduler task must not crash on unexpected errors
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            record_action(router_key, "stats_snapshot", False, elapsed_ms)
                            logger.warning(
                                "Stats snapshot failed for %s "
                                "(error type: %s): %s",
                                router_key,
                                type(e).__name__,
                                e,
                                extra={"component": COMPONENT_BACKUP},
                                exc_info=True,
                            )

    def start_daily(
        self,
        job_queue: Any,
        hour: int = 3,
        minute: int = 0,
        persist: bool = True,
    ) -> None:
        self.stop(job_queue, persist=False)
        now = datetime.now()
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target_time <= now:
            target_time += timedelta(days=1)
        job_queue.run_daily(
            self._do_backup,
            time=target_time.time(),
            name=JOB_NAME,
        )
        # فحص انتهاء الاشتراكات بعد 5 دقائق من الـ backup
        expiry_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(
            minutes=5
        )
        if expiry_time <= now:
            expiry_time += timedelta(days=1)
        job_queue.run_daily(
            self._do_expiry_check,
            time=expiry_time.time(),
            name=f"{JOB_NAME}_expiry",
        )
        # snapshot إحصائيات بعد 10 دقائق من الـ backup
        snapshot_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(
            minutes=10
        )
        if snapshot_time <= now:
            snapshot_time += timedelta(days=1)
        job_queue.run_daily(
            self._do_stats_snapshot,
            time=snapshot_time.time(),
            name=f"{JOB_NAME}_snapshot",
        )
        self._running = True
        if persist:
            from database.models import save_backup_schedule

            save_backup_schedule(True, hour, minute)
        logger.info("Backup scheduler started, next run daily at %02d:%02d", hour, minute)

    def stop(self, job_queue: Any | None, persist: bool = True) -> None:
        self._running = False
        if job_queue:
            for job in job_queue.get_jobs_by_name(JOB_NAME):
                job.schedule_removal()
            for job in job_queue.get_jobs_by_name(f"{JOB_NAME}_expiry"):
                job.schedule_removal()
            for job in job_queue.get_jobs_by_name(f"{JOB_NAME}_snapshot"):
                job.schedule_removal()
        if persist:
            from database.models import get_backup_schedule, save_backup_schedule

            current = get_backup_schedule()
            save_backup_schedule(
                False, int(current["schedule_hour"] or 3), int(current["schedule_minute"] or 0)
            )

    def is_running(self, job_queue: Any | None = None) -> bool:
        if job_queue:
            jobs = job_queue.get_jobs_by_name(JOB_NAME)
            if len(jobs) > 0:
                return True
        from database.models import get_backup_schedule

        return bool(get_backup_schedule().get("schedule_enabled", False))

    def restore(self, job_queue: Any) -> None:
        from database.models import get_backup_schedule

        settings = get_backup_schedule()
        if settings.get("schedule_enabled") and job_queue:
            self.start_daily(
                job_queue,
                int(settings["schedule_hour"] or 3),
                int(settings["schedule_minute"] or 0),
                persist=False,
            )


backup_scheduler = BackupScheduler()
