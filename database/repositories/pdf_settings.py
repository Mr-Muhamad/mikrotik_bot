"""PDF settings repository.

Holds the tunable PDF label/card layout settings. Isolated from the former
god-object ``database.models``.
"""
from __future__ import annotations

PDF_ALLOWED_COLUMNS = {
    "margin_top", "margin_bottom", "margin_left", "margin_right",
    "border_width", "card_width", "card_height",
    "spacing_x", "spacing_y", "cards_per_row",
    "footer_text", "header_text",
    "brand_name", "hotspot_dns", "show_qr", "cards_per_page",
    "label_spacing_single", "label_spacing_dual",
    "value_max_font_single", "value_max_font_dual",
}


def get_pdf_settings():
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pdf_settings LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else {}


def update_pdf_settings(**kwargs):
    from database.models import get_db

    with get_db() as conn:
        cursor = conn.cursor()
        unknown = set(kwargs.keys()) - PDF_ALLOWED_COLUMNS
        if unknown:
            raise ValueError(f"Unknown PDF settings columns: {unknown}")
        fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
        values = list(kwargs.values())
        cursor.execute(f"UPDATE pdf_settings SET {fields} WHERE id = 1", values)
