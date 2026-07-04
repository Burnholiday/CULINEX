# CULINEX Import Accuracy Improvements

## 1. Purpose

Track real-world extraction issues found during Sprint 3 testing so they can be improved later without interrupting the current prototype sprint.

This backlog is for observation and planning only. It should not change the current extraction code, parser behavior, or RecipePreview workflow.

## 2. Known Issues

### Issue 001: Pineapple Invoice Row Extracted Incorrectly

Expected:

- supplier_code: `WHO - PINEAPPLE`
- ingredient: `Pineapple`
- description: `Each`
- quantity: `4`
- unit_price: `18.35`
- line_total: `73.40`

Actual:

- ingredient: `WHO - PINEAPPLE`
- quantity: `1`
- unit: `Number of Items`
- item_cost: `null`

### Issue 002: Broccoli Ingredient Name Extracted Incorrectly

Expected:

- ingredient: `Broccoli`
- description: `Heads-kg`

Actual:

- ingredient: `Heads-kg`

### Issue 003: Invoice Rows Parsed From Plain OCR Text

Invoice rows are being interpreted from plain OCR text instead of structured table rows.

### Issue 004: Supplier Prefix Handling

Supplier prefixes like `WHO -` should be preserved as `supplier_code` but cleaned from ingredient names.

### Issue 005: Invoice Schema Gap

Invoice documents need a dedicated invoice JSON schema, separate from recipe JSON.

## 3. Example Documents

- Farm Fresh Direct invoice with pineapple row.
- Farm Fresh Direct invoice with broccoli row.
- Future failed invoice examples should be added here with file name, supplier, date, and observed extraction output.

## 4. Pattern Observed

- OCR can read some invoice text, but row structure is lost when the parser relies only on plain text.
- Supplier item codes and ingredient names are being merged.
- Descriptions such as `Each` or `Heads-kg` are sometimes mistaken for ingredient names or units.
- Recipe extraction JSON is not suitable for invoices because invoices require supplier codes, descriptions, quantities, prices, VAT fields, and line totals.

## 5. Proposed Future Fix

- Add an invoice-specific AI extraction schema.
- Prefer structured table rows from Sprint 2 when available.
- Preserve supplier item prefixes in a separate `supplier_code` field.
- Clean supplier prefixes from human-facing ingredient names.
- Add supplier-specific row cleanup rules where needed.
- Add regression examples for known difficult invoice rows.

## 6. Priority

High after Sprint 3.

This affects invoice capture accuracy, stock price updates, and client trust. It should be handled before invoice imports are considered client-ready.

## 7. Status

Open.

No code changes have been made for these issues yet.
