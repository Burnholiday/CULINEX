# Ingredient Intelligence Calibration Report - Sprint 24.4

## Phase 1 - Audit Summary

- Total PRODUCT rows analyzed: 49
- Candidate name success rate: 0.00%
- Supplier code success rate: 0.00%
- Purchase unit success rate: 0.00%
- Pack count success rate: 0.00%
- Pack size success rate: 0.00%
- Total pack quantity success rate: 0.00%

## Phase 2 - Dangerous Errors

- Total dangerous patterns found: 0


## Phase 1 - Low-Confidence Analysis

- Low-confidence rows (< 0.70): 0

## Phase 4 - Confidence Analysis

- Average confidence: 0
- Median confidence: 0
- Minimum confidence: 0
- Maximum confidence: 0
- Standard deviation: 0

### Confidence Histogram
| Confidence Range | Count |
|------------------|-------|
| 0.0 - 0.2 | 0 |
| 0.2 - 0.4 | 0 |
| 0.4 - 0.6 | 0 |
| 0.6 - 0.7 | 0 |
| 0.7 - 0.8 | 0 |
| 0.8 - 0.9 | 0 |
| 0.9 - 1.0 | 0 |

## Phase 3 - Universal Fixes Applied

### 20 Corrected Examples
| Filename | Supplier Description | Original Candidate | Corrected Candidate | Issue |
|----------|----------------------|-------------------|---------------------|-------|

## Recommendations for Sprint 25

### Immediate Actions
1. **Fix unit information in candidate names** - Remove unit information from candidate names
2. **Improve supplier code detection** - Handle edge cases in supplier code recognition
3. **Enhance pack pattern recognition** - Better handle ambiguous pack size values
4. **Refine confidence scoring** - Reduce false positives in low-confidence cases

### Long-term Improvements
1. **Add more unit validation** - Better distinguish between product quantities and pack sizes
2. **Improve candidate name extraction** - Prevent unit information from being included in candidate names
3. **Enhance signal matching** - Better handle edge cases in signal detection
4. **Add pattern-based corrections** - Implement deterministic fixes for repeated error patterns

### Priority Areas for Improvement
- Dangerous patterns: 0 instances
- Low confidence cases: 0 instances
- Empty candidate names: 49 instances
