"""Tests for pdf.pdf_renderer."""

from unittest.mock import MagicMock, patch

from pdf.pdf_renderer import PDFRenderer, pdf_renderer


class TestPDFRenderer:
    def setup_method(self):
        self.renderer = PDFRenderer()
        self.cards = [
            {"username": "111", "password": "222"},
            {"username": "333", "password": "444"},
        ]

    def test_init_sets_font(self):
        with patch("pdf.pdf_renderer._setup_arabic_support", return_value="ArabicFont"):
            r = PDFRenderer()
        assert r.font_name == "ArabicFont"

    def test_generate_cards_pdf_creates_file(self, tmp_path):
        output_path = str(tmp_path / "cards.pdf")
        settings = {
            "cards_per_row": 2,
            "cards_per_page": 4,
            "margin_top": 10,
            "margin_bottom": 10,
            "margin_left": 10,
            "margin_right": 10,
            "spacing_x": 5,
            "spacing_y": 5,
            "brand_name": "Brand",
            "hotspot_dns": "login.local",
            "footer_text": "",
            "show_qr": 0,
        }

        with (
            patch("pdf.pdf_renderer.get_pdf_settings", return_value=settings),
            patch("pdf.pdf_renderer.CardRenderer") as mock_cr,
        ):
            mock_cr.return_value.render_card = MagicMock()
            result = self.renderer.generate_cards_pdf(self.cards, output_path)
        assert result == output_path
        assert mock_cr.return_value.render_card.call_count == len(self.cards)

    def test_generate_cards_pdf_with_footer(self, tmp_path):
        output_path = str(tmp_path / "cards.pdf")
        settings = {
            "cards_per_row": 2,
            "cards_per_page": 4,
            "margin_top": 10,
            "margin_bottom": 10,
            "margin_left": 10,
            "margin_right": 10,
            "spacing_x": 5,
            "spacing_y": 5,
            "brand_name": "",
            "hotspot_dns": "",
            "footer_text": "My Footer",
            "show_qr": 0,
        }

        with (
            patch("pdf.pdf_renderer.get_pdf_settings", return_value=settings),
            patch("pdf.pdf_renderer.CardRenderer"),
        ):
            result = self.renderer.generate_cards_pdf(self.cards, output_path)
        assert result == output_path

    def test_generate_cards_pdf_multi_page(self, tmp_path):
        output_path = str(tmp_path / "cards.pdf")
        cards = [{"username": f"u{i}", "password": f"p{i}"} for i in range(10)]
        settings = {
            "cards_per_row": 2,
            "cards_per_page": 4,
            "margin_top": 10,
            "margin_bottom": 10,
            "margin_left": 10,
            "margin_right": 10,
            "spacing_x": 5,
            "spacing_y": 5,
            "brand_name": "",
            "hotspot_dns": "",
            "footer_text": "Footer",
            "show_qr": 0,
        }

        with (
            patch("pdf.pdf_renderer.get_pdf_settings", return_value=settings),
            patch("pdf.pdf_renderer.CardRenderer"),
        ):
            result = self.renderer.generate_cards_pdf(cards, output_path)
        assert result == output_path

    def test_generate_cards_pdf_uses_defaults_for_missing_settings(self, tmp_path):
        output_path = str(tmp_path / "cards.pdf")
        settings = {}  # empty settings - should use defaults

        with (
            patch("pdf.pdf_renderer.get_pdf_settings", return_value=settings),
            patch("pdf.pdf_renderer.CardRenderer"),
        ):
            result = self.renderer.generate_cards_pdf(self.cards, output_path)
        assert result == output_path

    def test_singleton_instance(self):
        assert pdf_renderer is not None
        assert isinstance(pdf_renderer, PDFRenderer)
