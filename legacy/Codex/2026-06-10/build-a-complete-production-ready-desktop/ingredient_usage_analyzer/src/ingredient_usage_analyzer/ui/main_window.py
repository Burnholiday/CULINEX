from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ingredient_usage_analyzer.controllers.app_controller import AppController
from ingredient_usage_analyzer.ui.widgets import populate_table


class MainWindow(QMainWindow):
    def __init__(self, controller: AppController) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Ingredient Usage Analyzer")
        self.resize(1280, 820)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self._build_dashboard()
        self._build_recipes()
        self._build_sales()
        self._build_usage()
        self._build_inventory()
        self._build_costing()
        self.refresh_all()
        self.setStyleSheet(
            """
            QMainWindow { background: #f6f8fa; }
            QTabWidget::pane { border: 1px solid #c8d0d6; background: white; }
            QPushButton { padding: 8px 12px; border: 1px solid #aab5bd; border-radius: 4px; background: #ffffff; }
            QPushButton:hover { background: #eef4f6; }
            QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox { padding: 6px; border: 1px solid #b8c3ca; border-radius: 4px; }
            QLabel#Title { font-size: 22px; font-weight: 700; color: #243746; }
            """
        )

    def _page(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        return page, layout

    def _build_dashboard(self) -> None:
        page, layout = self._page()
        title = QLabel("Ingredient Usage Analyzer")
        title.setObjectName("Title")
        layout.addWidget(title)
        layout.addWidget(QLabel("Restaurants, cafés, tea businesses, and food manufacturers can import recipes and sales reports, then calculate ingredient usage, variance, and cost."))
        actions = QHBoxLayout()
        sample = QPushButton("Load Sample Data")
        sample.clicked.connect(self._load_samples)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh_all)
        actions.addWidget(sample)
        actions.addWidget(refresh)
        actions.addStretch()
        layout.addLayout(actions)
        self.dashboard_table = QTableWidget()
        layout.addWidget(self.dashboard_table)
        self.tabs.addTab(page, "Dashboard")

    def _build_recipes(self) -> None:
        page, layout = self._page()
        controls = QHBoxLayout()
        import_button = QPushButton("Import Recipe OCR")
        import_button.clicked.connect(self._import_recipe)
        save_button = QPushButton("Save Manual Recipe")
        save_button.clicked.connect(self._save_recipe)
        controls.addWidget(import_button)
        controls.addWidget(save_button)
        controls.addStretch()
        layout.addLayout(controls)

        form = QFormLayout()
        self.recipe_name = QLineEdit()
        self.recipe_portion = QDoubleSpinBox()
        self.recipe_portion.setRange(0.001, 1_000_000)
        self.recipe_portion.setValue(1)
        self.recipe_portion_unit = QLineEdit("serving")
        self.recipe_is_batch = QCheckBox()
        self.recipe_yield_qty = QDoubleSpinBox()
        self.recipe_yield_qty.setRange(0, 1_000_000)
        self.recipe_yield_unit = QLineEdit()
        self.recipe_lines = QTextEdit()
        self.recipe_lines.setPlaceholderText("150 g Chicken Breast\n1 unit Burger Bun\n150 ml Chai Concentrate")
        form.addRow("Recipe name", self.recipe_name)
        form.addRow("Portion size", self.recipe_portion)
        form.addRow("Portion unit", self.recipe_portion_unit)
        form.addRow("Batch recipe", self.recipe_is_batch)
        form.addRow("Yield quantity", self.recipe_yield_qty)
        form.addRow("Yield unit", self.recipe_yield_unit)
        form.addRow("Ingredients", self.recipe_lines)
        layout.addLayout(form)
        self.recipes_table = QTableWidget()
        layout.addWidget(self.recipes_table)
        self.tabs.addTab(page, "Recipes")

    def _build_sales(self) -> None:
        page, layout = self._page()
        controls = QHBoxLayout()
        import_button = QPushButton("Import Sales Report")
        import_button.clicked.connect(self._import_sales)
        match_button = QPushButton("Run Matching")
        match_button.clicked.connect(self._run_matching)
        controls.addWidget(import_button)
        controls.addWidget(match_button)
        controls.addStretch()
        layout.addLayout(controls)
        self.sales_table = QTableWidget()
        layout.addWidget(self.sales_table)
        self.tabs.addTab(page, "Sales")

    def _build_usage(self) -> None:
        page, layout = self._page()
        filters = QHBoxLayout()
        self.start_date = QLineEdit()
        self.start_date.setPlaceholderText("YYYY-MM-DD")
        self.end_date = QLineEdit()
        self.end_date.setPlaceholderText("YYYY-MM-DD")
        refresh = QPushButton("Calculate")
        refresh.clicked.connect(self.refresh_usage)
        export_csv = QPushButton("Export CSV")
        export_csv.clicked.connect(lambda: self._export_current("Ingredient Usage Report", self.current_usage_rows, "csv"))
        export_excel = QPushButton("Export Excel")
        export_excel.clicked.connect(lambda: self._export_current("Ingredient Usage Report", self.current_usage_rows, "xlsx"))
        export_pdf = QPushButton("Export PDF")
        export_pdf.clicked.connect(lambda: self._export_current("Ingredient Usage Report", self.current_usage_rows, "pdf"))
        for widget in (QLabel("Start"), self.start_date, QLabel("End"), self.end_date, refresh, export_csv, export_excel, export_pdf):
            filters.addWidget(widget)
        filters.addStretch()
        layout.addLayout(filters)
        self.usage_table = QTableWidget()
        self.usage_table.setSortingEnabled(True)
        layout.addWidget(self.usage_table)
        self.current_usage_rows: list[dict] = []
        self.tabs.addTab(page, "Ingredient Usage")

    def _build_inventory(self) -> None:
        page, layout = self._page()
        controls = QHBoxLayout()
        add_button = QPushButton("Add Stock Entry")
        add_button.clicked.connect(self._add_inventory_entry)
        refresh = QPushButton("Variance Report")
        refresh.clicked.connect(self.refresh_inventory)
        export_pdf = QPushButton("Export PDF")
        export_pdf.clicked.connect(lambda: self._export_current("Inventory Variance Report", self.current_variance_rows, "pdf"))
        controls.addWidget(add_button)
        controls.addWidget(refresh)
        controls.addWidget(export_pdf)
        controls.addStretch()
        layout.addLayout(controls)
        self.inventory_table = QTableWidget()
        layout.addWidget(self.inventory_table)
        self.current_variance_rows: list[dict] = []
        self.tabs.addTab(page, "Inventory")

    def _build_costing(self) -> None:
        page, layout = self._page()
        controls = QHBoxLayout()
        set_cost = QPushButton("Set Ingredient Cost")
        set_cost.clicked.connect(self._set_cost)
        refresh = QPushButton("Refresh Costing")
        refresh.clicked.connect(self.refresh_costing)
        export_excel = QPushButton("Export Excel")
        export_excel.clicked.connect(lambda: self._export_current("Food Cost Report", self.current_cost_rows, "xlsx"))
        controls.addWidget(set_cost)
        controls.addWidget(refresh)
        controls.addWidget(export_excel)
        controls.addStretch()
        layout.addLayout(controls)
        self.costing_table = QTableWidget()
        layout.addWidget(self.costing_table)
        self.current_cost_rows: list[dict] = []
        self.tabs.addTab(page, "Costing")

    def _load_samples(self) -> None:
        self.controller.load_samples()
        self.refresh_all()
        QMessageBox.information(self, "Sample data", "Sample recipes, sales, matches, and costs have been loaded.")

    def _import_recipe(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Import recipe", "", "Recipe files (*.jpg *.jpeg *.png *.pdf)")
        if not file_path:
            return
        try:
            draft = self.controller.import_recipe_file(file_path)
            self.recipe_name.setText(draft.name)
            self.recipe_portion.setValue(draft.portion_size)
            self.recipe_portion_unit.setText(draft.portion_unit)
            self.recipe_is_batch.setChecked(draft.is_batch)
            self.recipe_yield_qty.setValue(draft.yield_quantity or 0)
            self.recipe_yield_unit.setText(draft.yield_unit or "")
            self.recipe_lines.setPlainText("\n".join(f"{line.quantity:g} {line.unit} {line.name}" for line in draft.ingredients))
        except Exception as exc:
            QMessageBox.critical(self, "OCR failed", str(exc))

    def _save_recipe(self) -> None:
        try:
            self.controller.save_recipe_from_text(
                self.recipe_name.text(),
                self.recipe_portion.value(),
                self.recipe_portion_unit.text() or "serving",
                self.recipe_lines.toPlainText(),
                self.recipe_is_batch.isChecked(),
                self.recipe_yield_qty.value() or None,
                self.recipe_yield_unit.text() or None,
            )
            self.refresh_all()
            QMessageBox.information(self, "Recipe saved", "Recipe saved successfully.")
        except Exception as exc:
            QMessageBox.critical(self, "Recipe error", str(exc))

    def _import_sales(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Import sales report", "", "Sales files (*.xlsx *.xls *.csv *.pdf)")
        if not file_path:
            return
        try:
            count = self.controller.import_sales_file(file_path)
            self.refresh_all()
            QMessageBox.information(self, "Sales imported", f"Imported {count} sales rows.")
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))

    def _run_matching(self) -> None:
        count = self.controller.matcher.match_pending_sales()
        self.refresh_all()
        QMessageBox.information(self, "Matching complete", f"Processed {count} pending sales rows.")

    def _add_inventory_entry(self) -> None:
        ingredients = self.controller.repository.list_ingredients()
        if not ingredients:
            QMessageBox.warning(self, "Inventory", "Add ingredients first.")
            return
        names = [row["name"] for row in ingredients]
        name, ok = QInputDialog.getItem(self, "Ingredient", "Ingredient", names, editable=False)
        if not ok:
            return
        ingredient = next(row for row in ingredients if row["name"] == name)
        opening, ok = QInputDialog.getDouble(self, "Opening stock", "Opening", 0, 0, 1_000_000, 3)
        if not ok:
            return
        purchases, ok = QInputDialog.getDouble(self, "Purchases", "Purchases", 0, 0, 1_000_000, 3)
        if not ok:
            return
        closing, ok = QInputDialog.getDouble(self, "Closing stock", "Closing", 0, 0, 1_000_000, 3)
        if not ok:
            return
        unit, ok = QInputDialog.getText(self, "Unit", "Unit", text=ingredient["default_unit"])
        if ok:
            self.controller.repository.add_inventory(int(ingredient["id"]), opening, purchases, closing, unit, None, None)
            self.refresh_inventory()

    def _set_cost(self) -> None:
        ingredients = self.controller.repository.list_ingredients()
        if not ingredients:
            QMessageBox.warning(self, "Costing", "Add ingredients first.")
            return
        name, ok = QInputDialog.getItem(self, "Ingredient", "Ingredient", [row["name"] for row in ingredients], editable=False)
        if not ok:
            return
        ingredient = next(row for row in ingredients if row["name"] == name)
        cost, ok = QInputDialog.getDouble(self, "Cost", "Cost per base unit", 0, 0, 1_000_000, 4)
        if ok:
            self.controller.repository.set_cost(int(ingredient["id"]), cost, "R")
            self.refresh_costing()

    def refresh_all(self) -> None:
        recipes = [{"Name": row["name"], "Portion": row["portion_size"], "Unit": row["portion_unit"], "Batch": "Yes" if row["is_batch"] else "No", "Yield": row["yield_quantity"] or ""} for row in self.controller.repository.list_recipes()]
        populate_table(self.recipes_table, recipes)
        sales = [{"Item": row["menu_item"], "Qty Sold": row["quantity_sold"], "Date": row["sale_date"] or "", "Matched Recipe": row["matched_recipe"] or "", "Status": row["match_status"], "Score": row["match_score"] or ""} for row in self.controller.repository.list_sales()]
        populate_table(self.sales_table, sales)
        populate_table(self.dashboard_table, [{"Metric": "Recipes", "Value": len(recipes)}, {"Metric": "Sales rows", "Value": len(sales)}, {"Metric": "Matched sales", "Value": sum(1 for row in sales if row["Matched Recipe"])}])
        self.refresh_usage()
        self.refresh_inventory()
        self.refresh_costing()

    def refresh_usage(self) -> None:
        self.current_usage_rows = self.controller.usage_rows(self.start_date.text() or None, self.end_date.text() or None)
        populate_table(self.usage_table, self.current_usage_rows)

    def refresh_inventory(self) -> None:
        self.current_variance_rows = self.controller.variance_rows()
        populate_table(self.inventory_table, self.current_variance_rows)

    def refresh_costing(self) -> None:
        self.current_cost_rows = self.controller.costing_rows()
        populate_table(self.costing_table, self.current_cost_rows)

    def _export_current(self, report_name: str, rows: list[dict], extension: str) -> None:
        if not rows:
            QMessageBox.warning(self, "Export", "No rows to export.")
            return
        path = self.controller.export_report(report_name, rows, extension)
        QMessageBox.information(self, "Exported", f"Saved report to {path}")
