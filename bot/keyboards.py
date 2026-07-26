from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.mikrotik_client import RouterOSRow
from core.network_probe import DiscoveredRouter
from database.models import get_router_display_name
from utils.pagination import Paginator

# Type aliases for keyboard construction
_KeyboardRow = list[InlineKeyboardButton]
_KeyboardLayout = list[_KeyboardRow]

SUBMENU_PAGE_SIZE = 20

TIME_OPTIONS: list[tuple[str, int | None]] = [
    ("اليوم", 1),
    ("آخر 7 أيام", 7),
    ("آخر 30 يوماً", 30),
    ("الكل", None),
]


def get_router_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard for selecting saved routers or discovering new ones."""
    from bot.handlers.callback_constants import CALLBACKS

    keyboard = [
        [InlineKeyboardButton("📋 أجهزة الراوتر", callback_data="saved_routers")],
        [InlineKeyboardButton("🔍 بحث عن راوتر", callback_data="discover_routers")],
        [InlineKeyboardButton("➕ إضافة راوتر", callback_data=CALLBACKS["manual_add_router"])],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Return the main bot menu keyboard with feature sections ordered by workflow.

    Layout philosophy (top → bottom by frequency & importance):
      Row 1: Router management (discover/connect/reboot/rename) + Monitoring
      Row 2: User management — Hotspot and User Manager kept as SEPARATE paths
             (they are distinct RouterOS subsystems with different APIs)
      Row 3: Cards generation + Statistics
      Row 4: Backup + Reports/Usage (secondary admin tools)
      Row 5: PDF settings (tertiary) + Switch router
    """
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
    """Return the router management submenu keyboard.

    Groups all router-level operations: discover, saved list, add manual.
    Reboot/rename/delete live inside the saved-router action keyboard.
    """
    from bot.handlers.callback_constants import CALLBACKS

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


def get_reports_keyboard() -> InlineKeyboardMarkup:
    """Return the reports submenu keyboard (usage report + sales/batches)."""
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


def get_hotspot_keyboard() -> InlineKeyboardMarkup:
    """Return the Hotspot management submenu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ إضافة", callback_data="hotspot_add"),
            InlineKeyboardButton("✏️ تعديل", callback_data="hotspot_edit"),
        ],
        [
            InlineKeyboardButton("🗑️ حذف", callback_data="hotspot_delete"),
            InlineKeyboardButton("🔍 بحث", callback_data="hotspot_search"),
        ],
        [
            InlineKeyboardButton("🎫 توليد كروت", callback_data="hotspot_cards"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="hotspot_stats"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_userman_keyboard() -> InlineKeyboardMarkup:
    """Return the User Manager submenu keyboard."""
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


def get_stats_keyboard() -> InlineKeyboardMarkup:
    """Return the statistics submenu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📡 ملخص سريع", callback_data="stats_hotspot"),
            InlineKeyboardButton("🎫 User Manager", callback_data="stats_userman"),
        ],
        [
            InlineKeyboardButton("📈 رسم بياني مصور", callback_data="stats_chart"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_report_keyboard() -> InlineKeyboardMarkup:
    """Return the Hotspot usage report keyboard with export and refresh options."""
    keyboard = [
        [
            InlineKeyboardButton("📊 ملف إكسيل منسق (.xlsx)", callback_data="report_excel"),
            InlineKeyboardButton("📄 نص مجرد (CSV)", callback_data="report_csv"),
        ],
        [InlineKeyboardButton("🔄 تحديث بيانات", callback_data="report_refresh")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_batches_keyboard(
    batches: list[RouterOSRow],
    page: int = 0,
    total: int = 0,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    """Return a keyboard listing saved card batches for selection with pagination."""
    from bot.handlers.callback_constants import batch_page

    keyboard: _KeyboardLayout = []
    for b in batches:
        label = f"#{b['id']} • {b.get('name', '')} • {b.get('count', 0)}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"batch_sel:{b['id']}")])

    nav_row: _KeyboardRow = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=batch_page(page - 1)))
    if total > (page + 1) * page_size:
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=batch_page(page + 1)))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_batch_detail_keyboard(
    batch_id: int, payment_status: str = "unpaid"
) -> InlineKeyboardMarkup:
    """Return the action keyboard for a single card batch with payment controls."""
    from bot.handlers.callback_constants import mark_payment_cb

    payment_row = []
    if payment_status != "paid":
        payment_row.append(
            InlineKeyboardButton("✅ تم الدفع", callback_data=mark_payment_cb(batch_id, "paid"))
        )
    if payment_status != "unpaid":
        payment_row.append(
            InlineKeyboardButton("🆓 لم يُدفع", callback_data=mark_payment_cb(batch_id, "unpaid"))
        )
    if payment_status != "deferred":
        payment_row.append(
            InlineKeyboardButton("⏳ آجل", callback_data=mark_payment_cb(batch_id, "deferred"))
        )
    keyboard = [
        [InlineKeyboardButton("🔄 إعادة طباعة", callback_data=f"batch_regen:{batch_id}")],
        [InlineKeyboardButton("📤 إرسال للعميل", callback_data=f"share_card:{batch_id}")],
    ]
    if payment_row:
        keyboard.append(payment_row)
    keyboard.append([InlineKeyboardButton("🔙 قائمة الدفعات", callback_data="batches_refresh")])
    return InlineKeyboardMarkup(keyboard)


def get_backup_keyboard() -> InlineKeyboardMarkup:
    """Return the backup submenu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("💾 نسخة للنظام بالكامل", callback_data="backup_full"),
            InlineKeyboardButton("🎫 نسخة لليوزر مانيجر", callback_data="backup_userman"),
        ],
        [InlineKeyboardButton("⏰ جدولة النسخ", callback_data="menu_schedule")],
        [
            InlineKeyboardButton("📥 استعادة النظام", callback_data="backup_restore"),
            InlineKeyboardButton("🎫 استعادة يوزر مانيجر", callback_data="userman_restore"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pdf_settings_keyboard() -> InlineKeyboardMarkup:
    """Return the PDF settings main categories keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔤 إعدادات النصوص والهوية", callback_data="pdf_group_text")],
        [InlineKeyboardButton("📐 إعدادات الهيكل والمقاسات", callback_data="pdf_group_layout")],
        [InlineKeyboardButton("📱 إعدادات الباركود", callback_data="pdf_group_misc")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_pdf_text_keyboard() -> InlineKeyboardMarkup:
    """Return the PDF text settings submenu."""
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
    """Return the PDF layout settings submenu."""
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
    """Return the PDF miscellaneous settings submenu."""
    keyboard = [
        [InlineKeyboardButton("📱 تفعيل QR Code", callback_data="pdf_show_qr")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_pdf_settings")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_card_type_keyboard() -> InlineKeyboardMarkup:
    """Return the card type selection keyboard for User Manager."""
    keyboard = [
        [InlineKeyboardButton("1️⃣ اسم + سر مختلفين", callback_data="card_type1")],
        [InlineKeyboardButton("2️⃣ اسم + سر متشابهين", callback_data="card_type2")],
        [InlineKeyboardButton("3️⃣ اسم + سر فارغة", callback_data="card_type3")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_userman")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_card_payment_keyboard() -> InlineKeyboardMarkup:
    """Return the payment-status selection keyboard for User Manager cards."""
    keyboard = [
        [InlineKeyboardButton("💰 مدفوع", callback_data="card_paid")],
        [InlineKeyboardButton("🆓 غير مدفوع", callback_data="card_unpaid")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="card_back_to_profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_card_mac_keyboard() -> InlineKeyboardMarkup:
    """Return the MAC-binding choice keyboard for User Manager cards."""
    keyboard = [
        [InlineKeyboardButton("🖥️ ربط بجهاز معروف", callback_data="card_bind_known")],
        [InlineKeyboardButton("🚫 بدون ربط", callback_data="card_no_bind")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="card_back_to_payment")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_profile_keyboard(
    profiles: list[str],
    prefix: str,
    back_callback: str = "main_menu",
) -> InlineKeyboardMarkup:
    """Return a keyboard listing profiles; callback_data uses index (prefix_0, prefix_1, …)."""
    keyboard: _KeyboardLayout = []
    for index, profile in enumerate(profiles):
        keyboard.append([InlineKeyboardButton(profile, callback_data=f"{prefix}_{index}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Return a confirm/cancel confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ تأكيد", callback_data="confirm_yes"),
            InlineKeyboardButton("❌ إلغاء", callback_data="confirm_no"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_discovered_routers_keyboard(
    routers: list[DiscoveredRouter],
) -> InlineKeyboardMarkup:
    """Return a keyboard listing discovered routers for selection."""
    keyboard: _KeyboardLayout = []
    for router in routers:
        name: str = router.display_name()
        keyboard.append(
            [InlineKeyboardButton(name, callback_data=f"disc_router_{router.ip_address}")]
        )
    keyboard.append([InlineKeyboardButton("🔄 إعادة بحث", callback_data="discover_routers")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_saved_routers_keyboard(
    routers: list[RouterOSRow],
) -> InlineKeyboardMarkup:
    """Return a keyboard listing saved routers with version info."""
    keyboard: _KeyboardLayout = []
    for r in routers:
        name: str = get_router_display_name(r)
        version: str = str(r.get("version", ""))
        if version:
            name += f" (v{version})"
        keyboard.append([InlineKeyboardButton(name, callback_data=f"saved_router_{r['id']}")])
    keyboard.append([InlineKeyboardButton("🔄 تحديث الحالة", callback_data="refresh_routers")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_router_action_keyboard(router_id: int) -> InlineKeyboardMarkup:
    """Return the action keyboard for a saved router (connect, reboot, rename, delete)."""
    keyboard = [
        [
            InlineKeyboardButton("✅ اتصال", callback_data=f"connect_router_{router_id}"),
            InlineKeyboardButton("🔄 إعادة تشغيل", callback_data=f"reboot_router_{router_id}"),
        ],
        [
            InlineKeyboardButton("✏️ تسمية", callback_data=f"rename_router_{router_id}"),
            InlineKeyboardButton("🗑️ حذف", callback_data=f"delete_router_{router_id}"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="saved_routers")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_delete_router_confirm_keyboard(router_id: int) -> InlineKeyboardMarkup:
    """Return a confirmation keyboard for deleting a saved router."""
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ تأكيد", callback_data=f"confirm_delete_router_yes_{router_id}"
            ),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"confirm_delete_router_no_{router_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_schedule_keyboard() -> InlineKeyboardMarkup:
    """Return the backup schedule enable/disable keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("🟢 تفعيل", callback_data="schedule_enable"),
            InlineKeyboardButton("🔴 تعطيل", callback_data="schedule_disable"),
        ],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_reboot_keyboard(router_key: str) -> InlineKeyboardMarkup:
    """Return a confirmation keyboard for rebooting a router."""
    keyboard = [
        [
            InlineKeyboardButton("✅ نعم، أعد التشغيل", callback_data=f"reboot_yes_{router_key}"),
            InlineKeyboardButton("❌ إلغاء", callback_data="reboot_no"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def _user_button_label(user: RouterOSRow) -> str:
    name = str(user.get("name", "N/A"))
    comment = str(user.get("comment", ""))
    label = f"{name} ({comment})" if comment else name
    if len(label) > 35:
        label = label[:32] + "..."
    return label


def get_user_selection_keyboard(
    users: list[RouterOSRow],
    action_prefix: str,
    back_callback: str = "menu_hotspot",
) -> InlineKeyboardMarkup:
    """Return a keyboard listing hotspot users for selection with a given action prefix."""
    keyboard: _KeyboardLayout = []
    for user in users:
        user_id: str = str(user.get(".id") or "*0")
        keyboard.append(
            [
                InlineKeyboardButton(
                    _user_button_label(user), callback_data=f"{action_prefix}_{user_id}"
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_paginated_user_keyboard(
    users: list[RouterOSRow],
    action_prefix: str,
    paginator: Paginator[RouterOSRow],
    back_callback: str = "menu_hotspot",
) -> InlineKeyboardMarkup:
    """Return a paginated keyboard listing hotspot users for selection."""
    keyboard: _KeyboardLayout = []
    for user in paginator.current_items:
        user_id: str = str(user.get(".id") or "*0")
        keyboard.append(
            [
                InlineKeyboardButton(
                    _user_button_label(user), callback_data=f"{action_prefix}_{user_id}"
                )
            ]
        )

    nav_row: _KeyboardRow = []
    if paginator.has_prev():
        nav_row.append(
            InlineKeyboardButton(
                f"◀️ السابق ({paginator.page})",
                callback_data=f"page_{action_prefix}_{paginator.prev_page()}",
            )
        )
    if paginator.has_next():
        nav_row.append(
            InlineKeyboardButton(
                f"التالي ({paginator.page + 2}) ▶️",
                callback_data=f"page_{action_prefix}_{paginator.next_page()}",
            )
        )
    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_edit_user_keyboard(users: list[RouterOSRow]) -> InlineKeyboardMarkup:
    """Return a keyboard listing hotspot users for selection to edit."""
    return get_user_selection_keyboard(users, "edit_user", "menu_hotspot")


def get_delete_user_keyboard(users: list[RouterOSRow]) -> InlineKeyboardMarkup:
    """Return a keyboard listing hotspot users for selection to delete."""
    return get_user_selection_keyboard(users, "delete_user", "menu_hotspot")


def get_edit_field_keyboard(is_disabled: bool = False) -> InlineKeyboardMarkup:
    """Return the field selection keyboard for editing a hotspot user."""
    toggle_label = "🔴 تعطيل" if not is_disabled else "🟢 تفعيل"
    keyboard = [
        [
            InlineKeyboardButton("👤 الاسم", callback_data="edit_field_name"),
            InlineKeyboardButton("🔑 الباسورد", callback_data="edit_field_password"),
        ],
        [
            InlineKeyboardButton("📋 البروفايل", callback_data="edit_field_profile"),
            InlineKeyboardButton("📊 الحد الكلى", callback_data="edit_field_bytes"),
        ],
        [
            InlineKeyboardButton("⏰ مدة الصلاحية", callback_data="edit_field_uptime"),
            InlineKeyboardButton("💬 التعليق", callback_data="edit_field_comment"),
        ],
        [InlineKeyboardButton("📅 يوم التجديد (التعليق)", callback_data="edit_field_renewal_day")],
        [InlineKeyboardButton(toggle_label, callback_data="edit_field_toggle_disabled")],
        [InlineKeyboardButton("🔄 تصفير العدادات", callback_data="edit_field_reset")],
        [InlineKeyboardButton("⛔ طرد المستخدم", callback_data="edit_kick_user")],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data="edit_back_search"),
            InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Return a keyboard with a back button and home button."""
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data=callback_data)],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_nav_back_keyboard() -> InlineKeyboardMarkup:
    """Return a navigation back button keyboard."""
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع", callback_data="go_back")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_skip_keyboard(skip_callback: str, back_callback: str) -> InlineKeyboardMarkup:
    """Return a keyboard with skip and back buttons."""
    keyboard = [
        [
            InlineKeyboardButton("⏭️ تخطي", callback_data=skip_callback),
            InlineKeyboardButton("🔙 رجوع", callback_data=back_callback),
        ],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Return a cancel and home button keyboard."""
    keyboard = [
        [InlineKeyboardButton("❌ إلغاء الإدخال", callback_data="cancel_edit")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_search_results_keyboard(
    paginator: Paginator[RouterOSRow],
    is_userman: bool = False,
) -> InlineKeyboardMarkup:
    """Return a keyboard listing search result hosts for selection using Paginator."""
    from bot.handlers.callback_constants import hotspot_search_page, userman_search_page

    keyboard: _KeyboardLayout = []
    prefix = "um_sel_" if is_userman else "host_sel_"

    # We iterate over current_items but need their absolute index
    start_idx: int = paginator.page * paginator.page_size
    for i, h in enumerate(paginator.current_items):
        abs_idx: int = start_idx + i
        name: str = str(h.get("name") or h.get("host-name") or h.get("user") or "") or "غير معروف"
        ip: str = str(h.get("address") or "") or "—"
        label: str = f"{abs_idx + 1}. {name}" if name else f"{abs_idx + 1}. {ip}"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"{prefix}{abs_idx}")])

    nav_row: _KeyboardRow = []
    if paginator.has_prev():
        cb_data = (
            userman_search_page(str(paginator.prev_page()))
            if is_userman
            else hotspot_search_page(str(paginator.prev_page()))
        )
        nav_row.append(InlineKeyboardButton("⬅️ السابق", callback_data=cb_data))
    if paginator.has_next():
        cb_data = (
            userman_search_page(str(paginator.next_page()))
            if is_userman
            else hotspot_search_page(str(paginator.next_page()))
        )
        nav_row.append(InlineKeyboardButton("التالي ➡️", callback_data=cb_data))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="search_back")])
    return InlineKeyboardMarkup(keyboard)


def get_host_detail_keyboard(is_disabled: bool = False, mac: str = "") -> InlineKeyboardMarkup:
    """Return the host detail keyboard with kick, block, and toggle options."""
    from bot.handlers.callback_constants import block_mac_cb

    toggle_text = "🟢 تفعيل المستخدم" if is_disabled else "🔴 تعطيل المستخدم"
    keyboard = [
        [
            InlineKeyboardButton("⛔ طرد من الشبكة", callback_data="host_kick_execute"),
            InlineKeyboardButton("🔄 تصفير العداد", callback_data="host_reset_counters"),
        ],
        [InlineKeyboardButton(toggle_text, callback_data="host_toggle_disabled")],
    ]
    if mac:
        keyboard.append([InlineKeyboardButton("🚫 حظر دائم", callback_data=block_mac_cb(mac))])
    keyboard.append([InlineKeyboardButton("📋 قائمة المحظورين", callback_data="blocked_list")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="search_back")])
    return InlineKeyboardMarkup(keyboard)


def get_blocked_macs_keyboard(
    blocked: list[RouterOSRow],
) -> InlineKeyboardMarkup:
    """لوحة مفاتيح قائمة MACs المحظورة مع زر رفع الحظر لكل عنصر."""
    from bot.handlers.callback_constants import unblock_mac_cb

    keyboard: _KeyboardLayout = []
    for entry in blocked:
        mac: str = str(entry.get("address", ""))
        comment: str = str(entry.get("comment", ""))
        label: str = f"🔓 {mac}" + (f" ({comment[:15]})" if comment else "")
        keyboard.append([InlineKeyboardButton(label, callback_data=unblock_mac_cb(mac))])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="hotspot_search")])
    return InlineKeyboardMarkup(keyboard)


def get_userman_detail_keyboard(is_disabled: bool = False) -> InlineKeyboardMarkup:
    """Return the User Manager detail keyboard with management options."""
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


def _logs_time_label(filters: dict[str, object]) -> str:
    since_days = filters.get("since_days")
    if not since_days:
        return "الكل"
    return next((name for name, days in TIME_OPTIONS if days == since_days), "الكل")


def get_logs_filter_keyboard(
    filters: dict[str, object],
    page: int = 0,
    total: int = 0,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    """Return the filter + pagination keyboard for the audit log view."""
    has_prev: bool = page > 0
    has_next: bool = (page + 1) * page_size < total
    router_label = str(filters.get("router") or "الكل")
    admin_label = str(filters.get("admin_label") or filters.get("admin_id") or "الكل")
    action_label = str(filters.get("action") or "الكل")
    time_label: str = _logs_time_label(filters)

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
    if any(
        (
            filters.get("router"),
            filters.get("admin_id"),
            filters.get("action"),
            filters.get("since_days"),
        )
    ):
        keyboard.append([InlineKeyboardButton("🧹 مسح الفلاتر", callback_data="logs_clear")])

    nav_buttons: _KeyboardRow = []
    if has_prev:
        nav_buttons.append(InlineKeyboardButton("◀️ السابس", callback_data=f"logs_page_{page - 1}"))
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
    """Return a keyboard listing filter options for the given category."""
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


def get_backup_restore_keyboard(
    backups: list[RouterOSRow],
) -> InlineKeyboardMarkup:
    """Return keyboard listing available backups for restore."""
    keyboard: _KeyboardLayout = []
    for idx, b in enumerate(backups[:10]):
        name: str = str(b.get("name", ""))
        btype: str = "📦" if str(b.get("type")) == "system" else "📄"
        keyboard.append([InlineKeyboardButton(f"{btype} {name}", callback_data=f"restore:{idx}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")])
    return InlineKeyboardMarkup(keyboard)


def get_restore_confirm_keyboard() -> InlineKeyboardMarkup:
    """Return confirmation keyboard for backup restore."""
    keyboard = [
        [InlineKeyboardButton("⚠️ نعم، استعادة", callback_data="confirm_restore")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="menu_backup")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_backup_download_keyboard(
    downloaded: list[str],
    backup_type: str,
    local_path: str = "",
) -> InlineKeyboardMarkup:
    """أزرار تحميل اختيارية تظهر بعد نجاح الباكوب.

    Args:
        downloaded: أسماء الملفات المحمّلة.
        backup_type: "full" أو "userman".
        local_path: المسار المحلي للملفات (يُخزّن في user_data).
    """
    keyboard: _KeyboardLayout = []
    for idx, fname in enumerate(downloaded):
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"📥 تحميل {fname}",
                    callback_data=f"backup_dl:{backup_type}:{idx}",
                )
            ]
        )
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")])
    return InlineKeyboardMarkup(keyboard)


def get_userman_restore_keyboard(
    tar_files: list[RouterOSRow],
) -> InlineKeyboardMarkup:
    """Return keyboard listing saved User Manager tar backups for restore."""
    keyboard: _KeyboardLayout = []
    for idx, f in enumerate(tar_files):
        name: str = str(f.get("filename", ""))
        size_kb: int = int(f.get("size") or 0) // 1024
        label: str = f"{name} ({size_kb}KB)"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"userman_restore_tar:{idx}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")])
    return InlineKeyboardMarkup(keyboard)


def get_userman_restore_confirm_keyboard() -> InlineKeyboardMarkup:
    """Return confirmation keyboard for userman restore."""
    keyboard = [
        [InlineKeyboardButton("⚠️ نعم، استعادة", callback_data="userman_restore_exec")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="menu_backup")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_operator_router_assignment_keyboard(
    operator_id: int,
    all_routers: list[RouterOSRow],
    assigned_router_ids: list[int],
) -> InlineKeyboardMarkup:
    """لوحة مفاتيح إسناد/سحب الروترات لمشغّل معيّن.

    كل راوتر يظهر بزر: ✅ (مُسنَد → اضغط لسحب) أو ⬜ (غير مُسنَد → اضغط لإسناد).
    """
    from bot.handlers.callback_constants import op_assign_cb, op_revoke_cb

    keyboard: _KeyboardLayout = []
    for r in all_routers:
        raw_rid = r.get("id")
        if raw_rid is None:
            continue
        rid_int: int = int(raw_rid)
        name: str = str(r.get("name_alias") or r.get("identity") or str(rid_int))
        ip: str = str(r.get("ip_address", ""))
        label_name: str = f"{name} ({ip})" if ip else name
        if rid_int in assigned_router_ids:
            label: str = f"✅ {label_name}"
            cb = op_revoke_cb(operator_id, rid_int)
        else:
            label = f"⬜ {label_name}"
            cb = op_assign_cb(operator_id, rid_int)
        keyboard.append([InlineKeyboardButton(label, callback_data=cb)])
    keyboard.append([InlineKeyboardButton("🔙 رجوع لقائمة الأدوار", callback_data="roles_back")])
    return InlineKeyboardMarkup(keyboard)
