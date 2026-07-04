from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from ingredient_usage_analyzer.db.database import Database
from ingredient_usage_analyzer.models import IngredientLine, RecipeDraft, SalesLine


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def upsert_ingredient(self, conn: sqlite3.Connection, name: str, default_unit: str = "g") -> int:
        conn.execute(
            "INSERT OR IGNORE INTO Ingredients(name, default_unit) VALUES (?, ?)",
            (name.strip(), default_unit),
        )
        row = conn.execute("SELECT id FROM Ingredients WHERE name = ?", (name.strip(),)).fetchone()
        return int(row["id"])

    def upsert_recipe(self, draft: RecipeDraft) -> int:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO Recipes(name, portion_size, portion_unit, is_batch, yield_quantity, yield_unit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    portion_size=excluded.portion_size,
                    portion_unit=excluded.portion_unit,
                    is_batch=excluded.is_batch,
                    yield_quantity=excluded.yield_quantity,
                    yield_unit=excluded.yield_unit,
                    notes=excluded.notes,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    draft.name.strip(),
                    draft.portion_size,
                    draft.portion_unit,
                    int(draft.is_batch),
                    draft.yield_quantity,
                    draft.yield_unit,
                    draft.notes,
                ),
            )
            recipe_id = int(conn.execute("SELECT id FROM Recipes WHERE name = ?", (draft.name.strip(),)).fetchone()["id"])
            conn.execute("DELETE FROM RecipeIngredients WHERE recipe_id = ?", (recipe_id,))
            if draft.is_batch and draft.yield_quantity and draft.yield_unit:
                conn.execute(
                    """
                    INSERT INTO BatchRecipes(recipe_id, yield_quantity, yield_unit)
                    VALUES (?, ?, ?)
                    ON CONFLICT(recipe_id) DO UPDATE SET yield_quantity=excluded.yield_quantity, yield_unit=excluded.yield_unit
                    """,
                    (recipe_id, draft.yield_quantity, draft.yield_unit),
                )
            else:
                conn.execute("DELETE FROM BatchRecipes WHERE recipe_id = ?", (recipe_id,))
            for index, line in enumerate(draft.ingredients):
                child_recipe_id = None
                ingredient_id = None
                if line.child_recipe_name:
                    child = conn.execute("SELECT id FROM Recipes WHERE name = ?", (line.child_recipe_name,)).fetchone()
                    if not child:
                        raise ValueError(f"Child recipe not found: {line.child_recipe_name}")
                    child_recipe_id = int(child["id"])
                else:
                    ingredient_id = self.upsert_ingredient(conn, line.name, line.unit)
                conn.execute(
                    """
                    INSERT INTO RecipeIngredients(recipe_id, ingredient_id, child_recipe_id, quantity, unit, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (recipe_id, ingredient_id, child_recipe_id, line.quantity, line.unit, index),
                )
            return recipe_id

    def list_recipes(self) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return list(conn.execute("SELECT * FROM Recipes ORDER BY name"))

    def get_recipe_ingredients(self, recipe_id: int) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT ri.*, i.name AS ingredient_name, r.name AS child_recipe_name
                    FROM RecipeIngredients ri
                    LEFT JOIN Ingredients i ON i.id = ri.ingredient_id
                    LEFT JOIN Recipes r ON r.id = ri.child_recipe_id
                    WHERE ri.recipe_id = ?
                    ORDER BY ri.sort_order, ri.id
                    """,
                    (recipe_id,),
                )
            )

    def delete_recipe(self, recipe_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute("DELETE FROM Recipes WHERE id = ?", (recipe_id,))

    def insert_sales(self, lines: Iterable[SalesLine]) -> int:
        count = 0
        with self.db.connect() as conn:
            for line in lines:
                conn.execute(
                    "INSERT INTO Sales(menu_item, quantity_sold, sale_date, source_file) VALUES (?, ?, ?, ?)",
                    (line.menu_item.strip(), line.quantity_sold, line.sale_date, line.source_file),
                )
                count += 1
        return count

    def list_sales(self) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return list(
                conn.execute(
                    """
                    SELECT s.*, r.name AS matched_recipe
                    FROM Sales s
                    LEFT JOIN Recipes r ON r.id = s.matched_recipe_id
                    ORDER BY COALESCE(s.sale_date, s.imported_at) DESC, s.id DESC
                    """
                )
            )

    def list_ingredients(self) -> list[sqlite3.Row]:
        with self.db.connect() as conn:
            return list(conn.execute("SELECT * FROM Ingredients ORDER BY name"))

    def set_cost(self, ingredient_id: int, cost_per_base_unit: float, currency: str = "R") -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO Costs(ingredient_id, cost_per_base_unit, currency)
                VALUES (?, ?, ?)
                ON CONFLICT(ingredient_id) DO UPDATE SET
                    cost_per_base_unit=excluded.cost_per_base_unit,
                    currency=excluded.currency,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (ingredient_id, cost_per_base_unit, currency),
            )

    def add_inventory(self, ingredient_id: int, opening: float, purchases: float, closing: float, unit: str, period_start: str | None, period_end: str | None) -> None:
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO Inventory(ingredient_id, opening_quantity, purchases_quantity, closing_quantity, unit, period_start, period_end)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ingredient_id, opening, purchases, closing, unit, period_start, period_end),
            )
