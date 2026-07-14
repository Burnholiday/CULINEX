#!/usr/bin/env python3
"""
Restaurant-specific ingredient memory.

This module is intentionally standalone. It does not read parser output,
create ingredients automatically, merge records, or connect to production
storage. The JSON repository is for local development and review workflows.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import tempfile
from typing import Dict, List, Optional


VALID_INGREDIENT_STATUSES = {"proposed", "approved", "rejected", "merged", "archived"}
DEFAULT_MEMORY_PATH = Path("data") / "ingredient-memory.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_key(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class SupplierIngredientVariant:
    supplier_name: str
    supplier_code: Optional[str]
    supplier_description: str
    candidate_name: str
    purchase_unit: Optional[str]
    pack_count: Optional[float]
    pack_size_value: Optional[float]
    pack_size_unit: Optional[str]
    first_seen_at: str
    last_seen_at: str
    observation_count: int
    match_confidence: float

    def identity_key(self) -> str:
        parts = [
            self.supplier_name,
            self.supplier_code or "",
            self.supplier_description,
            self.candidate_name,
            self.purchase_unit or "",
            "" if self.pack_count is None else str(self.pack_count),
            "" if self.pack_size_value is None else str(self.pack_size_value),
            self.pack_size_unit or "",
        ]
        return "|".join(normalize_key(part) for part in parts)


@dataclass
class IngredientRecord:
    ingredient_id: str
    canonical_name: str
    normalized_key: str
    aliases: List[str] = field(default_factory=list)
    supplier_variants: List[SupplierIngredientVariant] = field(default_factory=list)
    preferred_purchase_unit: Optional[str] = None
    observed_units: List[str] = field(default_factory=list)
    observed_pack_formats: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    status: str = "proposed"
    review_required: bool = True
    notes: str = ""


class IngredientMemoryRepository(ABC):
    @abstractmethod
    def create_ingredient(self, record: IngredientRecord) -> IngredientRecord:
        raise NotImplementedError

    @abstractmethod
    def get_ingredient(self, ingredient_id: str) -> Optional[IngredientRecord]:
        raise NotImplementedError

    @abstractmethod
    def find_by_normalized_key(self, normalized_key: str) -> Optional[IngredientRecord]:
        raise NotImplementedError

    @abstractmethod
    def list_ingredients(self) -> List[IngredientRecord]:
        raise NotImplementedError

    @abstractmethod
    def add_supplier_variant(
        self,
        ingredient_id: str,
        variant: SupplierIngredientVariant,
    ) -> IngredientRecord:
        raise NotImplementedError

    @abstractmethod
    def add_alias(self, ingredient_id: str, alias: str) -> IngredientRecord:
        raise NotImplementedError

    @abstractmethod
    def update_review_status(self, ingredient_id: str, status: str) -> IngredientRecord:
        raise NotImplementedError

    @abstractmethod
    def delete_ingredient(self, ingredient_id: str) -> bool:
        raise NotImplementedError


class LocalJsonIngredientMemoryRepository(IngredientMemoryRepository):
    def __init__(self, path: Path | str = DEFAULT_MEMORY_PATH):
        self.path = Path(path)
        self._ensure_store()

    def create_ingredient(self, record: IngredientRecord) -> IngredientRecord:
        data = self._read()
        normalized_key = normalize_key(record.normalized_key or record.canonical_name)
        if not normalized_key:
            raise ValueError("Ingredient normalized_key is required.")
        if record.status not in VALID_INGREDIENT_STATUSES:
            raise ValueError(f"Invalid ingredient status: {record.status}")
        if self._find_id_by_normalized_key(data, normalized_key):
            raise ValueError(f"Ingredient already exists for normalized_key: {normalized_key}")

        now = utc_now_iso()
        ingredient_id = record.ingredient_id or self._next_id(data)
        if ingredient_id in data["ingredients"]:
            raise ValueError(f"Ingredient already exists: {ingredient_id}")

        created = IngredientRecord(
            ingredient_id=ingredient_id,
            canonical_name=record.canonical_name.strip(),
            normalized_key=normalized_key,
            aliases=self._unique_strings(record.aliases),
            supplier_variants=list(record.supplier_variants),
            preferred_purchase_unit=record.preferred_purchase_unit,
            observed_units=self._unique_strings(record.observed_units),
            observed_pack_formats=self._unique_strings(record.observed_pack_formats),
            created_at=record.created_at or now,
            updated_at=now,
            status=record.status,
            review_required=record.review_required,
            notes=record.notes,
        )
        for variant in created.supplier_variants:
            if not variant.first_seen_at:
                variant.first_seen_at = now
            if not variant.last_seen_at:
                variant.last_seen_at = variant.first_seen_at
            if variant.observation_count < 1:
                variant.observation_count = 1
            self._add_observed_values(created, variant)
        data["ingredients"][ingredient_id] = self._record_to_dict(created)
        data["next_sequence"] = max(data.get("next_sequence", 1), self._id_number(ingredient_id) + 1)
        self._write(data)
        return created

    def get_ingredient(self, ingredient_id: str) -> Optional[IngredientRecord]:
        raw = self._read()["ingredients"].get(ingredient_id)
        return self._record_from_dict(raw) if raw else None

    def find_by_normalized_key(self, normalized_key: str) -> Optional[IngredientRecord]:
        data = self._read()
        ingredient_id = self._find_id_by_normalized_key(data, normalize_key(normalized_key))
        return self.get_ingredient(ingredient_id) if ingredient_id else None

    def list_ingredients(self) -> List[IngredientRecord]:
        ingredients = self._read()["ingredients"]
        return [
            self._record_from_dict(ingredients[ingredient_id])
            for ingredient_id in sorted(ingredients)
        ]

    def add_supplier_variant(
        self,
        ingredient_id: str,
        variant: SupplierIngredientVariant,
    ) -> IngredientRecord:
        data = self._read()
        raw = self._require_raw_record(data, ingredient_id)
        record = self._record_from_dict(raw)
        now = utc_now_iso()
        variant_key = variant.identity_key()

        for existing in record.supplier_variants:
            if existing.identity_key() == variant_key:
                existing.last_seen_at = variant.last_seen_at or now
                existing.observation_count = max(1, existing.observation_count) + max(1, variant.observation_count)
                existing.match_confidence = max(existing.match_confidence, variant.match_confidence)
                record.updated_at = now
                data["ingredients"][ingredient_id] = self._record_to_dict(record)
                self._write(data)
                return record

        if not variant.first_seen_at:
            variant.first_seen_at = now
        if not variant.last_seen_at:
            variant.last_seen_at = variant.first_seen_at
        if variant.observation_count < 1:
            variant.observation_count = 1
        record.supplier_variants.append(variant)
        self._add_observed_values(record, variant)
        record.updated_at = now
        data["ingredients"][ingredient_id] = self._record_to_dict(record)
        self._write(data)
        return record

    def add_alias(self, ingredient_id: str, alias: str) -> IngredientRecord:
        data = self._read()
        raw = self._require_raw_record(data, ingredient_id)
        record = self._record_from_dict(raw)
        cleaned = str(alias or "").strip()
        if not cleaned:
            raise ValueError("Alias is required.")
        existing = {normalize_key(value) for value in record.aliases}
        if normalize_key(cleaned) not in existing:
            record.aliases.append(cleaned)
            record.updated_at = utc_now_iso()
            data["ingredients"][ingredient_id] = self._record_to_dict(record)
            self._write(data)
        return record

    def update_review_status(self, ingredient_id: str, status: str) -> IngredientRecord:
        if status not in VALID_INGREDIENT_STATUSES:
            raise ValueError(f"Invalid ingredient status: {status}")
        data = self._read()
        raw = self._require_raw_record(data, ingredient_id)
        record = self._record_from_dict(raw)
        record.status = status
        record.review_required = status != "approved"
        record.updated_at = utc_now_iso()
        data["ingredients"][ingredient_id] = self._record_to_dict(record)
        self._write(data)
        return record

    def delete_ingredient(self, ingredient_id: str) -> bool:
        data = self._read()
        existed = ingredient_id in data["ingredients"]
        if existed:
            del data["ingredients"][ingredient_id]
            self._write(data)
        return existed

    def _ensure_store(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"schema_version": 1, "next_sequence": 1, "ingredients": {}})

    def _read(self) -> Dict:
        self._ensure_store()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("schema_version", 1)
        data.setdefault("next_sequence", 1)
        data.setdefault("ingredients", {})
        return data

    def _write(self, data: Dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(self.path.parent),
            delete=False,
            newline="\n",
        ) as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_path = Path(handle.name)
        temp_path.replace(self.path)

    def _next_id(self, data: Dict) -> str:
        sequence = int(data.get("next_sequence") or 1)
        while f"ING-{sequence:06d}" in data["ingredients"]:
            sequence += 1
        return f"ING-{sequence:06d}"

    def _id_number(self, ingredient_id: str) -> int:
        match = re.fullmatch(r"ING-(\d{6})", ingredient_id or "")
        return int(match.group(1)) if match else 0

    def _find_id_by_normalized_key(self, data: Dict, normalized_key: str) -> Optional[str]:
        for ingredient_id, raw in data["ingredients"].items():
            if raw.get("normalized_key") == normalized_key:
                return ingredient_id
        return None

    def _require_raw_record(self, data: Dict, ingredient_id: str) -> Dict:
        if ingredient_id not in data["ingredients"]:
            raise KeyError(f"Ingredient not found: {ingredient_id}")
        return data["ingredients"][ingredient_id]

    def _record_to_dict(self, record: IngredientRecord) -> Dict:
        raw = asdict(record)
        raw["aliases"] = self._unique_strings(raw.get("aliases", []))
        raw["observed_units"] = self._unique_strings(raw.get("observed_units", []))
        raw["observed_pack_formats"] = self._unique_strings(raw.get("observed_pack_formats", []))
        return raw

    def _record_from_dict(self, raw: Dict) -> IngredientRecord:
        variants = [
            self._variant_from_dict(variant)
            for variant in raw.get("supplier_variants", [])
        ]
        canonical_name = str(
            raw.get("canonical_name")
            or raw.get("name")
            or raw.get("display_name")
            or raw.get("normalized_key")
            or ""
        ).strip()
        normalized_key = normalize_key(raw.get("normalized_key") or canonical_name)
        status = raw.get("status", "proposed")
        if status not in VALID_INGREDIENT_STATUSES:
            status = "proposed"
        return IngredientRecord(
            ingredient_id=str(raw.get("ingredient_id") or ""),
            canonical_name=canonical_name,
            normalized_key=normalized_key,
            aliases=list(raw.get("aliases", [])),
            supplier_variants=variants,
            preferred_purchase_unit=raw.get("preferred_purchase_unit"),
            observed_units=list(raw.get("observed_units", [])),
            observed_pack_formats=list(raw.get("observed_pack_formats", [])),
            created_at=raw.get("created_at") or utc_now_iso(),
            updated_at=raw.get("updated_at") or utc_now_iso(),
            status=status,
            review_required=bool(raw.get("review_required", status != "approved")),
            notes=raw.get("notes", ""),
        )

    def _variant_from_dict(self, raw: Dict) -> SupplierIngredientVariant:
        return SupplierIngredientVariant(
            supplier_name=str(raw.get("supplier_name") or ""),
            supplier_code=raw.get("supplier_code"),
            supplier_description=str(raw.get("supplier_description") or ""),
            candidate_name=str(raw.get("candidate_name") or ""),
            purchase_unit=raw.get("purchase_unit"),
            pack_count=raw.get("pack_count"),
            pack_size_value=raw.get("pack_size_value"),
            pack_size_unit=raw.get("pack_size_unit"),
            first_seen_at=raw.get("first_seen_at") or utc_now_iso(),
            last_seen_at=raw.get("last_seen_at") or raw.get("first_seen_at") or utc_now_iso(),
            observation_count=max(1, int(raw.get("observation_count") or 1)),
            match_confidence=float(raw.get("match_confidence") or 0.0),
        )

    def _add_observed_values(
        self,
        record: IngredientRecord,
        variant: SupplierIngredientVariant,
    ) -> None:
        if variant.purchase_unit:
            self._append_unique(record.observed_units, variant.purchase_unit)
        pack_format = self._pack_format(variant)
        if pack_format:
            self._append_unique(record.observed_pack_formats, pack_format)

    def _pack_format(self, variant: SupplierIngredientVariant) -> Optional[str]:
        parts = []
        if variant.pack_count is not None:
            parts.append(self._format_number(variant.pack_count))
        if variant.pack_size_value is not None:
            size = self._format_number(variant.pack_size_value)
            if variant.pack_size_unit:
                size = f"{size}{variant.pack_size_unit}"
            parts.append(size)
        return " x ".join(parts) if parts else None

    def _format_number(self, value: float) -> str:
        number = float(value)
        return str(int(number)) if number.is_integer() else str(number)

    def _append_unique(self, values: List[str], value: str) -> None:
        if normalize_key(value) not in {normalize_key(existing) for existing in values}:
            values.append(value)

    def _unique_strings(self, values: List[str]) -> List[str]:
        result = []
        for value in values or []:
            cleaned = str(value or "").strip()
            if cleaned:
                self._append_unique(result, cleaned)
        return result
