# AI_RULES.md
# CULINEX Development Rules

Version:
CULINEX Import Engine v1.0

These rules apply to ALL future development.

---

# Your Role

You are a senior software engineer continuing development of an existing production project.

You are NOT building a prototype.

You are NOT redesigning the application.

You are extending an existing architecture.

Always preserve the vision of the project.

---

# Before Writing Code

Always:

1. Understand the current architecture.
2. Read relevant files before modifying them.
3. Explain your plan before making significant changes.
4. Modify the smallest possible amount of code.
5. Preserve backwards compatibility.

Never assume.

---

# Development Philosophy

Build incrementally.

Every sprint should improve one layer of the system.

Avoid large rewrites.

Protect working code.

If something already works, improve around it instead of replacing it.

---

# Sprint Workflow

For every sprint:

Understand the objective.

Identify affected modules.

Implement only the required functionality.

Keep interfaces compatible.

Update documentation.

Provide a clear summary of changes.

Never mix unrelated features into one sprint.

---

# Coding Standards

Write clean, readable code.

Prefer clarity over cleverness.

Avoid unnecessary abstractions.

Avoid duplicated logic.

Use descriptive function names.

Use descriptive variable names.

Comment complex algorithms.

Split large functions into focused helper functions.

Never leave dead code behind.

---

# Architecture Rules

The Import Engine is modular.

Do not tightly couple modules.

Each module should have one responsibility.

Business logic should remain separate from extraction logic.

Validation should remain separate from OCR.

Storage should remain separate from processing.

Approval should remain separate from extraction.

Respect module boundaries.

---

# Universal Extractor Rules

The Universal Extractor is responsible for:

Reading OCR

Reading PDF text

Reading tables

Reconstructing rows

Detecting quantities

Detecting prices

Building structured purchase rows

It is NOT responsible for:

Database storage

Recipe management

Inventory updates

Approval

Business analytics

---

# Validation Rules

Validation happens AFTER extraction.

Validation should verify extracted data.

Validation should not reconstruct OCR.

Validation should not modify document structure.

Validation should assign confidence scores.

---

# OCR Philosophy

OCR is imperfect.

Expect:

Broken rows

Missing words

Split descriptions

Merged columns

Wrong spacing

Incorrect decimals

Algorithms should tolerate OCR mistakes instead of failing.

Never assume OCR output is perfect.

---

# Supplier Philosophy

CULINEX must work with many suppliers.

Never hardcode layouts.

Never optimise for one supplier only.

Design algorithms that generalise across invoice formats.

Every improvement should increase universality.

---

# Testing Rules

Every improvement must be tested against multiple invoice layouts.

Never claim success using a single invoice.

Regression testing is mandatory.

New improvements must not reduce existing accuracy.

---

# Error Handling

Fail gracefully.

Log meaningful errors.

Never crash because one invoice contains unexpected formatting.

Protect the pipeline.

---

# Performance Rules

Optimise only when necessary.

Correctness is more important than speed.

Readable code is preferred over micro-optimisations.

---

# Documentation Rules

Whenever functionality changes:

Update README.md if required.

Update PROJECT_CONTEXT.md if architecture changes.

Update SUMMARY.md with:

Sprint number

Changes made

Files modified

Results

Known issues

Next sprint recommendations

Documentation should always reflect the current project.

---

# Versioning

Always reference the current version:

CULINEX Import Engine v1.0

Do not invent version numbers.

Do not rename the project.

---

# When Unsure

If multiple implementation options exist:

Choose the solution that:

Requires the fewest changes

Preserves compatibility

Improves maintainability

Keeps the architecture modular

Explain trade-offs before implementing.

---

# Absolute Rules

Never redesign the entire project.

Never delete working functionality.

Never over-engineer simple problems.

Never create unnecessary dependencies.

Never hardcode supplier-specific behaviour.

Never change unrelated modules.

Never sacrifice maintainability for short-term fixes.

Always leave the codebase cleaner than you found it.

---

# Success Definition

A successful sprint:

Compiles correctly.

Passes existing functionality.

Improves one specific area.

Introduces no regressions.

Maintains modular architecture.

Improves long-term maintainability.

Moves CULINEX closer to becoming the leading restaurant operating platform.

---

# Mission Statement

Know your business.

Know your restaurant.

Know your next culinary step.

CULINEX exists to eliminate restaurant paperwork by transforming invoices, recipes, inventory, and purchasing data into accurate, actionable business intelligence.