from telegram import InlineKeyboardButton, InlineKeyboardMarkup

_KeyboardRow = list[InlineKeyboardButton]
_KeyboardLayout = list[_KeyboardRow]


def get_router_keyboard() -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import CALLBACKS  # noqa: PLC0415 - avoid circular import

    keyboard = [
        [InlineKeyboardButton("📋 أجهزة الراوتر", callback_data="saved_routers")],
        [InlineKeyboardButton("🔍 بحث عن راوتر", callback_data="discover_routers")],
        [InlineKeyboardButton("➕ إضافة راوتر", callback_data=CALLBACKS["manual_add_router"])],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_main_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🌐 إدارة الروترات", callback_data="menu_routers"),
            InlineKeyboardButton("🔍 حالة الشبكة", callback_data="watchdog_status"),
        ],
        [
            InlineKeyboardButton("📡 هوتسبوت", callback_data="menu_hotspot"),
            InlineKeyboardButton("🎫 يوزر مانيجر", callback_data="menu_userman"),
        ],
        [
            InlineKeyboardButton("🖨️ طباعة الكروت", callback_data="hotspot_cards"),
            InlineKeyboardButton("⚙️ إعدادات الطباعة", callback_data="menu_pdf_settings"),
        ],
        [
            InlineKeyboardButton("📊 الإحصائيات", callback_data="menu_stats"),
            InlineKeyboardButton("📈 التقارير", callback_data="reports_menu"),
        ],
        [
            InlineKeyboardButton("💾 النسخ الاحتياطي والنظام", callback_data="menu_backup"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_routers_keyboard() -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import CALLBACKS  # noqa: PLC0415 - avoid circular import

    keyboard = [
        [
            InlineKeyboardButton("📋 الروترات المحفوظة", callback_data="saved_routers"),
            InlineKeyboardButton("🔍 بحث عن راوتر", callback_data="discover_routers"),
        ],
        [
            InlineKeyboardButton("➕ إضافة راوتر", callback_data=CALLBACKS["manual_add_router"]),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ تأكيد", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ إلغاء", callback_data="confirm_no"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_nav_back_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data="go_back")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_skip_keyboard(skip_callback: str, back_callback: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=skip_callback),
            InlineKeyboardButton("🔙 رجوع", callback_data=back_callback),
        ],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("❌ إلغاء الإدخال", callback_data="cancel_edit")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)
