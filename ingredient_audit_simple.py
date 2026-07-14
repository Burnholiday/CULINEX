#!/usr/bin/env python3
"""
Simple Ingredient Candidate Audit Script
Sprint 24.2 - Audit saved ingredient candidates for normalization errors
"""

import json
import os
import re
from pathlib import Path
from collections import Counter, defaultdict

def load_parser_test_results():
    """Load all parser test result files"""
    results_dir = Path("data/parser-test-results")
    if not results_dir.exists():
        raise FileNotFoundError("Parser test results directory not found")
    
    results = []
    for json_file in results_dir.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                results.append(data)
        except Exception as e:
            print(f"Error loading {json_file}: {e}")
    
    return results

def analyze_ingredient_diagnostics_simple(results):
    """Simple analysis of ingredient diagnostics from parser test results"""
    
    # Audit counters
    totals = {
        'product_rows_analyzed': 0,
        'candidate_name_present': 0,
        'supplier_code_detected': 0,
        'purchase_unit_detected': 0,
        'pack_count_detected': 0,
        'pack_size_detected': 0,
        'total_pack_quantity_calculated': 0,
        'low_confidence': 0,
        'conflicting_signals': 0
    }
    
    # Audit results
    evidence_table = []
    dangerous_errors = []
    patterns = defaultdict(list)
    
    # Process all results
    for result in results:
        filename = result.get('filename', 'Unknown')
        universal_extractor = result.get('universal_line_item_extractor', {})
        rows = universal_extractor.get('rows', [])
        
        for row in rows:
            # Only analyze PRODUCT rows (case insensitive)
            row_type = row.get('row_type', '').lower()
            if row_type != 'product':
                continue
                
            totals['product_rows_analyzed'] += 1
            
            # Check for ingredient diagnostics (they might not be present in current data)
            # We'll check what fields are available
            supplier_description = row.get('raw_text', '') or row.get('description', '')
            candidate_name = row.get('ingredient', '')  # This is the extracted ingredient name
            supplier_code = row.get('supplier_code', '')
            purchase_unit = row.get('purchase_unit', '')
            quantity = row.get('quantity', None)
            unit_price = row.get('unit_price', None)
            line_total = row.get('line_total', None)
            
            # Check for potential issues in the raw data
            if candidate_name:
                totals['candidate_name_present'] += 1
                
            if supplier_code:
                totals['supplier_code_detected'] += 1
                
            if purchase_unit:
                totals['purchase_unit_detected'] += 1
                
            # Check for dangerous patterns in the raw data
            if not candidate_name and supplier_description:
                # Check if supplier description contains what should be in candidate name
                dangerous_patterns = [
                    (r'\bkg\b', 'contains kg unit'),
                    (r'\bg\b', 'contains g unit'),
                    (r'\bml\b', 'contains ml unit'),
                    (r'\bl\b', 'contains l unit'),
                    (r'\d+\.\d+\s*[Rr]\b', 'contains price value'),
                    (r'\d+\.\d+\s*(?:kg|g|ml|l)\b', 'contains quantity with unit'),
                ]
                
                for pattern, description in dangerous_patterns:
                    if re.search(pattern, supplier_description, re.IGNORECASE):
                        dangerous_errors.append({
                            'filename': filename,
                            'error': f'Raw data issue: {description}',
                            'row': {
                                'filename': filename,
                                'supplier_description': supplier_description,
                                'candidate_name': candidate_name,
                                'supplier_code': supplier_code,
                                'purchase_unit': purchase_unit,
                                'quantity': quantity,
                                'unit_price': unit_price,
                                'line_total': line_total
                            }
                        })
            
            # Add to evidence table
            evidence_row = {
                'filename': filename,
                'supplier_description': supplier_description,
                'candidate_name': candidate_name,
                'supplier_code': supplier_code,
                'purchase_unit': purchase_unit,
                'quantity': quantity,
                'unit_price': unit_price,
                'line_total': line_total,
                'audit_assessment': 'unknown'
            }
            
            # Simple assessment based on what we can see
            assessment = 'likely_correct'
            
            # Check for obvious issues
            if not candidate_name:
                assessment = 'likely_incorrect'
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name empty',
                    'row': evidence_row
                })
            elif 'kg' in candidate_name.lower() or 'g' in candidate_name.lower():
                assessment = 'likely_incorrect'
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name contains unit information',
                    'row': evidence_row
                })
            elif '0.00' in candidate_name or '0.0' in candidate_name:
                assessment = 'likely_incorrect'
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name contains price value',
                    'row': evidence_row
                })
            
            evidence_row['audit_assessment'] = assessment
            evidence_table.append(evidence_row)
    
    # Categorize evidence table results
    likely_correct = [row for row in evidence_table if row['audit_assessment'] == 'likely_correct']
    likely_incorrect = [row for row in evidence_table if row['audit_assessment'] == 'likely_incorrect']
    ambiguous = []  # Not applicable in simple version
    
    return {
        'totals': totals,
        'evidence_table': evidence_table,
        'likely_correct': likely_correct,
        'likely_incorrect': likely_incorrect,
        'ambiguous': ambiguous,
        'dangerous_errors': dangerous_errors,
        'patterns': patterns
    }

def generate_simple_audit_report(analysis_results):
    """Generate a simple audit report"""
    
    totals = analysis_results['totals']
    evidence_table = analysis_results['evidence_table']
    likely_correct = analysis_results['likely_correct']
    likely_incorrect = analysis_results['likely_incorrect']
    dangerous_errors = analysis_results['dangerous_errors']
    
    # Generate report
    report_lines = [
        "# Simple Ingredient Candidate Audit Report - Sprint 24.2",
        "",
        "## Summary",
        f"- PRODUCT rows analyzed: {totals['product_rows_analyzed']}",
        f"- candidate_name present: {totals['candidate_name_present']}",
        f"- supplier_code detected: {totals['supplier_code_detected']}",
        f"- purchase_unit detected: {totals['purchase_unit_detected']}",
        f"- low-confidence rows: {totals['low_confidence']}",
        f"- conflicting-signal rows: {totals['conflicting_signals']}",
        "",
        "## Assessment Results",
        f"- Likely Correct: {len(likely_correct)}",
        f"- Likely Incorrect: {len(likely_incorrect)}",
        f"- Ambiguous: {len(analysis_results['ambiguous'])}",
        f"- Dangerous Errors: {len(dangerous_errors)}",
        "",
        "## Dangerous Errors Found",
        f"- Total dangerous errors: {len(dangerous_errors)}",
        ""
    ]
    
    # Add dangerous error details
    if dangerous_errors:
        report_lines.append("### Dangerous Error Details:")
        for error in dangerous_errors[:10]:  # Show first 10
            report_lines.append(f"- {error['filename']}: {error['error']}")
        if len(dangerous_errors) > 10:
            report_lines.append(f"... and {len(dangerous_errors) - 10} more dangerous errors")
        report_lines.append("")
    
    # Add evidence table header
    report_lines.extend([
        "## Evidence Table (First 20 rows)",
        "| Filename | Supplier Description | Candidate Name | Supplier Code | Purchase Unit | Quantity | Unit Price | Line Total | Assessment |",
        "|----------|----------------------|----------------|---------------|---------------|----------|------------|------------|------------|"
    ])
    
    # Add evidence table rows (limit to first 20 for readability)
    for row in evidence_table[:20]:
        report_lines.append(
            f"| {row['filename'][:20]} | {row['supplier_description'][:20]}... | {row['candidate_name'][:15]} | {row['supplier_code'] or ''} | {row['purchase_unit'] or ''} | {row['quantity'] or ''} | {row['unit_price'] or ''} | {row['line_total'] or ''} | {row['audit_assessment']} |"
        )
    
    if len(evidence_table) > 20:
        report_lines.append(f"... and {len(evidence_table) - 20} more rows")
    
    # Add recommendations
    report_lines.extend([
        "",
        "## Recommendations for Sprint 24.3",
        "",
        "### Immediate Actions",
        "1. **Fix candidate name extraction** - Ensure unit information is not included in candidate names",
        "2. **Improve supplier code detection** - Handle edge cases in supplier code recognition",
        "3. **Enhance raw text processing** - Better handle supplier descriptions that contain unit information",
        "4. **Add validation for empty candidate names** - Prevent empty ingredient names from being saved",
        "",
        "### Long-term Improvements",
        "1. **Add more comprehensive error detection** - Identify patterns that lead to dangerous errors",
        "2. **Implement deterministic fixes** - Add rules to correct common normalization issues",
        "3. **Improve confidence scoring** - Better distinguish between correct and incorrect extractions",
        "4. **Add pattern-based corrections** - Implement fixes for repeated error patterns",
        "",
        "### Priority Areas for Improvement",
        f"- Dangerous errors: {len(dangerous_errors)} instances",
        f"- Empty candidate names: {totals['product_rows_analyzed'] - totals['candidate_name_present']} instances",
        f"- Supplier code issues: {totals['supplier_code_detected']} instances",
        ""
    ])
    
    return "\n".join(report_lines)

def main():
    """Main function to run the simple audit"""
    print("Running Simple Ingredient Candidate Audit...")
    
    try:
        # Load parser test results
        results = load_parser_test_results()
        print(f"Loaded {len(results)} parser test results")
        
        # Analyze diagnostics
        analysis = analyze_ingredient_diagnostics_simple(results)
        
        # Generate report
        report = generate_simple_audit_report(analysis)
        
        # Save report
        with open('docs/SPRINT_24_2_SIMPLE_INGREDIENT_AUDIT.md', 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("Simple audit completed successfully!")
        print(f"Report saved to docs/SPRINT_24_2_SIMPLE_INGREDIENT_AUDIT.md")
        print(f"Total PRODUCT rows analyzed: {analysis['totals']['product_rows_analyzed']}")
        print(f"Dangerous errors found: {len(analysis['dangerous_errors'])}")
        
        # Print summary to console
        print("\n" + "="*50)
        print("SIMPLE AUDIT SUMMARY")
        print("="*50)
        print(f"PRODUCT rows analyzed: {analysis['totals']['product_rows_analyzed']}")
        print(f"Likely correct: {len(analysis['likely_correct'])}")
        print(f"Likely incorrect: {len(analysis['likely_incorrect'])}")
        print(f"Ambiguous: {len(analysis['ambiguous'])}")
        print(f"Dangerous errors: {len(analysis['dangerous_errors'])}")
        
    except Exception as e:
        print(f"Error during audit: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()