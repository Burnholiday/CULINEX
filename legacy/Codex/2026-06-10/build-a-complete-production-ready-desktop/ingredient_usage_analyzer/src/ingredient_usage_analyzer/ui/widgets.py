from __future__ import annotations

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem


def populate_table(table: QTableWidget, rows: list[dict]) -> None:
    table.clear()
    if not rows:
        table.setRowCount(0)
        table.setColumnCount(0)
        return
    headers = list(rows[0].keys())
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column_index, header in enumerate(headers):
            item = QTableWidgetItem(str(row.get(header, "")))
            table.setItem(row_index, column_index, item)
    table.resizeColumnsToContents()
