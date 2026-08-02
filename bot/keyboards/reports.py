from telegram import InlineKeyboardButton, InlineKeyboardMarkup

_KeyboardRow = list[InlineKeyboardButton]
_KeyboardLayout = list[_KeyboardRow]

SUBMENU_PAGE_SIZE = 20

TIME_OPTIONS: list[tuple[str, int | None]] = [
    ("اليوم", 1),
    ("آخر 7 أيام", 7),
    ("آخر 30 يوماً", 30),
    ("الكل", None),
]


def _logs_time_label(filters: dict[str, object]) -> str:
    since_days = filters.get("since_days")
    if not since_days:
        return "الكل"
    return next((name for name, days in TIME_OPTIONS if days == since_days), "الكل")


def get_reports_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("📊 تقرير استخدام", callback_data="usage_start"),
            InlineKeyboardButton("💰 المبيعات", callback_data="sales_summary"),
        ],
        [
            InlineKeyboardButton("📦 دفعات الكروت", callback_data="batches_menu"),
            InlineKeyboardButton("📋 سجل التدقيق", callback_data="logs_menu"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_report_keyboard() -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import CALLBACKS  # noqa: PLC0415 - avoid circular import

    keyboard = [
        [
            InlineKeyboardButton("📊 ملف إكسيل منسق (.xlsx)", callback_data=CALLBACKS["report_excel"]),
            InlineKeyboardButton("📄 نص مجرد (CSV)", callback_data=CALLBACKS["report_csv"]),
        ],
        [InlineKeyboardButton("🔄 تحديث بيانات", callback_data=CALLBACKS["report_refresh"])],
        [InlineKeyboardButton("🔙 رجوع", callback_data=CALLBACKS["main_menu"])],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_stats_keyboard() -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import CALLBACKS  # noqa: PLC0415 - avoid circular import

    keyboard = [
        [
            InlineKeyboardButton("📡 ملخص سريع", callback_data=CALLBACKS["stats_hotspot"]),
            InlineKeyboardButton("🎫 User Manager", callback_data=CALLBACKS["stats_userman"]),
        ],
        [
            InlineKeyboardButton("📈 رسم بياني مصور", callback_data=CALLBACKS["stats_chart"]),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data=CALLBACKS["main_menu"])],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_logs_filter_keyboard(
    filters: dict[str, object],
    page: int = 0,
    total: int = 0,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    has_prev: bool = page > 0
    has_next: bool = (page + 1) * page_size < total
    router_label = str(filters.get("router") or "الكل")
    admin_label = str(filters.get("admin_label") or filters.get("admin_id") or "الكل")
    action_label = str(filters.get("action") or "الكل")
    time_label: str = _logs_time_label(filters)
    search_text: str = str(filters.get("search_text") or "")

    keyboard: _KeyboardLayout = [
        [
            InlineKeyboardButton(f"🔍 راوتر: {router_label}", callback_data="logs_filter_router"),
            InlineKeyboardButton(f"👤 مشرف: {admin_label}", callback_data="logs_filter_admin"),
        ],
        [
            InlineKeyboardButton(f"⚙️ عملية: {action_label}", callback_data="logs_filter_action"),
            InlineKeyboardButton(f"🕓 مدة: {time_label}", callback_data="logs_filter_time"),
        ],
    ]
    text_label = f"🔍 بحث: {search_text}" if search_text else "🔍 بحث نصي"
    keyboard.append([InlineKeyboardButton(text_label, callback_data="logs_filter_text")])
    if any(
        (
            filters.get("router"),
            filters.get("admin_id"),
            filters.get("action"),
            filters.get("since_days"),
            filters.get("search_text"),
        )
    ):
        keyboard.append([InlineKeyboardButton("🧹 مسح الفلاتر", callback_data="logs_clear")])

    nav_buttons: _KeyboardRow = []
    if has_prev:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data=f"logs_page_{page - 1}"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data=f"logs_page_{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_logs_submenu_keyboard(
    suffix: str,
    options: list[str],
    page: int = 0,
    page_size: int = SUBMENU_PAGE_SIZE,
) -> InlineKeyboardMarkup:
    start: int = page * page_size
    chunk: list[str] = options[start : start + page_size]
    keyboard: _KeyboardLayout = []
    for i, opt in enumerate(chunk):
        label: str = str(opt)
        if len(label) > 60:
            label = label[:57] + "..."
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f"logs_set_{suffix}_{start + i}")]
        )
    nav_buttons: _KeyboardRow = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ السابق", callback_data="logs_sub_prev"))
    if start + page_size < len(options):
        nav_buttons.append(InlineKeyboardButton("التالي ▶️", callback_data="logs_sub_next"))
    if nav_buttons:
        keyboard.append(nav_buttons)
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="logs_back")])
    return InlineKeyboardMarkup(keyboard)
