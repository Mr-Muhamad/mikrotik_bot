from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_userman_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🎫 توليد كروت", callback_data="userman_cards"),
            InlineKeyboardButton("📋 قائمة المستخدمين", callback_data="userman_list"),
        ],
        [
            InlineKeyboardButton("📝 الباقات (Profiles)", callback_data="userman_profiles"),
        ],
        [InlineKeyboardButton("🔍 بحث", callback_data="userman_search")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_userman_detail_keyboard(is_disabled: bool = False) -> InlineKeyboardMarkup:
    toggle_text = "🟢 تفعيل المستخدم" if is_disabled else "🔴 تعطيل المستخدم"
    keyboard = [
        [
            InlineKeyboardButton("⛔ طرد الجلسة", callback_data="um_kick_execute"),
            InlineKeyboardButton("🔄 تصفير العداد", callback_data="um_reset_counters"),
        ],
        [InlineKeyboardButton(toggle_text, callback_data="um_toggle_disabled")],
        [InlineKeyboardButton("➕ إضافة باقة", callback_data="um_add_profile")],
        [InlineKeyboardButton("🗑️ حذف المستخدم", callback_data="um_delete")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="search_back")],
    ]
    return InlineKeyboardMarkup(keyboard)
