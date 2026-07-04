from __future__ import annotations

from ingredient_usage_analyzer.services.strict_parser import ParsedIngredient, ParsedRecipe, ParsedSale, RecipeSalesParser


def test_calculate_blocks_below_threshold() -> None:
    parser = RecipeSalesParser(similarity_threshold=95)
    recipes = [ParsedRecipe("CALIFORNIA SALMON 4PC", (ParsedIngredient("rice", 0.075),))]
    sales = [ParsedSale("UNKNOWN ITEM", 10)]

    result = parser.calculate(recipes, sales)

    assert result["status"] == "blocked"
    assert result["ingredient_usage"] == []
    assert result["validation"]["ambiguous_menu_matches"]


def test_calculate_aggregates_master_ingredients() -> None:
    parser = RecipeSalesParser(similarity_threshold=95)
    recipes = [
        ParsedRecipe("CALIFORNIA SALMON 4PC", (ParsedIngredient("rice", 0.075), ParsedIngredient("avo", 0.02))),
        ParsedRecipe("CALIFORNIA TUNA 4PC", (ParsedIngredient("rice", 0.05), ParsedIngredient("avocado", 0.03))),
    ]
    sales = [ParsedSale("CALIFORNIA SALMON 4PC", 59), ParsedSale("CALIFORNIA TUNA 4PC", 10)]

    result = parser.calculate(recipes, sales)

    assert result["status"] == "ok"
    assert {"ingredient": "Rice", "total_used": 4.925} in result["ingredient_usage"]
    assert {"ingredient": "Avocado", "total_used": 1.48} in result["ingredient_usage"]


def test_cali_alias_matches_california_at_high_threshold() -> None:
    parser = RecipeSalesParser(similarity_threshold=95)
    recipes = [ParsedRecipe("CALIFORNIA SALMON 4PC", (ParsedIngredient("rice", 0.075),))]
    sales = [ParsedSale("CALI SALMON 4PC", 59)]

    result = parser.calculate(recipes, sales)

    assert result["status"] == "ok"
    assert result["ingredient_usage"] == [{"ingredient": "Rice", "total_used": 4.425}]
