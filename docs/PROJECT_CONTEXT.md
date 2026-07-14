# CULINEX Import Engine v2.0.0
## Master Project Context

---

# Project Overview

CULINEX (Your Culinary Next Step) is a restaurant management platform focused on automating kitchen administration.

The Import Engine transforms supplier invoices into structured purchasing data that can be reviewed, approved, stored, and analyzed.

This is production software.

The project must remain modular and be developed sprint-by-sprint.

Never rewrite the architecture unless explicitly instructed.

---

# Primary Goals

The Import Engine should:

- Import invoices from any supplier.
- Be supplier agnostic.
- Extract line items accurately.
- Separate validated rows from rows that need human review.
- Require minimal manual correction.
- Continue improving without breaking previous functionality.

Target extraction accuracy:

99%+

---

# Core Philosophy

The software must never rely on one invoice layout.

Every improvement should make the engine more universal rather than overfitting to specific suppliers.

If a change only improves one supplier while hurting others, reject that approach.

Think like a document understanding engine, not a template matcher.

---

# Current Version

CULINEX Import Engine v2.0.0

---

# Current Development Stage

Sprint 26 - Ingredient Learning and Proposal Pipeline

Current objective:

Stabilize review-only ingredient learning, canonical matching, Ingredient Memory, and proposal generation before any production memory integration.

No data inference.
No supplier-specific logic.
Validation remains unchanged.

Proposal generation is disabled by default and must not change extraction, validation, accepted row counts, or discarded row counts.

---

# Completed Sprint

Sprint 26 - Ingredient Learning and Proposal Pipeline

Sprint 26 introduced:

- Ingredient Memory records and local JSON repository.
- Review-only ingredient proposals with explicit approval actions.
- Canonical ingredient matching diagnostics.
- Parser proposal observation in opt-in shadow mode.
- Duplicate proposal reuse and non-fatal proposal persistence failures.
- No automatic approval, automatic merge, or parser outcome changes.

---

# Current Import Pipeline

Upload Centre

↓

Content Extraction

↓

Universal Extractor

↓

OCR Row Reconstruction

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

    ✅ Validated
    ⚠️ Recovered - Needs Review
    ❌ Rejected

↓

Approval Queue

↓

Purchase Database

↓

Analytics

Every stage should remain independent.

---

# Modules

Current modules include:

- Upload Centre
- Content Extraction
- Universal Extractor
- OCR Row Reconstruction
- Header Detection
- Adaptive Column Detection
- Numeric Role Selection
- Validation
- Classification
- Approval Queue
- Purchase Database
- Recipe Vault
- Stock Engine
- Analytics
- Recipe Costing
- Supplier Management

These modules should remain loosely coupled.

---

# Universal Extractor Responsibilities

The Universal Extractor is responsible for:

- Reading OCR output.
- Reading PDF text.
- Reading tables.
- Combining extraction sources.
- Reconstructing broken rows.
- Detecting headers.
- Inferring columns.
- Detecting quantities.
- Detecting prices.
- Detecting totals.
- Selecting numeric roles.
- Building structured purchase rows.
- Classifying extracted rows as validated, recovered needs review, or rejected.

The Universal Extractor should not:

- Store data.
- Approve invoices.
- Modify recipes.
- Write database records.
- Perform business analytics.

---

# Validation Responsibilities

Validation occurs after extraction and numeric role selection.

Validation should:

- Verify row quality.
- Verify quantity x unit price equals line total.
- Preserve strict mathematical checks.
- Assign confidence.
- Reject impossible rows.

Validation should not:

- Reconstruct OCR.
- Weaken thresholds to improve row counts.
- Force uncertain rows into validated status.

Rows that are visible but mathematically or geometrically uncertain should remain Recovered Needs Review or Rejected.

---

# Current Benchmark Philosophy

The benchmark reports Universal Extractor rows separately:

- Validated rows.
- Recovered Needs Review rows.
- Rejected rows.

Strict Validation Pass Rate is calculated only from Validated rows.

Recovered Needs Review rows remain visible for user review and do not count as validation failures.

This keeps row recovery gains visible without weakening validation quality.

---

# Current Problem

The Import Engine now separates strict validation from recoverable review states.

Remaining work is focused on Adaptive Column Intelligence:

- Better inference of column structure.
- Better handling of missing or weak headers.
- Repeated alignment detection across OCR rows.
- Stronger numeric role selection.
- Supplier-independent semantic scoring.

---

# Development Rules

Always preserve backwards compatibility.

Never remove working functionality.

Prefer adding focused processing stages instead of replacing existing systems.

Each sprint should modify the smallest possible layer.

Avoid large rewrites.

---

# Coding Standards

Keep functions small.

Prefer readable code over clever code.

Separate extraction from validation.

Avoid duplicated logic.

Comment complex algorithms.

Use descriptive variable names.

---

# Supplier Support

The engine must work with invoices from:

- Food suppliers.
- Beverage suppliers.
- Fresh produce suppliers.
- Wholesale distributors.
- Retail grocery invoices.
- Cash-and-carry suppliers.

Future suppliers should require little to no custom coding.

---

# OCR Strategy

OCR should be considered imperfect.

Expect:

- Missing words.
- Merged words.
- Split rows.
- Wrong spacing.
- Incorrect columns.
- Missing decimals.

The extraction logic must tolerate these errors without hardcoding supplier layouts.

---

# Preferred Processing Order

1. Read document.
2. Extract text.
3. Extract tables.
4. Merge extraction sources.
5. Reconstruct OCR rows.
6. Detect headers.
7. Infer columns adaptively.
8. Select numeric roles.
9. Validate rows strictly.
10. Classify rows.
11. Send validated and reviewable rows to Approval Queue.

---

# What Not To Do

Do not redesign the architecture.

Do not remove existing modules.

Do not tightly couple components.

Do not hardcode supplier layouts.

Do not overfit algorithms to one invoice.

Do not rewrite the entire parser when only one layer needs improvement.

Do not weaken validation thresholds to improve row counts.

---

# Testing Requirements

Every extraction improvement should be tested against multiple suppliers.

Never validate success using only one invoice layout.

Success is measured by improvements across diverse invoice formats.

Regression testing is required after each sprint.

Benchmark reports must distinguish validated, recovered review, and rejected rows.

---

# Long-Term Vision

CULINEX will become a complete restaurant operating platform including:

- Invoice importing.
- Inventory management.
- Recipe costing.
- Recipe library.
- Menu engineering.
- Supplier analysis.
- Purchase analytics.
- Stock forecasting.
- Waste tracking.
- Kitchen dashboards.
- Staff training.
- Business intelligence.

The Import Engine is the foundation of the entire platform.

Protect its architecture carefully.

---

# Mission Statement

Know your business.
Know your restaurant.
Know your next culinary step.

CULINEX automates restaurant administration by transforming invoices, recipes, and inventory into reliable business intelligence with minimal manual work.
