import logging
import time
from datetime import datetime, timedelta

from telegram.ext import CallbackContext, JobQueue

from core.metrics import record_action, record_backup_duration
from core.mikrotik_client import RouterOSRow
from utils.async_blocking import run_blocking
from utils.formatters import sanitize_log_data
from utils.logging_setup import COMPONENT_BACKUP, bind_component, new_request_id
from utils.request_id import bind_request_id, bind_trace_id

logger = logging.getLogger(__name__)

JOB_NAME = "scheduled_backup"


class BackupScheduler:
    def __init__(self) -> None:
        self._running = False

    async def _backup_single_router(
        self,
        r: RouterOSRow,
        router_key: str,
        failed_routers: list[str],
        successful_routers: list[str],
    ) -> None:
        from core.backup_service import backup_service
        from core.mikrotik_api import mikrotik_api
        from database.models import record_backup_result

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

                t0 = time.monotonic()
                try:
                    await run_blocking(backup_service.userman_backup, router_key)
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    successful_routers.append(router_name)
                    record_action(router_key, "backup_userman", True, elapsed_ms)
                    record_backup_duration("userman", elapsed_ms / 1000)
                    await run_blocking(
                        record_backup_result,
                        router_key,
                        "userman",
                        True,
                        "scheduled backup ok",
                        router_name=router_name,
                    )
                    logger.info("Scheduled backup done for %s", router_key)
                except Exception as e:  # noqa: BLE001
                    elapsed_ms = (time.monotonic() - t0) * 1000
                    record_action(router_key, "backup_userman", False, elapsed_ms)
                    logger.error(
                        "Scheduled backup failed for %s in _run_daily_backup "
                        "(error type: %s): %s",
                        router_key,
                        type(e).__name__,
                        sanitize_log_data(str(e)),
                        extra={"component": COMPONENT_BACKUP},
                    )
                    failed_routers.append(str(router_name))
                    await run_blocking(
                        record_backup_result,
                        router_key,
                        "userman",
                        False,
                        sanitize_log_data(str(e)),
                        router_name=router_name,
                    )

                t1 = time.monotonic()
                try:
                    full_result = await run_blocking(backup_service.full_backup, router_key)
                    elapsed_ms = (time.monotonic() - t1) * 1000
                except Exception as e:  # noqa: BLE001
                    elapsed_ms = (time.monotonic() - t1) * 1000
                    record_action(router_key, "backup_full", False, elapsed_ms)
                    logger.error(
                        "Scheduled full backup failed for %s in _run_daily_backup "
                        "(error type: %s): %s",
                        router_key,
                        type(e).__name__,
                        sanitize_log_data(str(e)),
                        extra={"component": COMPONENT_BACKUP},
                    )
                    failed_routers.append(f"{router_name} (باكوب كامل)")
                    await run_blocking(
                        record_backup_result,
                        router_key,
                        "full",
                        False,
                        sanitize_log_data(str(e)),
                        router_name=router_name,
                    )
                else:
                    success = full_result.get("success")
                    default_msg = "scheduled full backup failed"
                    msg = (
                        full_result.get("message", default_msg)
                        if not success
                        else "scheduled full backup ok"
                    )
                    record_action(router_key, "backup_full", bool(success), elapsed_ms)
                    if success:
                        record_backup_duration("full", elapsed_ms / 1000)
                    if not success:
                        logger.error(
                            "Scheduled full backup failed for %s: %s",
                            router_key,
                            msg,
                            extra={"component": COMPONENT_BACKUP},
                        )
                        failed_routers.append(f"{router_name} (باكوب كامل)")
                    else:
                        logger.info("Scheduled full backup done for %s", router_key)
                    await run_blocking(
                        record_backup_result,
                        router_key,
                        "full",
                        success,
                        str(msg),
                        router_name=router_name,
                    )

    async def _do_backup(self, context: CallbackContext) -> None:  # type: ignore[reportMissingTypeArgument]
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

    async def _do_expiry_check(self, context: CallbackContext) -> None:  # type: ignore[reportMissingTypeArgument]
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
                        except Exception as e:  # noqa: BLE001
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            record_action(router_key, "expiry_check", False, elapsed_ms)
                            logger.warning(
                                "Expiry check failed for %s "
                                "(error type: %s): %s",
                                router_key,
                                type(e).__name__,
                                e,
                                extra={"component": COMPONENT_BACKUP},
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
                            except Exception as e:  # noqa: BLE001
                                logger.warning(
                                    "Failed to notify admin %s about expiry "
                                    "(error type: %s): %s",
                                    admin_id,
                                    type(e).__name__,
                                    e,
                                    extra={"component": COMPONENT_BACKUP},
                                )
                        try:
                            log_action("expiry_check_alert", "", router_name, 0)
                        except Exception as e:  # noqa: BLE001
                            logger.warning(
                                "Failed to log expiry check alert for %s: %s",
                                router_key,
                                e,
                                extra={"component": COMPONENT_BACKUP},
                            )

    async def _do_stats_snapshot(self, context: CallbackContext) -> None:  # type: ignore[reportMissingTypeArgument]
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
                            except Exception as e:  # noqa: BLE001
                                logger.warning(
                                    "Failed to log stats snapshot for %s: %s",
                                    router_key,
                                    e,
                                    extra={"component": COMPONENT_BACKUP},
                                )
                        except Exception as e:  # noqa: BLE001
                            elapsed_ms = (time.monotonic() - t0) * 1000
                            record_action(router_key, "stats_snapshot", False, elapsed_ms)
                            logger.warning(
                                "Stats snapshot failed for %s "
                                "(error type: %s): %s",
                                router_key,
                                type(e).__name__,
                                e,
                                extra={"component": COMPONENT_BACKUP},
                            )

    def start_daily(
        self,
        job_queue: JobQueue,  # type: ignore[reportMissingTypeArgument]
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

    def stop(self, job_queue: JobQueue, persist: bool = True) -> None:  # type: ignore[reportMissingTypeArgument]
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

    def is_running(self, job_queue: JobQueue | None = None) -> bool:  # type: ignore[reportMissingTypeArgument]
        if job_queue:
            jobs = job_queue.get_jobs_by_name(JOB_NAME)
            if len(jobs) > 0:
                return True
        from database.models import get_backup_schedule

        return bool(get_backup_schedule().get("schedule_enabled", False))

    def restore(self, job_queue: JobQueue) -> None:  # type: ignore[reportMissingTypeArgument]
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
