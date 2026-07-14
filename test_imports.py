#!/usr/bin/env python3
"""Test script to verify imports work correctly"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import adaptive_header_framework
    print("✓ adaptive_header_framework imported successfully")
    
    # Test that we can access HeaderCandidate
    from adaptive_header_framework import HeaderCandidate
    print("✓ HeaderCandidate imported successfully")
    
    # Test that we can access the imported table boundary classes
    from adaptive_header_framework import TableRegionDetector, HeaderRegionLocator, FooterRegionLocator, TableConfidenceEngine
    print("✓ Table boundary classes imported successfully")
    
    import table_boundary_framework
    print("✓ table_boundary_framework imported successfully")
    
    print("\nAll imports successful!")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()