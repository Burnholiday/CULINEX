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

**CULINEX Import Engine v1.1.0**

---

# Release Status

Development

---

# Current Epic

Epic 1 — Import Engine

---

# Current Sprint

Sprint 13

Status:
✅ Completed

---

# Current Focus

Improve Universal OCR Row Reconstruction.

Objectives:

- Better multiline item reconstruction
- Better OCR fragment merging
- Better quantity detection
- Better total detection
- Improve supplier independence
- Maintain backwards compatibility

---

# Current Architecture

Upload Centre

↓

Content Extraction

↓

Universal Extractor

↓

Invoice Validator

↓

Approval Queue

↓

Purchase Database

↓

Analytics

---

# Current Benchmark

Universal Extractor

Current validation success:

Approximately **97–98%**

Primary remaining issue:

OCR row fragmentation.

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

✓ Invoice Validation

✓ Approval Queue

✓ Purchase Storage

✓ Benchmark Testing

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

# Version History

## v1.1.0

Completed Sprint 13: OCR Row Reconstruction
- Implemented geometry-first OCR row reconstruction stage using dynamic bounding box height metrics.
- Supplier-agnostic design matching fragment rows by vertical proximity and math relation check (`qty * price = total`).
- Added detailed debug logging of raw OCR fragments, reconstructed candidate rows, and final validator inputs.

## v1.0

Initial Development

Import Engine

Universal Extractor

OCR Pipeline

Approval Queue

Benchmark Testing

---

# Next Milestone

CULINEX Import Engine v1.1

Target Features:

- Advanced OCR Row Reconstruction
- Improved Column Detection
- Better Confidence Scoring
- Universal Supplier Support
- Higher Extraction Accuracy

---

# Long-Term Vision

CULINEX will evolve into a complete restaurant management ecosystem capable of managing invoices, inventory, recipes, suppliers, analytics, purchasing, costing, forecasting, and business intelligence from a single platform.

---

Last Updated:

2026-07-05