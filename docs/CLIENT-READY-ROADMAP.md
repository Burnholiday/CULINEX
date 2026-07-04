# Recipe Vault Client-Ready Roadmap

The ChatGPT concept is the correct direction. Recipe Vault already has several pieces of it, but the app should become more database-first before relying heavily on AI.

## What The Current App Already Does

- Imports invoices, recipes, prep items, PDFs, Excel files, images, and screenshots.
- Uses the local PaddleOCR helper when available.
- Cleans OCR text and turns it into recipe, prep, or invoice rows.
- Shows a review screen before invoices update stock.
- Matches invoice items and recipe ingredients to stock items.
- Remembers manager-approved stock links.
- Calculates recipe, prep item, and food cost values.
- Stores invoice images with invoice history.
- Tracks stock and invoices by month.
- Supports backup, restore, support package export, import logs, AI decision summaries, and correction history.

## What Should Come Next

1. Move local data from browser `localStorage` to SQLite.
2. Keep the current review-first workflow.
3. Add a proper supplier table and supplier-specific invoice templates.
4. Add an alias table for stock and recipe ingredient names.
5. Store OCR text, structured JSON, confidence scores, and manager corrections per import.
6. Use local Ollama/Qwen for AI extraction by default, with OpenAI optional later.
7. Export support packages for failed imports.
8. Add automatic daily backups.
9. Add Base44 sync for cloud/subscription customers.

## Recommended Client Import Flow

```text
File upload
  -> pre-scan
  -> OCR/table extraction
  -> rule-based cleanup
  -> optional local AI validation
  -> confidence score
  -> review screen
  -> manager confirms links
  -> save to database
  -> correction history remembered
```

## Epic 1 Progress

### Sprint 1: Upload Centre

Done:

- Drag/drop and browse upload screen.
- Supports PDF, PNG, JPG, JPEG, XLSX, CSV, and TXT.
- Generates `file_id`.
- Detects file type.
- Shows upload cards.
- Saves files locally through the launcher to `outputs/data/uploads/<file_id>/`.
- Creates `upload.log`.

### Sprint 2: Content Extraction

Done:

- Reads Sprint 1 uploaded files by `file_id`.
- PDF text extraction uses `pdfplumber` first.
- PDF table extraction uses `pdfplumber`.
- PDF fallback uses PaddleOCR.
- Images use PaddleOCR.
- CSV uses Python CSV parsing.
- XLSX uses pandas/openpyxl when available, with a standard-library XLSX fallback.
- Shows extracted text and table rows in `ExtractedTextPreview`.

Not included yet:

- AI extraction.
- Recipe/invoice/prep parsing into final records.
- Database saving.
- Stock updates.

### Sprint 3: AI Recipe Extraction

Done:

- Adds `AIRecipeExtractor`.
- Builds a strict recipe extraction prompt with `build_recipe_prompt()`.
- Calls local Ollama/Qwen through the local helper with `call_ollama()`.
- Keeps OpenAI optional with `call_openai()`.
- Parses AI output with `parse_ai_response()`.
- Returns structured recipe JSON for preview only.
- Shows `RecipePreview` with recipe name, ingredients, yield, total cost, cost per portion, notes, and confidence when available.

Not included:

- Saving recipes.
- Ingredient matching or normalization.
- Duplicate detection.
- Recipe validation.
- Inventory updates.
- Cost calculation.

### Sprint 4: Review & Approval

Done:

- Adds `ReviewPanel`.
- Shows document type, AI provider, model, confidence, ingredient count, total cost, recipe name, and yield.
- Makes recipe fields editable before any future import.
- Makes ingredient rows editable before any future import.
- Highlights missing quantities, units, costs, and duplicate ingredient names.
- Adds Approve, Reject, Export JSON, and Back actions.

Not included:

- Database saving.
- Recipe import.
- Validation enforcement.
- Ingredient matching or normalization.
- Shopping lists.
- Meal planning.

## Technical Debt

### TD-001: Dense PDF Layout Detection And OCR Fallback

Status: Deferred until after Sprint 3.

Problem:

Dense multi-column spreadsheet-style PDFs, especially the sushi bulk prep PDF, can contain visual table layouts that are not reliably represented by normal PDF text extraction.

Future improvement:

```text
PDF
  -> detect whether the page contains normal selectable text
  -> if yes, extract text
  -> detect whether the page contains tables
  -> if yes, extract tables
  -> detect dense or multi-column layout
  -> render page as an image
  -> run PaddleOCR
  -> reconstruct layout from OCR boxes
```

Decision:

Do not block Sprint 3 on this. Keep the sushi PDF as a permanent benchmark/regression file so future extractor improvements can be tested against the same difficult document.

## Why Not Build AI First

AI should improve the workflow, not become the database. The reliable product is built from:

- clean entities
- strong validation
- manager approval
- alias memory
- support packages
- backups

Once those are stable, local AI can safely help with extraction and error checking.
