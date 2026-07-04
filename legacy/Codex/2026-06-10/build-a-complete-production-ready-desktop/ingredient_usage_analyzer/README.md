# Ingredient Usage Analyzer

Desktop application and strict parser for calculating ingredient consumption from recipe spreadsheets and sales spreadsheets.

## Strict Recipe & Sales Parser

The strict parser is designed for accuracy. It does not invent menu items, ingredients, or quantities. If a sold item has no recipe, a recipe is duplicated, an ingredient quantity is missing, or a fuzzy match is below 95%, calculation is blocked and validation issues are returned.

Recipe spreadsheets are read as blocks:

```text
CALIFORNIA SALMON 4PC
rice      0.075
salmon    0.020
avo       0.020
sesame    0.003

CALIFORNIA TUNA 4PC
rice      0.075
tuna      0.020
avocado   0.020
```

Sales spreadsheets must contain an item column and a quantity column, such as `Item Sold` and `Quantity Sold`.

Run:

```powershell
python -m ingredient_usage_analyzer.strict_cli --recipes recipes.xlsx --sales sales.xlsx --json usage.json --csv usage.csv
```

The output shape is:

```json
{
  "status": "ok",
  "validation": {
    "ok": true,
    "missing_recipes": [],
    "duplicate_recipes": [],
    "ambiguous_menu_matches": [],
    "invalid_ingredients": []
  },
  "ingredient_usage": [
    {
      "ingredient": "Rice",
      "total_used": 32.145
    }
  ],
  "table": [
    {
      "Ingredient": "Rice",
      "Total Used": "32.145"
    }
  ]
}
```

Built-in ingredient normalisation:

| Seen in recipes | Master ingredient |
| --- | --- |
| avo, avocado | Avocado |
| jap mayo, japanese mayo | Japanese Mayo |
| seaweed, nori | Nori |

Built-in menu alias:

| Sales name | Recipe name |
| --- | --- |
| CALI | CALIFORNIA |

## Desktop App

Install dependencies in Python 3.12:

```powershell
pip install -r requirements.txt
```

Start the desktop app:

```powershell
python -m ingredient_usage_analyzer.main
```

The app includes recipes, sales import, fuzzy matching, ingredient usage, inventory variance, costing, and report exports.
