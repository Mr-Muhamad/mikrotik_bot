from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.mikrotik_client import RouterOSRow
from core.network_probe import DiscoveredRouter
from database.repositories.routers import get_router_display_name

_KeyboardRow = list[InlineKeyboardButton]
_KeyboardLayout = list[_KeyboardRow]


def get_saved_routers_keyboard(routers: list[RouterOSRow]) -> InlineKeyboardMarkup:
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
    keyboard = [
        [
            InlineKeyboardButton(
                "✅ تأكيد", callback_data=f"confirm_delete_router_yes_{router_id}"
            ),
            InlineKeyboardButton("❌ إلغاء", callback_data=f"confirm_delete_router_no_{router_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_reboot_keyboard(router_key: str) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("✅ نعم، أعد التشغيل", callback_data=f"reboot_yes_{router_key}"),
            InlineKeyboardButton("❌ إلغاء", callback_data="reboot_no"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_discovered_routers_keyboard(routers: list[DiscoveredRouter]) -> InlineKeyboardMarkup:
    keyboard: _KeyboardLayout = []
    for router in routers:
        name: str = router.display_name()
        keyboard.append(
            [InlineKeyboardButton(name, callback_data=f"disc_router_{router.ip_address}")]
        )
    keyboard.append([InlineKeyboardButton("🔄 إعادة بحث", callback_data="discover_routers")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)


def get_backup_keyboard() -> InlineKeyboardMarkup:
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


def get_backup_restore_keyboard(backups: list[RouterOSRow]) -> InlineKeyboardMarkup:
    keyboard: _KeyboardLayout = []
    for idx, b in enumerate(backups[:10]):
        name: str = str(b.get("name", ""))
        btype: str = "📦" if str(b.get("type")) == "system" else "📄"
        keyboard.append([InlineKeyboardButton(f"{btype} {name}", callback_data=f"restore:{idx}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")])
    return InlineKeyboardMarkup(keyboard)


def get_restore_confirm_keyboard() -> InlineKeyboardMarkup:
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


def get_userman_restore_keyboard(tar_files: list[RouterOSRow]) -> InlineKeyboardMarkup:
    keyboard: _KeyboardLayout = []
    for idx, f in enumerate(tar_files):
        name: str = str(f.get("filename", ""))
        size_kb: int = int(f.get("size") or 0) // 1024
        label: str = f"{name} ({size_kb}KB)"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"userman_restore_tar:{idx}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="menu_backup")])
    return InlineKeyboardMarkup(keyboard)


def get_userman_restore_confirm_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("⚠️ نعم، استعادة", callback_data="userman_restore_exec")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="menu_backup")],
    ]
    return InlineKeyboardMarkup(keyboard)
