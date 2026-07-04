from __future__ import annotations

from ingredient_usage_analyzer.models import IngredientLine, RecipeDraft, SalesLine
from ingredient_usage_analyzer.services.repository import Repository


def load_sample_data(repository: Repository) -> None:
    chai = RecipeDraft(
        name="Chai Concentrate",
        portion_size=1,
        portion_unit="batch",
        is_batch=True,
        yield_quantity=10,
        yield_unit="L",
        ingredients=(
            IngredientLine("Tea", 500, "g"),
            IngredientLine("Sugar", 300, "g"),
            IngredientLine("Water", 5, "L"),
        ),
    )
    repository.upsert_recipe(chai)
    repository.upsert_recipe(
        RecipeDraft(
            name="Chicken Burger",
            ingredients=(
                IngredientLine("Chicken Breast", 150, "g"),
                IngredientLine("Burger Bun", 1, "unit"),
                IngredientLine("Lettuce", 20, "g"),
                IngredientLine("Mayo", 15, "g"),
                IngredientLine("Pickles", 10, "g"),
            ),
        )
    )
    repository.upsert_recipe(
        RecipeDraft(
            name="Chai Latte",
            ingredients=(
                IngredientLine("Chai Concentrate", 150, "ml", child_recipe_name="Chai Concentrate"),
                IngredientLine("Milk", 200, "ml"),
            ),
        )
    )
    repository.upsert_recipe(
        RecipeDraft(
            name="Fries",
            ingredients=(IngredientLine("Potatoes", 180, "g"), IngredientLine("Oil", 20, "ml"), IngredientLine("Salt", 2, "g")),
        )
    )
    repository.insert_sales(
        (
            SalesLine("Chicken Burger", 120, "2026-06-10", "sample"),
            SalesLine("Fries", 200, "2026-06-10", "sample"),
            SalesLine("Chai Latte Large", 80, "2026-06-10", "sample"),
        )
    )
