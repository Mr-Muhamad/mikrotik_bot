from core.mikrotik_client import RouterOSRow
from database.models import get_pdf_settings, update_pdf_settings

_NUMERIC_VALIDATORS = {
    "margin_top": (0, 100),
    "margin_bottom": (0, 100),
    "margin_left": (0, 100),
    "margin_right": (0, 100),
    "border_width": (0, 10),
    "spacing_x": (0, 50),
    "spacing_y": (0, 50),
    "cards_per_row": (1, 10),
    "cards_per_page": (1, 200),
    "value_max_font_single": (6, 24),
    "value_max_font_dual": (6, 24),
    "label_spacing_single": (0.1, 5.0),
    "label_spacing_dual": (0.1, 5.0),
}


class PDFSettings:
    """Manages PDF card generation settings."""

    def get_settings(self):
        return get_pdf_settings()

    def update(self, **kwargs: str | int | float | bool) -> RouterOSRow:
        for key, value in kwargs.items():
            if key in _NUMERIC_VALIDATORS:
                lo, hi = _NUMERIC_VALIDATORS[key]
                if not (lo <= float(value) <= hi):
                    raise ValueError(f"{key} يجب أن يكون بين {lo} و {hi}")
        update_pdf_settings(**kwargs)
        return self.get_settings()

    def format_settings(self):
        settings = self.get_settings()
        lines = [
            "⚙️ إعدادات PDF الحالية:",
            f"📏 الهوامش: أعلى={settings.get('margin_top', 10)} | أسفل={settings.get('margin_bottom', 10)} | يسار={settings.get('margin_left', 10)} | يمين={settings.get('margin_right', 10)}",  # noqa: E501
            f"📏 سمك الحدود: {settings.get('border_width', 1)} مم",
            f"↔️ الفواصل الأفقية: {settings.get('spacing_x', 5)} مم",
            f"↕️ الفواصل العمودية: {settings.get('spacing_y', 5)} مم",
            f"📄 الكروت في الصف: {settings.get('cards_per_row', 4)}",
            f"📄 الكروت في الصفحة: {settings.get('cards_per_page', 40)}",
            f"🏷️ اسم الشبكة: {settings.get('brand_name', '(فارغ)') or '(فارغ)'}",
            f"🌐 DNS الـ Hotspot: {settings.get('hotspot_dns', '(فارغ)') or '(فارغ)'}",
            f"📱 QR Code: {'✅ مفعّل' if settings.get('show_qr', 1) else '❌ معطّل'}",
            f"📝 التذييل: {settings.get('footer_text', '(فارغ)') or '(فارغ)'}",
            f"📐 تباعد رقم الشحن: {settings.get('label_spacing_single', 1.0)}",
            f"📐 تباعد اليوزر/الباسورد: {settings.get('label_spacing_dual', 1.0)}",
            f"🔤 حجم الخط (رقم شحن): {settings.get('value_max_font_single', 12)}",
            f"🔤 حجم الخط (يوزر/باسورد): {settings.get('value_max_font_dual', 11)}",
        ]
        return "\n".join(lines)


pdf_settings = PDFSettings()
