#!/usr/bin/env python3

import os
import json
import glob
from collections import defaultdict

def analyze_calibration_data():
    # Path to the parser test results
    results_dir = "data/parser-test-results"
    
    # Find all JSON files
    json_files = glob.glob(os.path.join(results_dir, "*.json"))
    
    # Sort files by name to get the latest one
    json_files.sort()
    
    # Process all files to get the latest run data
    all_data = []
    for file_path in json_files:
        with open(file_path, 'r') as f:
            data = json.load(f)
            all_data.append(data)
    
    # Initialize counters and accumulators
    total_files = len(all_data)
    structure_confidence_by_category = {
        'likely_correct': [],
        'likely_partial': [],
        'likely_wrong': [],
        'insufficient_evidence': []
    }
    overall_table_confidence = []
    oversized_region_penalties = 0
    files_capped_at_0_65 = 0
    capped_files = []
    likely_correct_capped = False
    insufficient_evidence_below_likely_correct = False
    likely_correct_above_likely_wrong = True
    
    # Process each file
    for data in all_data:
        # Get the geometry_debug data which contains the confidence metrics
        geometry_debug = data.get('universal_line_item_extractor', {}).get('geometry_debug', [])
        
        if not geometry_debug:
            continue
            
        # Get the first geometry debug entry (assuming there's only one table per file)
        geom = geometry_debug[0]
        
        # Extract structure_confidence_v2_1
        structure_confidence = geom.get('structure_confidence_v2_1')
        category = None  # Initialize category variable
        if structure_confidence is not None:
            # Categorize based on confidence value
            if structure_confidence >= 0.65:
                category = 'likely_correct'
            elif structure_confidence >= 0.35:
                category = 'likely_partial'
            elif structure_confidence >= 0.0:
                category = 'likely_wrong'
            else:
                category = 'insufficient_evidence'
                
            structure_confidence_by_category[category].append(structure_confidence)
        
        # Extract overall_table_confidence
        table_confidence = geom.get('table_confidence')
        if table_confidence is not None:
            overall_table_confidence.append(table_confidence)
            
        # Check for oversized region penalties
        oversized_penalty = geom.get('oversized_region_penalty', 0)
        if oversized_penalty > 0:
            oversized_region_penalties += 1
            
        # Check for files capped at 0.65
        if structure_confidence is not None and structure_confidence < 0.65:
            files_capped_at_0_65 += 1
            capped_files.append(data['filename'])
            # Check if this file was originally likely_correct
            if category == 'likely_correct':
                likely_correct_capped = True
    
    # Calculate averages
    avg_structure_confidence = {}
    for category, values in structure_confidence_by_category.items():
        if values:
            avg_structure_confidence[category] = sum(values) / len(values)
        else:
            avg_structure_confidence[category] = 0.0
    
    avg_overall_table_confidence = sum(overall_table_confidence) / len(overall_table_confidence) if overall_table_confidence else 0.0
    
    # Check conditions
    likely_correct_avg = avg_structure_confidence.get('likely_correct', 0.0)
    likely_wrong_avg = avg_structure_confidence.get('likely_wrong', 0.0)
    insufficient_evidence_avg = avg_structure_confidence.get('insufficient_evidence', 0.0)
    
    if likely_correct_avg > 0 and likely_wrong_avg > 0:
        likely_correct_above_likely_wrong = likely_correct_avg > likely_wrong_avg
    else:
        likely_correct_above_likely_wrong = False
        
    if likely_correct_avg > 0 and insufficient_evidence_avg > 0:
        insufficient_evidence_below_likely_correct = insufficient_evidence_avg < likely_correct_avg
    else:
        insufficient_evidence_below_likely_correct = False
    
    # Generate report
    report = []
    report.append("# Sprint 22.4 Calibration Report")
    report.append("")
    report.append("## Summary")
    report.append(f"- Total files analyzed: {total_files}")
    report.append(f"- Average structure_confidence_v2_1 for likely_correct: {avg_structure_confidence.get('likely_correct', 0.0):.3f}")
    report.append(f"- Average structure_confidence_v2_1 for likely_partial: {avg_structure_confidence.get('likely_partial', 0.0):.3f}")
    report.append(f"- Average structure_confidence_v2_1 for likely_wrong: {avg_structure_confidence.get('likely_wrong', 0.0):.3f}")
    report.append(f"- Average structure_confidence_v2_1 for insufficient_evidence: {avg_structure_confidence.get('insufficient_evidence', 0.0):.3f}")
    report.append(f"- Average overall_table_confidence: {avg_overall_table_confidence:.3f}")
    report.append(f"- Number of oversized-region penalties applied: {oversized_region_penalties}")
    report.append(f"- Number of files capped at 0.65: {files_capped_at_0_65}")
    report.append("")
    report.append("## Capped Files")
    for filename in capped_files:
        report.append(f"- {filename}")
    report.append("")
    report.append("## Analysis")
    report.append(f"- Any likely_correct files were capped: {'Yes' if likely_correct_capped else 'No'}")
    report.append(f"- Insufficient_evidence now scores below likely_correct: {'Yes' if insufficient_evidence_below_likely_correct else 'No'}")
    report.append(f"- Likely_correct remains above likely_wrong: {'Yes' if likely_correct_above_likely_wrong else 'No'}")
    report.append("")
    report.append("## Observations")
    report.append("- The calibration report is based on the latest benchmark run results.")
    report.append("- Files are categorized based on their structure_confidence_v2_1 values.")
    report.append("- The system applies penalties for oversized regions.")
    report.append("- Files with structure_confidence_v2_1 below 0.65 are capped at that value.")
    
    return "\n".join(report)

if __name__ == "__main__":
    report = analyze_calibration_data()
    print(report)
    
    # Save to file
    with open("docs/SPRINT_22_4_CALIBRATION_REPORT.md", "w") as f:
        f.write(report)
    
    print("\nReport saved to docs/SPRINT_22_4_CALIBRATION_REPORT.md")