from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


class ReportExporter:
    def export_csv(self, rows: Iterable[dict], path: str | Path) -> Path:
        out = Path(path)
        pd.DataFrame(list(rows)).to_csv(out, index=False)
        return out

    def export_excel(self, rows: Iterable[dict], path: str | Path, sheet_name: str = "Report") -> Path:
        out = Path(path)
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            pd.DataFrame(list(rows)).to_excel(writer, index=False, sheet_name=sheet_name[:31])
        return out

    def export_pdf(self, title: str, rows: Iterable[dict], path: str | Path) -> Path:
        out = Path(path)
        data = list(rows)
        doc = SimpleDocTemplate(str(out), pagesize=A4)
        styles = getSampleStyleSheet()
        story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
        if data:
            headers = list(data[0].keys())
            table_data = [headers] + [[str(row.get(header, "")) for header in headers] for row in data]
            table = Table(table_data, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243746")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8D0D6")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7F8")]),
                    ]
                )
            )
            story.append(table)
        else:
            story.append(Paragraph("No data available.", styles["BodyText"]))
        doc.build(story)
        return out
