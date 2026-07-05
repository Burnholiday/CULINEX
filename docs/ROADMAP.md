# ROADMAP.md
# CULINEX Development Roadmap

Project:
CULINEX – Your Culinary Next Step

Current Version:
CULINEX Import Engine v1.0

Current Status:
ACTIVE DEVELOPMENT

Current Sprint:
Sprint 13

Current Epic:
Epic 1 – Import Engine

---

# Project Vision

CULINEX is an AI-powered restaurant operating platform designed to automate restaurant administration.

Long-term platform modules include:

✓ Invoice Importing
✓ Inventory Management
✓ Recipe Vault
✓ Recipe Costing
✓ Supplier Management
✓ Purchase Analytics
✓ Stock Forecasting
✓ Waste Tracking
✓ Menu Engineering
✓ Kitchen Dashboard
✓ Staff Training
✓ Business Intelligence

The Import Engine is the foundation of the platform.

---

# Development Principles

• Build one sprint at a time.
• Never redesign working architecture.
• Maintain backwards compatibility.
• Keep modules independent.
• Test with multiple suppliers.
• Avoid supplier-specific logic.
• Keep AI prompts and documentation up to date.

---

# EPIC 1 — IMPORT ENGINE

Status:
IN PROGRESS

Goal:
Transform invoices into structured purchase records.

---

## Sprint 1 — Upload Centre

Status:
✅ Completed

Goal:
Upload files into CULINEX.

Deliverables:

- File upload
- Drag & drop
- File type detection
- Upload cards
- Upload logging

---

## Sprint 2 — Content Extraction

Status:
✅ Completed

Goal:
Read uploaded documents.

Deliverables:

- PDF text extraction
- PDF table extraction
- Excel extraction
- CSV extraction
- OCR extraction
- Text preview

---

## Sprint 3 — Universal Extractor

Status:
✅ Completed

Goal:
Combine all extraction methods.

Deliverables:

- Multi-source extraction
- OCR + PDF merge
- Structured output
- Initial purchase rows

---

## Sprint 4 — Invoice Validation

Status:
✅ Completed

Goal:
Validate extracted purchase data.

Deliverables:

- Quantity validation
- Price validation
- Total validation
- Confidence scoring

---

## Sprint 5 — Approval Queue

Status:
✅ Completed

Goal:
Manual review before import.

Deliverables:

- Review screen
- Edit rows
- Approve
- Reject

---

## Sprint 6 — Database Import

Status:
✅ Completed

Goal:
Store approved purchases.

Deliverables:

- Database models
- Purchase records
- Supplier records

---

## Sprint 7 — Purchase History

Status:
✅ Completed

Goal:
Historical purchasing.

Deliverables:

- Purchase list
- Search
- Filters

---

## Sprint 8 — Supplier Intelligence

Status:
✅ Completed

Goal:
Track supplier performance.

Deliverables:

- Supplier statistics
- Purchase totals
- Trends

---

## Sprint 9 — Universal Extractor Improvements

Status:
✅ Completed

Goal:
Improve extraction accuracy.

Focus:

- Better column detection
- Better OCR merging

---

## Sprint 10 — Confidence Engine

Status:
✅ Completed

Goal:
Improve confidence scoring.

Deliverables:

- Better scoring
- Error classification

---

## Sprint 11 — Benchmarking

Status:
✅ Completed

Goal:
Measure extraction quality.

Deliverables:

- Benchmark testing
- Accuracy reports
- Summary generation

---

## Sprint 12 — Universal Extractor Integration

Status:
✅ Completed

Goal:
Make Universal Extractor the primary parser.

Deliverables:

- Universal Extractor first
- InvoiceTableParser fallback
- Integration testing

Current Result:

Approximately 97–98% extraction success.

---

## Sprint 13 — OCR Row Reconstruction

Status:
🚧 In Progress

Current Goal:

Improve OCR row reconstruction before validation.

Current Problems:

- Wrapped descriptions
- Split quantities
- Broken rows
- Detached totals
- OCR fragmentation
- Supplier layout differences

Success Criteria:

- Better row merging
- Better description reconstruction
- No regression
- Higher multi-supplier accuracy

---

# Future Epics

## Epic 2 — Recipe Vault

Status:
Planned

Features:

- Recipe import
- AI recipe reader
- Ingredient extraction
- Recipe photos
- Version history

---

## Epic 3 — Inventory Engine

Status:
Planned

Features:

- Live stock
- Stock adjustments
- Batch tracking
- Stock counts

---

## Epic 4 — Recipe Costing

Status:
Planned

Features:

- Live food cost
- Portion costing
- Yield calculations

---

## Epic 5 — Restaurant Analytics

Status:
Planned

Features:

- Purchase analytics
- Food cost trends
- Supplier comparisons
- Monthly reports
- Dashboard

---

## Epic 6 — AI Assistant

Status:
Planned

Features:

- Ask CULINEX
- AI purchasing insights
- Inventory recommendations
- Forecasting

---

# Known Issues

Current focus:

Improve OCR reconstruction without affecting validated invoices.

Current benchmark:

~97–98% successful extraction.

Goal:

99%+ supplier-independent extraction.

---

# Documentation

This project should always maintain:

README.md

PROJECT_CONTEXT.md

AI_RULES.md

ROADMAP.md

SUMMARY.md

These documents represent the official project documentation.

Always keep them updated after each completed sprint.

---

# Current Mission

Complete the Import Engine until it reliably extracts invoices from virtually any supplier.

Only then continue with the remaining restaurant platform modules.

Know your business.

Know your restaurant.

Know your next culinary step.

CULINEX