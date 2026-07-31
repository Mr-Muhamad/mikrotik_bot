import io
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import asdict
from typing import Protocol, cast
from urllib.parse import quote

import qrcode
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from core.card_models import CardData
from core.mikrotik_client import RouterOSRow

logger = logging.getLogger(__name__)

CARD_BORDER_LINE_WIDTH = 1.2
CARD_SEPARATOR_LINE_WIDTH = 0.2

FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts")

class _ArabicReshaper(Protocol):
    def reshape(self, text: str) -> str: ...


_arabic_font: str | None = None
_arabic_reshaper: _ArabicReshaper | None = None
_bidi_display: Callable[[str], str | bytes] | None = None
_INIT_LOCK = threading.Lock()


def _setup_arabic_support() -> str:
    """Initialize Arabic text reshaping and bidirectional support."""
    global _arabic_font, _arabic_reshaper, _bidi_display

    with _INIT_LOCK:
        if _arabic_font is not None:
            return _arabic_font

        font_files = [
            ("HacenBeirut", "Hacen Beirut Heading.ttf"),
            ("NotoSansArabic", "NotoSansArabic-Regular.ttf"),
            ("Arial", "arial.ttf"),
        ]

        for font_name, font_file in font_files:
            font_path = os.path.join(FONT_PATH, font_file)
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
                    _arabic_font = font_name
                    logger.info("Loaded Arabic font: %s", font_name)
                    break
                except (OSError, ValueError) as e:
                    logger.warning("Failed to load font %s: %s", font_file, e)

        if _arabic_font is None:
            _arabic_font = "Helvetica"
            logger.warning("No Arabic font found, using Helvetica")

        try:
            from arabic_reshaper import ArabicReshaper
            from bidi.algorithm import get_display

            _arabic_reshaper = ArabicReshaper(configuration={"delete_harakat": False})
            _bidi_display = get_display
        except ImportError:
            logger.warning("arabic_reshaper or python-bidi not installed")

    return _arabic_font


# Expose a public alias for external modules — avoids importing a private name.
setup_arabic_support = _setup_arabic_support


def _arabic_text(text: str | None) -> str:
    """Reshape and reorder Arabic text for correct PDF rendering."""
    if not text:
        return ""
    if _arabic_reshaper is None or _bidi_display is None:
        return str(text)
    try:
        reshaped = _arabic_reshaper.reshape(str(text))
        result = _bidi_display(reshaped)
        return cast(str, result)
    except (ValueError, UnicodeEncodeError, UnicodeDecodeError) as e:
        logger.debug("Arabic text reshaping failed, using raw text: %s", e)
        return str(text)


def _normalize_card(card: RouterOSRow | CardData) -> RouterOSRow:
    """Convert a card (CardData or dict) into a plain dict for rendering."""
    if isinstance(card, dict):
        return card
    d: RouterOSRow = asdict(card)
    d["show_password"] = card.show_password
    return d


class CardRenderer:
    """Renders individual hotspot/userman cards onto a PDF canvas."""

    def __init__(
        self,
        font_name: str | None = None,
        brand_name: str = "",
        hotspot_dns: str = "",
        footer_text: str = "",
        show_qr: int = 1,
        label_spacing_single: float = 1.0,
        label_spacing_dual: float = 1.0,
        value_max_font_single: int = 12,
        value_max_font_dual: int = 11,
    ):
        self.font_name = font_name or _setup_arabic_support()
        self.brand_name = brand_name
        self.hotspot_dns = hotspot_dns
        self.footer_text = footer_text or ""
        self.show_qr = show_qr
        self.label_spacing_single = label_spacing_single
        self.label_spacing_dual = label_spacing_dual
        self.value_max_font_single = value_max_font_single
        self.value_max_font_dual = value_max_font_dual

    def render_card(
        self,
        canvas_obj: Canvas,
        x: float,
        y: float,
        width: float,
        height: float,
        card: RouterOSRow | CardData,
        index: int,
    ) -> None:
        """Draw a single card at the given coordinates."""
        card_dict: RouterOSRow = _normalize_card(card)
        canvas_obj.saveState()

        self._draw_border(canvas_obj, x, y, width, height)
        self._draw_header(canvas_obj, x, y, width, height)
        self._draw_title(canvas_obj, x, y, width, height)
        self._draw_credentials(canvas_obj, x, y, width, height, card_dict)
        if self.hotspot_dns and self.show_qr:
            self._draw_qr(canvas_obj, x, y, width, height, card_dict)
        self._draw_footer(canvas_obj, x, y, width, card_dict)

        canvas_obj.restoreState()

    def _draw_border(self, c: Canvas, x: float, y: float, width: float, height: float) -> None:
        """Draw rounded rectangle border."""
        c.setStrokeColorRGB(0, 0, 0)
        c.setLineWidth(CARD_BORDER_LINE_WIDTH)
        c.roundRect(x, y, width, height, 2)

    def _draw_header(self, c: Canvas, x: float, y: float, width: float, height: float) -> None:
        """Draw brand name and separator line."""
        if not self.brand_name:
            return
        header_y = y + height - 4.5 * mm
        c.setFont(self.font_name, 14)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(x + width / 2, header_y, _arabic_text(self.brand_name))

        line_y = y + height - 6 * mm
        c.setLineWidth(CARD_BORDER_LINE_WIDTH)
        c.line(x + 1.5 * mm, line_y, x + width - 1.5 * mm, line_y)

    def _draw_title(self, c: Canvas, x: float, y: float, width: float, height: float) -> None:
        """Draw card data title."""
        title_y = y + height - 9.5 * mm
        c.setFont(self.font_name, 7)
        c.setFillColorRGB(0, 0, 0)
        c.drawCentredString(x + width / 2, title_y, _arabic_text("- بـيـانـات الـكـارت -"))

        sep_y = y + height - 10.5 * mm
        c.setLineWidth(CARD_SEPARATOR_LINE_WIDTH)
        c.line(x + 4 * mm, sep_y, x + width - 4 * mm, sep_y)

    def _dynamic_font_size(
        self, text: str, max_width_mm: float, max_font: int = 11, min_font: int = 6
    ) -> int:
        """Pick the largest integer font size so *text* fits *max_width_mm*."""
        if not text:
            return max_font
        pt_per_mm = 72.0 / 25.4
        max_width_pt = max_width_mm * pt_per_mm
        for size in range(max_font, min_font - 1, -1):
            w = pdfmetrics.stringWidth(text, "Helvetica-Bold", size)
            if w <= max_width_pt:
                return size
        return min_font

    def _draw_credentials(
        self,
        c: Canvas,
        x: float,
        y: float,
        width: float,
        height: float,
        card: RouterOSRow | CardData,
    ) -> None:
        """Draw username and password fields with dynamic font sizing."""
        card = _normalize_card(card)
        username = str(card.get("username", ""))
        password_raw = card.get("password")
        password = str(password_raw) if password_raw else ""
        show_password = card.get("show_password", False)

        if show_password and not password:
            raise ValueError("Password is required for card generation")

        data_top = y + height - 10.5 * mm
        footer_line_y = y + 5 * mm
        v_middle = (data_top + footer_line_y) / 2

        if not show_password or not password:
            # حالة رقم الشحن فقط — استخدام label_spacing_single
            spacing = self.label_spacing_single
            label_x = x + 1 * mm * spacing
            value_x = x + 11 * mm * spacing
            max_text_width = (x + width) - value_x - 1.5 * mm

            fs = self._dynamic_font_size(
                username, max_text_width, max_font=self.value_max_font_single, min_font=7
            )
            c.setFont(self.font_name, 6.5)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(label_x, v_middle - 0.9 * mm, _arabic_text(":رقم الشحن"))
            c.setFont("Helvetica-Bold", fs)
            c.drawString(value_x, v_middle - 1.6 * mm, username)
        else:
            # حالة يوزر + باسورد — استخدام label_spacing_dual
            spacing = self.label_spacing_dual
            label_x = x + 1 * mm * spacing
            value_x = x + 11 * mm * spacing
            max_text_width = (x + width) - value_x - 1.5 * mm

            longer = username if len(username) >= len(password) else password
            fs = self._dynamic_font_size(
                longer, max_text_width, max_font=self.value_max_font_dual, min_font=7
            )

            c.setFont(self.font_name, 7)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(label_x, v_middle + 2 * mm, _arabic_text(":الــيـوزر"))
            c.setFont("Helvetica-Bold", fs)
            c.drawString(value_x, v_middle + 1.8 * mm, username)

            c.setFont(self.font_name, 7)
            c.drawString(label_x, v_middle - 3.5 * mm, _arabic_text(":الباسورد"))
            c.setFont("Helvetica-Bold", fs)
            c.drawString(value_x, v_middle - 3.8 * mm, password)

    def _draw_qr(
        self,
        c: Canvas,
        x: float,
        y: float,
        width: float,
        height: float,
        card: RouterOSRow | CardData,
    ) -> None:
        """Draw QR code for hotspot login."""
        card = _normalize_card(card)
        username = str(card.get("username", ""))

        if not username:
            return

        login_url = f"http://{self.hotspot_dns}/login?username={quote(username, safe='')}"
        qr = qrcode.make(login_url)

        qr_size = height * 0.45
        qr_x = x + width - qr_size - 1.5 * mm
        qr_y = y + 5 * mm

        buf = io.BytesIO()
        qr.save(buf, "PNG")
        buf.seek(0)
        c.drawImage(ImageReader(buf), qr_x, qr_y, width=qr_size, height=qr_size)

    def _draw_footer(
        self,
        c: Canvas,
        x: float,
        y: float,
        width: float,
        card: RouterOSRow | CardData | None = None,
    ) -> None:
        """Draw footer line and footer text."""
        footer_line_y = y + 5 * mm
        c.setLineWidth(CARD_BORDER_LINE_WIDTH)
        c.setFillColorRGB(0, 0, 0)
        c.line(x + 1.5 * mm, footer_line_y, x + width - 1.5 * mm, footer_line_y)

        if self.footer_text:
            c.setFont(self.font_name, 7)
            c.drawCentredString(
                x + width / 2,
                y + 2 * mm,
                _arabic_text(self.footer_text),
            )
