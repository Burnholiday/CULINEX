# Parser Test Results

Generated: 2026-07-04T13:12:29

## Summary

- Total files tested: 33
- InvoiceTableParser rows extracted: 34
- UniversalExtractor rows found: 187
- UniversalExtractor rows accepted: 48
- UniversalExtractor rows discarded: 139
- InvoiceTableParser validation pass rate: 73.5%
- UniversalExtractor validation pass rate: 97.9%
- Files where UniversalExtractor found rows but InvoiceTableParser found none: 0
- Files where both failed: 21
- Files needing review: 29

## Supplier Breakdown

- Farm Fresh Direct: 9
- Unknown: 8
- So-CA Foods: 7
- Grocery Express: 3
- DistriLiq: 3
- Morningside Eggs: 2
- Robberg: 1

## UniversalExtractor Common Failure Reasons

- Expected 152.00, got 174.80: 1

## UniversalExtractor Discard Reasons

- noise: 81
- not_enough_line_values: 25
- headers_not_detected: 12
- payment: 7
- footer: 6
- banking: 4
- subtotal: 3
- wrapped_without_previous_row: 1

## Files Needing Review

- 20260617_181206.jpg: no rows
- 20260617_181216.jpg: InvoiceTableParser 1 validation issue(s)
- 20260617_181221.jpg: InvoiceTableParser 1 validation issue(s)
- 20260618_090051.jpg: InvoiceTableParser 1 validation issue(s)
- 20260618_090213.jpg: no rows
- 20260618_095804.jpg: no rows
- 20260630_084427.jpg: InvoiceTableParser 2 validation issue(s)
- 20260702_153713.jpg: no rows
- 20260702_153727.jpg: no rows
- 20260702_153849.jpg: no rows
- 20260702_153907.jpg: no rows
- 20260702_153923.jpg: InvoiceTableParser 1 validation issue(s)
- 20260702_153931.jpg: no rows
- 20260703_152604.jpg: no rows
- 20260703_152612.jpg: no rows
- 20260703_154334.jpg: no rows
- 20260703_154350.jpg: no rows
- 20260703_174437.jpg: no rows
- AhaConvert_20260701_151217.jpg: no rows
- AhaConvert_20260701_151223.jpg: no rows
- AhaConvert_20260701_151255.jpg: InvoiceTableParser 1 validation issue(s), UniversalExtractor 1 validation issue(s)
- AhaConvert_20260701_151303.jpg: no rows
- AhaConvert_20260701_151313.jpg: InvoiceTableParser 1 validation issue(s)
- AhaConvert_20260701_151321.jpg: no rows
- AhaConvert_20260701_152913.jpg: no rows
- AhaConvert_20260701_152939.jpg: no rows
- AhaConvert_20260701_152943.jpg: no rows
- AhaConvert_20260701_171947.jpg: no rows
- IMG-20260616-WA0021.jpg: InvoiceTableParser 1 validation issue(s)

## UniversalExtractor Improvements

- None yet.

## Both Failed

- 20260617_181206.jpg: No rows extracted by either parser.
- 20260618_090213.jpg: No rows extracted by either parser.
- 20260618_095804.jpg: No rows extracted by either parser.
- 20260702_153713.jpg: No rows extracted by either parser.
- 20260702_153727.jpg: No rows extracted by either parser.
- 20260702_153849.jpg: No rows extracted by either parser.
- 20260702_153907.jpg: No rows extracted by either parser.
- 20260702_153931.jpg: No rows extracted by either parser.
- 20260703_152604.jpg: No rows extracted by either parser.
- 20260703_152612.jpg: No rows extracted by either parser.
- 20260703_154334.jpg: No rows extracted by either parser.
- 20260703_154350.jpg: No rows extracted by either parser.
- 20260703_174437.jpg: No rows extracted by either parser.
- AhaConvert_20260701_151217.jpg: No rows extracted by either parser.
- AhaConvert_20260701_151223.jpg: No rows extracted by either parser.
- AhaConvert_20260701_151303.jpg: No rows extracted by either parser.
- AhaConvert_20260701_151321.jpg: No rows extracted by either parser.
- AhaConvert_20260701_152913.jpg: No rows extracted by either parser.
- AhaConvert_20260701_152939.jpg: No rows extracted by either parser.
- AhaConvert_20260701_152943.jpg: No rows extracted by either parser.
- AhaConvert_20260701_171947.jpg: No rows extracted by either parser.

## Files Tested

- 20260617_162204.jpg: So-CA Foods | InvoiceTableParser 9 rows / 0 issue(s) | UniversalExtractor 9 accepted, 2 discarded / 0 issue(s)
- 20260617_162300.jpg: Grocery Express | InvoiceTableParser 1 rows / 0 issue(s) | UniversalExtractor 1 accepted, 13 discarded / 0 issue(s)
- 20260617_181158.jpg: So-CA Foods | InvoiceTableParser 12 rows / 0 issue(s) | UniversalExtractor 12 accepted, 2 discarded / 0 issue(s)
- 20260617_181206.jpg: Robberg | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 10 discarded / 0 issue(s)
- 20260617_181216.jpg: Farm Fresh Direct | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 2 accepted, 1 discarded / 0 issue(s)
- 20260617_181221.jpg: Farm Fresh Direct | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 0 accepted, 9 discarded / 0 issue(s)
- 20260618_090051.jpg: Farm Fresh Direct | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 14 accepted, 1 discarded / 0 issue(s)
- 20260618_090213.jpg: Farm Fresh Direct | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- 20260618_095804.jpg: Morningside Eggs | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 3 discarded / 0 issue(s)
- 20260630_084427.jpg: Farm Fresh Direct | InvoiceTableParser 2 rows / 2 issue(s) | UniversalExtractor 0 accepted, 4 discarded / 0 issue(s)
- 20260702_153713.jpg: So-CA Foods | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 10 discarded / 0 issue(s)
- 20260702_153727.jpg: So-CA Foods | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 4 discarded / 0 issue(s)
- 20260702_153849.jpg: So-CA Foods | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- 20260702_153907.jpg: So-CA Foods | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- 20260702_153923.jpg: Farm Fresh Direct | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 2 accepted, 8 discarded / 0 issue(s)
- 20260702_153931.jpg: Grocery Express | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 15 discarded / 0 issue(s)
- 20260703_152555.jpg: Unknown | InvoiceTableParser 3 rows / 0 issue(s) | UniversalExtractor 0 accepted, 3 discarded / 0 issue(s)
- 20260703_152604.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 5 discarded / 0 issue(s)
- 20260703_152612.jpg: Grocery Express | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 4 discarded / 0 issue(s)
- 20260703_154334.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- 20260703_154350.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- 20260703_174437.jpg: So-CA Foods | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 4 discarded / 0 issue(s)
- AhaConvert_20260701_151217.jpg: DistriLiq | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- AhaConvert_20260701_151223.jpg: DistriLiq | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- AhaConvert_20260701_151255.jpg: DistriLiq | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 1 accepted, 13 discarded / 1 issue(s)
- AhaConvert_20260701_151303.jpg: Morningside Eggs | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 2 discarded / 0 issue(s)
- AhaConvert_20260701_151313.jpg: Farm Fresh Direct | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 0 accepted, 13 discarded / 0 issue(s)
- AhaConvert_20260701_151321.jpg: Farm Fresh Direct | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- AhaConvert_20260701_152913.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- AhaConvert_20260701_152939.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- AhaConvert_20260701_152943.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- AhaConvert_20260701_171947.jpg: Unknown | InvoiceTableParser 0 rows / 0 issue(s) | UniversalExtractor 0 accepted, 1 discarded / 0 issue(s)
- IMG-20260616-WA0021.jpg: Farm Fresh Direct | InvoiceTableParser 1 rows / 1 issue(s) | UniversalExtractor 7 accepted, 1 discarded / 0 issue(s)
