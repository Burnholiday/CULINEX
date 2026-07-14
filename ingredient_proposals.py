#!/usr/bin/env python3
"""
Review-only ingredient proposal workflow.

This module bridges canonical ingredient suggestions to Ingredient Memory
without automatic approval, parser integration, merging, or production writes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional

from ingredient_memory import (
    DEFAULT_MEMORY_PATH,
    IngredientMemoryRepository,
    IngredientRecord,
    LocalJsonIngredientMemoryRepository,
    SupplierIngredientVariant,
    normalize_key,
    utc_now_iso,
)


DEFAULT_PROPOSAL_PATH = Path("data") / "ingredient-proposals.json"
PROPOSAL_TYPES = {
    "create_new",
    "attach_alias",
    "attach_supplier_variant",
    "possible_merge",
    "insufficient_evidence",
}
PROPOSAL_STATUSES = {"pending", "approved", "rejected", "deferred"}


class DuplicateProposalError(ValueError):
    def __init__(self, proposal_id: str):
        super().__init__(f"Duplicate proposal already exists: {proposal_id}")
        self.proposal_id = proposal_id


@dataclass
class IngredientProposal:
    proposal_id: str
    source_filename: Optional[str]
    source_row_id: Optional[str]
    supplier_name: Optional[str]
    supplier_code: Optional[str]
    supplier_description: str
    candidate_name: str
    normalized_match_key: str
    proposed_canonical_name: Optional[str]
    canonical_match_confidence: float
    existing_ingredient_id: Optional[str]
    proposal_type: str
    status: str
    reasons: List[str] = field(default_factory=list)
    conflicting_signals: List[str] = field(default_factory=list)
    matched_signals: List[str] = field(default_factory=list)
    modifier_tokens: Dict[str, Any] = field(default_factory=dict)
    packaging_identity_tokens: List[str] = field(default_factory=list)
    confidence_cap_reason: Optional[str] = None
    ingredient_conflict_cap_applied: bool = False
    observation_count: int = 1
    created_at: str = field(default_factory=utc_now_iso)
    reviewed_at: Optional[str] = None
    reviewer_note: str = ""

    def duplicate_key(self) -> str:
        parts = [
            self.source_filename or "",
            self.source_row_id or "",
            self.supplier_name or "",
            self.supplier_code or "",
            self.supplier_description,
            self.candidate_name,
            self.normalized_match_key,
            self.proposal_type,
            self.existing_ingredient_id or "",
        ]
        return "|".join(normalize_key(part) for part in parts)


class LocalJsonIngredientProposalRepository:
    def __init__(self, path: Path | str = DEFAULT_PROPOSAL_PATH):
        self.path = Path(path)
        self._ensure_store()

    def create_proposal(self, proposal: IngredientProposal) -> IngredientProposal:
        if proposal.proposal_type not in PROPOSAL_TYPES:
            raise ValueError(f"Invalid proposal type: {proposal.proposal_type}")
        if proposal.status not in PROPOSAL_STATUSES:
            raise ValueError(f"Invalid proposal status: {proposal.status}")
        data = self._read()
        duplicate_id = self._find_duplicate_id(data, proposal.duplicate_key())
        if duplicate_id:
            raise DuplicateProposalError(duplicate_id)

        proposal_id = proposal.proposal_id or self._next_id(data)
        if proposal_id in data["proposals"]:
            raise ValueError(f"Proposal already exists: {proposal_id}")
        created = IngredientProposal(
            proposal_id=proposal_id,
            source_filename=proposal.source_filename,
            source_row_id=proposal.source_row_id,
            supplier_name=proposal.supplier_name,
            supplier_code=proposal.supplier_code,
            supplier_description=proposal.supplier_description,
            candidate_name=proposal.candidate_name,
            normalized_match_key=proposal.normalized_match_key,
            proposed_canonical_name=proposal.proposed_canonical_name,
            canonical_match_confidence=proposal.canonical_match_confidence,
            existing_ingredient_id=proposal.existing_ingredient_id,
            proposal_type=proposal.proposal_type,
            status=proposal.status,
            reasons=list(proposal.reasons),
            conflicting_signals=list(proposal.conflicting_signals),
            matched_signals=list(proposal.matched_signals),
            modifier_tokens=dict(proposal.modifier_tokens),
            packaging_identity_tokens=list(proposal.packaging_identity_tokens),
            confidence_cap_reason=proposal.confidence_cap_reason,
            ingredient_conflict_cap_applied=proposal.ingredient_conflict_cap_applied,
            observation_count=max(1, int(proposal.observation_count or 1)),
            created_at=proposal.created_at or utc_now_iso(),
            reviewed_at=proposal.reviewed_at,
            reviewer_note=proposal.reviewer_note,
        )
        data["proposals"][proposal_id] = self._proposal_to_dict(created)
        data["next_sequence"] = max(data.get("next_sequence", 1), self._id_number(proposal_id) + 1)
        self._write(data)
        return created

    def get_proposal(self, proposal_id: str) -> Optional[IngredientProposal]:
        raw = self._read()["proposals"].get(proposal_id)
        return self._proposal_from_dict(raw) if raw else None

    def list_proposals(self) -> List[IngredientProposal]:
        proposals = self._read()["proposals"]
        return [
            self._proposal_from_dict(proposals[proposal_id])
            for proposal_id in sorted(proposals)
        ]

    def update_proposal(self, proposal: IngredientProposal) -> IngredientProposal:
        if proposal.status not in PROPOSAL_STATUSES:
            raise ValueError(f"Invalid proposal status: {proposal.status}")
        data = self._read()
        if proposal.proposal_id not in data["proposals"]:
            raise KeyError(f"Proposal not found: {proposal.proposal_id}")
        data["proposals"][proposal.proposal_id] = self._proposal_to_dict(proposal)
        self._write(data)
        return proposal

    def _ensure_store(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({"schema_version": 1, "next_sequence": 1, "proposals": {}})

    def _read(self) -> Dict:
        self._ensure_store()
        with self.path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("schema_version", 1)
        data.setdefault("next_sequence", 1)
        data.setdefault("proposals", {})
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
        while f"PROP-{sequence:06d}" in data["proposals"]:
            sequence += 1
        return f"PROP-{sequence:06d}"

    def _id_number(self, proposal_id: str) -> int:
        if not str(proposal_id or "").startswith("PROP-"):
            return 0
        suffix = str(proposal_id).split("-", 1)[1]
        return int(suffix) if suffix.isdigit() else 0

    def _find_duplicate_id(self, data: Dict, duplicate_key: str) -> Optional[str]:
        for proposal_id, raw in data["proposals"].items():
            existing = self._proposal_from_dict(raw)
            if existing.duplicate_key() == duplicate_key:
                return proposal_id
        return None

    def _proposal_to_dict(self, proposal: IngredientProposal) -> Dict:
        return asdict(proposal)

    def _proposal_from_dict(self, raw: Dict) -> IngredientProposal:
        proposal_type = raw.get("proposal_type", "insufficient_evidence")
        if proposal_type not in PROPOSAL_TYPES:
            proposal_type = "insufficient_evidence"
        status = raw.get("status", "pending")
        if status not in PROPOSAL_STATUSES:
            status = "pending"
        return IngredientProposal(
            proposal_id=str(raw.get("proposal_id") or ""),
            source_filename=raw.get("source_filename"),
            source_row_id=raw.get("source_row_id"),
            supplier_name=raw.get("supplier_name"),
            supplier_code=raw.get("supplier_code"),
            supplier_description=raw.get("supplier_description", ""),
            candidate_name=raw.get("candidate_name", ""),
            normalized_match_key=raw.get("normalized_match_key", ""),
            proposed_canonical_name=raw.get("proposed_canonical_name"),
            canonical_match_confidence=float(raw.get("canonical_match_confidence") or 0.0),
            existing_ingredient_id=raw.get("existing_ingredient_id"),
            proposal_type=proposal_type,
            status=status,
            reasons=list(raw.get("reasons", [])),
            conflicting_signals=list(raw.get("conflicting_signals", [])),
            matched_signals=list(raw.get("matched_signals", [])),
            modifier_tokens=dict(raw.get("modifier_tokens", {})),
            packaging_identity_tokens=list(raw.get("packaging_identity_tokens", [])),
            confidence_cap_reason=raw.get("confidence_cap_reason"),
            ingredient_conflict_cap_applied=bool(raw.get("ingredient_conflict_cap_applied", False)),
            observation_count=max(1, int(raw.get("observation_count") or 1)),
            created_at=raw.get("created_at") or utc_now_iso(),
            reviewed_at=raw.get("reviewed_at"),
            reviewer_note=raw.get("reviewer_note", ""),
        )


class IngredientProposalEngine:
    def __init__(
        self,
        memory_repository: Optional[IngredientMemoryRepository] = None,
        proposal_repository: Optional[LocalJsonIngredientProposalRepository] = None,
    ):
        self.memory_repository = memory_repository or LocalJsonIngredientMemoryRepository(DEFAULT_MEMORY_PATH)
        self.proposal_repository = proposal_repository or LocalJsonIngredientProposalRepository(DEFAULT_PROPOSAL_PATH)

    def create_proposal(
        self,
        ingredient_candidate: Any,
        canonical_match_candidate: Any,
        context: Optional[Dict] = None,
    ) -> IngredientProposal:
        context = context or {}
        normalized_key = self._canonical_attr(canonical_match_candidate, "normalized_match_key")
        normalized_key = normalize_key(normalized_key or self._candidate_attr(ingredient_candidate, "candidate_name"))
        existing, existing_match_kind = self._find_existing_target(normalized_key)
        conflicts = self._conflicts(ingredient_candidate, canonical_match_candidate)
        confidence = self._confidence(canonical_match_candidate)
        proposal_type = self._proposal_type(
            ingredient_candidate=ingredient_candidate,
            canonical_match_candidate=canonical_match_candidate,
            existing_ingredient_id=existing.ingredient_id if existing else None,
            conflicts=conflicts,
            confidence=confidence,
        )
        proposal = IngredientProposal(
            proposal_id="",
            source_filename=context.get("source_filename"),
            source_row_id=str(context.get("source_row_id")) if context.get("source_row_id") is not None else None,
            supplier_name=context.get("supplier_name") or self._candidate_attr(ingredient_candidate, "supplier_name"),
            supplier_code=self._candidate_attr(ingredient_candidate, "supplier_code"),
            supplier_description=self._candidate_attr(ingredient_candidate, "supplier_description") or "",
            candidate_name=self._candidate_attr(ingredient_candidate, "candidate_name") or "",
            normalized_match_key=normalized_key,
            proposed_canonical_name=self._canonical_attr(canonical_match_candidate, "proposed_canonical_name"),
            canonical_match_confidence=confidence,
            existing_ingredient_id=existing.ingredient_id if existing else None,
            proposal_type=proposal_type,
            status="pending",
            reasons=self._proposal_reasons(proposal_type, existing, confidence, existing_match_kind),
            conflicting_signals=conflicts,
            matched_signals=self._list_attr(canonical_match_candidate, "matched_signals"),
            modifier_tokens=self._dict_attr(canonical_match_candidate, "modifier_tokens"),
            packaging_identity_tokens=self._list_attr(canonical_match_candidate, "packaging_identity_tokens"),
            confidence_cap_reason=self._canonical_attr(canonical_match_candidate, "confidence_cap_reason"),
            ingredient_conflict_cap_applied=bool(self._attr(canonical_match_candidate, "ingredient_conflict_cap_applied")),
            observation_count=1,
            created_at=utc_now_iso(),
            reviewed_at=None,
            reviewer_note="",
        )
        return self.proposal_repository.create_proposal(proposal)

    def compare_with_memory(self, normalized_key: str) -> Optional[IngredientRecord]:
        return self.memory_repository.find_by_normalized_key(normalized_key)

    def approve_proposal(self, proposal_id: str, reviewer_note: str = "") -> IngredientProposal:
        proposal = self._pending_proposal(proposal_id)
        if proposal.proposal_type in {"possible_merge", "insufficient_evidence"}:
            raise ValueError(f"Proposal type cannot be approved automatically: {proposal.proposal_type}")
        if proposal.proposal_type == "create_new":
            self.memory_repository.create_ingredient(self._record_from_proposal(proposal))
        elif proposal.proposal_type == "attach_alias":
            if not proposal.existing_ingredient_id:
                raise ValueError("Alias proposal requires an existing ingredient.")
            self.memory_repository.add_alias(proposal.existing_ingredient_id, proposal.candidate_name)
        elif proposal.proposal_type == "attach_supplier_variant":
            if not proposal.existing_ingredient_id:
                raise ValueError("Supplier-variant proposal requires an existing ingredient.")
            self.memory_repository.add_supplier_variant(
                proposal.existing_ingredient_id,
                self._variant_from_proposal(proposal),
            )

        proposal.status = "approved"
        proposal.reviewed_at = utc_now_iso()
        proposal.reviewer_note = reviewer_note
        return self.proposal_repository.update_proposal(proposal)

    def reject_proposal(self, proposal_id: str, reviewer_note: str = "") -> IngredientProposal:
        proposal = self._pending_or_deferred_proposal(proposal_id)
        proposal.status = "rejected"
        proposal.reviewed_at = utc_now_iso()
        proposal.reviewer_note = reviewer_note
        return self.proposal_repository.update_proposal(proposal)

    def defer_proposal(self, proposal_id: str, reviewer_note: str = "") -> IngredientProposal:
        proposal = self._pending_or_deferred_proposal(proposal_id)
        proposal.status = "deferred"
        proposal.reviewed_at = utc_now_iso()
        proposal.reviewer_note = reviewer_note
        return self.proposal_repository.update_proposal(proposal)

    def return_to_pending(self, proposal_id: str, reviewer_note: str = "") -> IngredientProposal:
        proposal = self.proposal_repository.get_proposal(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal not found: {proposal_id}")
        if proposal.status != "deferred":
            raise ValueError(f"Only deferred proposals can return to pending: {proposal.status}")
        proposal.status = "pending"
        proposal.reviewed_at = None
        proposal.reviewer_note = reviewer_note
        return self.proposal_repository.update_proposal(proposal)

    def _proposal_type(
        self,
        ingredient_candidate: Any,
        canonical_match_candidate: Any,
        existing_ingredient_id: Optional[str],
        conflicts: List[str],
        confidence: float,
    ) -> str:
        if self._possible_merged_text(ingredient_candidate, canonical_match_candidate, conflicts):
            return "possible_merge"
        if self._has_blocking_conflict(conflicts):
            return "insufficient_evidence"
        if confidence < 0.7:
            return "possible_merge" if existing_ingredient_id else "insufficient_evidence"
        if existing_ingredient_id:
            if self._has_supplier_evidence(ingredient_candidate):
                return "attach_supplier_variant"
            return "attach_alias"
        if not self._plausible_standalone_ingredient(ingredient_candidate, canonical_match_candidate):
            return "insufficient_evidence"
        return "create_new"

    def _proposal_reasons(
        self,
        proposal_type: str,
        existing: Optional[IngredientRecord],
        confidence: float,
        existing_match_kind: Optional[str] = None,
    ) -> List[str]:
        reasons = ["Review-only proposal; no automatic approval"]
        if existing:
            if existing_match_kind == "exact":
                reasons.append(f"Existing normalized key match: {existing.ingredient_id}")
            else:
                reasons.append(f"Likely Ingredient Memory target requires review: {existing.ingredient_id}")
        else:
            reasons.append("No existing normalized key match")
        if confidence >= 0.9:
            reasons.append("Exact or strong canonical evidence")
        elif confidence >= 0.7:
            reasons.append("Reviewable canonical evidence")
        else:
            reasons.append("Ambiguous or weak canonical evidence")
        reasons.append(f"Proposal type: {proposal_type}")
        return reasons

    def _record_from_proposal(self, proposal: IngredientProposal) -> IngredientRecord:
        return IngredientRecord(
            ingredient_id="",
            canonical_name=proposal.proposed_canonical_name or proposal.candidate_name,
            normalized_key=proposal.normalized_match_key,
            aliases=[proposal.candidate_name] if proposal.candidate_name else [],
            supplier_variants=[self._variant_from_proposal(proposal)],
            preferred_purchase_unit=None,
            observed_units=[],
            observed_pack_formats=[],
            status="proposed",
            review_required=True,
            notes="Created from explicitly approved ingredient proposal.",
        )

    def _variant_from_proposal(self, proposal: IngredientProposal) -> SupplierIngredientVariant:
        now = utc_now_iso()
        return SupplierIngredientVariant(
            supplier_name=proposal.supplier_name or "",
            supplier_code=proposal.supplier_code,
            supplier_description=proposal.supplier_description,
            candidate_name=proposal.candidate_name,
            purchase_unit=None,
            pack_count=None,
            pack_size_value=None,
            pack_size_unit=None,
            first_seen_at=proposal.created_at or now,
            last_seen_at=now,
            observation_count=1,
            match_confidence=proposal.canonical_match_confidence,
        )

    def _pending_proposal(self, proposal_id: str) -> IngredientProposal:
        proposal = self.proposal_repository.get_proposal(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal not found: {proposal_id}")
        if proposal.status != "pending":
            raise ValueError(f"Proposal is not pending: {proposal.status}")
        return proposal

    def _pending_or_deferred_proposal(self, proposal_id: str) -> IngredientProposal:
        proposal = self.proposal_repository.get_proposal(proposal_id)
        if not proposal:
            raise KeyError(f"Proposal not found: {proposal_id}")
        if proposal.status not in {"pending", "deferred"}:
            raise ValueError(f"Proposal cannot be changed from status: {proposal.status}")
        return proposal

    def _has_blocking_conflict(self, conflicts: List[str]) -> bool:
        text = " ".join(conflicts).lower()
        return "ocr" in text or "numeric ambiguity" in text

    def _find_existing_target(self, normalized_key: str) -> tuple[Optional[IngredientRecord], Optional[str]]:
        exact = self.compare_with_memory(normalized_key)
        if exact:
            return exact, "exact"
        key_tokens = set(normalize_key(normalized_key).split())
        if not key_tokens:
            return None, None
        best_record = None
        best_score = 0.0
        for record in self.memory_repository.list_ingredients():
            record_tokens = set(normalize_key(record.normalized_key).split())
            if not record_tokens:
                continue
            overlap = len(key_tokens & record_tokens)
            score = overlap / max(len(key_tokens), len(record_tokens))
            if overlap >= 1 and score > best_score:
                best_record = record
                best_score = score
        if best_record and best_score >= 0.5:
            return best_record, "likely"
        return None, None

    def _possible_merged_text(
        self,
        ingredient_candidate: Any,
        canonical_match_candidate: Any,
        conflicts: List[str],
    ) -> bool:
        text = " ".join([
            self._candidate_attr(ingredient_candidate, "candidate_name") or "",
            self._candidate_attr(ingredient_candidate, "supplier_description") or "",
            " ".join(conflicts),
        ]).lower()
        if "merged" in text:
            return True
        identity_terms = {
            "crabstick", "crabsticks", "nori", "chicken", "bacon", "mushroom",
            "tomato", "tomatoes", "dates", "tofu", "salmon", "rice",
        }
        tokens = set(normalize_key(text).split())
        return len(tokens & identity_terms) >= 2

    def _has_supplier_evidence(self, ingredient_candidate: Any) -> bool:
        return bool(
            self._candidate_attr(ingredient_candidate, "supplier_name")
            or self._candidate_attr(ingredient_candidate, "supplier_code")
            or self._candidate_attr(ingredient_candidate, "supplier_description")
        )

    def _plausible_standalone_ingredient(
        self,
        ingredient_candidate: Any,
        canonical_match_candidate: Any,
    ) -> bool:
        key = self._canonical_attr(canonical_match_candidate, "normalized_match_key")
        tokens = normalize_key(key or self._candidate_attr(ingredient_candidate, "candidate_name")).split()
        if len(tokens) < 2:
            return False
        if all(token.isdigit() for token in tokens):
            return False
        generic = {"premium", "large", "small", "medium", "fresh", "frozen"}
        return bool(set(tokens) - generic)

    def _conflicts(self, ingredient_candidate: Any, canonical_match_candidate: Any) -> List[str]:
        conflicts = []
        for source in (ingredient_candidate, canonical_match_candidate):
            for field_name in ("conflicting_signals", "modifier_conflicts"):
                value = self._attr(source, field_name)
                if isinstance(value, list):
                    conflicts.extend(str(item) for item in value if item)
        return self._unique(conflicts)

    def _confidence(self, canonical_match_candidate: Any) -> float:
        value = self._canonical_attr(canonical_match_candidate, "match_confidence")
        if value is None:
            value = self._canonical_attr(canonical_match_candidate, "canonical_match_confidence")
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _list_attr(self, obj: Any, field_name: str) -> List[str]:
        value = self._attr(obj, field_name)
        return list(value) if isinstance(value, list) else []

    def _dict_attr(self, obj: Any, field_name: str) -> Dict[str, Any]:
        value = self._attr(obj, field_name)
        return dict(value) if isinstance(value, dict) else {}

    def _candidate_attr(self, candidate: Any, field_name: str) -> Optional[str]:
        value = self._attr(candidate, field_name)
        return str(value).strip() if value is not None and str(value).strip() else None

    def _canonical_attr(self, candidate: Any, field_name: str) -> Optional[str]:
        value = self._attr(candidate, field_name)
        return str(value).strip() if value is not None and str(value).strip() else None

    def _attr(self, obj: Any, field_name: str) -> Any:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj.get(field_name)
        return getattr(obj, field_name, None)

    def _unique(self, values: List[str]) -> List[str]:
        result = []
        seen = set()
        for value in values:
            key = normalize_key(value)
            if key and key not in seen:
                seen.add(key)
                result.append(value)
        return result
