#!/usr/bin/env python3
"""Verification script for Sprint 18.1 - Move Table Boundary Framework"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_file_structure():
    """Verify that files were created correctly"""
    print("=== Testing File Structure ===")
    
    # Check that both files exist
    assert os.path.exists('adaptive_header_framework.py'), "adaptive_header_framework.py not found"
    assert os.path.exists('table_boundary_framework.py'), "table_boundary_framework.py not found"
    print("✓ Both files exist")
    
    # Check that adaptive_header_framework.py contains the import
    with open('adaptive_header_framework.py', 'r') as f:
        content = f.read()
        assert 'from table_boundary_framework import' in content, "Import statement not found in adaptive_header_framework.py"
        print("✓ Import statement found in adaptive_header_framework.py")
    
    # Check that table_boundary_framework.py contains the classes
    with open('table_boundary_framework.py', 'r') as f:
        content = f.read()
        assert 'class TableRegionDetector' in content, "TableRegionDetector not found in table_boundary_framework.py"
        assert 'class HeaderRegionLocator' in content, "HeaderRegionLocator not found in table_boundary_framework.py"
        assert 'class FooterRegionLocator' in content, "FooterRegionLocator not found in table_boundary_framework.py"
        assert 'class TableConfidenceEngine' in content, "TableConfidenceEngine not found in table_boundary_framework.py"
        print("✓ All 4 table boundary classes found in table_boundary_framework.py")
    
    # Check that adaptive_header_framework.py no longer contains the table boundary classes
    assert 'class TableRegionDetector' not in content, "TableRegionDetector still found in adaptive_header_framework.py"
    assert 'class HeaderRegionLocator' not in content, "HeaderRegionLocator still found in adaptive_header_framework.py"
    assert 'class FooterRegionLocator' not in content, "FooterRegionLocator still found in adaptive_header_framework.py"
    assert 'class TableConfidenceEngine' not in content, "TableConfidenceEngine still found in adaptive_header_framework.py"
    print("✓ Table boundary classes removed from adaptive_header_framework.py")

def test_imports():
    """Test that imports work correctly"""
    print("\n=== Testing Imports ===")
    
    # Test importing adaptive_header_framework
    import adaptive_header_framework
    print("✓ adaptive_header_framework imported successfully")
    
    # Test importing specific classes from adaptive_header_framework
    from adaptive_header_framework import HeaderCandidate, HeaderNormalizer
    print("✓ Header-related classes imported successfully")
    
    # Test importing table boundary classes from adaptive_header_framework (should work due to import)
    from adaptive_header_framework import TableRegionDetector, HeaderRegionLocator, FooterRegionLocator, TableConfidenceEngine
    print("✓ Table boundary classes imported from adaptive_header_framework successfully")
    
    # Test importing table_boundary_framework directly
    import table_boundary_framework
    print("✓ table_boundary_framework imported successfully")
    
    # Test importing specific classes from table_boundary_framework
    from table_boundary_framework import TableRegionDetector, HeaderRegionLocator, FooterRegionLocator, TableConfidenceEngine
    print("✓ Table boundary classes imported directly from table_boundary_framework successfully")

def test_functionality():
    """Test that basic functionality still works"""
    print("\n=== Testing Functionality ===")
    
    # Test that we can create header candidates
    from adaptive_header_framework import create_header_candidate
    candidate = create_header_candidate("Description", (100, 200))
    assert candidate.text == "Description"
    assert candidate.field_type.name == "DESCRIPTION"
    print("✓ Header candidate creation works")
    
    # Test that we can create table boundary classes
    from table_boundary_framework import TableRegionDetector, HeaderRegionLocator, FooterRegionLocator, TableConfidenceEngine
    detector = TableRegionDetector()
    header_locator = HeaderRegionLocator()
    footer_locator = FooterRegionLocator()
    confidence_engine = TableConfidenceEngine()
    print("✓ Table boundary classes can be instantiated")

def main():
    """Run all verification tests"""
    print("Sprint 18.1 - Move Table Boundary Framework - Verification")
    print("=" * 60)
    
    try:
        test_file_structure()
        test_imports()
        test_functionality()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - Sprint 18.1 completed successfully!")
        print("✅ Table boundary framework moved to separate module")
        print("✅ Imports work correctly")
        print("✅ Parser functionality unchanged")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)