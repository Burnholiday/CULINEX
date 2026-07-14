"""
Adaptive Header Framework for CULINEX

This module provides a comprehensive framework for detecting, normalizing, and scoring
header candidates in invoice and recipe data extraction. It includes classes for:

1. HeaderCandidate: Represents a potential header with its properties
2. HeaderNormalizer: Normalizes header text to standard field names
3. HeaderConfidenceEngine: Calculates confidence scores for header candidates
4. HeaderBandDetector: Detects header bands and their alignment patterns

The framework is designed to work with both OCR-extracted and structured table data.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# Import table boundary classes for future integration
from table_boundary_framework import (
    TableRegionDetector,
    HeaderRegionLocator,
    FooterRegionLocator,
    TableConfidenceEngine
)


class HeaderType(Enum):
    """Enumeration of supported header types"""
    DESCRIPTION = "description"
    QUANTITY = "quantity"
    UNIT = "unit"
    UNIT_PRICE = "unit_price"
    TOTAL = "total"
    VAT = "vat"
    CODE = "code"
    UNKNOWN = "unknown"


@dataclass
class HeaderCandidate:
    """Represents a potential header with its properties"""
    text: str
    normalized_text: str
    field_type: HeaderType
    confidence: float = 0.0
    position: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))  # x, y coordinates
    alignment_score: float = 0.0
    context_score: float = 0.0
    geometric_score: float = 0.0
    frequency_score: float = 0.0
    
    def __post_init__(self):
        """Initialize scores if not provided"""
        # Only calculate confidence if it hasn't been explicitly set
        if self.confidence == 0.0:
            self.confidence = self.calculate_overall_confidence()
    
    def calculate_overall_confidence(self) -> float:
        """Calculate overall confidence based on component scores"""
        weights = {
            'alignment': 0.3,
            'context': 0.3,
            'geometric': 0.2,
            'frequency': 0.2
        }
        
        score = (
            weights['alignment'] * self.alignment_score +
            weights['context'] * self.context_score +
            weights['geometric'] * self.geometric_score +
            weights['frequency'] * self.frequency_score
        )
        
        return round(min(1.0, max(0.0, score)), 3)


class HeaderNormalizer:
    """Normalizes header text to standard field names"""
    
    # Mapping of common header variations to standard field names
    HEADER_MAPPINGS = {
        # Description variations
        "description": HeaderType.DESCRIPTION,
        "product": HeaderType.DESCRIPTION,
        "item": HeaderType.DESCRIPTION,
        "details": HeaderType.DESCRIPTION,
        "productdescription": HeaderType.DESCRIPTION,
        "name": HeaderType.DESCRIPTION,
        "ingredient": HeaderType.DESCRIPTION,
        
        # Quantity variations
        "qty": HeaderType.QUANTITY,
        "quantity": HeaderType.QUANTITY,
        "shipquantity": HeaderType.QUANTITY,
        "shipqty": HeaderType.QUANTITY,
        "orderedqty": HeaderType.QUANTITY,
        "orderqty": HeaderType.QUANTITY,
        "amount": HeaderType.QUANTITY,
        "count": HeaderType.QUANTITY,
        
        # Unit variations
        "unit": HeaderType.UNIT,
        "uom": HeaderType.UNIT,
        "pack": HeaderType.UNIT,
        "purchaseunit": HeaderType.UNIT,
        "measurement": HeaderType.UNIT,
        
        # Unit price variations
        "price": HeaderType.UNIT_PRICE,
        "unitprice": HeaderType.UNIT_PRICE,
        "unitcost": HeaderType.UNIT_PRICE,
        "cost": HeaderType.UNIT_PRICE,
        "rate": HeaderType.UNIT_PRICE,
        "priceeach": HeaderType.UNIT_PRICE,
        "discounted price": HeaderType.UNIT_PRICE,
        "discountedprice": HeaderType.UNIT_PRICE,
        
        # Total variations
        "amount": HeaderType.TOTAL,
        "total": HeaderType.TOTAL,
        "totai": HeaderType.TOTAL,
        "linetotal": HeaderType.TOTAL,
        "linetotai": HeaderType.TOTAL,
        "netamount": HeaderType.TOTAL,
        "nettamount": HeaderType.TOTAL,
        "netvalue": HeaderType.TOTAL,
        "nettvalue": HeaderType.TOTAL,
        "nettprice": HeaderType.TOTAL,
        "netprice": HeaderType.TOTAL,
        "nett": HeaderType.TOTAL,
        "net": HeaderType.TOTAL,
        
        # VAT variations
        "vat": HeaderType.VAT,
        "tax": HeaderType.VAT,
        "vatamt": HeaderType.VAT,
        "vatamnt": HeaderType.VAT,
        "vatamount": HeaderType.VAT,
        
        # Code variations
        "code": HeaderType.CODE,
        "itemcode": HeaderType.CODE,
        "stockcode": HeaderType.CODE,
        "productcode": HeaderType.CODE,
        "sku": HeaderType.CODE,
    }
    
    @classmethod
    def normalize_text(cls, text: str) -> str:
        """Normalize header text by removing noise and standardizing format"""
        if not text:
            return ""
        
        # Convert to lowercase and remove extra whitespace
        normalized = text.lower().strip()
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r"^\s*(item|product|line)\s+", "", normalized)
        normalized = re.sub(r"\s+(incl|excl|incl\.|excl\.)\s*$", "", normalized)
        
        # Remove special characters but keep alphanumeric and spaces
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        
        # Replace multiple spaces with single space
        normalized = re.sub(r"\s+", " ", normalized)
        
        return normalized.strip()
    
    @classmethod
    def identify_field_type(cls, text: str) -> HeaderType:
        """Identify the field type based on the header text"""
        # Check for forbidden terms that should not be classified as invoice columns
        forbidden_terms = {
            "email", "account", "customer", "computer", "tender", "deposit", 
            "terms", "phone", "invoice", "clerk", "banking", "currency", 
            "rounding", "change"
        }
        
        normalized = cls.normalize_text(text)
        
        # If the normalized text is in forbidden terms, return UNKNOWN
        if normalized in forbidden_terms:
            return HeaderType.UNKNOWN
        
        # Direct mapping lookup
        if normalized in cls.HEADER_MAPPINGS:
            return cls.HEADER_MAPPINGS[normalized]
        
        # Pattern matching for more complex cases
        if re.search(r"(description|product|item|details|name)", normalized):
            return HeaderType.DESCRIPTION
        elif re.search(r"\b(qty|quantity|amount|count)\b", normalized):
            return HeaderType.QUANTITY
        elif re.search(r"(unit|uom|pack)", normalized):
            return HeaderType.UNIT
        elif re.search(r"(price|cost|rate)", normalized):
            return HeaderType.UNIT_PRICE
        elif re.search(r"(total|net|amount)", normalized):
            return HeaderType.TOTAL
        elif re.search(r"(vat|tax)", normalized):
            return HeaderType.VAT
        elif re.search(r"(code|sku)", normalized):
            return HeaderType.CODE
        
        return HeaderType.UNKNOWN


class HeaderConfidenceEngine:
    """Calculates confidence scores for header candidates"""
    
    def __init__(self):
        self.context_patterns = {
            HeaderType.DESCRIPTION: ["description", "product", "item", "details"],
            HeaderType.QUANTITY: ["qty", "quantity", "amount", "count"],
            HeaderType.UNIT: ["unit", "uom", "pack"],
            HeaderType.UNIT_PRICE: ["price", "cost", "rate"],
            HeaderType.TOTAL: ["total", "net", "amount"],
            HeaderType.VAT: ["vat", "tax"],
            HeaderType.CODE: ["code", "sku"],
        }
    
    def calculate_alignment_score(self, candidate: HeaderCandidate, 
                                column_positions: Dict[str, float]) -> float:
        """Calculate alignment score based on column positioning consistency"""
        if not column_positions:
            return 0.5  # Neutral score when no alignment data available
        
        # Find the closest column position
        closest_pos = min(column_positions.values(), 
                         key=lambda x: abs(x - candidate.position[0]), 
                         default=candidate.position[0])
        
        # Calculate distance-based score (closer = higher score)
        distance = abs(candidate.position[0] - closest_pos)
        max_distance = 100.0  # Maximum expected column width
        
        return max(0.0, 1.0 - (distance / max_distance))
    
    def calculate_context_score(self, candidate: HeaderCandidate) -> float:
        """Calculate context score based on text matching patterns"""
        if candidate.field_type == HeaderType.UNKNOWN:
            return 0.1  # Low confidence for unknown types
        
        patterns = self.context_patterns.get(candidate.field_type, [])
        normalized_text = HeaderNormalizer.normalize_text(candidate.text)
        
        # Check for exact matches
        for pattern in patterns:
            if pattern in normalized_text:
                return 1.0
        
        # Check for partial matches
        for pattern in patterns:
            if pattern in normalized_text or normalized_text in pattern:
                return 0.8
        
        # Check for fuzzy matches
        for pattern in patterns:
            if self._fuzzy_match(pattern, normalized_text):
                return 0.6
        
        return 0.3  # Default low score if no matches
    
    def calculate_geometric_score(self, candidate: HeaderCandidate,
                                header_band_height: float,
                                line_height: float) -> float:
        """Calculate geometric score based on positioning within header band"""
        if header_band_height <= 0 or line_height <= 0:
            return 0.5  # Neutral score when geometry data unavailable
        
        # Score based on vertical positioning (headers should be at top of band)
        # Normalize y position to 0-1 range
        y_position_ratio = min(1.0, max(0.0, candidate.position[1] / header_band_height))
        vertical_score = 1.0 - y_position_ratio  # Higher score for top positioning
        
        # Score based on text size relative to line height
        # Prefer larger text (higher ratio = larger text)
        size_ratio = candidate.position[1] / line_height if line_height > 0 else 1.0
        size_score = min(1.0, max(0.0, size_ratio))  # Prefer larger text
        
        # Return weighted average with proper bounds
        return max(0.0, min(1.0, (vertical_score + size_score) / 2.0))
    
    def calculate_frequency_score(self, candidate: HeaderCandidate,
                                frequency_map: Dict[str, int]) -> float:
        """Calculate frequency score based on how often similar headers appear"""
        if not frequency_map:
            return 0.5  # Neutral score when no frequency data available
        
        normalized = HeaderNormalizer.normalize_text(candidate.text)
        frequency = frequency_map.get(normalized, 0)
        max_frequency = max(frequency_map.values(), default=1)
        
        if max_frequency == 0:
            return 0.5
        
        return min(1.0, frequency / max_frequency)
    
    def _fuzzy_match(self, pattern: str, text: str) -> bool:
        """Perform fuzzy matching between pattern and text"""
        # Simple edit distance check
        pattern_chars = set(pattern)
        text_chars = set(text)
        
        # Check if most characters match
        if len(pattern_chars) == 0:
            return False
        
        match_ratio = len(pattern_chars.intersection(text_chars)) / len(pattern_chars)
        return match_ratio >= 0.6


class HeaderBandDetector:
    """Detects header bands and their alignment patterns"""
    
    def __init__(self, band_threshold: float = 20.0):
        self.band_threshold = band_threshold  # Vertical distance threshold for band grouping
    
    def detect_header_bands(self, candidates: List[HeaderCandidate]) -> List[List[HeaderCandidate]]:
        """Group header candidates into bands based on vertical positioning"""
        if not candidates:
            return []
        
        # Sort candidates by vertical position
        sorted_candidates = sorted(candidates, key=lambda c: c.position[1])
        
        bands = []
        current_band = [sorted_candidates[0]]
        current_band_y = sorted_candidates[0].position[1]
        
        for candidate in sorted_candidates[1:]:
            # Check if candidate is within band threshold of the current band center.
            if abs(candidate.position[1] - current_band_y) <= self.band_threshold:
                current_band.append(candidate)
                current_band_y = sum(c.position[1] for c in current_band) / len(current_band)
            else:
                # Start new band
                bands.append(current_band)
                current_band = [candidate]
                current_band_y = candidate.position[1]
        
        # Add last band
        if current_band:
            bands.append(current_band)
        
        return bands
    
    def analyze_band_alignment(self, band: List[HeaderCandidate]) -> Dict[str, Any]:
        """Analyze alignment patterns within a header band"""
        if not band:
            return {}
        
        # Calculate statistics for x positions
        x_positions = [c.position[0] for c in band]
        y_positions = [c.position[1] for c in band]
        
        return {
            "mean_x": sum(x_positions) / len(x_positions),
            "min_x": min(x_positions),
            "max_x": max(x_positions),
            "mean_y": sum(y_positions) / len(y_positions),
            "min_y": min(y_positions),
            "max_y": max(y_positions),
            "width": max(x_positions) - min(x_positions),
            "height": max(y_positions) - min(y_positions),
            "count": len(band),
            "candidates": band
        }
    
    def find_best_header_row(self, bands: List[List[HeaderCandidate]]) -> Optional[List[HeaderCandidate]]:
        """Find the most likely header row from detected bands"""
        if not bands:
            return None
        
        # Score each band based on quality indicators
        band_scores = []
        
        for band in bands:
            score = self._score_header_band(band)
            band_scores.append((score, band))
        
        # Return band with highest score
        if band_scores:
            best_band = max(band_scores, key=lambda x: x[0])
            return best_band[1]
        
        return None
    
    def _score_header_band(self, band: List[HeaderCandidate]) -> float:
        """Score a header band based on quality indicators"""
        if not band:
            return 0.0
        
        # Factors that indicate a good header row:
        # 1. Contains diverse field types
        field_types = {c.field_type for c in band}
        diversity_score = len(field_types) / len(HeaderType)
        
        # 2. High confidence scores
        avg_confidence = sum(c.confidence for c in band) / len(band)
        
        # 3. Good horizontal distribution (not clustered)
        x_positions = [c.position[0] for c in band]
        if len(x_positions) > 1:
            x_range = max(x_positions) - min(x_positions)
            distribution_score = min(1.0, x_range / 1000)  # Normalize by expected width
        else:
            distribution_score = 0.5
        
        # 4. Appropriate vertical position (near top)
        avg_y = sum(c.position[1] for c in band) / len(band)
        position_score = max(0.0, 1.0 - (avg_y / 100))  # Prefer top positioning
        
        # Weighted combination of factors
        return (
            0.3 * diversity_score +
            0.3 * avg_confidence +
            0.2 * distribution_score +
            0.2 * position_score
        )


# Convenience functions for common operations
def create_header_candidate(text: str, position: Tuple[float, float] = (0.0, 0.0)) -> HeaderCandidate:
    """Create a HeaderCandidate with automatic normalization and type identification"""
    normalized_text = HeaderNormalizer.normalize_text(text)
    field_type = HeaderNormalizer.identify_field_type(text)
    
    return HeaderCandidate(
        text=text,
        normalized_text=normalized_text,
        field_type=field_type,
        position=position
    )


def process_headers_for_table(headers: List[str], 
                            positions: List[Tuple[float, float]] = None) -> List[HeaderCandidate]:
    """Process a list of header texts into HeaderCandidate objects"""
    if positions is None:
        positions = [(0.0, 0.0)] * len(headers)
    
    candidates = []
    for text, pos in zip(headers, positions):
        candidate = create_header_candidate(text, pos)
        candidates.append(candidate)
    
    # Calculate confidence scores
    confidence_engine = HeaderConfidenceEngine()
    frequency_map = {HeaderNormalizer.normalize_text(c.text): 1 for c in candidates}
    
    for candidate in candidates:
        candidate.alignment_score = confidence_engine.calculate_alignment_score(candidate, {})
        candidate.context_score = confidence_engine.calculate_context_score(candidate)
        candidate.geometric_score = confidence_engine.calculate_geometric_score(candidate, 20.0, 12.0)
        candidate.frequency_score = confidence_engine.calculate_frequency_score(candidate, frequency_map)
        candidate.confidence = candidate.calculate_overall_confidence()
    
    return candidates