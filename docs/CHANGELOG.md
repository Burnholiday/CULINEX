# Changelog


## v1.5.0 (2026-07-09)


Sprint 17 — Adaptive Header Intelligence


Added

- RowReconstructor fragment merging

- Recovery confidence metadata

- Improved OCR row recovery

- Reduced not_enough_line_values discard rate

- Header confidence scoring

- Adaptive header band detection


Changed

- Enhanced row recovery logic

- Better handling of fragmented OCR rows

- Improved header detection confidence calculation


Fixed

- Reduced discarded rows from 62 to 50

- Reduced not_enough_line_values from 21 to 15

- Reduced files needing review from 24 to 22

- Fixed HeaderType NameError

- Fixed confidence propagation in real parser execution

- Improved header band grouping algorithm


Known Issues

- Geometry metrics currently report 0.0.

- Two invoices trigger TypeError during extraction.

## v1.3.0 (2026-07-08)


Sprint 15 — Adaptive Column Intelligence


Added

- ColumnGeometryAnalyzer

- Geometry-aware role selection

- Column confidence metadata

- Role source metadata

- Geometry benchmark reporting


Changed

- Numeric role selection now considers OCR geometry.


Fixed

- Metadata propagation to invoice rows.


Known Issues

- Geometry metrics currently report 0.0.

- Two invoices trigger TypeError during extraction.

## v1.2.0 (2026-07-08)


Sprint 14 - Validation Recovery Classification


Added

- Validation Recovery Classification

- Separation of Validated, Recovered Needs Review, and Rejected rows

- Review reason classification

- Strict mathematical validation

- Improved benchmark reporting

- Supplier-agnostic recovery workflow


Known Issues

- Geometry metrics currently report 0.0.

- Two invoices trigger TypeError during extraction.