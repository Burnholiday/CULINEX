from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from ingredient_usage_analyzer.services.strict_parser import RecipeSalesParser


def main() -> int:
    parser = argparse.ArgumentParser(description="Strict recipe and sales parser.")
    parser.add_argument("--recipes", required=True, help="Recipe spreadsheet arranged in recipe blocks.")
    parser.add_argument("--sales", required=True, help="Sales spreadsheet with item and quantity columns.")
    parser.add_argument("--json", dest="json_path", help="Optional JSON output path.")
    parser.add_argument("--csv", dest="csv_path", help="Optional CSV table output path.")
    args = parser.parse_args()

    engine = RecipeSalesParser(similarity_threshold=95)
    recipes = engine.parse_recipe_spreadsheet(args.recipes)
    sales = engine.parse_sales_spreadsheet(args.sales)
    result = engine.calculate(recipes, sales)

    print(json.dumps(result, indent=2))
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.csv_path:
        if result["status"] != "ok":
            raise SystemExit("Validation failed. CSV was not written.")
        pd.DataFrame(result["table"]).to_csv(args.csv_path, index=False)
    return 0 if result["status"] == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())
