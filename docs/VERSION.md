# VERSION.md

# CULINEX
## Official Version Record

---

# Product

**Name:** CULINEX

**Tagline:**
*Know your business. Know your restaurant. Know your next culinary step.*

---

# Current Version

**CULINEX Import Engine v2.0.0**

---

# Release Status

Sprint 26 Complete

---

# Release Summary

CULINEX Import Engine v2.0.0 introduces the first controlled Ingredient Learning and Proposal Pipeline milestone.

This release adds review-only ingredient intelligence around the existing parser:
Ingredient Memory, canonical ingredient matching, proposal generation, and
parser-level proposal observation. Proposal generation is disabled by default
and remains shadow-only.

Verified Sprint 26 benchmark status:

- 49 files tested
- 166 validated rows
- 21 review rows
- 95 discarded rows
- 0 extraction errors
- 100% strict validation
- Ingredient Memory unchanged in shadow-mode benchmarks

Historical note:

CULINEX Import Engine v1.3.0 introduces Adaptive Column Intelligence.

This release improves supplier-agnostic invoice extraction by introducing
geometry-aware column analysis, column confidence scoring and metadata,
while preserving strict mathematical validation and backwards compatibility.

Benchmark Status

✓ 113 validated rows
✓ 100% strict validation
✓ 8.1% review rate
✓ +19% validation improvement over InvoiceTableParser

---

# Current Epic

Epic 2 - Invoice Intelligence Engine

---

# Current Sprint

Sprint 26 - Ingredient Learning and Proposal Pipeline

Status:
Completed

Goal:

Create a safe review-only learning layer between extracted invoice rows and
future restaurant-specific ingredient memory.

No data inference.
No supplier-specific logic.
Validation remains unchanged.
No automatic approval.
No automatic merge.

---

# Release History

v2.0.0 - Ingredient Learning and Proposal Pipeline
Sprint 26

v1.3.0 — Adaptive Column Intelligence
Sprint 15

v1.2.0 — Validation Recovery Classification
Sprint 14

v1.1.0 — OCR Row Reconstruction
Sprint 13

v1.0.0 — Universal Import Engine Foundation
Sprints 1–12

# Completed Sprint

Current Version:
CULINEX Import Engine v1.4.0

Completed Sprint:
Sprint 16 — Row Recovery Engine

Current Development Stage:
Sprint 17 — Adaptive Header Intelligence

Status:
Completed
---

# Current Focus

Improve deterministic OCR row recovery before validation.

Current work focuses on reducing
not_enough_line_values
through supplier-agnostic row reconstruction.

Validation remains unchanged.

Recovery reorganizes OCR fragments only.
---

# Current Architecture


Universal Extractor

↓

OCR Row Reconstruction

↓

Row Recovery Engine

↓

Header Detection

↓

Adaptive Column Detection

↓

Numeric Role Selection

↓

Validation

↓

Classification

    ✓ Validated
    ⚠ Recovered – Needs Review
    ✗ Rejected

↓

Approval Queue

↓

Purchase Database

↓

Analytics
---

# Current Benchmark Philosophy

The benchmark now reports Universal Extractor rows in separate groups:

- Validated rows
- Recovered Needs Review rows
- Rejected rows

Strict Validation Pass Rate is calculated only from Validated rows.

Recovered Needs Review rows remain visible for user review and do not count as validation failures.

Rows are only validated when they satisfy strict mathematical validation. Rows with unclear geometric or mathematical evidence remain in review or rejected status.

---

# Supported Imports

✓ PDF

✓ PNG

✓ JPG

✓ JPEG

✓ XLSX

✓ CSV

✓ TXT

---

# Supported Features

✓ Upload Centre

✓ OCR

✓ PDF Extraction

✓ Table Extraction

✓ Universal Extractor

✓ OCR Row Reconstruction

✓ Header Detection

✓ Numeric Role Selection

✓ Validation Recovery Classification

✓ Invoice Validation

✓ Approval Queue

✓ Purchase Storage

✓ Benchmark Testing

✓ Adaptive Column Intelligence

✓ Geometry Analysis

✓ Column Confidence Metadata

---

# Planned Modules

Recipe Vault

Inventory Engine

Recipe Costing

Supplier Intelligence

Analytics Dashboard

Waste Tracking

Menu Engineering

Kitchen Dashboard

Business Intelligence

AI Assistant

---

# Documentation

Project documentation includes:

PROJECT_CONTEXT.md

AI_RULES.md

ROADMAP.md

ARCHITECTURE.md

SUMMARY.md

CHANGELOG.md

TESTING.md

PROMPT_TEMPLATE.md

VERSION.md

VISION.md

---

# Coding Standard

Development follows:

Incremental Sprint Development

Backwards Compatibility

Modular Architecture

Supplier-Agnostic Design

Documentation-Driven Development

---

# Success Criteria

The Import Engine is considered production-ready when:

✓ 99%+ extraction accuracy

✓ Multiple supplier support

✓ OCR tolerant

✓ Minimal manual correction

✓ Stable approval workflow

✓ Zero regression across benchmark invoices

---

# Product Philosophy

CULINEX is not simply an invoice parser.

It is an intelligent restaurant operating platform.

Every feature should contribute toward helping restaurant owners make faster, more accurate, and more profitable decisions.

---

# Sprint History

## Sprint 15 - Adaptive Column Intelligence

Completed Sprint 15

- Introduced ColumnGeometryAnalyzer.
- Added geometry-aware numeric role selection.
- Added column confidence metadata.
- Added role source metadata.
- Added geometric benchmark reporting.
- Preserved strict validation.
- Maintained supplier-agnostic extraction.

## Sprint 14 - Validation Recovery Classification

Completed Sprint 14: Validation Recovery Classification

- Introduced Validation Recovery Classification.
- Separated Universal Extractor rows into Validated, Recovered Needs Review, and Rejected.
- Added review reason classification for recovered rows.
- Preserved strict mathematical validation.
- Improved benchmark reporting so review rows do not reduce strict validation pass rate.
- Maintained a supplier-agnostic recovery workflow.

## Sprint 13 - OCR Row Reconstruction

Completed Sprint 13: OCR Row Reconstruction

- Implemented geometry-first OCR row reconstruction stage using dynamic bounding box height metrics.
- Used supplier-agnostic vertical proximity and mathematical relation checks.
- Added detailed debug logging of raw OCR fragments, reconstructed candidate rows, and final validator inputs.

## Initial Import Engine Development

Initial Import Engine development

- Upload Centre
- Content Extraction
- Universal Extractor
- OCR Pipeline
- Approval Queue
- Benchmark Testing

---

# Next Milestone

CULINEX Import Engine v1.4.0

- Row Recovery Engine
- Description continuation detection
- OCR fragment merging
- Recovery confidence metadata
- Reduced not_enough_line_values discard rate
---

# Long-Term Vision

CULINEX will evolve into a complete restaurant management ecosystem capable of managing invoices, inventory, recipes, suppliers, analytics, purchasing, costing, forecasting, and business intelligence from a single platform.

---

Last Updated:

2026-07-07
