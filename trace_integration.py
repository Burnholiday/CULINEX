#!/usr/bin/env python3
"""
Trace Integration to Find Where It Breaks
"""

import sys
import os
sys.path.insert(0, '.')

# Import the module to test the actual integration
from run-parser-tests import load_recipe_vault_module, run_one

def trace_integration():
    """Trace the integration by running a single test"""
    
    print("=== TRACING INTEGRATION ===")
    
    # Use a test invoice file
    test_invoice = "data/test-invoices/20260617_162204.jpg"
    from pathlib import Path
    test_invoice_path = Path(test_invoice)
    
    if not test_invoice_path.exists():
        print(f"Test invoice not found: {test_invoice}")
        # Try to find any test invoice
        import glob
        test_files = list(Path("data/test-invoices").glob("*"))
        if test_files:
            test_invoice_path = test_files[0]
            print(f"Using: {test_invoice_path}")
        else:
            print("No test invoices found")
            return
    
    print(f"Testing with invoice: {test_invoice_path}")
    
    try:
        # Load the module
        module = load_recipe_vault_module()
        print("Module loaded successfully")
        
        # Run one test
        result = run_one(module, test_invoice_path)
        print("Test run completed successfully")
        
        # Check the result structure
        universal_extractor = result.get('universal_line_item_extractor', {})
        rows = universal_extractor.get('rows', [])
        print(f"Total rows in result: {len(rows)}")
        
        # Find PRODUCT rows
        product_rows = [r for r in rows if r.get('row_type', '').lower() == 'product']
        print(f"PRODUCT rows in result: {len(product_rows)}")
        
        if product_rows:
            first_product = product_rows[0]
            print(f"First PRODUCT row keys: {list(first_product.keys())}")
            print(f"Has ingredient_candidate: {'ingredient_candidate' in first_product}")
            
            # Check if it has the expected fields
            expected_fields = ['ingredient_candidate', 'ingredient_confidence', 'ingredient_reasons']
            for field in expected_fields:
                print(f"Has {field}: {field in first_product}")
                
            if 'ingredient_candidate' in first_product:
                candidate = first_product['ingredient_candidate']
                print(f"Ingredient candidate type: {type(candidate)}")
                if isinstance(candidate, dict):
                    print(f"Ingredient candidate keys: {list(candidate.keys())}")
                else:
                    print(f"Ingredient candidate value: {candidate}")
            else:
                print("ingredient_candidate is missing from the result!")
                
        # Save the result to see what's actually in the JSON
        import json
        output_file = "debug_test_result.json"
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"Result saved to {output_file}")
        
    except Exception as e:
        print(f"Error during tracing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    trace_integration()