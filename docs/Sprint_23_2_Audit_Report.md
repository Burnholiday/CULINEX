# Sprint 23.2 - Invoice Row Classification Audit

## Executive Summary

This report presents the audit of the Invoice Row Classification Framework implemented in Sprint 23.1. The audit analyzes the classification results from the latest benchmark run to determine if the classifier is accurate enough to keep and calibrate.

## Classification Results Summary

### Distribution of Classified Rows

| Row Type | Count | Average Confidence |
|----------|-------|-------------------|
| vat | 43 | 0.333 |
| unknown | 4 | 0.000 |

### Key Metrics

- **Total classified rows**: 47
- **Low-confidence rows (< 0.70)**: 47 (100%)
- **UNKNOWN rows**: 0
- **Rows with conflicting signals**: 0

## Evidence Table

| Filename | Raw Row Text | Parser Outcome | Assigned Row Type | Confidence | Matched Signals | Conflicting Signals | Audit Assessment |
|----------|--------------|----------------|-------------------|------------|-----------------|---------------------|------------------|
| 20260617_162216.json | POWER (4,45KG) COFFEE WOW POWER BEANS 1KG 2.00 327.35 0.00 98.21 654.70 | validated | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260617_181146.json | 10 MILK FRESH LEEUWENBOSCH (2LT) 12.00 1.00 109.99 34.50 0.00 0.00 16.50 109.99 | validated | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260617_181158.json | 000110 MILK FRESH LEEUWENBOSCH (2LT) 12.00 34.50 0.00 0.00 414.00 | validated | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260701_151255.json | MPA/700/6 MONIN PINEAPPLE SYRUP 700ML 1 152.00 0.00 22.80 174.80 | recovered_needs_review | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260701_151303.json | OXT MORNINGSIDE X-LARGE TRAYS 75.00 26.80 0.00 2,010.00 | validated | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260701_171947.json | 1137 GREEFF'S CRAFT BOEREWORS 10.065 4.402 0.00 0.00 115.95 105.95 15.00 15.00 1,066.37 | recovered_needs_review | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260702_153727.json | 1059 ZIPLOCK BAGS 215 X 315 (100'S) 1.00 82.98 0.00 139.99 | recovered_needs_review | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |
| 20260703_152555.json | KIN002 Black Butterfish PQ Portions 5.30 4.50 55.00 37.12 247.50 | validated | unknown | 0.000 |  |  | ambiguous |
| 20260703_152555.json | HAK028 WST006 Hake Fillet Fresh 220-Jumbo WhiteStump Frozen VP Dressed 25.90 135.00 524.47 3 496.50 | validated | unknown | 0.000 |  |  | ambiguous |
| 20260703_154334.json | 52 STEAK MINCE 80/20 5.022 0.00 105.95 15.00 288.10 | recovered_needs_review | vat | 0.333 | \b(?:0\.00|0\.0|0\.|0)\b |  | likely_incorrect |

## Audit Findings

### Dangerous Misclassifications

1. **VAT rows incorrectly classified as PRODUCT**: 
   - The classifier is misclassifying product rows that contain "0.00" values as VAT rows
   - This is happening because the classifier's pattern matching for VAT includes "0.00" which appears in product rows

2. **Low confidence scores**: 
   - All classified rows have confidence scores below 0.70 (47/47 rows)
   - This indicates the classifier needs significant improvement

3. **Missing PRODUCT classification**: 
   - No rows were classified as PRODUCT in the test results
   - This suggests the classifier is not properly identifying product rows

### Pattern Analysis

The classifier is primarily matching on the pattern `\b(?:0\.00|0\.0|0\.|0)\b` which is used for VAT detection. However, this pattern appears in many product rows that have "0.00" as a VAT amount, causing misclassification.

## Recommended Sprint 23.3 Calibration Plan

### Immediate Actions (Sprint 23.3)

1. **Fix Pattern Matching Logic**:
   - Improve the VAT detection to avoid false positives
   - Add better context checking for VAT rows
   - Ensure PRODUCT rows are properly identified

2. **Enhance Classification Rules**:
   - Add more specific product detection patterns
   - Improve conflict resolution between row types
   - Add better semantic analysis for distinguishing between VAT and product rows

3. **Improve Confidence Scoring**:
   - Increase minimum confidence thresholds for classifications
   - Add more robust validation for row type assignments

### Specific Improvements

1. **Product Detection Enhancement**:
   - Add more specific product keywords and patterns
   - Improve detection of product descriptions vs. VAT amounts
   - Better handling of numeric patterns in product rows

2. **VAT Detection Refinement**:
   - Add context validation for VAT rows (must be in VAT column)
   - Improve detection of actual VAT amounts vs. zero values
   - Add better distinction between VAT amounts and other zero values

3. **Confidence Scoring**:
   - Implement better confidence calculation based on multiple signals
   - Add validation that prevents misclassification of product rows as VAT

## Conclusion

The current classifier implementation has significant issues:
- Low confidence scores across all classifications
- Misclassification of product rows as VAT rows
- No PRODUCT classifications in the test data
- Over-reliance on simple pattern matching

The classifier needs substantial refinement before it can be reliably used for calibration purposes. The recommended approach is to focus on improving the core classification logic rather than just adjusting thresholds.

## Data Source

This audit was generated from the latest benchmark results in `data/parser-test-results/`.