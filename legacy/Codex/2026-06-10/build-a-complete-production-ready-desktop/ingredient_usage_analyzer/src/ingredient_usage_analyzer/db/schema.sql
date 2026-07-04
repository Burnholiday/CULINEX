PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    portion_size REAL DEFAULT 1,
    portion_unit TEXT DEFAULT 'serving',
    is_batch INTEGER NOT NULL DEFAULT 0,
    yield_quantity REAL,
    yield_unit TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    default_unit TEXT NOT NULL DEFAULT 'g',
    category TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS RecipeIngredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL REFERENCES Recipes(id) ON DELETE CASCADE,
    ingredient_id INTEGER REFERENCES Ingredients(id),
    child_recipe_id INTEGER REFERENCES Recipes(id),
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    CHECK ((ingredient_id IS NOT NULL AND child_recipe_id IS NULL) OR (ingredient_id IS NULL AND child_recipe_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS BatchRecipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipe_id INTEGER NOT NULL UNIQUE REFERENCES Recipes(id) ON DELETE CASCADE,
    yield_quantity REAL NOT NULL,
    yield_unit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item TEXT NOT NULL,
    quantity_sold REAL NOT NULL,
    sale_date TEXT,
    source_file TEXT,
    matched_recipe_id INTEGER REFERENCES Recipes(id),
    match_score REAL,
    match_status TEXT NOT NULL DEFAULT 'pending',
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL REFERENCES Ingredients(id) ON DELETE CASCADE,
    period_start TEXT,
    period_end TEXT,
    opening_quantity REAL NOT NULL DEFAULT 0,
    purchases_quantity REAL NOT NULL DEFAULT 0,
    closing_quantity REAL NOT NULL DEFAULT 0,
    unit TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS IngredientUsage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL REFERENCES Ingredients(id) ON DELETE CASCADE,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    source_sales_id INTEGER REFERENCES Sales(id) ON DELETE SET NULL,
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL UNIQUE REFERENCES Ingredients(id) ON DELETE CASCADE,
    cost_per_base_unit REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'R',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe ON RecipeIngredients(recipe_id);
CREATE INDEX IF NOT EXISTS idx_sales_menu_item ON Sales(menu_item);
CREATE INDEX IF NOT EXISTS idx_sales_date ON Sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_inventory_ingredient ON Inventory(ingredient_id);
