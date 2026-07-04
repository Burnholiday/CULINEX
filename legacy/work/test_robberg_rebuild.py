import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("outputs/recipe-vault-paddle-ocr").resolve()))
import server

def lines(name):
    return json.loads(Path(f"work/robberg-crops/{name}.json").read_text(encoding="utf-8"))["text"].splitlines()

codes = server.robberg_codes(lines("code"))
desc = server.robberg_description_names(lines("desc"))
qty = server.robberg_quantities(lines("qty_wide"))
prices = server.invoice_column_numbers(lines("unit_price"))
vats = server.invoice_column_numbers(lines("vat"))
print(f"codes={len(codes)} desc={len(desc)} qty={len(qty)} prices={len(prices)} vats={len(vats)}")
rows = []
for index in range(min(len(codes), len(desc), len(qty), len(prices))):
    row = server.invoice_row_from_name_qty_price(f"{codes[index]} {desc[index]}", qty[index], prices[index], vats[index] if index < len(vats) else None)
    if row:
        rows.append(row)
        print(f"{row['raw']}, {row['qty']}, {row['unit']}, {row['unitPrice']}, VAT {row.get('vatAmount')}, excl {row['lineTotal']}")
print(f"rows={len(rows)} excl={sum(row['lineTotal'] for row in rows):.2f} vat={sum(float(row.get('vatAmount') or 0) for row in rows):.2f} incl={sum(row['lineTotal'] + float(row.get('vatAmount') or 0) for row in rows):.2f}")
