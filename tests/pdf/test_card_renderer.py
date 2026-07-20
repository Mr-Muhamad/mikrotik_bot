"""Tests for pdf.card_renderer and pdf.card_generator — PDF rendering pipeline."""

import os
from unittest.mock import MagicMock, patch

from core.card_models import CardData
from pdf.card_generator import CardGenerator
from pdf.card_renderer import (
    CardRenderer,
    _arabic_text,
    _setup_arabic_support,
)


def _mock_canvas():
    c = MagicMock()
    c.setStrokeColorRGB = MagicMock()
    c.setFillColorRGB = MagicMock()
    c.setLineWidth = MagicMock()
    c.setFont = MagicMock()
    c.drawString = MagicMock()
    c.drawCentredString = MagicMock()
    c.line = MagicMock()
    c.roundRect = MagicMock()
    c.drawImage = MagicMock()
    c.saveState = MagicMock()
    c.restoreState = MagicMock()
    return c


def _sample_card() -> CardData:
    return CardData(
        username="user001",
        password="pass123",
        card_number=1,
        profile="default",
    )


# ─── _arabic_text tests ───────────────────────────────────────


class TestArabicText:
    def test_empty_returns_empty(self):
        assert _arabic_text("") == ""

    def test_none_returns_empty(self):
        assert _arabic_text(None) == ""

    def test_plain_text_passthrough_when_libs_missing(self):
        # If arabic_reshaper/bidi are not loaded, text passes through as-is
        result = _arabic_text("hello")
        assert result == "hello"


# ─── _setup_arabic_support tests ──────────────────────────────


class TestSetupArabicSupport:
    def test_returns_string_font_name(self):
        result = _setup_arabic_support()
        assert isinstance(result, str)
        assert len(result) > 0


# ─── CardRenderer init tests ─────────────────────────────────


class TestCardRendererInit:
    def test_default_construction(self):
        r = CardRenderer()
        assert r.font_name
        assert r.brand_name == ""
        assert r.hotspot_dns == ""

    def test_custom_construction(self):
        r = CardRenderer(font_name="Arial", brand_name="MyNet", hotspot_dns="login.mynet.com")
        assert r.font_name == "Arial"
        assert r.brand_name == "MyNet"
        assert r.hotspot_dns == "login.mynet.com"


# ─── CardRenderer._dynamic_font_size tests ───────────────────


class TestDynamicFontSize:
    def test_empty_text_returns_max(self):
        r = CardRenderer(font_name="Helvetica")
        assert r._dynamic_font_size("", max_width_mm=20) == 11

    def test_short_text_returns_max(self):
        r = CardRenderer(font_name="Helvetica")
        result = r._dynamic_font_size("hi", max_width_mm=100)
        # Should fit at the largest size
        assert result == 11

    def test_long_text_returns_min(self):
        r = CardRenderer(font_name="Helvetica")
        result = r._dynamic_font_size("x" * 1000, max_width_mm=1)
        # Should fall back to minimum (default min_font=6)
        assert result == 6

    def test_custom_min_font(self):
        r = CardRenderer(font_name="Helvetica")
        result = r._dynamic_font_size("x" * 1000, max_width_mm=1, min_font=7)
        assert result == 7


# ─── CardRenderer rendering tests ────────────────────────────


class TestCardRendererDraw:
    def test_render_card_calls_all_draws(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        card = _sample_card()
        r.render_card(c, 10, 10, 50, 80, card, index=0)
        # Should call all 6 draw methods
        c.saveState.assert_called_once()
        c.restoreState.assert_called_once()
        c.roundRect.assert_called_once()  # border
        c.drawCentredString.assert_called()  # header + title
        c.drawString.assert_called()  # credentials
        c.line.assert_called()  # separators

    def test_draw_border_sets_styling(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        r._draw_border(c, 10, 10, 50, 80)
        c.setStrokeColorRGB.assert_called_with(0, 0, 0)
        c.setLineWidth.assert_called_with(1.2)
        c.roundRect.assert_called_once()

    def test_draw_header_skips_when_no_brand(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica", brand_name="")
        r._draw_header(c, 10, 10, 50, 80)
        # No draw should be called
        c.setFont.assert_not_called()

    def test_draw_header_draws_when_brand_set(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica", brand_name="MyNet")
        r._draw_header(c, 10, 10, 50, 80)
        c.setFont.assert_called()
        c.drawCentredString.assert_called()
        c.line.assert_called()

    def test_draw_title_renders_arabic(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        r._draw_title(c, 10, 10, 50, 80)
        c.drawCentredString.assert_called()

    def test_draw_credentials_username_only(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        # Empty password → show_password returns False (it's a property)
        card = CardData(
            username="abc",
            password="",
            card_number=1,
            profile="default",
        )
        r._draw_credentials(c, 10, 10, 50, 80, card)
        # Should call drawString for label and value
        assert c.drawString.call_count >= 2

    def test_draw_credentials_with_password(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        # Different password → show_password returns True
        card = CardData(
            username="abc",
            password="xyz",
            card_number=1,
            profile="default",
        )
        r._draw_credentials(c, 10, 10, 50, 80, card)
        # Should draw both label-username and label-password
        assert c.drawString.call_count >= 4

    def test_show_password_property(self):
        # Same username/password → hide
        c1 = CardData(username="same", password="same", card_number=1, profile="p")
        assert c1.show_password is False
        # Different → show
        c2 = CardData(username="user", password="pass", card_number=1, profile="p")
        assert c2.show_password is True
        # Empty password → hide
        c3 = CardData(username="u", password="", card_number=1, profile="p")
        assert c3.show_password is False

    def test_draw_credentials_with_dict(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        # card can also be a dict
        r._draw_credentials(
            c,
            10,
            10,
            50,
            80,
            {
                "username": "u",
                "password": "p",
                "show_password": True,
            },
        )
        assert c.drawString.call_count >= 4

    def test_draw_qr_with_dns_renders(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica", hotspot_dns="login.mynet.com")
        card = _sample_card()
        with patch("tempfile.NamedTemporaryFile") as mock_tmp:
            tmp = MagicMock()
            tmp.name = "fake.png"
            mock_tmp.return_value = tmp
            with patch("os.unlink"):
                r._draw_qr(c, 10, 10, 50, 80, card)
        c.drawImage.assert_called_once()

    def test_draw_qr_no_username_skips(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica", hotspot_dns="login.com")
        card = CardData(username="", password="p", card_number=1, profile="default")
        r._draw_qr(c, 10, 10, 50, 80, card)
        c.drawImage.assert_not_called()

    def test_draw_footer_draws_line(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        r._draw_footer(c, 10, 10, 50)
        c.line.assert_called_once()


# ─── CardGenerator tests ─────────────────────────────────────


class TestCardGenerator:
    def test_generates_pdf_with_default_dir(self, tmp_path):
        gen = CardGenerator()
        cards = [_sample_card()]
        with patch("pdf.card_generator.pdf_renderer") as mock_renderer:
            result = gen.generate_pdf(cards, output_dir=str(tmp_path))
        # Should call renderer and return path
        mock_renderer.generate_cards_pdf.assert_called_once()
        # Result is in tmp_path
        assert str(tmp_path) in result or os.path.dirname(result) == str(tmp_path)

    def test_generates_pdf_with_custom_dir(self, tmp_path):
        gen = CardGenerator()
        cards = [_sample_card()]
        custom_dir = str(tmp_path / "custom")
        with patch("pdf.card_generator.pdf_renderer") as mock_renderer:
            result = gen.generate_pdf(cards, output_dir=custom_dir)
        mock_renderer.generate_cards_pdf.assert_called_once()
        # Custom dir was created
        assert os.path.isdir(custom_dir)
        assert custom_dir in result

    def test_pdf_filename_uses_timestamp(self, tmp_path):
        gen = CardGenerator()
        with patch("pdf.card_generator.pdf_renderer"):
            with patch("time.time", return_value=1234567890):
                result = gen.generate_pdf([], output_dir=str(tmp_path))
        assert "1234567890" in result
        assert result.endswith(".pdf")

    def test_passes_cards_to_renderer(self, tmp_path):
        gen = CardGenerator()
        cards = [_sample_card(), _sample_card()]
        with patch("pdf.card_generator.pdf_renderer") as mock_renderer:
            gen.generate_pdf(cards, output_dir=str(tmp_path))
        call_args = mock_renderer.generate_cards_pdf.call_args
        # First positional should be the cards list
        assert call_args.args[0] == cards or call_args.kwargs.get("cards") == cards


class TestDrawFooterCallerId:
    def test_no_mac_drawn_even_when_caller_id_set(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        r._draw_footer(c, 10, 10, 50, card={"caller_id": "AA:BB:CC:DD:EE:FF"})
        mac_calls = [a for a in c.drawCentredString.call_args_list if "MAC" in str(a)]
        assert not mac_calls

    def test_no_mac_when_caller_id_empty(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        r._draw_footer(c, 10, 10, 50, card={"caller_id": ""})
        mac_calls = [a for a in c.drawCentredString.call_args_list if "MAC" in str(a)]
        assert not mac_calls

    def test_no_mac_when_card_none(self):
        c = _mock_canvas()
        r = CardRenderer(font_name="Helvetica")
        r._draw_footer(c, 10, 10, 50)
        mac_calls = [a for a in c.drawCentredString.call_args_list if "MAC" in str(a)]
        assert not mac_calls
