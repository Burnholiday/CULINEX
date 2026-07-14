#!/usr/bin/env python3
"""
Ingredient Intelligence Framework
Supplier-agnostic deterministic ingredient analysis for PRODUCT rows.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple
import re
from enum import Enum


@dataclass
class IngredientCandidate:
    """Represents a candidate ingredient extracted from a product row"""
    supplier_description: str
    normalized_description: str
    candidate_name: str
    supplier_code: Optional[str]
    purchase_unit: Optional[str]
    pack_count: Optional[float]
    pack_size_value: Optional[float]
    pack_size_unit: Optional[str]
    total_pack_quantity: Optional[str]
    confidence: float
    reasons: List[str]
    matched_signals: List[str]
    conflicting_signals: List[str]
    canonical_match_id: Optional[str]
    canonical_match_confidence: float
    candidate_fragments: List[str]
    fragment_scores: List[Dict]
    selected_fragment: str
    candidate_selection_reason: str


class IngredientIntelligenceEngine:
    """Deterministic, supplier-agnostic ingredient intelligence engine"""
    
    def __init__(self):
        # Supported units for normalization
        self._supported_units = {
            'kg', 'g', 'l', 'ml', 'each', 'ea', 'unit', 'box', 'case', 'bag', 
            'pack', 'packet', 'pkt', 'punnet', 'tray', 'bottle', 'tin', 'can', 
            'carton', 'bunch', 'roll'
        }
        
        # Common pack patterns
        self._pack_patterns = [
            # Pattern: number x number unit (e.g., 10x1kg, 6 x 500g)
            r'(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(\w+)',
            # Pattern: number unit (e.g., 250g, 4.5L)
            r'(\d+(?:\.\d+)?)\s*(\w+)',
            # Pattern: number unit (e.g., 12 bottles)
            r'(\d+(?:\.\d+)?)\s*(\w+)',
            # Pattern: box of number (e.g., box of 10)
            r'box\s+of\s+(\d+(?:\.\d+)?)',
            # Pattern: case number (e.g., case 24)
            r'case\s+(\d+(?:\.\d+)?)',
        ]
        
        # Supplier code patterns (simple numeric or alphanumeric codes)
        self._supplier_code_patterns = [
            r'\b([A-Z]{2,3}\d{3,5})\b',  # e.g., NOR008, CHE009
            r'\b(\d{4,6})\b',            # e.g., 10456
            r'\b([A-Z]\d{3,5})\b',       # e.g., WHO-123
        ]
        
        # Unit normalization mapping
        self._unit_normalization = {
            'each': 'ea',
            'ea.': 'ea',
            'ea': 'ea',
            'unit': 'ea',
            'units': 'ea',
            'bottle': 'bottle',
            'bottles': 'bottle',
            'can': 'can',
            'cans': 'can',
            'tin': 'tin',
            'tins': 'tin',
            'bag': 'bag',
            'bags': 'bag',
            'box': 'box',
            'boxes': 'box',
            'case': 'case',
            'cases': 'case',
            'pack': 'pack',
            'packs': 'pack',
            'packet': 'packet',
            'packets': 'packet',
            'pkt': 'pkt',
            'pkts': 'pkt',
            'punnet': 'punnet',
            'punnets': 'punnet',
            'tray': 'tray',
            'trays': 'tray',
            'carton': 'carton',
            'cartons': 'carton',
            'bunch': 'bunch',
            'bunches': 'bunch',
            'roll': 'roll',
            'rolls': 'roll',
            'kg': 'kg',
            'g': 'g',
            'l': 'l',
            'ml': 'ml'
        }
    
    def analyze_product_row(self, row_text: str, row_data: Optional[Dict] = None, context: Optional[Dict] = None) -> IngredientCandidate:
        """
        Analyze a product row to extract ingredient information.
        
        Args:
            row_text: Text content of the product row
            row_data: Additional data about the row (optional)
            context: Context information about the invoice (optional)
            
        Returns:
            IngredientCandidate with extracted information
        """
        # Preserve original supplier description while using the row description
        # as the primary ingredient identity source.
        supplier_description = str(row_text or "").strip()
        identity_text = (
            str((row_data or {}).get("description") or "").strip()
            or supplier_description
        )
        
        # Normalize the description
        normalized_description = self._normalize_description(identity_text)
        
        # Initialize result components
        candidate_name = ""
        supplier_code = None
        purchase_unit = None
        pack_count = None
        pack_size_value = None
        pack_size_unit = None
        total_pack_quantity = None
        confidence = 0.0
        reasons = []
        matched_signals = []
        conflicting_signals = []
        
        # Extract candidate name and other components
        (
            candidate_name,
            supplier_code,
            purchase_unit,
            pack_count,
            pack_size_value,
            pack_size_unit,
            candidate_fragments,
            fragment_scores,
            selected_fragment,
            candidate_selection_reason,
            possible_merged_product,
        ) = self._extract_components(
            normalized_description
        )
        
        # Calculate total pack quantity if applicable
        if pack_count is not None and pack_size_value is not None and pack_size_unit:
            total_pack_quantity = f"{pack_count * pack_size_value} {pack_size_unit}"
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            normalized_description,
            candidate_name,
            supplier_code,
            purchase_unit,
            pack_count,
            pack_size_value,
            pack_size_unit
        )
        
        # Add reasons based on what was found
        if candidate_name:
            reasons.append("Product-like description detected")
        if supplier_code:
            reasons.append("Supplier code detected")
        if purchase_unit:
            reasons.append("Purchase unit detected")
        if pack_count is not None and pack_size_value is not None:
            reasons.append("Pack pattern detected")
        
        # Check for conflicting signals
        if self._has_conflicting_numeric_patterns(normalized_description):
            conflicting_signals.append("Conflicting numeric patterns detected")
            confidence *= 0.7  # Reduce confidence due to ambiguity
        if possible_merged_product:
            conflicting_signals.append("Possible merged product text detected")
        
        return IngredientCandidate(
            supplier_description=supplier_description,
            normalized_description=normalized_description,
            candidate_name=candidate_name,
            supplier_code=supplier_code,
            purchase_unit=purchase_unit,
            pack_count=pack_count,
            pack_size_value=pack_size_value,
            pack_size_unit=pack_size_unit,
            total_pack_quantity=total_pack_quantity,
            confidence=confidence,
            reasons=reasons,
            matched_signals=matched_signals,
            conflicting_signals=conflicting_signals,
            canonical_match_id=None,
            canonical_match_confidence=0.0,
            candidate_fragments=candidate_fragments,
            fragment_scores=fragment_scores,
            selected_fragment=selected_fragment,
            candidate_selection_reason=candidate_selection_reason
        )
    
    def analyze_many(self, rows: List[str]) -> List[IngredientCandidate]:
        """
        Analyze multiple product rows at once.
        
        Args:
            rows: List of row texts to analyze
            
        Returns:
            List of IngredientCandidate objects
        """
        return [self.analyze_product_row(row) for row in rows]
    
    def _normalize_description(self, description: str) -> str:
        """
        Normalize description by trimming whitespace, normalizing punctuation and spacing.
        """
        # Trim whitespace
        normalized = description.strip()
        
        # Normalize repeated punctuation
        normalized = re.sub(r'[^\w\s\-\.\/\(\)\[\]\{\}]+', ' ', normalized)
        
        # Normalize spacing
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove extra spaces around punctuation
        normalized = re.sub(r'\s*([.,;:])\s*', r'\1 ', normalized)
        
        # Remove extra spaces around parentheses
        normalized = re.sub(r'\s*([()])\s*', r'\1', normalized)
        
        return normalized
    
    def _extract_components(self, description: str) -> Tuple[str, Optional[str], Optional[str], Optional[float], Optional[float], Optional[str], List[str], List[Dict], str, str, bool]:
        """
        Extract components from normalized description.
        """
        # Initialize components
        candidate_name = ""
        supplier_code = None
        purchase_unit = None
        pack_count = None
        pack_size_value = None
        pack_size_unit = None
        candidate_fragments = []
        fragment_scores = []
        selected_fragment = ""
        candidate_selection_reason = "No meaningful candidate fragment found"
        possible_merged_product = False
        
        # Look for supplier codes first
        for pattern in self._supplier_code_patterns:
            match = re.search(pattern, description)
            if match:
                supplier_code = match.group(1)
                # Remove supplier code from description for further processing
                description = description.replace(supplier_code, '', 1)
                break
        
        # Look for pack patterns
        for pattern in self._pack_patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    # Handle different pattern types
                    if len(groups) == 3:
                        # Pattern: number x number unit (e.g., 10x1kg)
                        pack_count = float(groups[0])
                        pack_size_value = float(groups[1])
                        pack_size_unit = groups[2]
                    elif len(groups) == 2:
                        # Pattern: number unit (e.g., 250g)
                        if self._is_unit(groups[1]):
                            pack_size_value = float(groups[0])
                            pack_size_unit = groups[1]
                        else:
                            # Could be a pack count
                            pack_count = float(groups[0])
                            # Look for unit in remaining text
                            remaining = description[match.end():]
                            unit_match = re.search(r'\b(' + '|'.join(self._supported_units) + r')\b', remaining, re.IGNORECASE)
                            if unit_match:
                                pack_size_unit = unit_match.group(1)
                break
        
        # Normalize unit if found
        if pack_size_unit:
            normalized_unit = self._unit_normalization.get(pack_size_unit.lower(), pack_size_unit.lower())
            if normalized_unit in self._supported_units:
                pack_size_unit = normalized_unit
        
        # Extract candidate name from a cleaned identity string. Keep packaging
        # words available to the scorer because they can be part of identity.
        candidate_text = description
        if supplier_code:
            candidate_text = candidate_text.replace(supplier_code, '', 1)

        candidate_text = self._remove_pack_evidence_for_candidate(candidate_text)
        candidate_name, candidate_fragments, fragment_scores, selected_fragment, candidate_selection_reason = (
            self._select_candidate_fragment(candidate_text)
        )
        possible_merged_product = self._looks_like_merged_product(candidate_fragments, selected_fragment)
        
        # If we have a pack size but no pack count, assume pack count is 1
        if pack_size_value and pack_count is None:
            pack_count = 1.0
        
        return (
            candidate_name,
            supplier_code,
            purchase_unit,
            pack_count,
            pack_size_value,
            pack_size_unit,
            candidate_fragments,
            fragment_scores,
            selected_fragment,
            candidate_selection_reason,
            possible_merged_product,
        )

    def _remove_pack_evidence_for_candidate(self, text: str) -> str:
        """Remove numeric pack evidence without dropping identity packaging words."""
        cleaned = text
        cleaned = re.sub(
            r'\b\d+(?:\.\d+)?\s*[xX]\s*\d+(?:\.\d+)?(?:\s*[xX]\s*\d+(?:\.\d+)?)?\b',
            ' ',
            cleaned,
        )
        cleaned = re.sub(
            r'\b\d+(?:\.\d+)?\s*(?:kg|g|l|ml|lb|mc|mic)\b',
            ' ',
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r'\(\s*\d+\s*\'?\s*s\s*\)', ' ', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b\d+\s*\'?\s*s\b', ' ', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b\d+(?:\.\d+)?\b', ' ', cleaned)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _select_candidate_fragment(self, text: str) -> Tuple[str, List[str], List[Dict], str, str]:
        """Score deterministic candidate fragments and choose the strongest one."""
        fragments = self._candidate_fragments(text)
        scored = []
        for index, fragment in enumerate(fragments):
            score, reasons = self._score_candidate_fragment(fragment, index, fragments)
            scored.append({
                "fragment": fragment,
                "score": round(score, 3),
                "reasons": reasons,
            })

        meaningful = [item for item in scored if item["score"] > 0]
        if not meaningful:
            return "", fragments, scored, "", "No fragment scored above zero"

        selected = max(meaningful, key=lambda item: (item["score"], len(item["fragment"])))
        selected_fragment = self._clean_selected_fragment(selected["fragment"])
        reason = "Selected highest-scoring meaningful fragment"
        if selected["reasons"]:
            reason = f"{reason}: {', '.join(selected['reasons'])}"
        return selected_fragment, fragments, scored, selected_fragment, reason

    def _candidate_fragments(self, text: str) -> List[str]:
        """Split candidate text on separators that usually separate phrases."""
        parts = re.split(r'\s+-\s+|\s+-|-\s+|(?<=[A-Za-z])-(?=[A-Za-z])|[()\[\],;]', text)
        fragments = []
        for part in parts:
            fragment = re.sub(r'\s+', ' ', part).strip(" .:")
            if fragment:
                fragments.append(fragment)
        return fragments

    def _clean_selected_fragment(self, fragment: str) -> str:
        """Remove leftover structural tokens from the chosen fragment."""
        cleaned = fragment
        true_units = r'kg|g|l|ml|ea|each|unit'
        cleaned = re.sub(r'\b(?:' + true_units + r')\b$', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\b[xX]\b', '', cleaned)
        words = re.findall(r'[A-Za-z/]+', cleaned)
        if len(words) >= 3 and words[0].lower() in {'can', 'tin', 'pack'}:
            cleaned = re.sub(r'^\s*' + re.escape(words[0]) + r'\b', '', cleaned, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', cleaned).strip(" .:-")

    def _score_candidate_fragment(self, fragment: str, index: int, fragments: List[str]) -> Tuple[float, List[str]]:
        score = 0.0
        reasons = []
        words = re.findall(r'[A-Za-z]+', fragment)
        numbers = re.findall(r'\d+', fragment)
        word_count = len(words)
        upper_words = [word for word in words if word.isupper()]
        unit_words = {unit.lower() for unit in self._supported_units}
        generic_packaging = {
            'bag', 'box', 'pack', 'packet', 'pkt', 'case', 'carton',
            'tray', 'tin', 'can', 'roll', 'unit', 'ea', 'each'
        }
        descriptors = {
            'red', 'green', 'yellow', 'black', 'white', 'baby', 'large',
            'medium', 'small', 'loose', 'whole', 'fresh', 'salted',
            'pitted', 'granny', 'flat', 'italian', 'heavy', 'duty',
            'hduty', 'poly', 'vacuum', 'refuse', 'black'
        }

        if word_count:
            score += 2.0
            reasons.append("contains alphabetic product words")
        if word_count >= 2:
            score += 1.5
            reasons.append("contains multiple meaningful words")
        if len(fragment) >= 8:
            score += min(2.0, len(fragment) / 18.0)
            reasons.append("longer descriptive phrase")
        if index > 0 and self._is_short_prefix(fragments[index - 1]):
            score += 2.0
            reasons.append("appears after short prefix separator")
        if any(word.lower() in descriptors for word in words):
            score += 0.5
            reasons.append("contains descriptive modifier")

        lowered_words = [word.lower() for word in words]
        if word_count == 1 and lowered_words[0] in unit_words:
            score -= 4.0
            reasons.append("isolated unit token")
        if word_count == 1 and lowered_words[0] in generic_packaging:
            score -= 2.5
            reasons.append("isolated packaging token")
        if word_count <= 2 and fragment.isupper() and len(fragment) <= 10:
            score -= 2.0
            reasons.append("very short all-caps fragment")
        if numbers and len(''.join(numbers)) >= len(re.sub(r'\D', '', fragment)):
            if len(numbers) >= word_count:
                score -= 2.0
                reasons.append("mostly numeric")
        if re.fullmatch(r'[A-Z]{1,3}\d{2,5}', fragment.strip()):
            score -= 4.0
            reasons.append("supplier-code shaped")
        if word_count <= 2 and all(word.isupper() and len(word) <= 5 for word in upper_words):
            score -= 1.0
            reasons.append("only one or two generic-looking tokens")
        if re.search(r'\d+\s*[xX]\s*\d+', fragment):
            score -= 3.0
            reasons.append("dimension-like fragment")
        if len(re.sub(r'[\w\s]', '', fragment)) > max(2, len(fragment) // 3):
            score -= 1.0
            reasons.append("punctuation-heavy fragment")

        return max(0.0, score), reasons

    def _is_short_prefix(self, fragment: str) -> bool:
        words = re.findall(r'[A-Za-z]+', fragment)
        return bool(words) and len(words) <= 2 and len(fragment) <= 12

    def _looks_like_merged_product(self, fragments: List[str], selected_fragment: str) -> bool:
        product_like = [
            fragment for fragment in fragments
            if fragment != selected_fragment and self._score_candidate_fragment(fragment, 0, fragments)[0] >= 3.0
        ]
        return len(product_like) >= 1 and len(fragments) >= 3
    
    def _is_unit(self, text: str) -> bool:
        """Check if text is a recognized unit."""
        return text.lower() in self._supported_units
    
    def _has_conflicting_numeric_patterns(self, description: str) -> bool:
        """
        Check if there are conflicting numeric patterns that might cause ambiguity.
        """
        # Look for multiple numeric patterns that could be ambiguous
        numeric_patterns = re.findall(r'\d+(?:\.\d+)?', description)
        
        # If we have more than 2 numbers and they're not clearly part of a pack pattern,
        # it might be ambiguous
        if len(numeric_patterns) > 2:
            # Look for patterns that might be conflicting
            # e.g., "10 250g" could be 10 items of 250g each or 10 items of 250g total
            return True
        
        return False
    
    def _calculate_confidence(self, description: str, candidate_name: str, supplier_code: Optional[str], 
                           purchase_unit: Optional[str], pack_count: Optional[float], 
                           pack_size_value: Optional[float], pack_size_unit: Optional[str]) -> float:
        """
        Calculate confidence score based on extracted components.
        """
        score = 0.0
        
        # Base confidence from description quality
        if len(description) > 10:
            score += 0.2
        
        # Confidence from candidate name
        if candidate_name and len(candidate_name) > 2:
            score += 0.3
        
        # Confidence from supplier code
        if supplier_code:
            score += 0.15
        
        # Confidence from unit detection
        if purchase_unit:
            score += 0.15
        elif pack_size_unit:
            score += 0.1
        
        # Confidence from pack pattern detection
        if pack_count is not None and pack_size_value is not None:
            score += 0.2
        
        # Normalize to 0-1 range
        confidence = min(1.0, score)
        
        # Apply penalties for missing components
        if not candidate_name:
            confidence *= 0.7
        if not (purchase_unit or pack_size_unit):
            confidence *= 0.8
        
        return confidence


# Example usage:
if __name__ == "__main__":
    engine = IngredientIntelligenceEngine()
    
    # Test examples
    test_rows = [
        "WHO - STRAWBERRIES Punnet 250g",
        "10x1kg Tomatoes",
        "NOR008 Norwegian Salmon Fresh Whole 10.90kg",
        "6 x 500g Chicken Breasts",
        "24x330ml Cola",
        "4.5L Milk",
        "2kg Apples",
        "12 bottles Water",
        "box of 10 Eggs",
        "case 24 Bananas",
        "CHE009 Cheese 1kg",
        "10456 Beef 2kg",
        "10x1kg Tomatoes",
        "250g Cheese",
        "100g Flour"
    ]
    
    for i, row in enumerate(test_rows):
        result = engine.analyze_product_row(row)
        print(f"Row {i+1}: {row}")
        print(f"  Candidate Name: {result.candidate_name}")
        print(f"  Supplier Code: {result.supplier_code}")
        print(f"  Unit: {result.pack_size_unit}")
        print(f"  Pack Count: {result.pack_count}")
        print(f"  Pack Size: {result.pack_size_value}")
        print(f"  Total Quantity: {result.total_pack_quantity}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Reasons: {', '.join(result.reasons)}")
        print()
