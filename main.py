import atexit
import logging
import signal
import sys
import asyncio
from telegram.ext import (
    Application,
    JobQueue,
)
from config import BOT_TOKEN, WATCHDOG_INTERVAL, WATCHDOG_FIRST_DELAY
from database.models import init_db
from core.backup_scheduler import backup_scheduler
from core.mikrotik_api import mikrotik_api
from utils.logging_setup import configure_logging
from bot.registrations import build_all
from utils.bot_commands import set_bot_commands
from utils.singleton_lock import single_instance

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("librouteros").setLevel(logging.WARNING)
logging.getLogger("utils.chat_cleaner").setLevel(logging.WARNING)
configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    await set_bot_commands(app)
    # استعادة حالة الـ watchdog من DB قبل بدء الجدولة
    from core.watchdog import load_status_from_db

    load_status_from_db()
    if app.job_queue:
        backup_scheduler.restore(app.job_queue)
        logger.info("Backup schedule restored from database")
        existing = app.job_queue.get_jobs_by_name("router_watchdog")
        if not existing:
            from bot.handlers.watchdog import _check_all_routers

            app.job_queue.run_repeating(
                _check_all_routers,
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
                mikrotik_api.close()
                logger.info("Connection pool cleaned up")
            except Exception as e:
                logger.error(f"Error during pool cleanup: {e}")

        atexit.register(_cleanup_pool)

        logger.info("🐱 Bot is running...")

        # Signal handlers for graceful shutdown
        shutdown_event = asyncio.Event()

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            shutdown_event.set()

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        # Run polling with shutdown support
        async def run_with_shutdown():
            assert application.updater is not None, "Updater was not initialized by PTB"
            updater = application.updater
            try:
                await application.initialize()
                await application.start()
                await updater.start_polling()
                await shutdown_event.wait()
                logger.info("Shutting down polling...")
            finally:
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
