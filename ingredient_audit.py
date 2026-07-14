#!/usr/bin/env python3
"""
Ingredient Candidate Audit Script
Sprint 24.2 - Audit saved ingredient candidates for normalization errors
"""

import json
import os
import re
from pathlib import Path
from collections import Counter, defaultdict

# Audit configuration
MIN_CONFIDENCE_THRESHOLD = 0.70
AUDIT_TARGETS = {
    'weight_based': 20,
    'each_based': 15,
    'multi_pack': 0,  # Will count dynamically
    'supplier_code': 0,  # Will count dynamically
    'low_confidence': 0,  # Will count dynamically
    'conflicting_signals': 0  # Will count dynamically
}

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

def analyze_ingredient_diagnostics(results):
    """Analyze ingredient diagnostics from parser test results"""
    
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
    
    # Track counts for audit targets
    weight_based_count = 0
    each_based_count = 0
    multi_pack_count = 0
    supplier_code_count = 0
    low_confidence_count = 0
    conflicting_signals_count = 0
    
    # Process all results
    for result in results:
        filename = result.get('filename', 'Unknown')
        universal_extractor = result.get('universal_line_item_extractor', {})
        rows = universal_extractor.get('rows', [])
        
        for row in rows:
            # Only analyze PRODUCT rows
            if row.get('row_type') != 'PRODUCT':
                continue
                
            totals['product_rows_analyzed'] += 1
            
            # Check for ingredient diagnostics
            ingredient_candidate = row.get('ingredient_candidate')
            if not ingredient_candidate:
                # This shouldn't happen if integration is working properly
                continue
                
            # Extract diagnostic information
            candidate_name = ingredient_candidate.get('candidate_name', '')
            supplier_code = ingredient_candidate.get('supplier_code', None)
            purchase_unit = ingredient_candidate.get('purchase_unit', None)
            pack_count = ingredient_candidate.get('pack_count', None)
            pack_size_value = ingredient_candidate.get('pack_size_value', None)
            pack_size_unit = ingredient_candidate.get('pack_size_unit', None)
            total_pack_quantity = ingredient_candidate.get('total_pack_quantity', None)
            confidence = ingredient_candidate.get('confidence', 0.0)
            matched_signals = ingredient_candidate.get('matched_signals', [])
            conflicting_signals = ingredient_candidate.get('conflicting_signals', [])
            
            # Update totals
            if candidate_name:
                totals['candidate_name_present'] += 1
            if supplier_code:
                totals['supplier_code_detected'] += 1
                supplier_code_count += 1
            if purchase_unit:
                totals['purchase_unit_detected'] += 1
            if pack_count is not None:
                totals['pack_count_detected'] += 1
            if pack_size_value is not None:
                totals['pack_size_detected'] += 1
            if total_pack_quantity:
                totals['total_pack_quantity_calculated'] += 1
            if confidence < MIN_CONFIDENCE_THRESHOLD:
                totals['low_confidence'] += 1
                low_confidence_count += 1
            if conflicting_signals:
                totals['conflicting_signals'] += 1
                conflicting_signals_count += 1
            
            # Add to evidence table
            evidence_row = {
                'filename': filename,
                'supplier_description': ingredient_candidate.get('supplier_description', ''),
                'normalized_description': ingredient_candidate.get('normalized_description', ''),
                'candidate_name': candidate_name,
                'supplier_code': supplier_code,
                'purchase_unit': purchase_unit,
                'pack_count': pack_count,
                'pack_size_value': pack_size_value,
                'pack_size_unit': pack_size_unit,
                'total_pack_quantity': total_pack_quantity,
                'confidence': confidence,
                'matched_signals': matched_signals,
                'conflicting_signals': conflicting_signals,
                'audit_assessment': 'unknown'
            }
            
            # Determine audit assessment
            assessment = 'likely_correct'
            error_found = False
            
            # Check for dangerous errors
            if not candidate_name:
                assessment = 'likely_incorrect'
                error_found = True
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name empty',
                    'row': evidence_row
                })
            elif 'kg' in candidate_name.lower() or 'g' in candidate_name.lower():
                # Check if candidate name contains unit information that shouldn't be there
                assessment = 'likely_incorrect'
                error_found = True
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name contains unit information',
                    'row': evidence_row
                })
            elif '0.00' in candidate_name or '0.0' in candidate_name:
                # Check for price values in candidate name
                assessment = 'likely_incorrect'
                error_found = True
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name contains price value',
                    'row': evidence_row
                })
            elif 'R' in candidate_name and re.search(r'\d+\.\d+', candidate_name):
                # Check for currency values in candidate name
                assessment = 'likely_incorrect'
                error_found = True
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'candidate_name contains currency value',
                    'row': evidence_row
                })
            elif pack_size_value is not None and pack_size_value <= 0:
                # Check for invalid pack sizes
                assessment = 'likely_incorrect'
                error_found = True
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'invalid pack size value',
                    'row': evidence_row
                })
            elif pack_count is not None and pack_count <= 0:
                # Check for invalid pack counts
                assessment = 'likely_incorrect'
                error_found = True
                dangerous_errors.append({
                    'filename': filename,
                    'error': 'invalid pack count value',
                    'row': evidence_row
                })
            elif pack_size_unit and pack_size_unit.lower() in ['kg', 'g', 'l', 'ml']:
                # Check if pack size unit is actually a product quantity
                if pack_size_value and pack_size_value > 1000 and pack_size_unit.lower() in ['kg', 'g']:
                    assessment = 'likely_incorrect'
                    error_found = True
                    dangerous_errors.append({
                        'filename': filename,
                        'error': 'pack size unit appears to be product quantity',
                        'row': evidence_row
                    })
            
            # Check for patterns that might indicate issues
            if '0.00' in evidence_row['supplier_description'] or '0.0' in evidence_row['supplier_description']:
                patterns['price_in_supplier_description'].append(evidence_row)
            if 'R' in evidence_row['supplier_description'] and re.search(r'\d+\.\d+', evidence_row['supplier_description']):
                patterns['currency_in_supplier_description'].append(evidence_row)
            if 'kg' in evidence_row['supplier_description'].lower() and 'kg' in evidence_row['candidate_name'].lower():
                patterns['unit_in_both'].append(evidence_row)
            if evidence_row['pack_count'] is not None and evidence_row['pack_count'] > 100:
                patterns['suspicious_pack_count'].append(evidence_row)
            if evidence_row['pack_size_value'] is not None and evidence_row['pack_size_value'] > 10000:
                patterns['suspicious_pack_size'].append(evidence_row)
            
            evidence_row['audit_assessment'] = assessment
            evidence_table.append(evidence_row)
            
            # Track for audit targets
            if pack_size_unit and pack_size_unit.lower() in ['kg', 'g']:
                weight_based_count += 1
            if purchase_unit and purchase_unit.lower() in ['ea', 'each', 'unit']:
                each_based_count += 1
            if pack_count is not None and pack_count > 1:
                multi_pack_count += 1
            if supplier_code:
                supplier_code_count += 1
            if confidence < MIN_CONFIDENCE_THRESHOLD:
                low_confidence_count += 1
            if conflicting_signals:
                conflicting_signals_count += 1
    
    # Update audit targets with actual counts
    AUDIT_TARGETS['weight_based'] = min(weight_based_count, AUDIT_TARGETS['weight_based'])
    AUDIT_TARGETS['each_based'] = min(each_based_count, AUDIT_TARGETS['each_based'])
    AUDIT_TARGETS['multi_pack'] = multi_pack_count
    AUDIT_TARGETS['supplier_code'] = supplier_code_count
    AUDIT_TARGETS['low_confidence'] = low_confidence_count
    AUDIT_TARGETS['conflicting_signals'] = conflicting_signals_count
    
    # Categorize evidence table results
    likely_correct = [row for row in evidence_table if row['audit_assessment'] == 'likely_correct']
    likely_incorrect = [row for row in evidence_table if row['audit_assessment'] == 'likely_incorrect']
    ambiguous = [row for row in evidence_table if row['audit_assessment'] == 'ambiguous']
    
    return {
        'totals': totals,
        'evidence_table': evidence_table,
        'likely_correct': likely_correct,
        'likely_incorrect': likely_incorrect,
        'ambiguous': ambiguous,
        'dangerous_errors': dangerous_errors,
        'patterns': patterns
    }

def generate_audit_report(analysis_results):
    """Generate a comprehensive audit report"""
    
    totals = analysis_results['totals']
    evidence_table = analysis_results['evidence_table']
    likely_correct = analysis_results['likely_correct']
    likely_incorrect = analysis_results['likely_incorrect']
    ambiguous = analysis_results['ambiguous']
    dangerous_errors = analysis_results['dangerous_errors']
    patterns = analysis_results['patterns']
    
    # Count by assessment
    assessment_counts = Counter(row['audit_assessment'] for row in evidence_table)
    
    # Generate report
    report_lines = [
        "# Ingredient Candidate Audit Report - Sprint 24.2",
        "",
        "## Summary",
        f"- PRODUCT rows analyzed: {totals['product_rows_analyzed']}",
        f"- candidate_name present: {totals['candidate_name_present']}",
        f"- supplier_code detected: {totals['supplier_code_detected']}",
        f"- purchase_unit detected: {totals['purchase_unit_detected']}",
        f"- pack_count detected: {totals['pack_count_detected']}",
        f"- pack_size detected: {totals['pack_size_detected']}",
        f"- total_pack_quantity calculated: {totals['total_pack_quantity_calculated']}",
        f"- low-confidence (< 0.70): {totals['low_confidence']}",
        f"- conflicting-signal rows: {totals['conflicting_signals']}",
        "",
        "## Assessment Results",
        f"- Likely Correct: {len(likely_correct)}",
        f"- Likely Incorrect: {len(likely_incorrect)}",
        f"- Ambiguous: {len(ambiguous)}",
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
    
    # Add pattern analysis
    if patterns:
        report_lines.append("## Repeated Patterns Found:")
        for pattern_name, pattern_rows in patterns.items():
            report_lines.append(f"- {pattern_name}: {len(pattern_rows)} occurrences")
        report_lines.append("")
    
    # Add evidence table header
    report_lines.extend([
        "## Evidence Table",
        "| Filename | Supplier Description | Candidate Name | Supplier Code | Purchase Unit | Pack Count | Pack Size | Confidence | Assessment |",
        "|----------|----------------------|----------------|---------------|---------------|------------|-----------|------------|------------|"
    ])
    
    # Add evidence table rows (limit to first 20 for readability)
    for row in evidence_table[:20]:
        report_lines.append(
            f"| {row['filename'][:20]} | {row['supplier_description'][:20]}... | {row['candidate_name'][:15]} | {row['supplier_code'] or ''} | {row['purchase_unit'] or ''} | {row['pack_count'] or ''} | {row['pack_size_value'] or ''} {row['pack_size_unit'] or ''} | {row['confidence']:.2f} | {row['audit_assessment']} |"
        )
    
    if len(evidence_table) > 20:
        report_lines.append(f"... and {len(evidence_table) - 20} more rows")
    
    # Add recommended plan
    report_lines.extend([
        "",
        "## Recommended Sprint 24.3 Calibration Plan",
        "",
        "### Immediate Actions",
        "1. **Fix repeated normalization errors** - Address patterns that appear frequently",
        "2. **Improve supplier code detection** - Handle edge cases in supplier code recognition",
        "3. **Enhance pack pattern recognition** - Better handle ambiguous pack size values",
        "4. **Refine confidence scoring** - Reduce false positives in low-confidence cases",
        "",
        "### Long-term Improvements",
        "1. **Add more unit validation** - Better distinguish between product quantities and pack sizes",
        "2. **Improve candidate name extraction** - Prevent unit information from being included in candidate names",
        "3. **Enhance signal matching** - Better handle edge cases in signal detection",
        "4. **Add pattern-based corrections** - Implement deterministic fixes for repeated error patterns",
        "",
        "### Priority Areas for Improvement",
        f"- Dangerous errors: {len(dangerous_errors)} instances",
        f"- Low confidence cases: {totals['low_confidence']} instances",
        f"- Conflicting signals: {totals['conflicting_signals']} instances",
        f"- Supplier code issues: {totals['supplier_code_detected']} instances",
        ""
    ])
    
    return "\n".join(report_lines)

def main():
    """Main function to run the audit"""
    print("Running Ingredient Candidate Audit...")
    
    try:
        # Load parser test results
        results = load_parser_test_results()
        print(f"Loaded {len(results)} parser test results")
        
        # Analyze diagnostics
        analysis = analyze_ingredient_diagnostics(results)
        
        # Generate report
        report = generate_audit_report(analysis)
        
        # Save report
        with open('docs/SPRINT_24_2_INGREDIENT_AUDIT.md', 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("Audit completed successfully!")
        print(f"Report saved to docs/SPRINT_24_2_INGREDIENT_AUDIT.md")
        print(f"Total PRODUCT rows analyzed: {analysis['totals']['product_rows_analyzed']}")
        print(f"Dangerous errors found: {len(analysis['dangerous_errors'])}")
        
        # Print summary to console
        print("\n" + "="*50)
        print("AUDIT SUMMARY")
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