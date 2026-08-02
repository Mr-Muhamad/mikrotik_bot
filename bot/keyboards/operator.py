from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.mikrotik_client import RouterOSRow

_KeyboardLayout = list[list[InlineKeyboardButton]]


def get_operator_router_assignment_keyboard(
    operator_id: int,
    all_routers: list[RouterOSRow],
    assigned_router_ids: list[int],
) -> InlineKeyboardMarkup:
    from bot.handlers.callback_constants import op_assign_cb, op_revoke_cb  # noqa: PLC0415 - avoid circular import

    keyboard: _KeyboardLayout = []
    for r in all_routers:
        raw_rid = r.get("id")
        if raw_rid is None:
            continue
        rid_int: int = int(raw_rid)
        name: str = str(r.get("name_alias") or r.get("identity") or str(rid_int))
        ip_raw = r.get("ip_address")
        if not ip_raw:
            raise ValueError("IP address is required for router listing")
        ip: str = str(ip_raw)
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
