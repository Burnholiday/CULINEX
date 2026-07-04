import json
import re

import pdfplumber


PDF_PATH = r"C:\Users\Burn Holiday\Downloads\BB Summer Menu Costings 2025 - SUSHI_RECIPES_2026.pdf"


def cell(row, index):
    return (row[index] or "").replace("\n", " ").strip() if index < len(row) else ""


def number(value):
    try:
        return float(value.replace("R", "").replace(",", "").strip())
    except (AttributeError, ValueError):
        return None


recipes = []
with pdfplumber.open(PDF_PATH) as pdf:
    for page_no, page in enumerate(pdf.pages, 1):
        tables = page.extract_tables() or []
        if not tables:
            continue
        table = max(tables, key=len)
        starts = [
            index
            for index in range(len(table[0]))
            if any(cell(row, index) == "COSTING SHEET" for row in table)
            and index + 4 < len(table[0])
        ]
        print("page", page_no, "columns", len(table[0]), "starts", starts)

        for start in starts:
            row_index = 0
            while row_index < len(table):
                if cell(table[row_index], start) != "COSTING SHEET":
                    row_index += 1
                    continue

                title = ""
                for next_row in range(row_index + 1, min(len(table), row_index + 7)):
                    candidate = cell(table[next_row], start)
                    if candidate and candidate not in {"COSTING SHEET", "Ingredients"}:
                        title = candidate
                        break

                ingredient_start = None
                for next_row in range(row_index + 1, min(len(table), row_index + 12)):
                    if cell(table[next_row], start) == "Ingredients":
                        ingredient_start = next_row + 1
                        break

                if not title or ingredient_start is None:
                    row_index += 1
                    continue

                ingredients = []
                menu_price = 0
                next_index = ingredient_start
                while next_index < len(table):
                    name = cell(table[next_index], start)
                    if name == "COSTING SHEET":
                        break
                    if name.startswith("WASTAGE"):
                        break
                    if name == "MENU PRICE":
                        menu_price = number(cell(table[next_index], start + 3)) or number(
                            cell(table[next_index], start + 4)
                        ) or 0
                        break

                    qty = number(cell(table[next_index], start + 1))
                    if name and qty is not None:
                        ingredients.append(
                            {
                                "name": name,
                                "qty": qty,
                                "bulk": cell(table[next_index], start + 2),
                                "price": cell(table[next_index], start + 3),
                                "cost": cell(table[next_index], start + 4),
                            }
                        )
                    next_index += 1

                recipes.append(
                    {
                        "page": page_no,
                        "title": title,
                        "ingredients": ingredients,
                        "menu_price": menu_price,
                    }
                )
                row_index = next_index if next_index > row_index else row_index + 1

print("recipes", len(recipes))
for recipe in recipes[:30]:
    print(
        recipe["page"],
        recipe["title"],
        "count",
        len(recipe["ingredients"]),
        "price",
        recipe["menu_price"],
        "first",
        recipe["ingredients"][:3],
    )

with open("work/sushi_recipe_parse.json", "w", encoding="utf-8") as output:
    json.dump(recipes, output, indent=2)
