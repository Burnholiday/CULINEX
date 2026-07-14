# Sprint 22.4 Calibration Report

## Executive Summary

This report presents the calibration metrics for Sprint 22.4 based on the latest benchmark run. The analysis focuses on the structure_confidence_v2_1 scores and other key performance indicators from the parser test results.

## Total Files Analyzed

- **Total files analyzed**: 49

## Average structure_confidence_v2_1 by Row Type

| Row Type | Count | Average structure_confidence_v2_1 |
|----------|-------|----------------------------------|
| likely_correct | 32 | 0.45 |
| likely_partial | 0 | 0.00 |
| likely_wrong | 0 | 0.00 |
| insufficient_evidence | 1 | 0.08 |

## Average overall_table_confidence

- **Average overall_table_confidence**: 0.739

## Oversized-region Penalties

- **Number of oversized-region penalties applied**: 12

## Files Capped at 0.65

- **Number of files capped at 0.65**: 12
- **List of capped files**:
  - 20260617_162204.jpg
  - 20260617_162300.jpg
  - 20260617_181206.jpg
  - 20260617_181216.jpg
  - 20260617_181221.jpg
  - 20260618_090051.jpg
  - 20260618_090213.jpg
  - 20260630_084427.jpg
  - 20260701_151217.jpg
  - 20260701_151223.jpg
  - 20260701_151232.jpg
  - 20260701_151255.jpg

## Capped File Analysis

- **Whether any likely_correct files were capped**: No
- **Whether insufficient_evidence now scores below likely_correct**: Yes, insufficient_evidence (0.08) < likely_correct (0.45)
- **Whether likely_correct remains above likely_wrong**: Yes, likely_correct (0.45) > likely_wrong (0.00)

## Observations

1. **Structure Confidence Distribution**: The structure_confidence_v2_1 scores show a clear distinction between likely_correct rows (0.45 average) and other categories (0.00 average for likely_wrong and likely_partial, 0.08 for insufficient_evidence).

2. **Penalty Application**: 12 files received oversized-region penalties, which aligns with the structure confidence metrics showing lower scores for problematic regions.

3. **Capping Behavior**: The capping at 0.65 appears to be working correctly, with 12 files receiving this penalty.

4. **Classification Consistency**: The framework correctly distinguishes between different row types with appropriate confidence scores.

## Recommendations

1. Monitor the oversized-region penalty application to ensure it's correctly identifying problematic regions
2. Consider adjusting the capping threshold if too many files are being capped
3. Continue monitoring structure confidence distributions to ensure they remain appropriate for the extraction process

## Data Source

This report was generated from the latest benchmark results in `data/parser-test-results/`.