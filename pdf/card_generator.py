import os
import tempfile
import time
from core.mikrotik_client import RouterOSRow

from pdf.pdf_renderer import pdf_renderer


class CardGenerator:
    def generate_pdf(self, cards: list[RouterOSRow], output_dir: str | None = None) -> str:
        if output_dir is None:
            output_dir = tempfile.gettempdir()

        os.makedirs(output_dir, exist_ok=True)

        filename = f"cards_{int(time.time())}.pdf"
        output_path = os.path.join(output_dir, filename)

        pdf_renderer.generate_cards_pdf(cards, output_path)
        return output_path


card_generator = CardGenerator()
