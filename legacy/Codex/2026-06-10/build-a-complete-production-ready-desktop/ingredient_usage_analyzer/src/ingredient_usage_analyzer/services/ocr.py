from __future__ import annotations

import re
from pathlib import Path

from ingredient_usage_analyzer.models import IngredientLine, RecipeDraft


LINE_RE = re.compile(r"^\s*(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<unit>kg|g|ml|l|lt|tsp|tbsp|cup|unit|piece|pieces)?\s+(?P<name>.+?)\s*$", re.IGNORECASE)


class RecipeOcrService:
    """Extracts recipe text with EasyOCR when available and parses common recipe-sheet lines."""

    def extract_text(self, file_path: str | Path) -> str:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf_text(path)
        try:
            import easyocr

            reader = easyocr.Reader(["en"], gpu=False)
            result = reader.readtext(str(path), detail=0, paragraph=True)
            return "\n".join(result)
        except Exception:
            try:
                import pytesseract
                from PIL import Image

                return pytesseract.image_to_string(Image.open(path))
            except Exception as exc:
                raise RuntimeError("OCR failed. Install EasyOCR or Tesseract and ensure the source image is readable.") from exc

    def _extract_pdf_text(self, path: Path) -> str:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass
        raise RuntimeError("PDF has no embedded text. Convert scanned PDF pages to images and import them, or add OCR PDF rendering.")

    def parse_recipe(self, text: str) -> RecipeDraft:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if not lines:
            raise ValueError("No recipe text found.")
        name = lines[0]
        portion_size = 1.0
        portion_unit = "serving"
        ingredients: list[IngredientLine] = []
        is_batch = False
        yield_quantity = None
        yield_unit = None

        for line in lines[1:]:
            lower = line.lower()
            if lower.startswith("portion"):
                portion_size, portion_unit = self._parse_quantity_unit(line, default_unit="serving")
                continue
            if lower.startswith("yield"):
                is_batch = True
                yield_quantity, yield_unit = self._parse_quantity_unit(line, default_unit="unit")
                continue
            match = LINE_RE.match(line)
            if match:
                quantity = float(match.group("qty").replace(",", "."))
                unit = (match.group("unit") or "unit").lower()
                ingredients.append(IngredientLine(match.group("name").strip(), quantity, unit))
        return RecipeDraft(name=name, portion_size=portion_size, portion_unit=portion_unit, ingredients=tuple(ingredients), is_batch=is_batch, yield_quantity=yield_quantity, yield_unit=yield_unit)

    def _parse_quantity_unit(self, line: str, default_unit: str) -> tuple[float, str]:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)?", line)
        if not match:
            return 1.0, default_unit
        return float(match.group(1).replace(",", ".")), (match.group(2) or default_unit)
