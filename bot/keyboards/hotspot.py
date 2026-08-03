from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.mikrotik_client import RouterOSRow
from utils.pagination import Paginator

_KeyboardRow = list[InlineKeyboardButton]
_KeyboardLayout = list[_KeyboardRow]


def _user_button_label(user: RouterOSRow) -> str:
    name = str(user.get("name", "N/A"))
    comment = str(user.get("comment", ""))
    label = f"{name} ({comment})" if comment else name
    if len(label) > 35:
        label = label[:32] + "..."
    return label


def get_hotspot_keyboard() -> InlineKeyboardMarkup:
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


def get_card_type_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("1️⃣ اسم + سر مختلفين", callback_data="card_type1")],
        [InlineKeyboardButton("2️⃣ اسم + سر متشابهين", callback_data="card_type2")],
        [InlineKeyboardButton("3️⃣ اسم + سر فارغة", callback_data="card_type3")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="menu_userman")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_card_payment_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("💰 مدفوع", callback_data="card_paid")],
        [InlineKeyboardButton("🆓 غير مدفوع", callback_data="card_unpaid")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="card_back_to_profile")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_card_timestamp_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🕐 الآن (بدون تحديد)", callback_data="card_timestamp_now")],
        [InlineKeyboardButton("📅 تاريخ مخصص", callback_data="card_timestamp_custom")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="card_back_to_payment")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_card_mac_keyboard() -> InlineKeyboardMarkup:
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
    keyboard: _KeyboardLayout = []
    for index, profile in enumerate(profiles):
        keyboard.append([InlineKeyboardButton(profile, callback_data=f"{prefix}_{index}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_callback)])
    keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_user_selection_keyboard(
    users: list[RouterOSRow],
    action_prefix: str,
    back_callback: str = "menu_hotspot",
) -> InlineKeyboardMarkup:
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
    return get_user_selection_keyboard(users, "edit_user", "menu_hotspot")


def get_delete_user_keyboard(users: list[RouterOSRow]) -> InlineKeyboardMarkup:
    return get_user_selection_keyboard(users, "delete_user", "menu_hotspot")


def get_edit_field_keyboard(is_disabled: bool = False) -> InlineKeyboardMarkup:
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


def get_search_results_keyboard(
    paginator: Paginator[RouterOSRow],
    is_userman: bool = False,
) -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import (  # noqa: PLC0415 - avoid circular import
        hotspot_search_page,
        userman_search_page,
    )

    keyboard: _KeyboardLayout = []
    prefix = "um_sel_" if is_userman else "host_sel_"

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
    from bot.handlers.callback_constants import block_mac_cb  # noqa: PLC0415 - avoid circular import

    toggle_text = "🟢 تفعيل المستخدم" if is_disabled else "🔴 تعطيل المستخدم"
    keyboard = [
        [InlineKeyboardButton("⛔ طرد من الشبكة", callback_data="host_kick_execute")],
        [InlineKeyboardButton(toggle_text, callback_data="host_toggle_disabled")],
    ]
    if mac:
        keyboard.append([InlineKeyboardButton("🚫 حظر دائم", callback_data=block_mac_cb(mac))])
    keyboard.append([InlineKeyboardButton("📋 قائمة المحظورين", callback_data="blocked_list")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="search_back")])
    return InlineKeyboardMarkup(keyboard)


def get_blocked_macs_keyboard(blocked: list[RouterOSRow]) -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import unblock_mac_cb  # noqa: PLC0415 - avoid circular import

    keyboard: _KeyboardLayout = []
    for entry in blocked:
        mac: str = str(entry.get("address", ""))
        comment: str = str(entry.get("comment", ""))
        label: str = f"🔓 {mac}" + (f" ({comment[:15]})" if comment else "")
        keyboard.append([InlineKeyboardButton(label, callback_data=unblock_mac_cb(mac))])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="hotspot_search")])
    return InlineKeyboardMarkup(keyboard)


def get_usage_select_keyboard(users: list[RouterOSRow]) -> InlineKeyboardMarkup:
    keyboard: _KeyboardLayout = []
    for idx, user in enumerate(users):
        name = str(user.get("name", "—"))
        uptime = str(user.get("uptime", ""))
        label = f"{name} — {uptime}" if uptime else name
        keyboard.append([InlineKeyboardButton(label, callback_data=f"usage_sel_{idx}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="reports_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_batches_keyboard(
    batches: list[RouterOSRow],
    page: int = 0,
    total: int = 0,
    page_size: int = 10,
) -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import batch_page  # noqa: PLC0415 - avoid circular import

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

    keyboard.append([InlineKeyboardButton("🔍 بحث", callback_data="batches_search")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="reports_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_batch_detail_keyboard(
    batch_id: int, payment_status: str = "unpaid"
) -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import mark_payment_cb  # noqa: PLC0415 - avoid circular import

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
