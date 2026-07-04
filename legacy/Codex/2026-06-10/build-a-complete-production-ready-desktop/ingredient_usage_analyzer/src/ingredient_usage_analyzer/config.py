from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


APP_NAME = "Ingredient Usage Analyzer"
SUPPORTED_RECIPE_FILES = {".jpg", ".jpeg", ".png", ".pdf"}
SUPPORTED_SALES_FILES = {".xlsx", ".xls", ".csv", ".pdf"}


@dataclass(frozen=True)
class AppPaths:
    root: Path
    data_dir: Path
    reports_dir: Path
    database_path: Path

    @classmethod
    def default(cls) -> "AppPaths":
        root = Path.home() / ".ingredient_usage_analyzer"
        data_dir = root / "data"
        reports_dir = root / "reports"
        return cls(root=root, data_dir=data_dir, reports_dir=reports_dir, database_path=data_dir / "ingredient_usage.sqlite3")

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
