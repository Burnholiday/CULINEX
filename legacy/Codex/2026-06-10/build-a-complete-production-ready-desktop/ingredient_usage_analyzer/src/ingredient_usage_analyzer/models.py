from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientLine:
    name: str
    quantity: float
    unit: str
    child_recipe_name: str | None = None


@dataclass(frozen=True)
class RecipeDraft:
    name: str
    portion_size: float = 1
    portion_unit: str = "serving"
    ingredients: tuple[IngredientLine, ...] = ()
    is_batch: bool = False
    yield_quantity: float | None = None
    yield_unit: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class SalesLine:
    menu_item: str
    quantity_sold: float
    sale_date: str | None = None
    source_file: str | None = None
