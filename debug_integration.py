#!/usr/bin/env python3
"""
Debug Script to Trace Ingredient Intelligence Integration
"""

import json
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, '.')

def debug_integration():
    """Debug the integration step by step"""
    
    # Load a test file that we know has PRODUCT rows
    test_file = Path('data/parser-test-results/20260617_162204.json')
    
    if not test_file.exists():
        print(f"Test file not found: {test_file}")
        return
    
    print("=== DEBUGGING INTEGRATION ===")
    print(f"Loading test file: {test_file}")
    
    # Load the test data
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    print(f"File loaded successfully")
    print(f"Total rows in universal extractor: {len(data.get('universal_line_item_extractor', {}).get('rows', []))}")
    
    # Check row types
    universal_rows = data.get('universal_line_item_extractor', {}).get('rows', [])
    product_rows = [r for r in universal_rows if r.get('row_type', '').lower() == 'product']
    print(f"PRODUCT rows found: {len(product_rows)}")
    
    if product_rows:
        first_product = product_rows[0]
        print(f"First PRODUCT row keys: {list(first_product.keys())}")
        print(f"Row type: {first_product.get('row_type')}")
        print(f"Raw text: {first_product.get('raw_text', '')[:100]}...")
        
        # Check if ingredient_candidate is already there
        has_ingredient_candidate = 'ingredient_candidate' in first_product
        print(f"Has ingredient_candidate: {has_ingredient_candidate}")
        
        # Check if it has classification fields
        has_classification = 'row_type_confidence' in first_product
        print(f"Has classification fields: {has_classification}")
        
        if has_classification:
            print(f"Row type confidence: {first_product.get('row_type_confidence')}")
            print(f"Classification reasons: {first_product.get('classification_reasons')}")
        
        # Show what the raw text looks like
        raw_text = first_product.get('raw_text', '') or first_product.get('description', '')
        print(f"Raw text for ingredient analysis: {raw_text}")
        
        # Try to manually run the ingredient analysis
        try:
            from ingredient_intelligence import IngredientIntelligenceEngine
            engine = IngredientIntelligenceEngine()
            result = engine.analyze_product_row(raw_text, first_product)
            print(f"Manual analysis successful!")
            print(f"Candidate name: {result.candidate_name}")
            print(f"Pack size value: {result.pack_size_value}")
            print(f"Pack size unit: {result.pack_size_unit}")
            print(f"Confidence: {result.confidence}")
        except Exception as e:
            print(f"Manual analysis failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("No PRODUCT rows found in this file")

if __name__ == "__main__":
    debug_integration()