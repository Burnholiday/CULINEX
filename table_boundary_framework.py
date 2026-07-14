"""
Table Boundary Framework for CULINEX

This module provides a comprehensive framework for detecting, locating, and scoring
table regions, header regions, footer regions, and their confidence in document extraction.
It includes classes for detecting table boundaries before header detection and provides
intelligent region detection capabilities for invoice and recipe data extraction.

The framework is designed to work with both OCR-extracted and structured table data.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


class TableRegionDetector:
    """Detects invoice table boundaries in document content"""
    
    def __init__(self):
        # Common patterns that indicate table boundaries
        self.header_patterns = [
            r"(?:invoice|tax\s*invoice|purchase\s*order|receipt)\s*(?:no|number|ref|doc)",
            r"(?:supplier|vendor|seller|company)\s*(?:name|info)",
            r"(?:customer|client|buyer)\s*(?:name|info)",
            r"(?:date|invoice\s*date|order\s*date)",
            r"(?:total|amount|price|cost)",
            r"(?:vat|tax|gst|sales\s*tax)",
            r"(?:quantity|qty|amount)",
            r"(?:description|item|product)",
            r"(?:unit\s*price|price\s*each)",
            r"(?:line\s*total|subtotal|grand\s*total)",
        ]
        
        self.footer_patterns = [
            r"(?:total|amount|price|cost)\s*(?:due|owed|paid|balance)",
            r"(?:terms|conditions|payment|due\s*date)",
            r"(?:banking|account|payment|transfer)",
            r"(?:vat|tax|gst|sales\s*tax)\s*(?:number|reg)",
            r"(?:invoice\s*number|order\s*number|reference)",
            r"(?:page\s*\d+\s*of\s*\d+|footer|end)",
        ]
        
        self.table_boundary_indicators = [
            r"(?:line\s*item|item\s*line|description)",
            r"(?:quantity|qty|amount)",
            r"(?:unit\s*price|price\s*each)",
            r"(?:total|amount|cost)",
            r"(?:vat|tax|gst)",
        ]
    
    def detect_table_regions(self, text_content: str, ocr_items: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Detect potential table regions in document content.
        
        Args:
            text_content: Extracted text from document
            ocr_items: List of OCR items with position information
            
        Returns:
            List of detected table regions with boundaries and metadata
        """
        regions = []
        
        # If OCR items are provided, use them for more precise detection
        if ocr_items:
            regions.extend(self._detect_from_ocr_items(ocr_items))
        
        # Use text analysis as fallback
        regions.extend(self._detect_from_text(text_content))
        
        # Merge overlapping regions
        merged_regions = self._merge_overlapping_regions(regions)
        
        return merged_regions
    
    def _detect_from_ocr_items(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """Detect table regions from OCR item positions"""
        regions = []
        
        # Group items by vertical proximity to identify potential table rows
        if not items:
            return regions
            
        # Sort items by y position
        sorted_items = sorted(items, key=lambda item: item.get('y', 0))
        
        # Group items into potential table sections
        current_section = []
        last_y = None
        section_threshold = 20.0  # Vertical distance threshold for grouping
        
        for item in sorted_items:
            y = item.get('y', 0)
            if last_y is None or abs(y - last_y) <= section_threshold:
                current_section.append(item)
            else:
                if len(current_section) >= 2:  # Minimum 2 items to form a table section
                    regions.append(self._analyze_table_section(current_section))
                current_section = [item]
            last_y = y
        
        # Add the last section
        if len(current_section) >= 2:
            regions.append(self._analyze_table_section(current_section))
            
        return regions
    
    def _detect_from_text(self, text_content: str) -> List[Dict[str, Any]]:
        """Detect table regions from text content analysis"""
        regions = []
        
        # Look for header patterns that indicate table start
        lines = text_content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Check if this line looks like a table header
            if self._is_table_header_line(line):
                # Look for a reasonable table structure below this line
                table_end = self._find_table_end(i, lines)
                if table_end > i:
                    regions.append({
                        'type': 'table_region',
                        'start_line': i,
                        'end_line': table_end,
                        'confidence': 0.7,
                        'content_preview': '\n'.join(lines[i:min(i+10, table_end+1)])
                    })
        
        return regions
    
    def _is_table_header_line(self, line: str) -> bool:
        """Check if a line appears to be a table header"""
        line_lower = line.lower()
        for pattern in self.header_patterns:
            if re.search(pattern, line_lower):
                return True
        return False
    
    def _find_table_end(self, start_line: int, lines: List[str]) -> int:
        """Find the end of a table section starting from start_line"""
        # Look for a reasonable table structure
        for i in range(start_line + 1, min(start_line + 20, len(lines))):
            line = lines[i].strip()
            if not line:
                continue
            # If we find a footer pattern or a line that looks like a new section
            if self._is_footer_line(line) or self._is_new_section_line(line):
                return i - 1
        return len(lines) - 1
    
    def _is_footer_line(self, line: str) -> bool:
        """Check if a line appears to be a footer"""
        line_lower = line.lower()
        for pattern in self.footer_patterns:
            if re.search(pattern, line_lower):
                return True
        return False
    
    def _is_new_section_line(self, line: str) -> bool:
        """Check if a line indicates a new document section"""
        # Look for common section indicators
        section_indicators = [
            r"page\s*\d+\s*of\s*\d+",
            r"end\s*of\s*document",
            r"total\s*amount",
            r"invoice\s*total",
            r"payment\s*summary",
            r"terms\s*and\s*conditions"
        ]
        
        line_lower = line.lower()
        for pattern in section_indicators:
            if re.search(pattern, line_lower):
                return True
        return False
    
    def _analyze_table_section(self, items: List[Dict]) -> Dict[str, Any]:
        """Analyze a section of OCR items to determine if it's a table"""
        if not items:
            return {}
            
        # Calculate bounding box
        x_coords = [item.get('x', 0) for item in items if item.get('x') is not None]
        y_coords = [item.get('y', 0) for item in items if item.get('y') is not None]
        w_coords = [item.get('w', 0) for item in items if item.get('w') is not None]
        h_coords = [item.get('h', 0) for item in items if item.get('h') is not None]
        
        if not x_coords or not y_coords:
            return {}
            
        return {
            'type': 'table_region',
            'start_x': min(x_coords),
            'end_x': max(x_coords) + (max(w_coords) if w_coords else 0),
            'start_y': min(y_coords),
            'end_y': max(y_coords) + (max(h_coords) if h_coords else 0),
            'item_count': len(items),
            'confidence': 0.8,
            'content_preview': ' '.join([item.get('text', '') for item in items[:5]])
        }
    
    def _merge_overlapping_regions(self, regions: List[Dict]) -> List[Dict]:
        """Merge overlapping table regions"""
        if not regions:
            return []
            
        # Sort regions by start position
        sorted_regions = sorted(regions, key=lambda r: r.get('start_y', 0))
        merged = [sorted_regions[0]]
        
        for region in sorted_regions[1:]:
            last_region = merged[-1]
            # Check if regions overlap or are close
            if (region.get('start_y', 0) <= last_region.get('end_y', 0) + 10):
                # Merge regions
                merged[-1] = {
                    'type': 'table_region',
                    'start_x': min(last_region.get('start_x', 0), region.get('start_x', 0)),
                    'end_x': max(last_region.get('end_x', 0), region.get('end_x', 0)),
                    'start_y': min(last_region.get('start_y', 0), region.get('start_y', 0)),
                    'end_y': max(last_region.get('end_y', 0), region.get('end_y', 0)),
                    'item_count': last_region.get('item_count', 0) + region.get('item_count', 0),
                    'confidence': (last_region.get('confidence', 0) + region.get('confidence', 0)) / 2,
                    'content_preview': f"{last_region.get('content_preview', '')} {region.get('content_preview', '')}"
                }
            else:
                merged.append(region)
                
        return merged


class HeaderRegionLocator:
    """Locates header regions within detected table boundaries"""
    
    def __init__(self):
        # Common header indicators that help identify header regions
        self.header_indicators = [
            r"(?:description|item|product|line|item\s*description)",
            r"(?:quantity|qty|amount|number)",
            r"(?:unit\s*price|price\s*each|unit\s*cost)",
            r"(?:total|amount|line\s*total|subtotal)",
            r"(?:vat|tax|gst|sales\s*tax)",
            r"(?:code|sku|item\s*code)",
            r"(?:excl|excl\s*vat|incl|incl\s*vat)",
            r"(?:discount|disc)",
        ]
    
    def locate_header_regions(self, table_region: Dict, ocr_items: List[Dict]) -> List[Dict[str, Any]]:
        """
        Locate header regions within a table region.
        
        Args:
            table_region: Detected table region from TableRegionDetector
            ocr_items: List of OCR items in the document
            
        Returns:
            List of header regions with their boundaries and metadata
        """
        if not table_region or not ocr_items:
            return []
            
        header_regions = []
        
        # Filter items that fall within the table region
        table_items = self._filter_items_in_region(ocr_items, table_region)
        
        if not table_items:
            return []
            
        # Group items by vertical proximity to identify header bands
        header_bands = self._group_header_bands(table_items)
        
        # Analyze each band to identify header regions
        for band_items in header_bands:
            if len(band_items) >= 2:  # Minimum 2 items to form a header region
                header_region = self._analyze_header_band(band_items)
                if header_region:
                    header_regions.append(header_region)
        
        return header_regions
    
    def _filter_items_in_region(self, items: List[Dict], table_region: Dict) -> List[Dict]:
        """Filter OCR items that fall within a table region"""
        table_start_x = table_region.get('start_x', 0)
        table_end_x = table_region.get('end_x', 0)
        table_start_y = table_region.get('start_y', 0)
        table_end_y = table_region.get('end_y', 0)
        
        filtered_items = []
        for item in items:
            x = item.get('x', 0)
            y = item.get('y', 0)
            if (table_start_x <= x <= table_end_x and 
                table_start_y <= y <= table_end_y):
                filtered_items.append(item)
        
        return filtered_items
    
    def _group_header_bands(self, items: List[Dict]) -> List[List[Dict]]:
        """Group items into header bands based on vertical proximity"""
        if not items:
            return []
            
        # Sort items by y position
        sorted_items = sorted(items, key=lambda item: item.get('y', 0))
        
        bands = []
        current_band = [sorted_items[0]]
        last_y = sorted_items[0].get('y', 0)
        band_threshold = 15.0  # Vertical distance threshold for band grouping
        
        for item in sorted_items[1:]:
            y = item.get('y', 0)
            if abs(y - last_y) <= band_threshold:
                current_band.append(item)
            else:
                if len(current_band) >= 1:  # Minimum 1 item to form a band
                    bands.append(current_band)
                current_band = [item]
            last_y = y
        
        # Add the last band
        if len(current_band) >= 1:
            bands.append(current_band)
            
        return bands
    
    def _analyze_header_band(self, band_items: List[Dict]) -> Optional[Dict[str, Any]]:
        """Analyze a band of items to determine if it's a header region"""
        if not band_items:
            return None
            
        # Calculate bounding box
        x_coords = [item.get('x', 0) for item in band_items if item.get('x') is not None]
        y_coords = [item.get('y', 0) for item in band_items if item.get('y') is not None]
        w_coords = [item.get('w', 0) for item in band_items if item.get('w') is not None]
        h_coords = [item.get('h', 0) for item in band_items if item.get('h') is not None]
        
        if not x_coords or not y_coords:
            return None
            
        # Check if this band contains header-like content
        header_text = ' '.join([item.get('text', '') for item in band_items[:3]])
        header_text_lower = header_text.lower()
        
        # If it contains header indicators, it's likely a header region
        header_indicators_found = 0
        for pattern in self.header_indicators:
            if re.search(pattern, header_text_lower):
                header_indicators_found += 1
        
        if header_indicators_found >= 1:  # At least one header indicator
            return {
                'type': 'header_region',
                'start_x': min(x_coords),
                'end_x': max(x_coords) + (max(w_coords) if w_coords else 0),
                'start_y': min(y_coords),
                'end_y': max(y_coords) + (max(h_coords) if h_coords else 0),
                'item_count': len(band_items),
                'confidence': 0.85,
                'content_preview': header_text,
                'header_indicators': header_indicators_found
            }
        
        return None


class FooterRegionLocator:
    """Locates footer regions in document content"""
    
    def __init__(self):
        # Common footer indicators
        self.footer_indicators = [
            r"(?:total|amount|price|cost)\s*(?:due|owed|paid|balance)",
            r"(?:terms|conditions|payment|due\s*date)",
            r"(?:banking|account|payment|transfer)",
            r"(?:vat|tax|gst|sales\s*tax)\s*(?:number|reg)",
            r"(?:invoice\s*number|order\s*number|reference)",
            r"(?:page\s*\d+\s*of\s*\d+|footer|end)",
            r"(?:copyright|all\s*rights\s*reserved)",
            r"(?:email|phone|fax|website)",
            r"(?:company|business|organization)",
        ]
    
    def locate_footer_regions(self, text_content: str, ocr_items: List[Dict] = None) -> List[Dict[str, Any]]:
        """
        Locate footer regions in document content.
        
        Args:
            text_content: Extracted text from document
            ocr_items: List of OCR items with position information
            
        Returns:
            List of footer regions with their boundaries and metadata
        """
        regions = []
        
        # If OCR items are provided, use them for more precise detection
        if ocr_items:
            regions.extend(self._detect_from_ocr_items(ocr_items))
        
        # Use text analysis as fallback
        regions.extend(self._detect_from_text(text_content))
        
        return regions
    
    def _detect_from_ocr_items(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """Detect footer regions from OCR item positions"""
        regions = []
        
        if not items:
            return regions
            
        # Sort items by y position (bottom to top)
        sorted_items = sorted(items, key=lambda item: item.get('y', 0), reverse=True)
        
        # Look for footer indicators at the bottom of the document
        footer_items = []
        for item in sorted_items[:10]:  # Check top 10 items from bottom
            text = item.get('text', '').lower()
            if self._is_footer_text(text):
                footer_items.append(item)
        
        if len(footer_items) >= 2:  # Minimum 2 items to form a footer region
            # Calculate bounding box for footer region
            x_coords = [item.get('x', 0) for item in footer_items if item.get('x') is not None]
            y_coords = [item.get('y', 0) for item in footer_items if item.get('y') is not None]
            w_coords = [item.get('w', 0) for item in footer_items if item.get('w') is not None]
            h_coords = [item.get('h', 0) for item in footer_items if item.get('h') is not None]
            
            if x_coords and y_coords:
                regions.append({
                    'type': 'footer_region',
                    'start_x': min(x_coords),
                    'end_x': max(x_coords) + (max(w_coords) if w_coords else 0),
                    'start_y': min(y_coords),
                    'end_y': max(y_coords) + (max(h_coords) if h_coords else 0),
                    'item_count': len(footer_items),
                    'confidence': 0.75,
                    'content_preview': ' '.join([item.get('text', '') for item in footer_items[:3]])
                })
        
        return regions
    
    def _detect_from_text(self, text_content: str) -> List[Dict[str, Any]]:
        """Detect footer regions from text content analysis"""
        regions = []
        
        # Look for footer patterns at the end of the document
        lines = text_content.split('\n')
        # Check last few lines for footer indicators
        for i in range(max(0, len(lines) - 5), len(lines)):
            line = lines[i].strip()
            if not line:
                continue
            if self._is_footer_text(line.lower()):
                regions.append({
                    'type': 'footer_region',
                    'start_line': i,
                    'end_line': i,
                    'confidence': 0.6,
                    'content_preview': line
                })
        
        return regions
    
    def _is_footer_text(self, text: str) -> bool:
        """Check if text appears to be a footer"""
        for pattern in self.footer_indicators:
            if re.search(pattern, text):
                return True
        return False


class TableConfidenceEngine:
    """Calculates confidence scores for table regions and their components"""
    
    def __init__(self):
        self.table_structure_indicators = [
            'description', 'quantity', 'unit_price', 'total', 'vat', 'code'
        ]
    
    def calculate_table_confidence(self, table_region: Dict, header_regions: List[Dict], 
                                 footer_regions: List[Dict], ocr_items: List[Dict]) -> float:
        """
        Calculate overall confidence for a table region.
        
        Args:
            table_region: Detected table region
            header_regions: Header regions within the table
            footer_regions: Footer regions within the table
            ocr_items: All OCR items in the document
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not table_region:
            return 0.0
            
        # Base confidence from table region quality
        base_confidence = table_region.get('confidence', 0.0)
        
        # Header quality contribution
        header_confidence = self._calculate_header_confidence(header_regions)
        
        # Footer quality contribution
        footer_confidence = self._calculate_footer_confidence(footer_regions)
        
        # Structure quality contribution
        structure_confidence = self._calculate_structure_confidence(
            table_region,
            ocr_items,
            header_regions,
            footer_regions,
        )
        
        # Weighted combination
        final_confidence = (
            0.4 * base_confidence +
            0.3 * header_confidence +
            0.2 * footer_confidence +
            0.1 * structure_confidence
        )
        
        return round(min(1.0, max(0.0, final_confidence)), 3)
    
    def _calculate_header_confidence(self, header_regions: List[Dict]) -> float:
        """Calculate confidence based on header region quality"""
        if not header_regions:
            return 0.0
            
        # Average confidence of header regions
        avg_confidence = sum(region.get('confidence', 0.0) for region in header_regions) / len(header_regions)
        
        # Bonus for having multiple header regions
        if len(header_regions) >= 2:
            avg_confidence = min(1.0, avg_confidence * 1.1)  # 10% bonus
            
        return avg_confidence
    
    def _calculate_footer_confidence(self, footer_regions: List[Dict]) -> float:
        """Calculate confidence based on footer region quality"""
        if not footer_regions:
            return 0.0
            
        # Average confidence of footer regions
        avg_confidence = sum(region.get('confidence', 0.0) for region in footer_regions) / len(footer_regions)
        
        return avg_confidence
    
    def calculate_structure_diagnostics(
        self,
        table_region: Dict,
        ocr_items: List[Dict],
        header_regions: Optional[List[Dict]] = None,
        footer_regions: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """Calculate region-local structure diagnostics for shadow-mode scoring."""
        region_items = self._items_inside_region(table_region, ocr_items)
        row_bands = self._row_bands(region_items)
        numeric_lanes = self._numeric_lanes(region_items, row_bands)

        row_density_score = self._row_density_score(row_bands)
        vertical_spacing_score = self._vertical_spacing_score(row_bands)
        numeric_column_lane_score = self._numeric_column_lane_score(numeric_lanes)
        header_alignment_score = self._header_alignment_score(
            header_regions or [],
            numeric_lanes,
            row_bands,
        )
        description_density_score = self._description_density_score(row_bands)
        footer_position_score = self._footer_position_score(table_region, footer_regions or [])
        product_band_support = self._product_band_support(row_bands, numeric_lanes)
        product_band_score = product_band_support["product_band_score"]
        product_band_count = product_band_support["product_band_count"]
        structured_band_count = product_band_support["structured_band_count"]
        calibrated_row_density_score = row_density_score * product_band_score
        calibrated_vertical_spacing_score = vertical_spacing_score * product_band_score
        calibrated_numeric_lane_score = numeric_column_lane_score * product_band_score
        oversized_region_penalty = self._oversized_region_penalty(
            len(region_items),
            product_band_score,
        )

        structure_confidence = (
            0.25 * row_density_score
            + 0.20 * vertical_spacing_score
            + 0.20 * numeric_column_lane_score
            + 0.15 * header_alignment_score
            + 0.10 * description_density_score
            + 0.10 * footer_position_score
        )
        structure_confidence_v2_1 = (
            0.25 * calibrated_row_density_score
            + 0.20 * calibrated_vertical_spacing_score
            + 0.20 * calibrated_numeric_lane_score
            + 0.15 * header_alignment_score
            + 0.10 * description_density_score
            + 0.10 * footer_position_score
        ) * oversized_region_penalty
        if oversized_region_penalty < 1.0 and product_band_score < 0.5:
            structure_confidence_v2_1 = min(structure_confidence_v2_1, 0.65)

        return {
            "structure_confidence_v2": round(min(1.0, max(0.0, structure_confidence)), 3),
            "structure_confidence_v2_1": round(min(1.0, max(0.0, structure_confidence_v2_1)), 3),
            "row_density_score": round(row_density_score, 3),
            "vertical_spacing_score": round(vertical_spacing_score, 3),
            "numeric_column_lane_score": round(numeric_column_lane_score, 3),
            "header_alignment_score": round(header_alignment_score, 3),
            "description_density_score": round(description_density_score, 3),
            "footer_position_score": round(footer_position_score, 3),
            "product_band_score": round(product_band_score, 3),
            "product_band_count": product_band_count,
            "structured_band_count": structured_band_count,
            "oversized_region_penalty": round(oversized_region_penalty, 3),
            "calibrated_row_density_score": round(calibrated_row_density_score, 3),
            "calibrated_vertical_spacing_score": round(calibrated_vertical_spacing_score, 3),
            "calibrated_numeric_lane_score": round(calibrated_numeric_lane_score, 3),
            "region_item_count": len(region_items),
        }

    def _calculate_structure_confidence(
        self,
        table_region: Dict,
        ocr_items: List[Dict],
        header_regions: Optional[List[Dict]] = None,
        footer_regions: Optional[List[Dict]] = None,
    ) -> float:
        """Calculate confidence based on table structure quality"""
        diagnostics = self.calculate_structure_diagnostics(
            table_region,
            ocr_items,
            header_regions,
            footer_regions,
        )
        return diagnostics["structure_confidence_v2_1"]

    def _items_inside_region(self, table_region: Dict, ocr_items: List[Dict]) -> List[Dict]:
        if not table_region or not ocr_items:
            return []

        left = self._to_float(table_region.get("start_x"))
        right = self._to_float(table_region.get("end_x"))
        top = self._to_float(table_region.get("start_y"))
        bottom = self._to_float(table_region.get("end_y"))
        if None in (left, right, top, bottom):
            return []

        region_items = []
        for item in ocr_items:
            if not isinstance(item, dict):
                continue
            center_x = self._item_center_x(item)
            center_y = self._item_center_y(item)
            if center_x is None or center_y is None:
                continue
            if left <= center_x <= right and top <= center_y <= bottom:
                region_items.append(item)
        return region_items

    def _row_bands(self, items: List[Dict]) -> List[Dict[str, Any]]:
        if not items:
            return []

        heights = [
            self._to_float(item.get("h"))
            for item in items
            if self._to_float(item.get("h")) and self._to_float(item.get("h")) > 0
        ]
        median_height = self._median(heights) if heights else 20.0
        row_tolerance = max(12.0, min(45.0, median_height * 0.75))
        bands: List[Dict[str, Any]] = []

        for item in sorted(items, key=lambda value: self._item_center_y(value) or 0.0):
            center_y = self._item_center_y(item)
            if center_y is None:
                continue
            if not bands or abs(center_y - bands[-1]["center_y"]) > row_tolerance:
                bands.append({"center_y": center_y, "items": [item]})
                continue
            band_items = bands[-1]["items"]
            band_items.append(item)
            bands[-1]["center_y"] = sum(
                self._item_center_y(band_item) or center_y
                for band_item in band_items
            ) / len(band_items)

        return bands

    def _numeric_lanes(self, items: List[Dict], row_bands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        numeric_items = [
            item for item in items
            if self._is_numeric_text(str(item.get("text", "")))
        ]
        if not numeric_items:
            return []

        x_centers = [
            self._item_center_x(item)
            for item in numeric_items
            if self._item_center_x(item) is not None
        ]
        widths = [
            self._to_float(item.get("w"))
            for item in numeric_items
            if self._to_float(item.get("w")) and self._to_float(item.get("w")) > 0
        ]
        median_width = self._median(widths) if widths else 60.0
        lane_tolerance = max(45.0, min(140.0, median_width * 1.5))
        lanes: List[Dict[str, Any]] = []

        for item in sorted(numeric_items, key=lambda value: self._item_center_x(value) or 0.0):
            center_x = self._item_center_x(item)
            if center_x is None:
                continue
            matching_lane = None
            for lane in lanes:
                if abs(center_x - lane["center_x"]) <= lane_tolerance:
                    matching_lane = lane
                    break
            if matching_lane is None:
                lanes.append({"center_x": center_x, "items": [item], "row_count": 0})
                continue
            matching_lane["items"].append(item)
            matching_lane["center_x"] = sum(
                self._item_center_x(lane_item) or center_x
                for lane_item in matching_lane["items"]
            ) / len(matching_lane["items"])

        for lane in lanes:
            lane_rows = set()
            for item in lane["items"]:
                center_y = self._item_center_y(item)
                if center_y is None:
                    continue
                for index, row in enumerate(row_bands):
                    if item in row["items"] or abs(center_y - row["center_y"]) <= 20.0:
                        lane_rows.add(index)
                        break
            lane["row_count"] = len(lane_rows)

        return lanes

    def _row_density_score(self, row_bands: List[Dict[str, Any]]) -> float:
        if not row_bands:
            return 0.0
        structured_rows = sum(1 for row in row_bands if len(row["items"]) >= 2)
        return min(1.0, structured_rows / 8.0)

    def _vertical_spacing_score(self, row_bands: List[Dict[str, Any]]) -> float:
        structured_rows = [row for row in row_bands if len(row["items"]) >= 2]
        if len(structured_rows) < 3:
            return 0.0
        gaps = [
            structured_rows[index + 1]["center_y"] - structured_rows[index]["center_y"]
            for index in range(len(structured_rows) - 1)
            if structured_rows[index + 1]["center_y"] > structured_rows[index]["center_y"]
        ]
        if len(gaps) < 2:
            return 0.0
        median_gap = self._median(gaps)
        if not median_gap:
            return 0.0
        deviations = [abs(gap - median_gap) for gap in gaps]
        relative_deviation = self._median(deviations) / median_gap
        return min(1.0, max(0.0, 1.0 - (relative_deviation * 2.0)))

    def _numeric_column_lane_score(self, numeric_lanes: List[Dict[str, Any]]) -> float:
        stable_lanes = [
            lane for lane in numeric_lanes
            if len(lane["items"]) >= 2 and lane.get("row_count", 0) >= 2
        ]
        return min(1.0, len(stable_lanes) / 4.0)

    def _product_band_support(
        self,
        row_bands: List[Dict[str, Any]],
        numeric_lanes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        structured_rows = [row for row in row_bands if len(row["items"]) >= 2]
        if not structured_rows:
            return {
                "product_band_score": 0.0,
                "product_band_count": 0,
                "structured_band_count": 0,
            }

        stable_lanes = [
            lane for lane in numeric_lanes
            if len(lane["items"]) >= 2 and lane.get("row_count", 0) >= 2
        ]
        if not stable_lanes:
            return {
                "product_band_score": 0.0,
                "product_band_count": 0,
                "structured_band_count": len(structured_rows),
            }

        product_band_count = 0
        for row in structured_rows:
            if self._is_product_like_band(row, stable_lanes):
                product_band_count += 1

        return {
            "product_band_score": product_band_count / len(structured_rows),
            "product_band_count": product_band_count,
            "structured_band_count": len(structured_rows),
        }

    def _is_product_like_band(self, row: Dict[str, Any], stable_lanes: List[Dict[str, Any]]) -> bool:
        numeric_items = [
            item for item in row["items"]
            if self._is_numeric_text(str(item.get("text", "")))
        ]
        text_items = [
            item for item in row["items"]
            if self._is_description_like_text(str(item.get("text", "")))
        ]
        if len(numeric_items) < 2 or not text_items:
            return False

        numeric_centers = [
            self._item_center_x(item)
            for item in numeric_items
            if self._item_center_x(item) is not None
        ]
        text_centers = [
            self._item_center_x(item)
            for item in text_items
            if self._item_center_x(item) is not None
        ]
        if not numeric_centers or not text_centers:
            return False
        if min(text_centers) >= max(numeric_centers):
            return False

        lane_tolerance = self._stable_lane_tolerance(stable_lanes)
        aligned_numeric_count = 0
        aligned_lane_indexes = set()
        for center in numeric_centers:
            for index, lane in enumerate(stable_lanes):
                if center <= min(text_centers):
                    continue
                if abs(center - lane["center_x"]) <= lane_tolerance:
                    aligned_numeric_count += 1
                    aligned_lane_indexes.add(index)
                    break

        return aligned_numeric_count >= 2 and len(aligned_lane_indexes) >= 2

    def _oversized_region_penalty(self, region_item_count: int, product_band_score: float) -> float:
        if region_item_count <= 100:
            return 1.0
        if region_item_count >= 130 and product_band_score < 0.9:
            return 0.65
        if product_band_score >= 0.5:
            return 1.0
        if region_item_count >= 150:
            return 0.65
        oversize_ratio = (region_item_count - 100) / 50.0
        return max(0.65, 1.0 - (0.35 * oversize_ratio))

    def _stable_lane_tolerance(self, stable_lanes: List[Dict[str, Any]]) -> float:
        widths = [
            self._to_float(item.get("w"))
            for lane in stable_lanes
            for item in lane["items"]
            if self._to_float(item.get("w")) and self._to_float(item.get("w")) > 0
        ]
        median_width = self._median(widths) if widths else 60.0
        return max(45.0, min(140.0, median_width * 1.5))

    def _is_description_like_text(self, text: str) -> bool:
        text = text.strip()
        if not text or not re.search(r"[A-Za-z]", text):
            return False
        lowered = text.lower()
        non_product_patterns = [
            r"\b(?:tax|vat|invoice|account|customer|supplier|deliver|shipping)\b",
            r"\b(?:bank|branch|payment|tender|deposit|balance|routing)\b",
            r"\b(?:subtotal|total|discount|rounding|currency|amount)\b",
            r"\b(?:signature|signed|received|created|printed|page)\b",
            r"\b(?:telephone|email|fax|whatsapp|address|terms)\b",
        ]
        return not any(re.search(pattern, lowered) for pattern in non_product_patterns)

    def _header_alignment_score(
        self,
        header_regions: List[Dict],
        numeric_lanes: List[Dict[str, Any]],
        row_bands: List[Dict[str, Any]],
    ) -> float:
        if not header_regions or not row_bands:
            return 0.0

        header_centers = []
        for region in header_regions:
            left = self._to_float(region.get("start_x"))
            right = self._to_float(region.get("end_x"))
            if left is not None and right is not None:
                header_centers.append((left + right) / 2.0)
        if not header_centers:
            return 0.0

        lane_centers = [
            lane["center_x"]
            for lane in numeric_lanes
            if len(lane["items"]) >= 2
        ]
        text_centers = [
            self._item_center_x(item)
            for row in row_bands
            for item in row["items"]
            if not self._is_numeric_text(str(item.get("text", "")))
        ]
        text_centers = [center for center in text_centers if center is not None]
        if text_centers:
            lane_centers.append(self._median(text_centers))
        if not lane_centers:
            return 0.0

        aligned = 0
        for header_center in header_centers:
            if min(abs(header_center - lane_center) for lane_center in lane_centers) <= 350.0:
                aligned += 1
        return aligned / len(header_centers)

    def _description_density_score(self, row_bands: List[Dict[str, Any]]) -> float:
        structured_rows = [row for row in row_bands if len(row["items"]) >= 2]
        if not structured_rows:
            return 0.0
        description_rows = 0
        for row in structured_rows:
            sorted_items = sorted(row["items"], key=lambda item: self._item_center_x(item) or 0.0)
            numeric_positions = [
                self._item_center_x(item)
                for item in sorted_items
                if self._is_numeric_text(str(item.get("text", "")))
            ]
            text_positions = [
                self._item_center_x(item)
                for item in sorted_items
                if not self._is_numeric_text(str(item.get("text", "")))
                and str(item.get("text", "")).strip()
            ]
            numeric_positions = [position for position in numeric_positions if position is not None]
            text_positions = [position for position in text_positions if position is not None]
            if text_positions and numeric_positions and min(text_positions) < max(numeric_positions):
                description_rows += 1
        return description_rows / len(structured_rows)

    def _footer_position_score(self, table_region: Dict, footer_regions: List[Dict]) -> float:
        if not table_region:
            return 0.0
        if not footer_regions:
            return 0.5

        bottom = self._to_float(table_region.get("end_y"))
        if bottom is None:
            return 0.0

        scores = []
        for region in footer_regions:
            start_y = self._to_float(region.get("start_y"))
            end_y = self._to_float(region.get("end_y"))
            if start_y is None or end_y is None:
                scores.append(0.5)
            elif start_y >= bottom:
                scores.append(1.0)
            elif end_y <= bottom:
                scores.append(0.0)
            else:
                scores.append(0.25)
        return max(scores) if scores else 0.5

    def _is_numeric_text(self, text: str) -> bool:
        text = text.strip().replace(" ", "")
        if not text:
            return False
        return bool(re.match(r"^[+-]?\d+(?:[,.]\d+)?%?$", text))

    def _item_center_x(self, item: Dict) -> Optional[float]:
        x = self._to_float(item.get("x"))
        if x is None:
            return None
        width = self._to_float(item.get("w")) or 0.0
        return x + (width / 2.0)

    def _item_center_y(self, item: Dict) -> Optional[float]:
        y = self._to_float(item.get("y"))
        if y is None:
            return None
        height = self._to_float(item.get("h")) or 0.0
        return y + (height / 2.0)

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _median(self, values: List[float]) -> float:
        clean_values = sorted(value for value in values if value is not None)
        if not clean_values:
            return 0.0
        midpoint = len(clean_values) // 2
        if len(clean_values) % 2:
            return clean_values[midpoint]
        return (clean_values[midpoint - 1] + clean_values[midpoint]) / 2.0
