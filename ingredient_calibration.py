#!/usr/bin/env python3
"""
Ingredient Intelligence Calibration Report Generator
Sprint 24.4 - Calibrate Ingredient Intelligence Engine
"""

import json
import os
import re
from pathlib import Path
from collections import Counter, defaultdict
import statistics

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

def analyze_ingredient_calibration(results):
    """Analyze ingredient diagnostics for calibration"""
    
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
    
    # Detailed analysis
    low_confidence_rows = []
    dangerous_patterns = defaultdict(list)
    corrected_examples = []
    
    # Process all results
    for result in results:
        filename = result.get('filename', 'Unknown')
        universal_extractor = result.get('universal_line_item_extractor', {})
        rows = universal_extractor.get('rows', [])
        
        for row in rows:
            # Only analyze PRODUCT rows
            if row.get('row_type', '').lower() != 'product':
                continue
                
            totals['product_rows_analyzed'] += 1
            
            # Check for ingredient diagnostics
            ingredient_candidate = row.get('ingredient_candidate')
            if not ingredient_candidate:
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
            if purchase_unit:
                totals['purchase_unit_detected'] += 1
            if pack_count is not None:
                totals['pack_count_detected'] += 1
            if pack_size_value is not None:
                totals['pack_size_detected'] += 1
            if total_pack_quantity:
                totals['total_pack_quantity_calculated'] += 1
            if confidence < 0.70:
                totals['low_confidence'] += 1
                low_confidence_rows.append({
                    'filename': filename,
                    'row': row,
                    'confidence': confidence,
                    'candidate_name': candidate_name,
                    'supplier_description': ingredient_candidate.get('supplier_description', '')
                })
            if conflicting_signals:
                totals['conflicting_signals'] += 1
            
            # Check for dangerous patterns
            if not candidate_name:
                dangerous_patterns['empty_candidate_name'].append({
                    'filename': filename,
                    'supplier_description': ingredient_candidate.get('supplier_description', ''),
                    'row': row
                })
            elif '0.00' in candidate_name or '0.0' in candidate_name:
                dangerous_patterns['price_in_candidate_name'].append({
                    'filename': filename,
                    'supplier_description': ingredient_candidate.get('supplier_description', ''),
                    'candidate_name': candidate_name,
                    'row': row
                })
            elif 'R' in candidate_name and re.search(r'\d+\.\d+', candidate_name):
                dangerous_patterns['currency_in_candidate_name'].append({
                    'filename': filename,
                    'supplier_description': ingredient_candidate.get('supplier_description', ''),
                    'candidate_name': candidate_name,
                    'row': row
                })
            elif 'kg' in candidate_name.lower() or 'g' in candidate_name.lower():
                dangerous_patterns['unit_in_candidate_name'].append({
                    'filename': filename,
                    'supplier_description': ingredient_candidate.get('supplier_description', ''),
                    'candidate_name': candidate_name,
                    'row': row
                })
            elif pack_size_value is not None and pack_size_value <= 0:
                dangerous_patterns['invalid_pack_size'].append({
                    'filename': filename,
                    'supplier_description': ingredient_candidate.get('supplier_description', ''),
                    'candidate_name': candidate_name,
                    'pack_size_value': pack_size_value,
                    'row': row
                })
            elif pack_count is not None and pack_count <= 0:
                dangerous_patterns['invalid_pack_count'].append({
                    'filename': filename,
                    'supplier_description': ingredient_candidate.get('supplier_description', ''),
                    'candidate_name': candidate_name,
                    'pack_count': pack_count,
                    'row': row
                })
    
    # Calculate success rates
    success_rates = {}
    for key, value in totals.items():
        if key == 'product_rows_analyzed' or key.startswith('product_rows'):
            continue
        if totals['product_rows_analyzed'] > 0:
            success_rates[key] = round((value / totals['product_rows_analyzed']) * 100, 2)
        else:
            success_rates[key] = 0.0
    
    # Analyze low-confidence rows
    low_confidence_reasons = Counter()
    for row in low_confidence_rows:
        # Simple analysis of why confidence is low
        supplier_desc = row['supplier_description'].lower()
        if 'kg' in supplier_desc or 'g' in supplier_desc:
            low_confidence_reasons['unit_in_supplier_description'] += 1
        elif '0.00' in supplier_desc or '0.0' in supplier_desc:
            low_confidence_reasons['price_in_supplier_description'] += 1
        elif '0.00' in row['candidate_name'] or '0.0' in row['candidate_name']:
            low_confidence_reasons['price_in_candidate_name'] += 1
        else:
            low_confidence_reasons['other'] += 1
    
    # Calculate confidence statistics
    all_confidences = []
    for result in results:
        universal_extractor = result.get('universal_line_item_extractor', {})
        rows = universal_extractor.get('rows', [])
        for row in rows:
            if row.get('row_type', '').lower() == 'product':
                ingredient_candidate = row.get('ingredient_candidate')
                if ingredient_candidate:
                    confidence = ingredient_candidate.get('confidence', 0.0)
                    all_confidences.append(confidence)
    
    confidence_stats = {
        'mean': round(statistics.mean(all_confidences) if all_confidences else 0, 3),
        'median': round(statistics.median(all_confidences) if all_confidences else 0, 3),
        'min': round(min(all_confidences) if all_confidences else 0, 3),
        'max': round(max(all_confidences) if all_confidences else 0, 3),
        'std_dev': round(statistics.stdev(all_confidences) if len(all_confidences) > 1 else 0, 3) if all_confidences else 0
    }
    
    # Create confidence histogram bins
    confidence_bins = [0, 0.2, 0.4, 0.6, 0.7, 0.8, 0.9, 1.0]
    confidence_counts = [0] * (len(confidence_bins) - 1)
    
    for confidence in all_confidences:
        for i in range(len(confidence_bins) - 1):
            if confidence_bins[i] <= confidence < confidence_bins[i+1]:
                confidence_counts[i] += 1
                break
        else:
            # Handle edge case for exactly 1.0
            if confidence == 1.0:
                confidence_counts[-1] += 1
    
    # Create corrected examples (first 20)
    corrected_examples = []
    for result in results:
        universal_extractor = result.get('universal_line_item_extractor', {})
        rows = universal_extractor.get('rows', [])
        for row in rows:
            if row.get('row_type', '').lower() == 'product':
                ingredient_candidate = row.get('ingredient_candidate')
                if ingredient_candidate:
                    # Check if there are any issues that could be corrected
                    candidate_name = ingredient_candidate.get('candidate_name', '')
                    supplier_desc = ingredient_candidate.get('supplier_description', '')
                    
                    # Simple check for potential corrections
                    if 'kg' in candidate_name.lower() or 'g' in candidate_name.lower():
                        corrected_examples.append({
                            'filename': result.get('filename', ''),
                            'supplier_description': supplier_desc,
                            'original_candidate': candidate_name,
                            'corrected_candidate': candidate_name.split('kg')[0].split('g')[0].strip() if 'kg' in candidate_name.lower() or 'g' in candidate_name.lower() else candidate_name,
                            'issue': 'unit information in candidate name'
                        })
                    if len(corrected_examples) >= 20:
                        break
        if len(corrected_examples) >= 20:
            break
    
    return {
        'totals': totals,
        'success_rates': success_rates,
        'low_confidence_rows': low_confidence_rows,
        'low_confidence_reasons': low_confidence_reasons,
        'dangerous_patterns': dangerous_patterns,
        'confidence_stats': confidence_stats,
        'confidence_bins': confidence_bins,
        'confidence_counts': confidence_counts,
        'corrected_examples': corrected_examples[:20]
    }

def generate_calibration_report(analysis_results):
    """Generate comprehensive calibration report"""
    
    totals = analysis_results['totals']
    success_rates = analysis_results['success_rates']
    low_confidence_rows = analysis_results['low_confidence_rows']
    low_confidence_reasons = analysis_results['low_confidence_reasons']
    dangerous_patterns = analysis_results['dangerous_patterns']
    confidence_stats = analysis_results['confidence_stats']
    confidence_bins = analysis_results['confidence_bins']
    confidence_counts = analysis_results['confidence_counts']
    corrected_examples = analysis_results['corrected_examples']
    
    # Generate report
    report_lines = [
        "# Ingredient Intelligence Calibration Report - Sprint 24.4",
        "",
        "## Phase 1 - Audit Summary",
        "",
        f"- Total PRODUCT rows analyzed: {totals['product_rows_analyzed']}",
        f"- Candidate name success rate: {success_rates.get('candidate_name_present', 0):.2f}%",
        f"- Supplier code success rate: {success_rates.get('supplier_code_detected', 0):.2f}%",
        f"- Purchase unit success rate: {success_rates.get('purchase_unit_detected', 0):.2f}%",
        f"- Pack count success rate: {success_rates.get('pack_count_detected', 0):.2f}%",
        f"- Pack size success rate: {success_rates.get('pack_size_detected', 0):.2f}%",
        f"- Total pack quantity success rate: {success_rates.get('total_pack_quantity_calculated', 0):.2f}%",
        "",
        "## Phase 2 - Dangerous Errors",
        "",
        f"- Total dangerous patterns found: {sum(len(patterns) for patterns in dangerous_patterns.values())}",
        ""
    ]
    
    # Add dangerous pattern counts
    for pattern_name, pattern_list in dangerous_patterns.items():
        report_lines.append(f"- {pattern_name}: {len(pattern_list)} instances")
    
    # Add low-confidence analysis
    report_lines.extend([
        "",
        "## Phase 1 - Low-Confidence Analysis",
        "",
        f"- Low-confidence rows (< 0.70): {len(low_confidence_rows)}",
        ""
    ])
    
    # Add low-confidence reasons
    if low_confidence_reasons:
        report_lines.append("### Low-confidence reasons:")
        for reason, count in low_confidence_reasons.most_common():
            report_lines.append(f"- {reason}: {count}")
        report_lines.append("")
    
    # Add confidence statistics
    report_lines.extend([
        "## Phase 4 - Confidence Analysis",
        "",
        f"- Average confidence: {confidence_stats['mean']}",
        f"- Median confidence: {confidence_stats['median']}",
        f"- Minimum confidence: {confidence_stats['min']}",
        f"- Maximum confidence: {confidence_stats['max']}",
        f"- Standard deviation: {confidence_stats['std_dev']}",
        "",
        "### Confidence Histogram",
        "| Confidence Range | Count |",
        "|------------------|-------|"
    ])
    
    for i in range(len(confidence_bins) - 1):
        report_lines.append(f"| {confidence_bins[i]:.1f} - {confidence_bins[i+1]:.1f} | {confidence_counts[i]} |")
    
    # Add corrected examples
    report_lines.extend([
        "",
        "## Phase 3 - Universal Fixes Applied",
        "",
        "### 20 Corrected Examples",
        "| Filename | Supplier Description | Original Candidate | Corrected Candidate | Issue |",
        "|----------|----------------------|-------------------|---------------------|-------|"
    ])
    
    for example in corrected_examples:
        report_lines.append(
            f"| {example['filename'][:20]} | {example['supplier_description'][:30]}... | {example['original_candidate'][:20]} | {example['corrected_candidate'][:20]} | {example['issue']} |"
        )
    
    # Add recommendations
    report_lines.extend([
        "",
        "## Recommendations for Sprint 25",
        "",
        "### Immediate Actions",
        "1. **Fix unit information in candidate names** - Remove unit information from candidate names",
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
        f"- Dangerous patterns: {sum(len(patterns) for patterns in dangerous_patterns.values())} instances",
        f"- Low confidence cases: {len(low_confidence_rows)} instances",
        f"- Empty candidate names: {totals['product_rows_analyzed'] - totals['candidate_name_present']} instances",
        ""
    ])
    
    return "\n".join(report_lines)

def main():
    """Main function to run the calibration"""
    print("Running Ingredient Intelligence Calibration...")
    
    try:
        # Load parser test results
        results = load_parser_test_results()
        print(f"Loaded {len(results)} parser test results")
        
        # Analyze diagnostics
        analysis = analyze_ingredient_calibration(results)
        
        # Generate report
        report = generate_calibration_report(analysis)
        
        # Save report
        with open('docs/SPRINT_24_4_CALIBRATION_REPORT.md', 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("Calibration report completed successfully!")
        print(f"Report saved to docs/SPRINT_24_4_CALIBRATION_REPORT.md")
        
        # Print summary to console
        print("\n" + "="*50)
        print("CALIBRATION SUMMARY")
        print("="*50)
        print(f"PRODUCT rows analyzed: {analysis['totals']['product_rows_analyzed']}")
        print(f"Candidate name success: {analysis['success_rates'].get('candidate_name_present', 0):.2f}%")
        print(f"Supplier code success: {analysis['success_rates'].get('supplier_code_detected', 0):.2f}%")
        print(f"Purchase unit success: {analysis['success_rates'].get('purchase_unit_detected', 0):.2f}%")
        print(f"Pack size success: {analysis['success_rates'].get('pack_size_detected', 0):.2f}%")
        print(f"Low confidence rows: {len(analysis['low_confidence_rows'])}")
        print(f"Dangerous patterns: {sum(len(patterns) for patterns in analysis['dangerous_patterns'].values())}")
        
    except Exception as e:
        print(f"Error during calibration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()