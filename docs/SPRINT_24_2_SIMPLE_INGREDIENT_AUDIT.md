# Simple Ingredient Candidate Audit Report - Sprint 24.2

## Summary
- PRODUCT rows analyzed: 49
- candidate_name present: 0
- supplier_code detected: 0
- purchase_unit detected: 0
- low-confidence rows: 0
- conflicting-signal rows: 0

## Assessment Results
- Likely Correct: 0
- Likely Incorrect: 49
- Ambiguous: 0
- Dangerous Errors: 92

## Dangerous Errors Found
- Total dangerous errors: 92

### Dangerous Error Details:
- 20260617_162204.jpg: candidate_name empty
- 20260617_181216.jpg: Raw data issue: contains kg unit
- 20260617_181216.jpg: candidate_name empty
- 20260617_181216.jpg: Raw data issue: contains kg unit
- 20260617_181216.jpg: candidate_name empty
- 20260617_181221.jpg: Raw data issue: contains kg unit
- 20260617_181221.jpg: candidate_name empty
- 20260617_181221.jpg: Raw data issue: contains kg unit
- 20260617_181221.jpg: candidate_name empty
- 20260617_181221.jpg: Raw data issue: contains kg unit
... and 82 more dangerous errors

## Evidence Table (First 20 rows)
| Filename | Supplier Description | Candidate Name | Supplier Code | Purchase Unit | Quantity | Unit Price | Line Total | Assessment |
|----------|----------------------|----------------|---------------|---------------|----------|------------|------------|------------|
| 20260617_162204.jpg | SPA040 CAN CONDENSED... |  |  |  | 2.00 | 29.99 |  | likely_incorrect |
| 20260617_181216.jpg | (SUURLEMOEN) WHO-LEM... |  |  |  | 0.645 | 29.85 |  | likely_incorrect |
| 20260617_181216.jpg | SMITH WHO - ORANGES ... |  |  |  | 0.62 | 15.85 |  | likely_incorrect |
| 20260617_181221.jpg | WHO - CUCUMBER. WHO ... |  |  |  | 4.1 | 17.85 |  | likely_incorrect |
| 20260617_181221.jpg | WHO - TOMATOES Kg 2.... |  |  |  | 2.035 | 36.85 |  | likely_incorrect |
| 20260617_181221.jpg | WHO - BEETROOT KG 1.... |  |  |  | 1.06 | 20.85 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - CHILLIES RED K... |  |  |  | 0.21 | 92.65 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - CHILLIES GREEN... |  |  |  | 0.205 | 77.65 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - ONIONS RED Kg ... |  |  |  | 2.065 | 37.85 |  | likely_incorrect |
| 20260618_090051.jpg | KG WHO - POTATOES 10... |  |  |  | 2 | 117.85 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - GARLIC kg 1.11... |  |  |  | 1.112 | 142.85 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - BANANAS KG 2.2... |  |  |  | 2.21 | 22.65 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - CARROT kg 3.20... |  |  |  | 3.205 | 23.65 |  | likely_incorrect |
| 20260618_090051.jpg | WHO - GINGER KG 1.14... |  |  |  | 1.144 | 148.65 |  | likely_incorrect |
| 20260618_090051.jpg | WHOLE WHO - PUMPKIN ... |  |  |  | 13.26 | 18.85 |  | likely_incorrect |
| 20260630_084427.jpg | WHO - CARROT WHO - P... |  |  |  | 1.08 | 23.65 |  | likely_incorrect |
| 20260701_151313.jpg | WHO -BROCCOLI Heads-... |  |  |  | 1.17 | 35.85 |  | likely_incorrect |
| 20260701_151313.jpg | WHO - APPLES GRANNY ... |  |  |  | 2.58 | 29.85 |  | likely_incorrect |
| 20260701_151313.jpg | WHO-BUTTERNUT kg 4.1... |  |  |  | 4.19 | 20.85 |  | likely_incorrect |
| 20260701_151313.jpg | 5KG WHO - ORANGES kg... |  |  |  | 1.1 | 15.85 |  | likely_incorrect |
... and 29 more rows

## Recommendations for Sprint 24.3

### Immediate Actions
1. **Fix candidate name extraction** - Ensure unit information is not included in candidate names
2. **Improve supplier code detection** - Handle edge cases in supplier code recognition
3. **Enhance raw text processing** - Better handle supplier descriptions that contain unit information
4. **Add validation for empty candidate names** - Prevent empty ingredient names from being saved

### Long-term Improvements
1. **Add more comprehensive error detection** - Identify patterns that lead to dangerous errors
2. **Implement deterministic fixes** - Add rules to correct common normalization issues
3. **Improve confidence scoring** - Better distinguish between correct and incorrect extractions
4. **Add pattern-based corrections** - Implement fixes for repeated error patterns

### Priority Areas for Improvement
- Dangerous errors: 92 instances
- Empty candidate names: 49 instances
- Supplier code issues: 0 instances
