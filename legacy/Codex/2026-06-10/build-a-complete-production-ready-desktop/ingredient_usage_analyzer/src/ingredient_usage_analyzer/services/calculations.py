from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ingredient_usage_analyzer.db.database import Database
from ingredient_usage_analyzer.services.units import UnitConverter


@dataclass(frozen=True)
class UsageRow:
    ingredient_id: int
    ingredient: str
    quantity_base: float
    base_unit: str
    display_quantity: float
    display_unit: str


class IngredientCalculationEngine:
    def __init__(self, db: Database) -> None:
        self.db = db

    def calculate_usage(self, start_date: str | None = None, end_date: str | None = None) -> list[UsageRow]:
        totals: dict[tuple[int, str, str], float] = defaultdict(float)
        with self.db.connect() as conn:
            query = """
                SELECT s.id, s.quantity_sold, s.matched_recipe_id
                FROM Sales s
                WHERE s.matched_recipe_id IS NOT NULL
            """
            params: list[str] = []
            if start_date:
                query += " AND (s.sale_date IS NULL OR s.sale_date >= ?)"
                params.append(start_date)
            if end_date:
                query += " AND (s.sale_date IS NULL OR s.sale_date <= ?)"
                params.append(end_date)
            conn.execute("DELETE FROM IngredientUsage")
            for sale in conn.execute(query, params):
                exploded = self._explode_recipe(conn, int(sale["matched_recipe_id"]), float(sale["quantity_sold"]), set())
                for ingredient_id, ingredient_name, qty_base, base_unit in exploded:
                    totals[(ingredient_id, ingredient_name, base_unit)] += qty_base
                    conn.execute(
                        "INSERT INTO IngredientUsage(ingredient_id, quantity, unit, source_sales_id) VALUES (?, ?, ?, ?)",
                        (ingredient_id, qty_base, base_unit, int(sale["id"])),
                    )
        rows: list[UsageRow] = []
        for (ingredient_id, ingredient_name, base_unit), quantity in sorted(totals.items(), key=lambda item: item[0][1]):
            display_quantity, display_unit = UnitConverter.from_base_for_display(quantity, base_unit)
            rows.append(UsageRow(ingredient_id, ingredient_name, quantity, base_unit, display_quantity, display_unit))
        return rows

    def _explode_recipe(self, conn, recipe_id: int, multiplier: float, seen: set[int]) -> list[tuple[int, str, float, str]]:
        if recipe_id in seen:
            raise ValueError("Circular batch recipe detected.")
        seen.add(recipe_id)
        rows: list[tuple[int, str, float, str]] = []
        recipe = conn.execute("SELECT * FROM Recipes WHERE id = ?", (recipe_id,)).fetchone()
        if not recipe:
            return rows
        portion_size = float(recipe["portion_size"] or 1)
        serving_multiplier = multiplier / portion_size
        for line in conn.execute(
            """
            SELECT ri.*, i.name AS ingredient_name, r.name AS child_recipe_name
            FROM RecipeIngredients ri
            LEFT JOIN Ingredients i ON i.id = ri.ingredient_id
            LEFT JOIN Recipes r ON r.id = ri.child_recipe_id
            WHERE ri.recipe_id = ?
            ORDER BY ri.sort_order
            """,
            (recipe_id,),
        ):
            line_qty = float(line["quantity"]) * serving_multiplier
            if line["ingredient_id"] is not None:
                qty_base, base_unit = UnitConverter.to_base(line_qty, line["unit"])
                rows.append((int(line["ingredient_id"]), line["ingredient_name"], qty_base, base_unit))
                continue
            child = conn.execute("SELECT * FROM Recipes WHERE id = ?", (int(line["child_recipe_id"]),)).fetchone()
            if not child or not child["yield_quantity"] or not child["yield_unit"]:
                raise ValueError(f"Nested recipe {line['child_recipe_name']} must have a yield.")
            required_child_base, child_base_unit = UnitConverter.to_base(line_qty, line["unit"])
            yield_base, yield_base_unit = UnitConverter.to_base(float(child["yield_quantity"]), child["yield_unit"])
            if child_base_unit != yield_base_unit:
                raise ValueError(f"Nested recipe unit mismatch for {line['child_recipe_name']}.")
            child_multiplier = required_child_base / yield_base
            rows.extend(self._explode_recipe(conn, int(line["child_recipe_id"]), child_multiplier, set(seen)))
        return rows


class InventoryService:
    def __init__(self, db: Database, calculator: IngredientCalculationEngine) -> None:
        self.db = db
        self.calculator = calculator

    def variance_report(self, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, float | str]]:
        expected = {row.ingredient_id: row for row in self.calculator.calculate_usage(start_date, end_date)}
        report = []
        with self.db.connect() as conn:
            for row in conn.execute(
                """
                SELECT inv.*, i.name AS ingredient_name
                FROM Inventory inv
                JOIN Ingredients i ON i.id = inv.ingredient_id
                ORDER BY i.name, inv.id DESC
                """
            ):
                actual = float(row["opening_quantity"]) + float(row["purchases_quantity"]) - float(row["closing_quantity"])
                actual_base, actual_unit = UnitConverter.to_base(actual, row["unit"])
                expected_row = expected.get(int(row["ingredient_id"]))
                expected_base = expected_row.quantity_base if expected_row and expected_row.base_unit == actual_unit else 0
                variance_base = actual_base - expected_base
                variance_display, variance_unit = UnitConverter.from_base_for_display(variance_base, actual_unit)
                actual_display, actual_display_unit = UnitConverter.from_base_for_display(actual_base, actual_unit)
                expected_display, expected_display_unit = UnitConverter.from_base_for_display(expected_base, actual_unit)
                report.append(
                    {
                        "ingredient": row["ingredient_name"],
                        "actual": round(actual_display, 3),
                        "actual_unit": actual_display_unit,
                        "expected": round(expected_display, 3),
                        "expected_unit": expected_display_unit,
                        "variance": round(variance_display, 3),
                        "variance_unit": variance_unit,
                    }
                )
        return report


class CostingService:
    def __init__(self, db: Database, calculator: IngredientCalculationEngine) -> None:
        self.db = db
        self.calculator = calculator

    def recipe_costs(self) -> list[dict[str, float | str]]:
        results = []
        with self.db.connect() as conn:
            recipes = list(conn.execute("SELECT * FROM Recipes ORDER BY name"))
            costs = {int(row["ingredient_id"]): (float(row["cost_per_base_unit"]), row["currency"]) for row in conn.execute("SELECT * FROM Costs")}
            for recipe in recipes:
                total = 0.0
                currency = "R"
                for ingredient_id, _, quantity_base, _ in self.calculator._explode_recipe(conn, int(recipe["id"]), float(recipe["portion_size"] or 1), set()):
                    cost = costs.get(ingredient_id)
                    if cost:
                        total += quantity_base * cost[0]
                        currency = cost[1]
                portion_size = float(recipe["portion_size"] or 1)
                results.append(
                    {
                        "recipe": recipe["name"],
                        "total_cost": round(total, 2),
                        "cost_per_serving": round(total / portion_size, 2) if portion_size else round(total, 2),
                        "currency": currency,
                    }
                )
        return results

    def ingredient_usage_costs(self, start_date: str | None = None, end_date: str | None = None) -> list[dict[str, float | str]]:
        usage = self.calculator.calculate_usage(start_date, end_date)
        with self.db.connect() as conn:
            costs = {int(row["ingredient_id"]): (float(row["cost_per_base_unit"]), row["currency"]) for row in conn.execute("SELECT * FROM Costs")}
        rows = []
        for item in usage:
            cost = costs.get(item.ingredient_id, (0.0, "R"))
            rows.append(
                {
                    "ingredient": item.ingredient,
                    "quantity": round(item.display_quantity, 3),
                    "unit": item.display_unit,
                    "cost": round(item.quantity_base * cost[0], 2),
                    "currency": cost[1],
                }
            )
        return rows
