import asyncio
import atexit
import logging
import signal
import sys
from types import FrameType

from telegram.ext import (
    Application,
    JobQueue,
)

from bot.registrations import build_all
from config import BOT_TOKEN, WATCHDOG_FIRST_DELAY, WATCHDOG_INTERVAL
from core.backup_scheduler import backup_scheduler
from core.mikrotik_api import mikrotik_api
from database.models import init_db
from utils.bot_commands import set_bot_commands
from utils.logging_setup import COMPONENT_SYSTEM, bind_component, configure_logging
from utils.singleton_lock import single_instance

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("librouteros").setLevel(logging.WARNING)
logging.getLogger("utils.chat_cleaner").setLevel(logging.WARNING)
configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:  # type: ignore[reportMissingTypeArgument]
    with bind_component(COMPONENT_SYSTEM):
        await set_bot_commands(app)
    # استعادة حالة الـ watchdog من DB قبل بدء الجدولة
    from core.watchdog import load_status_from_db

    load_status_from_db()
    if app.job_queue:
        backup_scheduler.restore(app.job_queue)
        logger.info("Backup schedule restored from database")
        existing = app.job_queue.get_jobs_by_name("router_watchdog")
        if not existing:
            from bot.handlers.watchdog import check_all_routers

            app.job_queue.run_repeating(
                check_all_routers,
                interval=WATCHDOG_INTERVAL,
                first=WATCHDOG_FIRST_DELAY,
                name="router_watchdog",
            )
            logger.info("Router watchdog auto-started")

        # Chat Cleaner Background GC (runs every 1 hour)
        from utils.chat_cleaner import run_background_cleanup

        app.job_queue.run_repeating(
            run_background_cleanup, interval=3600, first=60, name="chat_cleaner_gc"
        )
        logger.info("Chat cleaner GC job scheduled")


def main():
    # Allow --no-lock escape flag for debugging/development
    force_lock = "--no-lock" not in sys.argv

    with single_instance(force=not force_lock):
        init_db()

        from core.backup.file_server import start_file_server

        start_file_server()

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            # Single ConversationHandler manages 28 states across all features.
            # concurrent_updates=False prevents state corruption when multiple
            # updates arrive simultaneously (PTB warning is cosmetic).
            .concurrent_updates(False)
            .job_queue(JobQueue())
            .post_init(post_init)
            .build()
        )

        build_all(application)

        def _cleanup_pool():
            try:
                from core.backup.file_server import stop_file_server

                stop_file_server()
                mikrotik_api.close()
                logger.info("Connection pool cleaned up")
            except (OSError, RuntimeError) as e:
                logger.error("Error during pool cleanup: %s", e)

        atexit.register(_cleanup_pool)

        logger.info("🐱 Bot is running...")

        # Signal handlers for graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler(signum: int, frame: FrameType | None) -> None:
            logger.info("Received signal %d, initiating graceful shutdown...", signum)
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Run polling with shutdown support
        async def run_with_shutdown():
            from utils.logging_setup import COMPONENT_SYSTEM, bind_component

            with bind_component(COMPONENT_SYSTEM):
                assert application.updater is not None, "Updater was not initialized by PTB"
                updater = application.updater
                try:
                    await application.initialize()
                    await application.start()
                    await updater.start_polling()
                    await shutdown_event.wait()
                    logger.info("Shutting down polling...")
                finally:
                    from core.backup.file_server import stop_file_server

                    stop_file_server()
                    await updater.stop()
                    await application.stop()
                    await application.shutdown()
                    mikrotik_api.close()
                    logger.info("Graceful shutdown complete")

        try:
            asyncio.run(run_with_shutdown())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")


if __name__ == "__main__":
    main()
