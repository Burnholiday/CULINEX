import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("outputs/recipe-vault-paddle-ocr").resolve()))
import server

def lines(name):
    return json.loads(Path(f"work/vat-test/{name}.json").read_text(encoding="utf-8"))["text"].splitlines()

names = server.grocery_express_description_names(lines("code_desc"))
qtys = server.invoice_column_numbers(lines("qty"))
prices = server.invoice_column_numbers(lines("unit_price"))
vats = server.invoice_column_numbers(lines("vat"))
rows = []
for index in range(min(len(names), len(qtys), len(prices))):
    vat = vats[index] if index < len(vats) else None
    row = server.invoice_row_from_name_qty_price(names[index], qtys[index], prices[index], vat)
    if row:
        rows.append(row)
print(f"names={len(names)} qtys={len(qtys)} prices={len(prices)} vats={len(vats)} rows={len(rows)}")
print(f"excl={sum(row['lineTotal'] for row in rows):.2f} vat={sum(float(row.get('vatAmount') or 0) for row in rows):.2f} incl={sum(row['lineTotal'] + float(row.get('vatAmount') or 0) for row in rows):.2f}")
