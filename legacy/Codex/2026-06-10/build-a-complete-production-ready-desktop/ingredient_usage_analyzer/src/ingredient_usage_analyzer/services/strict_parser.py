from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from rapidfuzz import fuzz, process
except ModuleNotFoundError:
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def WRatio(left: str, right: str) -> float:
            return SequenceMatcher(None, left.lower(), right.lower()).ratio() * 100

    class _FallbackProcess:
        @staticmethod
        def extractOne(query: str, choices, scorer):
            best_choice = None
            best_score = -1.0
            for index, choice in enumerate(choices):
                score = scorer(query, choice)
                if score > best_score:
                    best_choice = choice
                    best_score = score
                    best_index = index
            if best_choice is None:
                return None
            return best_choice, best_score, best_index

    fuzz = _FallbackFuzz()
    process = _FallbackProcess()


MASTER_INGREDIENTS = {
    "avo": "Avocado",
    "avocado": "Avocado",
    "jap mayo": "Japanese Mayo",
    "japanese mayo": "Japanese Mayo",
    "seaweed": "Nori",
    "nori": "Nori",
}

MENU_NAME_ALIASES = {
    "cali": "california",
}


@dataclass(frozen=True)
class ParsedIngredient:
    ingredient: str
    quantity: float


@dataclass(frozen=True)
class ParsedRecipe:
    dish_name: str
    ingredients: tuple[ParsedIngredient, ...]


@dataclass(frozen=True)
class ParsedSale:
    item: str
    sold: float


@dataclass(frozen=True)
class MenuMatch:
    sale_item: str
    recipe_name: str | None
    score: float
    status: str


@dataclass
class ValidationResult:
    missing_recipes: list[str] = field(default_factory=list)
    duplicate_recipes: list[str] = field(default_factory=list)
    ambiguous_menu_matches: list[MenuMatch] = field(default_factory=list)
    invalid_ingredients: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_recipes or self.duplicate_recipes or self.ambiguous_menu_matches or self.invalid_ingredients)


class StrictParserError(ValueError):
    pass


class RecipeSalesParser:
    """Strict spreadsheet parser for recipe blocks and item/quantity sales rows."""

    def __init__(self, similarity_threshold: float = 95) -> None:
        self.similarity_threshold = similarity_threshold

    def parse_recipe_spreadsheet(self, file_path: str | Path) -> list[ParsedRecipe]:
        frame = self._read_table(file_path)
        rows = self._clean_rows(frame)
        recipes: list[ParsedRecipe] = []
        current_name: str | None = None
        current_ingredients: list[ParsedIngredient] = []

        for row in rows:
            if self._is_blank_row(row):
                if current_name is not None:
                    recipes.append(self._finish_recipe(current_name, current_ingredients))
                    current_name = None
                    current_ingredients = []
                continue

            ingredient_name, quantity = self._ingredient_from_row(row)
            if ingredient_name is not None and quantity is not None:
                if current_name is None:
                    raise StrictParserError(f"Ingredient row appears before recipe title: {ingredient_name}")
                current_ingredients.append(ParsedIngredient(ingredient_name, quantity))
                continue

            title = self._title_from_row(row)
            if not title:
                raise StrictParserError(f"Could not classify recipe row: {row}")
            if current_name is not None:
                recipes.append(self._finish_recipe(current_name, current_ingredients))
                current_ingredients = []
            current_name = title

        if current_name is not None:
            recipes.append(self._finish_recipe(current_name, current_ingredients))
        return recipes

    def parse_sales_spreadsheet(self, file_path: str | Path) -> list[ParsedSale]:
        frame = self._read_table(file_path, header=0)
        lower_columns = {str(col).strip().lower(): col for col in frame.columns}
        item_col = self._find_column(lower_columns, ("item sold", "item", "menu item", "description", "product", "name"))
        qty_col = self._find_column(lower_columns, ("quantity sold", "qty sold", "qty", "quantity", "sold"))
        sales: list[ParsedSale] = []
        for _, row in frame.iterrows():
            item = self._clean_text(row[item_col])
            quantity = self._to_number(row[qty_col])
            if not item and quantity is None:
                continue
            if not item:
                raise StrictParserError("Sales row is missing item name.")
            if quantity is None:
                raise StrictParserError(f"Sales row for {item} has a non-numeric quantity.")
            sales.append(ParsedSale(item, quantity))
        return sales

    def calculate(self, recipes: list[ParsedRecipe], sales: list[ParsedSale], master_ingredients: dict[str, str] | None = None) -> dict[str, Any]:
        matches = self.match_sales_to_recipes(recipes, sales)
        validation = self.validate(recipes, sales, matches)
        if not validation.ok:
            return {
                "status": "blocked",
                "validation": self.validation_to_dict(validation),
                "ingredient_usage": [],
                "table": [],
            }

        recipe_by_name = {recipe.dish_name: recipe for recipe in recipes}
        totals: dict[str, float] = defaultdict(float)
        normalizer = {**MASTER_INGREDIENTS, **(master_ingredients or {})}
        for sale in sales:
            match = matches[sale.item]
            recipe = recipe_by_name[match.recipe_name or ""]
            for ingredient in recipe.ingredients:
                master_name = normalizer.get(ingredient.ingredient.strip().lower(), ingredient.ingredient.strip().title())
                totals[master_name] += ingredient.quantity * sale.sold

        usage = [{"ingredient": ingredient, "total_used": round(total, 3)} for ingredient, total in sorted(totals.items())]
        table = [{"Ingredient": row["ingredient"], "Total Used": f"{row['total_used']:.3f}"} for row in usage]
        return {"status": "ok", "validation": self.validation_to_dict(validation), "ingredient_usage": usage, "table": table}

    def match_sales_to_recipes(self, recipes: list[ParsedRecipe], sales: list[ParsedSale]) -> dict[str, MenuMatch]:
        recipe_names = [recipe.dish_name for recipe in recipes]
        normalized_recipes = {self._normalize_menu_name(name): name for name in recipe_names}
        matches: dict[str, MenuMatch] = {}
        for sale in sales:
            normalized_sale = self._normalize_menu_name(sale.item)
            result = process.extractOne(normalized_sale, normalized_recipes.keys(), scorer=fuzz.WRatio)
            if not result:
                matches[sale.item] = MenuMatch(sale.item, None, 0.0, "missing_recipe")
                continue
            normalized_recipe_name, score, _ = result
            recipe_name = normalized_recipes[normalized_recipe_name]
            status = "matched" if score >= self.similarity_threshold else "review"
            matches[sale.item] = MenuMatch(sale.item, recipe_name if status == "matched" else None, float(score), status)
        return matches

    def validate(self, recipes: list[ParsedRecipe], sales: list[ParsedSale], matches: dict[str, MenuMatch]) -> ValidationResult:
        result = ValidationResult()
        names = [recipe.dish_name for recipe in recipes]
        result.duplicate_recipes = sorted(name for name, count in Counter(names).items() if count > 1)

        for recipe in recipes:
            if not recipe.ingredients:
                result.invalid_ingredients.append(f"{recipe.dish_name}: no ingredients found")
            for ingredient in recipe.ingredients:
                if not ingredient.ingredient:
                    result.invalid_ingredients.append(f"{recipe.dish_name}: ingredient name missing")
                if not isinstance(ingredient.quantity, int | float):
                    result.invalid_ingredients.append(f"{recipe.dish_name}: {ingredient.ingredient} quantity is not numeric")

        for sale in sales:
            match = matches[sale.item]
            if match.status == "missing_recipe":
                result.missing_recipes.append(sale.item)
            elif match.status == "review":
                result.ambiguous_menu_matches.append(match)
        return result

    def validation_to_dict(self, validation: ValidationResult) -> dict[str, Any]:
        return {
            "ok": validation.ok,
            "missing_recipes": validation.missing_recipes,
            "duplicate_recipes": validation.duplicate_recipes,
            "ambiguous_menu_matches": [
                {"item": match.sale_item, "candidate": match.recipe_name, "score": round(match.score, 2), "status": match.status}
                for match in validation.ambiguous_menu_matches
            ],
            "invalid_ingredients": validation.invalid_ingredients,
        }

    def _read_table(self, file_path: str | Path, header: int | None = None) -> pd.DataFrame:
        path = Path(file_path)
        if path.suffix.lower() == ".csv":
            if header is None:
                return pd.read_csv(path, header=None, names=range(20), engine="python", skip_blank_lines=False)
            return pd.read_csv(path, header=header)
        if path.suffix.lower() in {".xlsx", ".xls"}:
            return pd.read_excel(path, header=header)
        raise StrictParserError(f"Unsupported file type: {path.suffix}")

    def _clean_rows(self, frame: pd.DataFrame) -> list[list[Any]]:
        return [[cell for cell in row.tolist()] for _, row in frame.iterrows()]

    def _finish_recipe(self, name: str, ingredients: list[ParsedIngredient]) -> ParsedRecipe:
        if not ingredients:
            raise StrictParserError(f"Recipe has no ingredient rows: {name}")
        return ParsedRecipe(name, tuple(ingredients))

    def _ingredient_from_row(self, row: list[Any]) -> tuple[str | None, float | None]:
        values = [cell for cell in row if self._clean_text(cell)]
        if len(values) < 2:
            return None, None
        first = self._clean_text(values[0])
        second = self._to_number(values[1])
        if first and second is not None:
            return first, second
        if len(values) >= 3:
            quantity = self._to_number(values[2])
            name_parts = [self._clean_text(values[0]), self._clean_text(values[1])]
            name = " ".join(part for part in name_parts if part)
            if name and quantity is not None:
                return name, quantity
        return None, None

    def _title_from_row(self, row: list[Any]) -> str | None:
        values = [self._clean_text(cell) for cell in row if self._clean_text(cell)]
        if len(values) == 1 and self._to_number(values[0]) is None:
            return values[0]
        return None

    def _find_column(self, lower_columns: dict[str, Any], choices: tuple[str, ...]) -> Any:
        for choice in choices:
            if choice in lower_columns:
                return lower_columns[choice]
        raise StrictParserError(f"Could not find required sales column: {', '.join(choices)}")

    def _is_blank_row(self, row: list[Any]) -> bool:
        return all(not self._clean_text(cell) for cell in row)

    def _clean_text(self, value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        text = str(value).strip()
        return "" if text.lower() == "nan" else text

    def _to_number(self, value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        try:
            number = float(str(value).strip().replace(",", "."))
        except ValueError:
            return None
        return number

    def _normalize_menu_name(self, value: str) -> str:
        words = []
        for word in value.lower().split():
            words.append(MENU_NAME_ALIASES.get(word, word))
        return " ".join(words)
