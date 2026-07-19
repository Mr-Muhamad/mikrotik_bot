"""Expiry alert message templates for the backup scheduler.

Kept in the core layer (not in bot.messages) so that core modules do not
depend on the Telegram-facing bot package, preserving the architectural
rule that core must remain Telegram-independent.
"""

EXPIRY_ALERT_HEADER = "⏰ <b>تنبيه انتهاء الاشتراك — {router_name}</b>\n\nالمستخدمون التالية تنتهي صلاحيتهم خلال {days} أيام:\n"

EXPIRY_ALERT_USER_ROW = (
    "• <b>{name}</b> | بروفايل: {profile} | متبقي: {remaining_days} يوم"
)

EXPIRY_ALERT_EMPTY = (
    "✅ لا توجد اشتراكات منتهية خلال {days} أيام القادمة على {router_name}"
)
