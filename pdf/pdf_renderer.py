import logging

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from core.mikrotik_client import RouterOSRow
from database.models import get_pdf_settings
from pdf.card_renderer import CardRenderer, setup_arabic_support

logger = logging.getLogger(__name__)


class PDFRenderer:
    """Generates PDF files with card layouts for printing."""

    def __init__(self):
        self.font_name = setup_arabic_support()

    def generate_cards_pdf(self, cards: list[RouterOSRow], output_path: str):
        """Generate a PDF with all cards arranged in a grid layout."""
        settings = get_pdf_settings()

        cols = max(1, settings.get("cards_per_row", 4))
        requested_per_page = max(cols, settings.get("cards_per_page", 40))
        rows = max(1, requested_per_page // cols)
        cards_per_page = rows * cols

        margin_top = settings.get("margin_top", 10) * mm
        margin_bottom = settings.get("margin_bottom", 10) * mm
        margin_left = settings.get("margin_left", 10) * mm
        margin_right = settings.get("margin_right", 10) * mm
        spacing_x = settings.get("spacing_x", 5) * mm
        spacing_y = settings.get("spacing_y", 5) * mm

        page_width, page_height = A4
        usable_width = page_width - margin_left - margin_right
        usable_height = page_height - margin_top - margin_bottom

        card_width = (usable_width - (cols - 1) * spacing_x) / cols
        card_height = (usable_height - (rows - 1) * spacing_y) / rows

        if card_width <= 0 or card_height <= 0:
            raise ValueError(
                f"أبعاد الكارت غير صالحة: {card_width / mm:.1f}x{card_height / mm:.1f} مم. "
                f"قلّل الهوامش أو الفواصل."
            )

        brand_name = settings.get("brand_name", "")
        hotspot_dns = settings.get("hotspot_dns", "")
        footer_text = settings.get("footer_text", "")
        show_qr = settings.get("show_qr", 1)
        label_spacing_single = settings.get("label_spacing_single", 1.0)
        label_spacing_dual = settings.get("label_spacing_dual", 1.0)
        value_max_font_single = settings.get("value_max_font_single", 12)
        value_max_font_dual = settings.get("value_max_font_dual", 11)

        card_renderer = CardRenderer(
            font_name=self.font_name,
            brand_name=brand_name,
            hotspot_dns=hotspot_dns,
            footer_text=footer_text,
            show_qr=show_qr,
            label_spacing_single=label_spacing_single,
            label_spacing_dual=label_spacing_dual,
            value_max_font_single=value_max_font_single,
            value_max_font_dual=value_max_font_dual,
        )

        c = canvas.Canvas(output_path, pagesize=A4)

        for i, card in enumerate(cards):
            card_on_page = i % cards_per_page

            if card_on_page == 0 and i > 0:
                c.showPage()

            col = card_on_page % cols
            row = rows - 1 - (card_on_page // cols)

            x = margin_left + col * (card_width + spacing_x)
            y = margin_bottom + row * (card_height + spacing_y)

            card_renderer.render_card(c, x, y, card_width, card_height, card, i + 1)

        c.save()
        return output_path


pdf_renderer = PDFRenderer()
