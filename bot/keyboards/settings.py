from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_pdf_settings_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔤 إعدادات النصوص والهوية", callback_data="pdf_group_text")],
        [InlineKeyboardButton("📐 إعدادات الهيكل والمقاسات", callback_data="pdf_group_layout")],
        [InlineKeyboardButton("📱 إعدادات الباركود", callback_data="pdf_group_misc")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pdf_text_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🏷️ اسم الشبكة", callback_data="pdf_brand_name"),
            InlineKeyboardButton("🌐 DNS الـ Hotspot", callback_data="pdf_hotspot_dns"),
        ],
        [InlineKeyboardButton("📝 التذييل", callback_data="pdf_footer")],
        [InlineKeyboardButton("🔤 أحجام الخط", callback_data="pdf_value_font_size")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_pdf_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pdf_layout_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📏 الهوامش", callback_data="pdf_margins")],
        [InlineKeyboardButton("↔️ الفواصل", callback_data="pdf_spacing")],
        [
            InlineKeyboardButton("📄 الكروت/صف", callback_data="pdf_cards_per_row"),
            InlineKeyboardButton("📄 الكروت/صفحة", callback_data="pdf_cards_per_page"),
        ],
        [InlineKeyboardButton("📐 تباعد النصوص", callback_data="pdf_label_spacing")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_pdf_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pdf_misc_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📱 تفعيل QR Code", callback_data="pdf_show_qr")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_pdf_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_schedule_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🟢 تفعيل", callback_data="schedule_enable"),
            InlineKeyboardButton("🔴 تعطيل", callback_data="schedule_disable"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")],
    ]
    return InlineKeyboardMarkup(keyboard)
