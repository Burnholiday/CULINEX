from __future__ import annotations

from pathlib import Path

import pandas as pd

from ingredient_usage_analyzer.models import SalesLine


class SalesImporter:
    MENU_COLUMNS = ("item", "menu item", "product", "description", "name")
    QTY_COLUMNS = ("qty", "qty sold", "quantity", "quantity sold", "sold")
    DATE_COLUMNS = ("date", "sale date", "business date")

    def import_file(self, file_path: str | Path) -> list[SalesLine]:
        path = Path(file_path)
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path)
        elif suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(path)
        elif suffix == ".pdf":
            df = self._read_pdf_text_table(path)
        else:
            raise ValueError(f"Unsupported sales report type: {suffix}")
        return self._frame_to_sales(df, path.name)

    def _read_pdf_text_table(self, path: Path) -> pd.DataFrame:
        try:
            from pypdf import PdfReader

            text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
        except Exception as exc:
            raise RuntimeError("Unable to extract text from PDF sales report.") from exc
        rows = []
        for line in text.splitlines():
            parts = line.rsplit(maxsplit=1)
            if len(parts) == 2:
                try:
                    rows.append({"Item": parts[0], "Qty Sold": float(parts[1])})
                except ValueError:
                    continue
        if not rows:
            raise ValueError("No item/quantity rows found in PDF.")
        return pd.DataFrame(rows)

    def _frame_to_sales(self, df: pd.DataFrame, source_file: str) -> list[SalesLine]:
        normalized = {str(col).strip().lower(): col for col in df.columns}
        item_col = self._find_column(normalized, self.MENU_COLUMNS)
        qty_col = self._find_column(normalized, self.QTY_COLUMNS)
        date_col = self._find_column(normalized, self.DATE_COLUMNS, required=False)
        lines: list[SalesLine] = []
        for _, row in df.iterrows():
            item = str(row[item_col]).strip()
            if not item or item.lower() == "nan":
                continue
            quantity = pd.to_numeric(row[qty_col], errors="coerce")
            if pd.isna(quantity):
                continue
            sale_date = None
            if date_col and not pd.isna(row[date_col]):
                sale_date = str(row[date_col])[:10]
            lines.append(SalesLine(item, float(quantity), sale_date, source_file))
        return lines

    def _find_column(self, normalized: dict[str, str], choices: tuple[str, ...], required: bool = True) -> str | None:
        for choice in choices:
            if choice in normalized:
                return normalized[choice]
        if required:
            raise ValueError(f"Could not find any of these columns: {', '.join(choices)}")
        return None
