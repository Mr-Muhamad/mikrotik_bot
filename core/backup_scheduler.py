import logging
from datetime import datetime, timedelta

from utils.async_blocking import run_blocking

logger = logging.getLogger(__name__)

JOB_NAME = "scheduled_backup"


class BackupScheduler:
    def __init__(self):
        self._running = False

    async def _do_backup(self, context):
        from core.backup_service import backup_service
        from core.mikrotik_api import mikrotik_api
        from config import ROUTER_KEY_PREFIX, ADMIN_IDS, SCHEDULE_FULL_BACKUP
        from database.models import get_saved_routers, record_backup_result
        from librouteros.exceptions import LibRouterosError

        failed_routers = []
        successful_routers = []
        routers = await run_blocking(get_saved_routers, active_only=True)

        logger.info(f"Scheduled backup starting for {len(routers)} routers...")

        for r in routers:
            if not r.get("username"):
                continue
            router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"

            # فحص صحة الاتصال أولاً
            is_healthy, health_msg = await run_blocking(
                mikrotik_api.check_connection_health, router_key
            )
            if not is_healthy:
                logger.warning(f"Router {router_key} is not healthy ({health_msg}), skipping backup")
                failed_routers.append(f"{r.get('identity', router_key)} (غير متصل)")
                continue

            try:
                await run_blocking(backup_service.userman_backup, router_key)
                successful_routers.append(r.get("identity", router_key))
                from database.models import record_backup_result

                await run_blocking(
                    record_backup_result,
                    router_key, "userman", True,
                    "scheduled backup ok", router_name=r.get("identity", router_key),
                )
                logger.info(f"Scheduled backup done for {router_key}")
            except (LibRouterosError, ConnectionError, OSError) as e:
                logger.error(f"Scheduled backup failed for {router_key}: {e}")
                failed_routers.append(r.get("identity", router_key))
                from database.models import record_backup_result

                await run_blocking(
                    record_backup_result,
                    router_key, "userman", False,
                    str(e), router_name=r.get("identity", router_key),
                )

        if SCHEDULE_FULL_BACKUP:
            try:
                full_result = await run_blocking(backup_service.full_backup, router_key)
            except (LibRouterosError, ConnectionError, OSError) as e:
                logger.error(f"Scheduled full backup failed for {router_key}: {e}")
                failed_routers.append(f"{r.get('identity', router_key)} (باكوب كامل)")
                await run_blocking(
                    record_backup_result, router_key, "full", False,
                    str(e), router_name=r.get("identity", router_key),
                )
            else:
                if full_result.get("success"):
                    logger.info(f"Scheduled full backup done for {router_key}")
                    await run_blocking(
                        record_backup_result, router_key, "full", True,
                        "scheduled full backup ok",
                        router_name=r.get("identity", router_key),
                    )
                else:
                    msg = full_result.get("message", "scheduled full backup failed")
                    logger.error(f"Scheduled full backup failed for {router_key}: {msg}")
                    failed_routers.append(f"{r.get('identity', router_key)} (باكوب كامل)")
                    await run_blocking(
                        record_backup_result, router_key, "full", False,
                        str(msg), router_name=r.get("identity", router_key),
                    )

        # تقرير النتائج
        if successful_routers:
            logger.info(f"Backup completed successfully for {len(successful_routers)} routers")

        if failed_routers and context.bot:
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"⚠️ فشل الباكوب الآلي لـ {len(failed_routers)} روتر:\n" +
                        "\n".join(f"• {r}" for r in failed_routers)
                    )
                except (OSError, ConnectionError) as e:
                    logger.warning(f"Failed to notify admin {admin_id} about backup failures: {e}")

    async def _do_expiry_check(self, context):
        """فحص يومي لاشتراكات Hotspot المشارفة على الانتهاء وإرسال تنبيه للمشرفين."""
        from core.hotspot_manager import hotspot_manager
        from config import ROUTER_KEY_PREFIX, ADMIN_IDS
        from database.models import get_saved_routers
        from bot.messages import EXPIRY_ALERT_HEADER, EXPIRY_ALERT_USER_ROW

        routers = await run_blocking(get_saved_routers, active_only=True)
        days = 3

        for r in routers:
            if not r.get("username"):
                continue
            router_key = f"{ROUTER_KEY_PREFIX}{r['id']}"
            router_name = r.get("identity", router_key)
            try:
                expiring = await run_blocking(
                    hotspot_manager.get_expiring_users, router_key, days
                )
            except Exception as e:
                logger.warning(f"Expiry check failed for {router_key}: {e}")
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
                except Exception as e:
                    logger.warning(f"Failed to notify admin {admin_id} about expiry: {e}")

    def start_daily(
        self, job_queue, hour: int = 3, minute: int = 0, persist: bool = True
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
        expiry_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(minutes=5)
        if expiry_time <= now:
            expiry_time += timedelta(days=1)
        job_queue.run_daily(
            self._do_expiry_check,
            time=expiry_time.time(),
            name=f"{JOB_NAME}_expiry",
        )
        self._running = True
        if persist:
            from database.models import save_backup_schedule

            save_backup_schedule(True, hour, minute)
        logger.info(f"Backup scheduler started, next run daily at {hour:02d}:{minute:02d}")

    def stop(self, job_queue, persist: bool = True):
        self._running = False
        if job_queue:
            for job in job_queue.get_jobs_by_name(JOB_NAME):
                job.schedule_removal()
            for job in job_queue.get_jobs_by_name(f"{JOB_NAME}_expiry"):
                job.schedule_removal()
        if persist:
            from database.models import get_backup_schedule, save_backup_schedule

            current = get_backup_schedule()
            save_backup_schedule(
                False, current["schedule_hour"], current["schedule_minute"]
            )

    def is_running(self, job_queue=None) -> bool:
        if job_queue:
            jobs = job_queue.get_jobs_by_name(JOB_NAME)
            if len(jobs) > 0:
                return True
        from database.models import get_backup_schedule

        return get_backup_schedule().get("schedule_enabled", False)

    def restore(self, job_queue) -> None:
        from database.models import get_backup_schedule

        settings = get_backup_schedule()
        if settings.get("schedule_enabled") and job_queue:
            self.start_daily(
                job_queue,
                settings["schedule_hour"],
                settings["schedule_minute"],
                persist=False,
            )


backup_scheduler = BackupScheduler()
