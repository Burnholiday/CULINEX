from __future__ import annotations

from dataclasses import dataclass


class UnitConversionError(ValueError):
    pass


@dataclass(frozen=True)
class UnitDefinition:
    dimension: str
    factor_to_base: float
    display_unit: str


class UnitConverter:
    """Normalizes units to base units so reports can aggregate accurately."""

    UNITS: dict[str, UnitDefinition] = {
        "g": UnitDefinition("mass", 1.0, "kg"),
        "gram": UnitDefinition("mass", 1.0, "kg"),
        "grams": UnitDefinition("mass", 1.0, "kg"),
        "kg": UnitDefinition("mass", 1000.0, "kg"),
        "kilogram": UnitDefinition("mass", 1000.0, "kg"),
        "kilograms": UnitDefinition("mass", 1000.0, "kg"),
        "ml": UnitDefinition("volume", 1.0, "L"),
        "millilitre": UnitDefinition("volume", 1.0, "L"),
        "milliliter": UnitDefinition("volume", 1.0, "L"),
        "l": UnitDefinition("volume", 1000.0, "L"),
        "lt": UnitDefinition("volume", 1000.0, "L"),
        "liter": UnitDefinition("volume", 1000.0, "L"),
        "litre": UnitDefinition("volume", 1000.0, "L"),
        "tsp": UnitDefinition("volume", 5.0, "L"),
        "teaspoon": UnitDefinition("volume", 5.0, "L"),
        "tbsp": UnitDefinition("volume", 15.0, "L"),
        "tablespoon": UnitDefinition("volume", 15.0, "L"),
        "cup": UnitDefinition("volume", 250.0, "L"),
        "unit": UnitDefinition("count", 1.0, "unit"),
        "piece": UnitDefinition("count", 1.0, "unit"),
        "pieces": UnitDefinition("count", 1.0, "unit"),
        "each": UnitDefinition("count", 1.0, "unit"),
    }

    @classmethod
    def canonical(cls, unit: str) -> str:
        normalized = unit.strip().lower()
        if normalized not in cls.UNITS:
            raise UnitConversionError(f"Unsupported unit: {unit}")
        return normalized

    @classmethod
    def dimension(cls, unit: str) -> str:
        return cls.UNITS[cls.canonical(unit)].dimension

    @classmethod
    def to_base(cls, quantity: float, unit: str) -> tuple[float, str]:
        definition = cls.UNITS[cls.canonical(unit)]
        base_unit = {"mass": "g", "volume": "ml", "count": "unit"}[definition.dimension]
        return quantity * definition.factor_to_base, base_unit

    @classmethod
    def from_base_for_display(cls, quantity: float, base_unit: str) -> tuple[float, str]:
        base = cls.canonical(base_unit)
        dimension = cls.UNITS[base].dimension
        if dimension == "mass" and abs(quantity) >= 1000:
            return quantity / 1000, "kg"
        if dimension == "volume" and abs(quantity) >= 1000:
            return quantity / 1000, "L"
        if dimension == "count":
            return quantity, "unit"
        return quantity, {"mass": "g", "volume": "ml"}[dimension]

    @classmethod
    def convert(cls, quantity: float, from_unit: str, to_unit: str) -> float:
        from_def = cls.UNITS[cls.canonical(from_unit)]
        to_def = cls.UNITS[cls.canonical(to_unit)]
        if from_def.dimension != to_def.dimension:
            raise UnitConversionError(f"Cannot convert {from_unit} to {to_unit}")
        base_quantity = quantity * from_def.factor_to_base
        return base_quantity / to_def.factor_to_base
