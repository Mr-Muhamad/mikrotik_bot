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
        BotCommand("add", "➕ إضافة هوتسبوت"),
        BotCommand("edit", "✏️ تعديل هوتسبوت"),
        BotCommand("delete", "🗑️ حذف هوتسبوت"),
        BotCommand("search", "🔍 بحث هوتسبوت"),
        BotCommand("cards", "🎫 كروت هوتسبوت"),
        BotCommand("userman", "🎫 يوزر مانيجر"),
        BotCommand("backup", "📦 النسخ الاحتياطي"),
        BotCommand("routers", "🌐 أجهزة الراوتر"),
        BotCommand("settings", "⚙️ إعدادات الطباعة"),
        BotCommand("reboot", "🔄 إعادة التشغيل"),
        BotCommand("metrics", "📊 أداء الاتصال"),
        BotCommand("logs", "📋 سجل التدقيق"),
        BotCommand("sync", "🔄 تحديث القائمة"),
        BotCommand("clean", "🧹 مسح المحادثة"),
        BotCommand("usage", "📊 تقرير الاستخدام"),
        BotCommand("report", "📊 تقرير المبيعات"),
        BotCommand("watchdog", "🔍 حالة الروترات"),
        BotCommand("watchdog_start", "🟢 بدء المراقبة"),
        BotCommand("roles", "👥 أدوار المشرفين"),
        BotCommand("batches", "📦 دفعات الكروت"),
        BotCommand("sales", "💰 المبيعات"),
        BotCommand("addrouter", "🌐 إضافة راوتر"),
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
