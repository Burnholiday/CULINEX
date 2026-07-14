#!/usr/bin/env python3
"""
Canonical ingredient matching framework.

Shadow-mode only: this module proposes deterministic canonical names and
candidate equivalence diagnostics without assigning permanent IDs or merging.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re


@dataclass
class CanonicalMatchCandidate:
    source_candidate_name: str
    normalized_match_key: str
    proposed_canonical_name: Optional[str]
    match_confidence: float
    match_reasons: List[str]
    matched_signals: List[str]
    conflicting_signals: List[str]
    canonical_match_id: Optional[str]
    canonical_match_confidence: float
    alternative_candidates: List[Dict[str, Any]]
    review_required: bool
    modifier_tokens: Dict[str, List[str]] = field(default_factory=dict)
    modifier_conflicts: List[str] = field(default_factory=list)
    confidence_cap_reason: Optional[str] = None
    packaging_identity_tokens: List[str] = field(default_factory=list)
    ingredient_conflict_cap_applied: bool = False
    proposal_generated: bool = False
    proposal_id: Optional[str] = None
    proposal_type: Optional[str] = None
    proposal_status: Optional[str] = None
    proposal_reason: Optional[str] = None
    proposal_error: Optional[str] = None


class IngredientMatcher:
    """Deterministic, supplier-agnostic ingredient matcher."""

    def __init__(self, memory_repository: Any = None, proposal_engine: Any = None):
        self.memory_repository = memory_repository
        self.proposal_engine = proposal_engine

    _unit_tokens = {
        "kg", "g", "gr", "gram", "grams", "l", "lt", "liter", "litre",
        "liters", "litres", "ml", "ea", "each", "unit", "units",
        "pkt", "packet", "packets", "punnet", "punnets", "lb", "lbs", "s",
    }
    _packaging_tokens = {"pack", "case", "carton", "tray", "tin", "can"}
    _packaging_identity_terms = {
        "bag", "box", "roll", "poly", "vacuum", "refuse", "lunch",
        "pack", "case", "carton", "tray", "tin", "can",
    }
    _colours = {
        "red", "green", "yellow", "black", "white", "brown", "orange",
        "purple",
    }
    _cuts = {
        "whole", "breast", "fillet", "fillets", "diced", "sliced",
        "chopped", "minced", "coarse", "skin", "skins", "wrappers",
    }
    _preparations = {
        "fresh", "smoked", "salted", "pitted", "frozen", "dried",
        "pickled", "roasted",
    }
    _style_terms = {
        "baby", "large", "medium", "small", "loose", "flat", "italian",
        "granny", "smith", "herb", "rocket", "kewpie", "happy", "belly",
        "pocket",
    }
    _product_nouns = {
        "tomato", "lemon", "lime", "pepper", "apple", "potato", "garlic",
        "ginger", "onion", "salmon", "chicken", "butternut", "carrot",
        "beetroot", "banana", "cucumber", "broccoli", "cauliflower",
        "marrow", "rocket", "milk", "butter", "sugar", "bag", "box",
        "rice", "vinegar", "mayonnaise", "cheese", "flour", "oil",
    }
    _plural_map = {
        "tomatoes": "tomato",
        "tomatoe": "tomato",
        "lemons": "lemon",
        "limes": "lime",
        "peppers": "pepper",
        "apples": "apple",
        "potatoes": "potato",
        "chillies": "chilli",
        "marrows": "marrow",
        "berries": "berry",
        "strawberries": "strawberry",
        "blueberries": "blueberry",
        "wrappers": "wrapper",
        "skins": "skin",
    }

    def analyze_candidate(self, ingredient_candidate: Any, context: Optional[Dict] = None) -> Optional[CanonicalMatchCandidate]:
        source_name = self._candidate_name(ingredient_candidate)
        normalized_key = self.normalized_match_key(self._candidate_match_text(ingredient_candidate))
        if not normalized_key:
            return None

        proposed_name = self._display_name(normalized_key)
        matched_signals = ["Meaningful normalized identity key generated"]
        conflicting_signals = []
        reasons = ["Shadow-mode canonical suggestion only"]
        confidence = 0.65
        confidence_cap_reason = None
        ingredient_conflict_cap_applied = False

        tokens = normalized_key.split()
        modifier_tokens = self._modifier_tokens(tokens)
        packaging_identity_tokens = self._packaging_identity_tokens(tokens)
        if any(token in self._product_nouns for token in tokens):
            confidence += 0.15
            matched_signals.append("Contains recognizable product noun")
        if len(tokens) >= 2:
            confidence += 0.05
            matched_signals.append("Contains descriptive identity terms")
        ingredient_conflicts = self._ingredient_conflicts(ingredient_candidate)
        if self._has_merged_warning(ingredient_candidate):
            conflicting_signals.append("Ingredient candidate has merged-product warning")
        if self._has_numeric_ambiguity(ingredient_candidate):
            conflicting_signals.append("Ingredient candidate has numeric ambiguity")
        if self._weak_candidate_name(source_name):
            conflicting_signals.append("Weak candidate name")
        if self._noise_heavy(source_name) or self._has_ocr_noise(ingredient_candidate):
            conflicting_signals.append("OCR-noise-heavy candidate")
        if len(tokens) < 1:
            confidence = 0.0
            conflicting_signals.append("Insufficient identity words")
        cap, cap_reason = self._ingredient_conflict_cap(ingredient_candidate, source_name)
        if cap is not None:
            confidence = min(confidence, cap)
            confidence_cap_reason = cap_reason
            ingredient_conflict_cap_applied = True
            if ingredient_conflicts:
                matched = set(conflicting_signals)
                conflicting_signals.extend(signal for signal in ingredient_conflicts if signal not in matched)

        confidence = self._clamp(confidence)
        return CanonicalMatchCandidate(
            source_candidate_name=source_name,
            normalized_match_key=normalized_key,
            proposed_canonical_name=proposed_name,
            match_confidence=confidence,
            match_reasons=reasons,
            matched_signals=matched_signals,
            conflicting_signals=conflicting_signals,
            canonical_match_id=None,
            canonical_match_confidence=0.0,
            alternative_candidates=[],
            review_required=True,
            modifier_tokens=modifier_tokens,
            modifier_conflicts=[],
            confidence_cap_reason=confidence_cap_reason,
            packaging_identity_tokens=packaging_identity_tokens,
            ingredient_conflict_cap_applied=ingredient_conflict_cap_applied,
        )

    def match_ingredient(
        self,
        ingredient_candidate: Any,
        context: Optional[Dict] = None,
        generate_proposals: bool = False,
        proposal_engine: Any = None,
    ) -> Optional[CanonicalMatchCandidate]:
        result = self.analyze_candidate(ingredient_candidate, context=context)
        if result is None:
            return None
        if not generate_proposals:
            return result

        engine = proposal_engine or self.proposal_engine
        memory_repository = self.memory_repository or getattr(engine, "memory_repository", None)
        existing = self._find_memory_match(result, ingredient_candidate, memory_repository)
        if existing and self._is_safe_existing_match(existing, result, ingredient_candidate):
            result.canonical_match_id = self._ingredient_id(existing)
            result.canonical_match_confidence = max(result.canonical_match_confidence, 0.95)
            result.matched_signals.append("Safe existing Ingredient Memory match")
            result.proposal_reason = "Safe existing Ingredient Memory match"
            return result

        if engine is None:
            result.proposal_error = "Proposal generation requested without a proposal engine"
            return result

        try:
            proposal = engine.create_proposal(
                self._proposal_candidate_payload(ingredient_candidate, context),
                result,
                context=context,
            )
            result.proposal_generated = True
            result.proposal_id = proposal.proposal_id
            result.proposal_type = proposal.proposal_type
            result.proposal_status = proposal.status
            result.proposal_reason = "; ".join(proposal.reasons)
        except ValueError as exc:
            existing_proposal = self._proposal_from_duplicate_error(engine, exc)
            if existing_proposal:
                result.proposal_generated = False
                result.proposal_id = existing_proposal.proposal_id
                result.proposal_type = existing_proposal.proposal_type
                result.proposal_status = existing_proposal.status
                result.proposal_reason = "Equivalent proposal already exists"
            else:
                result.proposal_error = str(exc)
        except Exception as exc:
            result.proposal_error = f"Unable to persist ingredient proposal: {exc}"
        return result

    def compare_candidates(self, left: Any, right: Any) -> CanonicalMatchCandidate:
        left_name = self._candidate_name(left)
        right_name = self._candidate_name(right)
        left_key = self.normalized_match_key(self._candidate_match_text(left))
        right_key = self.normalized_match_key(self._candidate_match_text(right))
        matched_signals = []
        conflicting_signals = []
        reasons = []
        confidence_cap_reason = None
        ingredient_conflict_cap_applied = False
        modifier_conflicts = []

        if not left_key or not right_key:
            conflicting_signals.append("Insufficient identity words")
            confidence = 0.0
        elif left_key == right_key:
            confidence = 0.95
            matched_signals.append("Exact normalized key match")
            reasons.append("Equivalent after deterministic normalization")
        else:
            left_tokens = left_key.split()
            right_tokens = right_key.split()
            left_set = set(left_tokens)
            right_set = set(right_tokens)
            same_core = self._same_core_product(left_tokens, right_tokens)
            confidence = 0.25

            if left_set == right_set:
                confidence = max(confidence, 0.88)
                matched_signals.append("Reordered equivalent tokens")
            if same_core:
                confidence = max(confidence, 0.62)
                matched_signals.append("Same core product noun")
            if same_core and self._same_modifier_profile(left_tokens, right_tokens):
                confidence = max(confidence, 0.9)
                matched_signals.append("Same core product plus same variety/cut/style terms")

            conflicts = self._conflicting_attributes(left_tokens, right_tokens)
            if conflicts:
                conflicting_signals.extend(conflicts)
                confidence = min(confidence, 0.45)
                modifier_conflicts.extend(conflicts)
                confidence_cap_reason = "conflicting modifier evidence"
            elif same_core and self._has_missing_modifier_evidence(left_tokens, right_tokens):
                confidence = min(confidence, 0.7)
                modifier_conflicts.append("Missing modifier evidence")
                confidence_cap_reason = "same core with missing modifier evidence"
            if same_core and self._packaging_type_mismatch(left_tokens, right_tokens):
                conflicting_signals.append("Packaging-type mismatch")
                modifier_conflicts.append("Packaging-type mismatch")
                confidence = min(confidence, 0.45)
                confidence_cap_reason = "packaging-type mismatch"
            if not same_core:
                conflicting_signals.append("Materially different product nouns")
                confidence = min(confidence, 0.35)
            if self._has_merged_warning(left) or self._has_merged_warning(right):
                conflicting_signals.append("Merged-product warning")
                confidence = min(confidence, 0.6)
                confidence_cap_reason = "merged-product or OCR ambiguity"
                ingredient_conflict_cap_applied = True
            if self._has_numeric_ambiguity(left) or self._has_numeric_ambiguity(right):
                conflicting_signals.append("Numeric ambiguity")
                confidence = min(confidence, 0.6)
                confidence_cap_reason = "merged-product or OCR ambiguity"
                ingredient_conflict_cap_applied = True
            if self._noise_heavy(left_name) or self._noise_heavy(right_name) or self._has_ocr_noise(left) or self._has_ocr_noise(right):
                conflicting_signals.append("OCR-noise-heavy candidate")
                confidence = min(confidence, 0.6)
                confidence_cap_reason = "merged-product or OCR ambiguity"
                ingredient_conflict_cap_applied = True
            if self._weak_candidate_name(left_name) or self._weak_candidate_name(right_name):
                conflicting_signals.append("Weak candidate name")
                confidence = min(confidence, 0.6)
                confidence_cap_reason = "weak candidate name"
                ingredient_conflict_cap_applied = True

        left_cap, left_cap_reason = self._ingredient_conflict_cap(left, left_name)
        right_cap, right_cap_reason = self._ingredient_conflict_cap(right, right_name)
        ingredient_caps = [cap for cap in (left_cap, right_cap) if cap is not None]
        if ingredient_caps:
            confidence = min(confidence, min(ingredient_caps))
            confidence_cap_reason = left_cap_reason or right_cap_reason
            ingredient_conflict_cap_applied = True
            for signal in self._ingredient_conflicts(left) + self._ingredient_conflicts(right):
                if signal not in conflicting_signals:
                    conflicting_signals.append(signal)

        left_tokens = left_key.split() if left_key else []
        right_tokens = right_key.split() if right_key else []
        modifier_tokens = {
            "left": self._modifier_tokens(left_tokens),
            "right": self._modifier_tokens(right_tokens),
        }
        packaging_identity_tokens = sorted(
            set(self._packaging_identity_tokens(left_tokens))
            | set(self._packaging_identity_tokens(right_tokens))
        )

        source = f"{left_name} <> {right_name}".strip()
        canonical_key = left_key if left_key == right_key else left_key
        alternative = {
            "source_candidate_name": right_name,
            "normalized_match_key": right_key,
            "proposed_canonical_name": self._display_name(right_key) if right_key else None,
        }
        conflicting_signals = self._dedupe_adjacent(conflicting_signals)
        modifier_conflicts = self._dedupe_adjacent(modifier_conflicts)
        return CanonicalMatchCandidate(
            source_candidate_name=source,
            normalized_match_key=canonical_key,
            proposed_canonical_name=self._display_name(canonical_key) if canonical_key else None,
            match_confidence=self._clamp(confidence),
            match_reasons=reasons,
            matched_signals=matched_signals,
            conflicting_signals=conflicting_signals,
            canonical_match_id=None,
            canonical_match_confidence=0.0,
            alternative_candidates=[alternative],
            review_required=True,
            modifier_tokens=modifier_tokens,
            modifier_conflicts=modifier_conflicts,
            confidence_cap_reason=confidence_cap_reason,
            packaging_identity_tokens=packaging_identity_tokens,
            ingredient_conflict_cap_applied=ingredient_conflict_cap_applied,
        )

    def analyze_many(self, candidates: List[Any]) -> List[CanonicalMatchCandidate]:
        results = []
        for candidate in candidates:
            analyzed = self.analyze_candidate(candidate)
            if analyzed:
                results.append(analyzed)
        return results

    def _find_memory_match(
        self,
        result: CanonicalMatchCandidate,
        ingredient_candidate: Any,
        memory_repository: Any,
    ) -> Any:
        if memory_repository is None:
            return None
        normalized_key = result.normalized_match_key
        try:
            existing = memory_repository.find_by_normalized_key(normalized_key)
            if existing:
                return existing
            for record in memory_repository.list_ingredients():
                if self._record_has_alias(record, normalized_key):
                    return record
                if self._record_has_supplier_variant(record, ingredient_candidate):
                    return record
        except Exception:
            return None
        return None

    def _is_safe_existing_match(
        self,
        record: Any,
        result: CanonicalMatchCandidate,
        ingredient_candidate: Any,
    ) -> bool:
        if self._record_status(record) != "approved":
            return False
        normalized_key = result.normalized_match_key
        if getattr(record, "normalized_key", None) == normalized_key:
            return result.match_confidence >= 0.9 or not result.conflicting_signals
        return (
            self._record_has_alias(record, normalized_key)
            or self._record_has_supplier_variant(record, ingredient_candidate)
        )

    def _record_has_alias(self, record: Any, normalized_key: str) -> bool:
        return any(
            self.normalized_match_key(alias) == normalized_key
            for alias in getattr(record, "aliases", []) or []
        )

    def _record_has_supplier_variant(self, record: Any, ingredient_candidate: Any) -> bool:
        candidate_code = self._candidate_field(ingredient_candidate, "supplier_code")
        candidate_description = self._candidate_field(ingredient_candidate, "supplier_description")
        candidate_name = self._candidate_name(ingredient_candidate)
        for variant in getattr(record, "supplier_variants", []) or []:
            if candidate_code and candidate_code == getattr(variant, "supplier_code", None):
                return True
            if candidate_description and candidate_description == getattr(variant, "supplier_description", None):
                return True
            if candidate_name and candidate_name == getattr(variant, "candidate_name", None):
                return True
        return False

    def _proposal_candidate_payload(self, ingredient_candidate: Any, context: Optional[Dict]) -> Dict[str, Any]:
        context = context or {}
        payload = {
            "candidate_name": self._candidate_name(ingredient_candidate),
            "supplier_description": self._supplier_description(ingredient_candidate),
            "supplier_name": context.get("supplier_name") or self._candidate_field(ingredient_candidate, "supplier_name"),
            "supplier_code": context.get("supplier_code") or self._candidate_field(ingredient_candidate, "supplier_code"),
            "conflicting_signals": self._ingredient_conflicts(ingredient_candidate),
        }
        return payload

    def _proposal_from_duplicate_error(self, engine: Any, error: Any) -> Any:
        proposal_id = getattr(error, "proposal_id", None)
        if not proposal_id:
            match = re.search(r"(PROP-\d{6})", str(error or ""))
            if not match:
                return None
            proposal_id = match.group(1)
        repository = getattr(engine, "proposal_repository", None)
        if repository is None:
            return None
        try:
            return repository.get_proposal(proposal_id)
        except Exception:
            return None

    def _ingredient_id(self, record: Any) -> Optional[str]:
        return getattr(record, "ingredient_id", None)

    def _record_status(self, record: Any) -> str:
        return str(getattr(record, "status", "") or "").strip().lower()

    def _candidate_field(self, candidate: Any, field_name: str) -> Optional[str]:
        if isinstance(candidate, dict):
            value = candidate.get(field_name)
        elif candidate is not None and not isinstance(candidate, str):
            value = getattr(candidate, field_name, None)
        else:
            value = None
        return str(value).strip() if value is not None and str(value).strip() else None

    def normalized_match_key(self, value: str) -> str:
        text = str(value or "").lower()
        is_packaging = self._looks_like_packaging(text)
        packaging_evidence = self._packaging_evidence_tokens(text) if is_packaging else []
        text = re.sub(r"\d+(?:\.\d+)?\s*[xX]\s*\d+(?:\.\d+)?(?:\s*[xX]\s*\d+(?:\.\d+)?)?", " ", text)
        text = re.sub(r"\d+(?:\.\d+)?\s*(?:kg|g|gr|l|lt|ml|mc|mic|lb|lbs)\b", " ", text)
        text = re.sub(r"[^a-z0-9\s/]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        tokens = []
        for token in text.split():
            normalized = self._normalize_token(token)
            if not normalized:
                continue
            if normalized in self._unit_tokens:
                continue
            if normalized in self._packaging_tokens and len(text.split()) > 1:
                continue
            tokens.append(normalized)

        tokens.extend(packaging_evidence)
        tokens = self._dedupe_adjacent(tokens)
        tokens = self._remove_duplicate_product_terms(tokens)
        tokens = self._canonical_order(tokens)
        return " ".join(tokens)

    def _candidate_match_text(self, candidate: Any) -> str:
        name = self._candidate_name(candidate)
        description = self._supplier_description(candidate)
        if name and self._looks_like_packaging(name) and description:
            return f"{name} {description}".strip()
        return name

    def _candidate_name(self, candidate: Any) -> str:
        if candidate is None:
            return ""
        if isinstance(candidate, str):
            return candidate.strip()
        if isinstance(candidate, dict):
            return str(candidate.get("candidate_name") or candidate.get("source_candidate_name") or "").strip()
        return str(getattr(candidate, "candidate_name", "") or getattr(candidate, "source_candidate_name", "") or "").strip()

    def _supplier_description(self, candidate: Any) -> str:
        if isinstance(candidate, dict):
            return str(candidate.get("supplier_description") or "").strip()
        if candidate is not None and not isinstance(candidate, str):
            return str(getattr(candidate, "supplier_description", "") or "").strip()
        return ""

    def _normalize_token(self, token: str) -> str:
        token = token.strip().lower()
        if not token or token.isdigit():
            return ""
        if token in self._plural_map:
            return self._plural_map[token]
        if len(token) > 4 and token.endswith("ies"):
            return token[:-3] + "y"
        if len(token) > 3 and token.endswith("oes"):
            return token[:-2]
        if len(token) > 3 and token.endswith("es"):
            base = token[:-2]
            if base in self._product_nouns:
                return base
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            base = token[:-1]
            if base in self._product_nouns or base in self._style_terms:
                return base
        return token

    def _dedupe_adjacent(self, tokens: List[str]) -> List[str]:
        deduped = []
        for token in tokens:
            if not deduped or deduped[-1] != token:
                deduped.append(token)
        return deduped

    def _remove_duplicate_product_terms(self, tokens: List[str]) -> List[str]:
        result = []
        seen = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            result.append(token)
        return result

    def _canonical_order(self, tokens: List[str]) -> List[str]:
        if not tokens:
            return []
        token_set = set(tokens)
        if "pepper" in token_set:
            ordered = [token for token in tokens if token in self._colours]
            ordered += [token for token in tokens if token == "pepper"]
            ordered += [token for token in tokens if token not in set(ordered)]
            return ordered
        if "apple" in token_set:
            ordered = [token for token in tokens if token in {"granny", "smith", "green"}]
            ordered += [token for token in tokens if token == "apple"]
            ordered += [token for token in tokens if token not in set(ordered)]
            return ordered
        if "potato" in token_set and "baby" in token_set:
            ordered = [token for token in tokens if token == "baby"]
            ordered += [token for token in tokens if token == "potato"]
            ordered += [token for token in tokens if token not in set(ordered)]
            return ordered
        return tokens

    def _same_core_product(self, left_tokens: List[str], right_tokens: List[str]) -> bool:
        left_products = set(left_tokens) & self._product_nouns
        right_products = set(right_tokens) & self._product_nouns
        return bool(left_products and right_products and left_products == right_products)

    def _same_modifier_profile(self, left_tokens: List[str], right_tokens: List[str]) -> bool:
        left_modifiers = self._modifier_tokens(left_tokens)
        right_modifiers = self._modifier_tokens(right_tokens)
        return all(
            set(left_modifiers.get(group, [])) == set(right_modifiers.get(group, []))
            for group in left_modifiers
        )

    def _conflicting_attributes(self, left_tokens: List[str], right_tokens: List[str]) -> List[str]:
        conflicts = []
        left = self._modifier_tokens(left_tokens)
        right = self._modifier_tokens(right_tokens)
        labels = {
            "colour": "Conflicting colour",
            "variety": "Conflicting variety",
            "cut_form": "Conflicting cut/form",
            "preparation": "Conflicting preparation",
            "size_age": "Conflicting size/age",
            "packaging_type": "Packaging-type mismatch",
        }
        for group, label in labels.items():
            left_values = set(left.get(group, []))
            right_values = set(right.get(group, []))
            if left_values and right_values and left_values != right_values:
                conflicts.append(label)
        return conflicts

    def _modifier_tokens(self, tokens: List[str]) -> Dict[str, List[str]]:
        token_set = set(tokens)
        modifiers = {
            "colour": sorted(token_set & self._colours),
            "variety": sorted(token_set & {"granny", "smith", "kewpie", "nola", "clover", "cerebos", "huletts"}),
            "cut_form": sorted(token_set & (self._cuts | {"loose", "pocket", "head", "heads", "loaf"})),
            "preparation": sorted(token_set & self._preparations),
            "size_age": sorted(token_set & {"baby", "large", "medium", "small"}),
            "packaging_type": sorted(token_set & self._packaging_identity_terms),
        }
        return modifiers

    def _has_missing_modifier_evidence(self, left_tokens: List[str], right_tokens: List[str]) -> bool:
        left = self._modifier_tokens(left_tokens)
        right = self._modifier_tokens(right_tokens)
        for group in ("colour", "variety", "cut_form", "preparation", "size_age", "packaging_type"):
            if bool(left.get(group)) != bool(right.get(group)):
                return True
        return False

    def _packaging_type_mismatch(self, left_tokens: List[str], right_tokens: List[str]) -> bool:
        left_packaging = set(self._packaging_identity_tokens(left_tokens))
        right_packaging = set(self._packaging_identity_tokens(right_tokens))
        return bool(left_packaging and right_packaging and left_packaging != right_packaging)

    def _looks_like_packaging(self, text: str) -> bool:
        tokens = set(re.findall(r"[a-zA-Z]+", str(text or "").lower()))
        return bool(tokens & self._packaging_identity_terms)

    def _packaging_identity_tokens(self, tokens: List[str]) -> List[str]:
        return [token for token in tokens if token in self._packaging_identity_terms or token.startswith(("dim_", "count_"))]

    def _packaging_evidence_tokens(self, text: str) -> List[str]:
        text = str(text or "").lower()
        evidence = []
        for match in re.findall(r"\b\d+(?:\.\d+)?\s*x\s*\d+(?:\.\d+)?(?:\s*x\s*\d+(?:\.\d+)?)?\b", text):
            evidence.append("dim_" + re.sub(r"\s+", "", match))
        for match in re.findall(r"\(\s*\d+\s*'?s\s*\)|\b\d+\s*'?s\b", text):
            digits = re.sub(r"\D", "", match)
            if digits:
                evidence.append(f"count_{digits}")
        return evidence

    def _has_merged_warning(self, candidate: Any) -> bool:
        signals = self._ingredient_conflicts(candidate)
        return any("merged" in str(signal).lower() for signal in signals)

    def _has_numeric_ambiguity(self, candidate: Any) -> bool:
        signals = self._ingredient_conflicts(candidate)
        return any("numeric" in str(signal).lower() or "ambigu" in str(signal).lower() for signal in signals)

    def _has_ocr_noise(self, candidate: Any) -> bool:
        signals = self._ingredient_conflicts(candidate)
        return any("ocr" in str(signal).lower() or "noise" in str(signal).lower() for signal in signals)

    def _ingredient_conflicts(self, candidate: Any) -> List[str]:
        if isinstance(candidate, dict):
            return list(candidate.get("conflicting_signals") or [])
        if candidate is not None and not isinstance(candidate, str):
            return list(getattr(candidate, "conflicting_signals", []) or [])
        return []

    def _ingredient_conflict_cap(self, candidate: Any, candidate_name: str) -> tuple:
        if self._has_merged_warning(candidate):
            return 0.6, "merged-product or OCR ambiguity"
        if self._has_numeric_ambiguity(candidate):
            return 0.6, "merged-product or OCR ambiguity"
        if self._noise_heavy(candidate_name) or self._has_ocr_noise(candidate):
            return 0.6, "merged-product or OCR ambiguity"
        if self._weak_candidate_name(candidate_name):
            return 0.6, "weak candidate name"
        return None, None

    def _weak_candidate_name(self, text: str) -> bool:
        tokens = re.findall(r"[A-Za-z]+", str(text or ""))
        return not tokens or (len(tokens) == 1 and len(tokens[0]) <= 2)

    def _noise_heavy(self, text: str) -> bool:
        if not text:
            return True
        punctuation = len(re.findall(r"[^A-Za-z0-9\s]", text))
        letters = len(re.findall(r"[A-Za-z]", text))
        return letters == 0 or punctuation > max(2, letters // 3)

    def _display_name(self, normalized_key: str) -> Optional[str]:
        if not normalized_key:
            return None
        return " ".join(token.capitalize() for token in normalized_key.split())

    def _clamp(self, value: float) -> float:
        return round(max(0.0, min(1.0, value)), 3)
