import asyncio
import logging

from telegram import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from telegram.ext import Application

logger = logging.getLogger(__name__)


async def set_bot_commands(app: Application):
    """Set bot commands menu for both private chats and groups — retries 3 times."""
    PRIVATE = BotCommandScopeAllPrivateChats()
    GROUP = BotCommandScopeAllGroupChats()
    commands = [
        BotCommand("start", "🏠 القائمة الرئيسية"),
        BotCommand("help", "❓ مساعدة"),
        BotCommand("add", "➕ إضافة مستخدم هوت سبوت"),
        BotCommand("edit", "✏️ تعديل مستخدم هوت سبوت"),
        BotCommand("delete", "🗑️ حذف مستخدم هوت سبوت"),
        BotCommand("search", "🔍 بحث عن مستخدم"),
        BotCommand("cards", "🎫 إنشاء كروت هوت سبوت"),
        BotCommand("userman", "🎫 إدارة User Manager"),
        BotCommand("backup", "📦 الباكوب"),
        BotCommand("routers", "🌐 إدارة الروترات"),
        BotCommand("settings", "⚙️ الإعدادات"),
        BotCommand("reboot", "🔄 إعادة تشغيل الراوتر"),
        BotCommand("metrics", "📊 أداء الاتصال"),
        BotCommand("logs", "📋 سجل التدقيق"),
        BotCommand("sync", "🔄 تحديث قائمة الأوامر"),
        BotCommand("clean", "🧹 تنظيف الشات"),
        BotCommand("usage", "📊 تقرير استخدام مستخدم"),
        BotCommand("report", "📊 تقرير استخدام هوت سبوت"),
        BotCommand("watchdog", "🔍 حالة الروترات"),
        BotCommand("watchdog_start", "🟢 بدء مراقبة الروترات"),
        BotCommand("roles", "👥 أدوار المشرفين"),
        BotCommand("batches", "📦 دفعات الكروت المحفوظة"),
        BotCommand("sales", "💰 ملخص المبيعات"),
        BotCommand("addrouter", "🌐 إضافة روتر يدوياً"),
        BotCommand("cancel", "❌ إلغاء"),
    ]
    for attempt in range(1, 4):
        try:
            await app.bot.delete_my_commands()
            await app.bot.delete_my_commands(scope=PRIVATE)
            await app.bot.delete_my_commands(scope=GROUP)
            await app.bot.set_my_commands(commands, scope=PRIVATE)
            await app.bot.set_my_commands(commands, scope=GROUP)
            logger.info(f"✅ Set {len(commands)} bot commands for private+group (attempt {attempt})")
            return
        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt}/3 — set_bot_commands failed: {e}")
            if attempt < 3:
                await asyncio.sleep(2 ** attempt)
