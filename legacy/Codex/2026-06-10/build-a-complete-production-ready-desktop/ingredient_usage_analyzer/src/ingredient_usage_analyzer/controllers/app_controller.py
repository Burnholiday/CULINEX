from __future__ import annotations

from pathlib import Path

from ingredient_usage_analyzer.config import AppPaths
from ingredient_usage_analyzer.db.database import Database
from ingredient_usage_analyzer.models import IngredientLine, RecipeDraft
from ingredient_usage_analyzer.sample_data import load_sample_data
from ingredient_usage_analyzer.services.calculations import CostingService, IngredientCalculationEngine, InventoryService
from ingredient_usage_analyzer.services.importers import SalesImporter
from ingredient_usage_analyzer.services.matching import RecipeMatcher
from ingredient_usage_analyzer.services.ocr import RecipeOcrService
from ingredient_usage_analyzer.services.reports import ReportExporter
from ingredient_usage_analyzer.services.repository import Repository


class AppController:
    def __init__(self, db: Database, paths: AppPaths) -> None:
        self.db = db
        self.paths = paths
        self.repository = Repository(db)
        self.ocr = RecipeOcrService()
        self.importer = SalesImporter()
        self.matcher = RecipeMatcher(db)
        self.calculator = IngredientCalculationEngine(db)
        self.inventory = InventoryService(db, self.calculator)
        self.costing = CostingService(db, self.calculator)
        self.exporter = ReportExporter()

    def load_samples(self) -> None:
        load_sample_data(self.repository)
        self.matcher.match_pending_sales()
        self._seed_costs()

    def _seed_costs(self) -> None:
        cost_by_name = {
            "Tea": 0.12,
            "Sugar": 0.025,
            "Milk": 0.018,
            "Chicken Breast": 0.085,
            "Burger Bun": 4.0,
            "Lettuce": 0.035,
            "Mayo": 0.055,
            "Pickles": 0.04,
            "Potatoes": 0.018,
            "Oil": 0.04,
            "Salt": 0.01,
            "Water": 0.001,
        }
        for ingredient in self.repository.list_ingredients():
            if ingredient["name"] in cost_by_name:
                self.repository.set_cost(int(ingredient["id"]), cost_by_name[ingredient["name"]], "R")

    def import_recipe_file(self, file_path: str) -> RecipeDraft:
        return self.ocr.parse_recipe(self.ocr.extract_text(file_path))

    def save_recipe_from_text(self, name: str, portion: float, portion_unit: str, lines_text: str, is_batch: bool = False, yield_quantity: float | None = None, yield_unit: str | None = None) -> int:
        ingredients = []
        for raw in lines_text.splitlines():
            parts = raw.strip().split(maxsplit=2)
            if len(parts) < 3:
                continue
            quantity = float(parts[0])
            unit = parts[1]
            item_name = parts[2]
            child_recipe_name = item_name if any(r["name"].lower() == item_name.lower() for r in self.repository.list_recipes()) else None
            ingredients.append(IngredientLine(item_name, quantity, unit, child_recipe_name))
        return self.repository.upsert_recipe(
            RecipeDraft(
                name=name,
                portion_size=portion,
                portion_unit=portion_unit,
                ingredients=tuple(ingredients),
                is_batch=is_batch,
                yield_quantity=yield_quantity,
                yield_unit=yield_unit,
            )
        )

    def import_sales_file(self, file_path: str) -> int:
        rows = self.importer.import_file(file_path)
        count = self.repository.insert_sales(rows)
        self.matcher.match_pending_sales()
        return count

    def usage_rows(self, start_date: str | None = None, end_date: str | None = None) -> list[dict]:
        return [
            {
                "Ingredient": row.ingredient,
                "Total Used": round(row.display_quantity, 3),
                "Unit": row.display_unit,
                "Base Quantity": round(row.quantity_base, 3),
                "Base Unit": row.base_unit,
            }
            for row in self.calculator.calculate_usage(start_date, end_date)
        ]

    def variance_rows(self) -> list[dict]:
        return self.inventory.variance_report()

    def costing_rows(self) -> list[dict]:
        return self.costing.recipe_costs()

    def export_report(self, report_name: str, rows: list[dict], extension: str) -> Path:
        safe_name = report_name.lower().replace(" ", "_")
        out = self.paths.reports_dir / f"{safe_name}.{extension}"
        if extension == "csv":
            return self.exporter.export_csv(rows, out)
        if extension == "xlsx":
            return self.exporter.export_excel(rows, out, report_name)
        if extension == "pdf":
            return self.exporter.export_pdf(report_name, rows, out)
        raise ValueError(f"Unsupported export format: {extension}")
