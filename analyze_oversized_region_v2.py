#!/usr/bin/env python3

import os
import json
import glob

def analyze_oversized_region_data():
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
    
    # Analyze oversized region penalties and capped files properly
    oversized_region_penalties = 0
    files_capped_at_0_65 = 0
    capped_files = set()  # Use set to avoid duplicates
    files_with_oversized_penalty = set()
    files_without_oversized_penalty = set()
    
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
        
        # Check for oversized region penalties
        oversized_penalty = geom.get('oversized_region_penalty', 0)
        if oversized_penalty > 0:
            oversized_region_penalties += 1
            files_with_oversized_penalty.add(data['filename'])
        else:
            files_without_oversized_penalty.add(data['filename'])
            
        # Check for files capped at 0.65
        if structure_confidence is not None and structure_confidence < 0.65:
            capped_files.add(data['filename'])
    
    print(f"Total files analyzed: {len(all_data)}")
    print(f"Files with oversized region penalties: {len(files_with_oversized_penalty)}")
    print(f"Files capped at 0.65: {len(capped_files)}")
    print(f"Files without oversized penalties but still capped: {len(capped_files - files_with_oversized_penalty)}")
    
    print("\nFiles with oversized penalties:")
    for filename in sorted(files_with_oversized_penalty):
        print(f"  - {filename}")
        
    print("\nFiles without oversized penalties but still capped:")
    for filename in sorted(capped_files - files_with_oversized_penalty):
        print(f"  - {filename}")
    
    # Let's examine a few specific files that were capped but without oversized penalties
    print("\nExamining files that were capped but without oversized penalties:")
    capped_minus_oversized = capped_files - files_with_oversized_penalty
    for filename in sorted(capped_minus_oversized):
        with open(os.path.join(results_dir, filename), 'r') as f:
            data = json.load(f)
            geom = data['universal_line_item_extractor']['geometry_debug'][0]
            print(f"  {filename}: structure_confidence_v2_1 = {geom['structure_confidence_v2_1']}, oversized_penalty = {geom['oversized_region_penalty']}")

if __name__ == "__main__":
    analyze_oversized_region_data()