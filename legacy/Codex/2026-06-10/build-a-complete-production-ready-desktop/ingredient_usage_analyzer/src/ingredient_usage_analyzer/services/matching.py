from __future__ import annotations

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
            best_index = 0
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

from ingredient_usage_analyzer.db.database import Database


class RecipeMatcher:
    def __init__(self, db: Database, threshold: float = 95) -> None:
        self.db = db
        self.threshold = threshold

    def match_pending_sales(self) -> int:
        with self.db.connect() as conn:
            recipes = list(conn.execute("SELECT id, name FROM Recipes"))
            choices = {row["name"]: int(row["id"]) for row in recipes}
            updated = 0
            for sale in conn.execute("SELECT id, menu_item FROM Sales WHERE match_status = 'pending'"):
                result = process.extractOne(sale["menu_item"], choices.keys(), scorer=fuzz.WRatio)
                if not result:
                    continue
                recipe_name, score, _ = result
                status = "auto" if score >= self.threshold else "needs_review"
                conn.execute(
                    "UPDATE Sales SET matched_recipe_id = ?, match_score = ?, match_status = ? WHERE id = ?",
                    (choices[recipe_name] if score >= self.threshold else None, float(score), status, int(sale["id"])),
                )
                updated += 1
            return updated

    def override_match(self, sale_id: int, recipe_id: int) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE Sales SET matched_recipe_id = ?, match_score = 100, match_status = 'manual' WHERE id = ?",
                (recipe_id, sale_id),
            )
