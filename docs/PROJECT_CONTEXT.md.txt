# CULINEX Import Engine v1.0
## Master Project Context

---

# Project Overview

CULINEX (Your Culinary Next Step) is a restaurant management platform focused on automating kitchen administration.

The Import Engine is responsible for transforming supplier invoices into structured purchasing data that can be reviewed, approved and stored.

This is production software.

The project must remain modular and be developed sprint-by-sprint.

Never rewrite the architecture unless explicitly instructed.

---

# Primary Goals

The Import Engine should:

• Import invoices from any supplier
• Be supplier agnostic
• Extract line items accurately
• Require minimal manual correction
• Continue improving without breaking previous functionality

Target extraction accuracy:

99%+

---

# Core Philosophy

The software must NEVER rely on one invoice layout.

Every improvement should make the engine more universal rather than overfitting to specific suppliers.

If a change only improves one supplier while hurting others, reject that approach.

Think like a document understanding engine—not a template matcher.

---

# Current Version

CULINEX Import Engine v1.0

---

# Current Development Stage

Sprint 13

Focus:

Universal OCR Row Reconstruction

Current objective:

Improve extraction BEFORE validation.

Do NOT redesign approval, storage or downstream systems.

---

# Current Import Pipeline

Upload

↓

File Detection

↓

Content Extraction

↓

Universal Extractor

↓

Invoice Validator

↓

Approval Queue

↓

Database

↓

Analytics

Every stage should remain independent.

---

# Modules

Current modules include:

Upload Centre

Content Extraction

Universal Extractor

Invoice Validator

Approval Queue

Purchase Database

Recipe Vault

Stock Engine

Analytics

Recipe Costing

Supplier Management

These modules should remain loosely coupled.

---

# Universal Extractor Responsibilities

The Universal Extractor is responsible for:

• Reading OCR output
• Reading PDF text
• Reading tables
• Combining extraction sources
• Reconstructing broken rows
• Detecting quantities
• Detecting prices
• Detecting totals
• Building structured purchase rows

The Universal Extractor should NOT:

Store data

Approve invoices

Modify recipes

Write database records

Perform business logic

---

# Validation Responsibilities

Validation occurs AFTER extraction.

Validation should:

Verify row quality

Verify totals

Assign confidence

Reject impossible rows

The validator should not attempt to reconstruct OCR.

---

# Current Problem

Current benchmark:

Approximately 97–98% validation success.

Remaining failures mostly come from OCR fragmentation.

Typical problems:

Wrapped descriptions

Split quantities

Detached totals

Broken OCR rows

Multi-line products

Orphan numeric values

The reconstruction algorithm should solve these before validation begins.

---

# Development Rules

Always preserve backwards compatibility.

Never remove working functionality.

Prefer adding new processing stages instead of replacing existing ones.

Each sprint should modify the smallest possible layer.

Avoid giant rewrites.

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

Food suppliers

Beverage suppliers

Fresh produce suppliers

Wholesale distributors

Retail grocery invoices

Cash-and-carry suppliers

Future suppliers should require little to no custom coding.

---

# OCR Strategy

OCR should be considered imperfect.

Expect:

Missing words

Merged words

Split rows

Wrong spacing

Incorrect columns

Missing decimals

The extraction logic must tolerate these errors.

---

# Preferred Processing Order

1. Read document

2. Extract text

3. Extract tables

4. Merge extraction sources

5. Reconstruct rows

6. Detect columns

7. Validate rows

8. Score confidence

9. Send to Approval Queue

---

# What NOT to Do

Do not redesign the architecture.

Do not remove existing modules.

Do not tightly couple components.

Do not hardcode supplier layouts.

Do not overfit algorithms to one invoice.

Do not rewrite the entire parser when only one layer needs improvement.

---

# AI Development Guidelines

Before making changes:

Understand the existing architecture.

Identify the correct module.

Modify only that module.

Preserve interfaces.

Avoid unnecessary refactoring.

Explain reasoning before major architectural changes.

When proposing improvements, prefer incremental enhancements over rewrites.

---

# Testing Requirements

Every extraction improvement should be tested against multiple suppliers.

Never validate success using only one invoice layout.

Success is measured by improvements across diverse invoice formats.

Regression testing is required after each sprint.

---

# Long-Term Vision

CULINEX will become a complete restaurant operating platform including:

Invoice importing

Inventory management

Recipe costing

Recipe library

Menu engineering

Supplier analysis

Purchase analytics

Stock forecasting

Waste tracking

Kitchen dashboards

Staff training

Business intelligence

The Import Engine is the foundation of the entire platform.

Protect its architecture carefully.

---

# Mission Statement

Know your business.
Know your restaurant.
Know your next culinary step.

CULINEX automates restaurant administration by transforming invoices, recipes and inventory into reliable business intelligence with minimal manual work.