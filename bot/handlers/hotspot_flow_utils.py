from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.messages import SEND_UPTIME_DAYS, SEND_UPTIME_HOURS


def get_uptime_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("⏰ بالساعات", callback_data="uptime_hours"),
            InlineKeyboardButton("📅 بالأيام", callback_data="uptime_days"),
        ],
        [InlineKeyboardButton("⏭️ تخطي", callback_data="skip_uptime")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def convert_uptime_value(value: str, unit: str) -> str:
    try:
        num = int(value)
    except ValueError:
        return ""
    if num <= 0:
        return ""
    if unit == "hours":
        return f"{num:02d}:00:00"
    return f"{num}d00:00:00"


def set_uptime_unit(user_data: dict | None, key: str, unit: str) -> tuple[str, str]:
    if user_data is None:
        user_data = {}
    user_data[key] = unit
    if unit == "hours":
        return SEND_UPTIME_HOURS, "hours"
    return SEND_UPTIME_DAYS, "days"
