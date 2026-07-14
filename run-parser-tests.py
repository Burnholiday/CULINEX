import importlib.util
import json
import multiprocessing as mp
import os
import re
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TEST_INVOICE_DIR = ROOT / "data" / "test-invoices"
RESULT_DIR = ROOT / "data" / "parser-test-results"
LOCAL_SERVER_PATH = ROOT / "recipe-vault-local-server.py"
SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv", ".txt"}
PER_FILE_TIMEOUT_SECONDS = int(os.environ.get("CULINEX_PARSER_TEST_TIMEOUT", "180"))


SUPPLIER_PATTERNS = [
    ("Farm Fresh Direct", [r"farm\s*fresh\s*direct", r"farmfreshdirect"]),
    ("So-CA Foods", [r"\bso[-\s]?ca\s+foods\b", r"\bsoca\s+foods\b", r"\biqinv"]),
    ("Grocery Express", [r"\bgrocery\s+express\b", r"\bge\d{4,}\b"]),
    ("Robberg", [r"\brobberg\b"]),
    ("Morningside Eggs", [r"\bmorningside\s+eggs\b", r"\bmorningside\s+poultry\b"]),
    ("DistriLiq", [r"\bdistriliq\b", r"\bdistri\s*liq\b"]),
]


def now_iso():
    return datetime.now().replace(microsecond=0).isoformat()


def safe_name(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("_")[:120] or "invoice"


def load_recipe_vault_module():
    spec = importlib.util.spec_from_file_location("recipe_vault_local_server", LOCAL_SERVER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {LOCAL_SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def is_product_row_type(value, row_type_cls=None):
    product = getattr(row_type_cls, "PRODUCT", None) if row_type_cls else None
    if product is not None and isinstance(value, row_type_cls):
        return value == product
    product_value = getattr(product, "value", "product")
    return str(value or "").strip().lower() == product_value


def detect_supplier(text="", metadata=None, filename=""):
    candidates = [
        str((metadata or {}).get("supplier") or ""),
        str(filename or ""),
        str(text or ""),
    ]
    combined = "\n".join(candidates)
    for supplier, patterns in SUPPLIER_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, combined, re.IGNORECASE):
                return supplier
    return "Unknown"


def validation_failures(rows):
    failures = []
    for index, row in enumerate(rows or [], 1):
        validation = row.get("validation") if isinstance(row, dict) else {}
        if (validation or {}).get("status") != "ok":
            failures.append({
                "row_index": index,
                "ingredient": row.get("ingredient") if isinstance(row, dict) else None,
                "supplier_code": row.get("supplier_code") if isinstance(row, dict) else None,
                "validation": validation or {"status": "missing", "message": "No validation result"},
            })
    return failures


def universal_validation_failures(rows, module):
    failures = []
    for index, row in enumerate(rows or [], 1):
        if not isinstance(row, dict):
            validation = {"status": "missing", "message": "Invalid row", "affected_field": "row"}
        else:
            validation = row.get("validation") or module.validate_invoice_math(
                module.parse_money_number(row.get("quantity")),
                module.parse_money_number(row.get("unit_price")),
                module.parse_money_number(row.get("total")),
            )
        if validation.get("status") != "ok":
            failures.append({
                "row_index": index,
                "description": row.get("description") if isinstance(row, dict) else None,
                "validation": validation,
            })
    return failures


def pass_rate(row_count, failure_count):
    if not row_count:
        return 0.0
    return round(((row_count - failure_count) / row_count) * 100, 1)


def failure_reason_counts(results, parser_key):
    counts = Counter()
    for item in results:
        parser = item.get(parser_key) or {}
        for failure in parser.get("validation_failures") or []:
            validation = failure.get("validation") or {}
            counts[validation.get("message") or validation.get("status") or "unknown"] += 1
    return counts


def review_reason_counts(results):
    counts = Counter()
    for item in results:
        parser = item.get("universal_line_item_extractor") or {}
        for row in parser.get("recovered_needs_review") or []:
            if not isinstance(row, dict):
                continue
            counts[row.get("review_reason") or "unknown"] += 1
    return counts


def review_reason_counts_by_supplier(results):
    counts = {}
    for item in results:
        supplier = item.get("detected_supplier") or "Unknown"
        parser = item.get("universal_line_item_extractor") or {}
        for row in parser.get("recovered_needs_review") or []:
            if not isinstance(row, dict):
                continue
            reason = row.get("review_reason") or "unknown"
            counts.setdefault(supplier, Counter())[reason] += 1
    return counts


def discard_reason_counts(results):
    counts = Counter()
    for item in results:
        parser = item.get("universal_line_item_extractor") or {}
        for discarded in parser.get("discarded_rows") or []:
            counts[discarded.get("reason") or "unknown"] += 1
    return counts


def proposal_summary_from_rows(rows):
    summary = {
        "accepted_rows_evaluated": 0,
        "strong_memory_matches": 0,
        "proposals_generated_by_type": {},
        "duplicate_proposals_reused": 0,
        "proposal_errors": 0,
    }
    generated_by_type = Counter()
    for row in rows or []:
        if not isinstance(row, dict) or not row.get("ingredient_candidate"):
            continue
        summary["accepted_rows_evaluated"] += 1
        if row.get("canonical_match_candidate", {}).get("canonical_match_id") or row.get("canonical_match_id"):
            summary["strong_memory_matches"] += 1
        if row.get("ingredient_proposal_generated"):
            generated_by_type[row.get("ingredient_proposal_type") or "unknown"] += 1
        elif row.get("ingredient_proposal_id") and row.get("ingredient_proposal_status"):
            summary["duplicate_proposals_reused"] += 1
        if row.get("ingredient_proposal_error"):
            summary["proposal_errors"] += 1
    summary["proposals_generated_by_type"] = dict(generated_by_type)
    return summary


def proposal_summary_metrics(results):
    aggregate = {
        "accepted_rows_evaluated": 0,
        "strong_memory_matches": 0,
        "proposals_generated_by_type": Counter(),
        "duplicate_proposals_reused": 0,
        "proposal_errors": 0,
    }
    for item in results:
        parser = item.get("universal_line_item_extractor") or {}
        summary = parser.get("ingredient_proposals") or proposal_summary_from_rows(parser.get("rows") or [])
        aggregate["accepted_rows_evaluated"] += int(summary.get("accepted_rows_evaluated") or 0)
        aggregate["strong_memory_matches"] += int(summary.get("strong_memory_matches") or 0)
        aggregate["duplicate_proposals_reused"] += int(summary.get("duplicate_proposals_reused") or 0)
        aggregate["proposal_errors"] += int(summary.get("proposal_errors") or 0)
        aggregate["proposals_generated_by_type"].update(summary.get("proposals_generated_by_type") or {})
    aggregate["proposals_generated_by_type"] = dict(aggregate["proposals_generated_by_type"])
    return aggregate


def parser_debug(rows):
    debug = []
    for index, row in enumerate(rows or [], 1):
        if not isinstance(row, dict):
            continue
        debug.append({
            "row_index": index,
            "ingredient": row.get("ingredient"),
            "supplier_code": row.get("supplier_code"),
            "parser_debug": row.get("parser_debug") or {},
        })
    return debug


def numeric_sum(values):
    total = 0.0
    found = False
    for value in values:
        if isinstance(value, (int, float)):
            total += float(value)
            found = True
    return round(total, 2) if found else None


def run_one(module, invoice_path):
    file_id = f"parser_test_{safe_name(invoice_path.stem)}"
    content = module.extract_content(invoice_path, file_id=file_id)
    text = content.get("extracted_text") or ""
    tables = content.get("extracted_tables") or []

    parsed = module.InvoiceTableParser(text, tables).parse()
    rows = parsed.get("rows") or content.get("invoice_table_rows") or []
    universal = module.LineItemExtractor().extract(text, tables)
    universal_all_rows = universal.get("extracted_rows") or []
    universal_rows = universal.get("validated_rows") or [
        row for row in universal_all_rows
        if isinstance(row, dict) and (row.get("validation") or {}).get("status") == "ok"
    ]
    universal_review_rows = universal.get("recovered_needs_review") or [
        row for row in universal_all_rows
        if isinstance(row, dict) and row.get("review_status") == "recovered_needs_review"
    ]
    metadata = {
        **(content.get("invoice_metadata") or {}),
        **(parsed.get("metadata") or {}),
    }
    document_type, classifier_confidence, classifier_scores = module.classify_document(text, tables)
    supplier = detect_supplier(text=text, metadata=metadata, filename=invoice_path.name)
    failures = validation_failures(rows)
    universal_failures = universal_validation_failures(universal_rows, module)
    universal_review_failures = universal_validation_failures(universal_review_rows, module)
    line_total_sum = numeric_sum(row.get("line_total") for row in rows if isinstance(row, dict))
    universal_visible_rows = len(universal_rows) + len(universal_review_rows)
    universal_review_rate = pass_rate(universal_visible_rows, len(universal_rows)) if universal_visible_rows else 0.0

    # Add invoice row classification diagnostics
    classifier = module.InvoiceRowClassifier()
    classified_rows = []
    proposal_generation_enabled = bool(getattr(module, "enable_ingredient_proposals", False))
    proposal_matcher = None
    proposal_engine = None
    if proposal_generation_enabled and hasattr(module, "build_ingredient_matcher"):
        proposal_matcher, proposal_engine = module.build_ingredient_matcher(True)
    
    # Classify all rows from universal extractor
    for row in universal_all_rows:
        if isinstance(row, dict):
            # Get the raw text for classification
            raw_text = row.get("raw_text") or row.get("description") or ""
            classification_result = classifier.classify(raw_text)
            
            # Add classification diagnostics to the row
            row_with_classification = dict(row)
            row_with_classification["row_type"] = classification_result.row_type.value
            row_with_classification["row_type_confidence"] = classification_result.confidence
            row_with_classification["classification_reasons"] = classification_result.reasons
            row_with_classification["matched_signals"] = classification_result.matched_signals
            row_with_classification["conflicting_signals"] = classification_result.conflicting_signals
            
            # Add ingredient intelligence diagnostics for PRODUCT rows
            if is_product_row_type(row_with_classification.get("row_type"), module.RowType):
                # Initialize ingredient engine for this row
                ingredient_engine = module.IngredientIntelligenceEngine()
                ingredient_candidate = ingredient_engine.analyze_product_row(raw_text, row)
                
                # Convert IngredientCandidate to JSON-safe dictionary
                if ingredient_candidate:
                    from dataclasses import asdict, is_dataclass
                    if is_dataclass(ingredient_candidate):
                        ingredient_candidate_json = asdict(ingredient_candidate)
                    elif hasattr(ingredient_candidate, "to_dict"):
                        ingredient_candidate_json = ingredient_candidate.to_dict()
                    elif isinstance(ingredient_candidate, dict):
                        ingredient_candidate_json = ingredient_candidate
                    else:
                        ingredient_candidate_json = {}
                    
                    # Add ingredient diagnostics to the row
                    row_with_classification["ingredient_candidate"] = ingredient_candidate_json
                    row_with_classification["ingredient_confidence"] = float(
                        ingredient_candidate_json.get("confidence", 0.0) or 0.0
                    )
                    row_with_classification["ingredient_reasons"] = list(
                        ingredient_candidate_json.get("reasons", []) or []
                    )
                    row_with_classification["ingredient_matched_signals"] = list(
                        ingredient_candidate_json.get("matched_signals", []) or []
                    )
                    row_with_classification["ingredient_conflicting_signals"] = list(
                        ingredient_candidate_json.get("conflicting_signals", []) or []
                    )
                    if hasattr(module, "match_ingredient_candidate_for_row"):
                        canonical_match_candidate = module.match_ingredient_candidate_for_row(
                            ingredient_candidate,
                            row=row,
                            context={
                                "source_filename": invoice_path.name,
                                "source_row_id": row.get("row_id") or row.get("row_index") or len(classified_rows) + 1,
                                "supplier_name": supplier,
                                "supplier_code": row.get("supplier_code"),
                            },
                            enable_proposals=proposal_generation_enabled,
                            ingredient_matcher=proposal_matcher,
                            proposal_engine=proposal_engine,
                        )
                    else:
                        ingredient_matcher = module.IngredientMatcher()
                        canonical_match_candidate = ingredient_matcher.analyze_candidate(ingredient_candidate)
                    if canonical_match_candidate:
                        canonical_match_candidate_json = asdict(canonical_match_candidate)
                        row_with_classification["canonical_match_candidate"] = canonical_match_candidate_json
                        row_with_classification["normalized_match_key"] = canonical_match_candidate_json.get("normalized_match_key")
                        row_with_classification["proposed_canonical_name"] = canonical_match_candidate_json.get("proposed_canonical_name")
                        row_with_classification["match_confidence"] = float(
                            canonical_match_candidate_json.get("match_confidence", 0.0) or 0.0
                        )
                        row_with_classification["match_reasons"] = list(
                            canonical_match_candidate_json.get("match_reasons", []) or []
                        )
                        row_with_classification["canonical_matched_signals"] = list(
                            canonical_match_candidate_json.get("matched_signals", []) or []
                        )
                        row_with_classification["canonical_conflicting_signals"] = list(
                            canonical_match_candidate_json.get("conflicting_signals", []) or []
                        )
                        row_with_classification["alternative_candidates"] = list(
                            canonical_match_candidate_json.get("alternative_candidates", []) or []
                        )
                        row_with_classification["review_required"] = bool(
                            canonical_match_candidate_json.get("review_required", False)
                        )
                        row_with_classification["ingredient_proposal_generated"] = bool(
                            canonical_match_candidate_json.get("proposal_generated", False)
                        )
                        row_with_classification["ingredient_proposal_id"] = canonical_match_candidate_json.get("proposal_id")
                        row_with_classification["ingredient_proposal_type"] = canonical_match_candidate_json.get("proposal_type")
                        row_with_classification["ingredient_proposal_status"] = canonical_match_candidate_json.get("proposal_status")
                        row_with_classification["ingredient_proposal_error"] = canonical_match_candidate_json.get("proposal_error")
                    elif hasattr(module, "ingredient_proposal_diagnostics"):
                        row_with_classification.update(module.ingredient_proposal_diagnostics(None))
            
            classified_rows.append(row_with_classification)
        else:
            classified_rows.append(row)

    ingredient_proposals_summary = proposal_summary_from_rows(classified_rows)

    return {
        "tested_at": now_iso(),
        "file_id": file_id,
        "filename": invoice_path.name,
        "file_path": str(invoice_path),
        "detected_supplier": supplier,
        "document_type": document_type,
        "classifier_confidence": classifier_confidence,
        "classifier_scores": classifier_scores,
        "invoice_number": metadata.get("invoice_number"),
        "invoice_date": metadata.get("invoice_date"),
        "line_count": len(rows),
        "subtotal": line_total_sum,
        "total": metadata.get("total"),
        "currency": metadata.get("currency"),
        "extraction_status": content.get("extraction_status"),
        "engine": content.get("engine"),
        "errors": content.get("errors") or [],
        "extracted_rows": rows,
        "validation_failures": failures,
        "parser_debug": parser_debug(rows),
        "invoice_table_parser": {
            "row_count": len(rows),
            "rows": rows,
            "metadata": parsed.get("metadata") or {},
            "validation_failures": failures,
            "validation_pass_rate": pass_rate(len(rows), len(failures)),
            "parser_debug": parser_debug(rows),
        },
        "universal_line_item_extractor": {
            "row_count": len(universal_all_rows),
            "rows_found": len(universal_rows) + len(universal_review_rows) + len(universal.get("discarded_rows") or []),
            "rows_accepted": len(universal_rows),
            "rows_recovered_needs_review": len(universal_review_rows),
            "rows_discarded": len(universal.get("discarded_rows") or []),
            "rows": classified_rows,  # Use classified rows instead of original
            "validated_rows": universal_rows,
            "recovered_needs_review": universal_review_rows,
            "detected_headers": universal.get("detected_headers") or [],
            "detected_columns": universal.get("detected_columns") or [],
            "geometry_debug": universal.get("geometry_debug") or [],
            "discarded_rows": universal.get("discarded_rows") or [],
            "confidence": universal.get("confidence", 0),
            "validation_failures": universal_failures,
            "validation_pass_rate": pass_rate(len(universal_rows), len(universal_failures)),
            "strict_validation_pass_rate": pass_rate(len(universal_rows), len(universal_failures)),
            "recovered_needs_review_rate": universal_review_rate,
            "review_reason_counts": dict(Counter(
                row.get("review_reason") or "unknown"
                for row in universal_review_rows
                if isinstance(row, dict)
            )),
            "review_failures": universal_review_failures,
            "ingredient_proposals": ingredient_proposals_summary,
        },
        "needs_review": bool(content.get("errors")) or (not rows and not universal_rows and not universal_review_rows) or bool(failures) or bool(universal_failures) or bool(universal_review_rows),
    }


def run_one_worker(invoice_path_text, worker_result_path_text):
    try:
        module = load_recipe_vault_module()
        payload = {"ok": True, "result": run_one(module, Path(invoice_path_text))}
    except Exception as exc:
        payload = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    Path(worker_result_path_text).write_text(json.dumps(payload), encoding="utf-8")


def run_one_with_timeout(invoice_path, timeout_seconds=PER_FILE_TIMEOUT_SECONDS):
    worker_result_path = RESULT_DIR / f".worker-{safe_name(invoice_path.stem)}.json"
    try:
        worker_result_path.unlink()
    except OSError:
        pass
    process = mp.Process(target=run_one_worker, args=(str(invoice_path), str(worker_result_path)))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(5)
        return timeout_result(invoice_path, timeout_seconds)
    if not worker_result_path.exists():
        return error_result(invoice_path, "Parser worker exited without returning a result.")
    try:
        payload = json.loads(worker_result_path.read_text(encoding="utf-8"))
    finally:
        try:
            worker_result_path.unlink()
        except OSError:
            pass
    if payload.get("ok"):
        return payload.get("result")
    return error_result(invoice_path, payload.get("error") or "Parser worker failed.", payload.get("traceback") or "")


def timeout_result(invoice_path, timeout_seconds):
    return error_result(invoice_path, f"Parser test timed out after {timeout_seconds} seconds.")


def error_result(invoice_path, message, trace=""):
    return {
        "tested_at": now_iso(),
        "filename": invoice_path.name,
        "file_path": str(invoice_path),
        "detected_supplier": detect_supplier(filename=invoice_path.name),
        "document_type": "supplier_invoice",
        "invoice_number": None,
        "invoice_date": None,
        "line_count": 0,
        "subtotal": None,
        "total": None,
        "extracted_rows": [],
        "validation_failures": [],
        "parser_debug": [],
        "invoice_table_parser": {
            "row_count": 0,
            "rows": [],
            "metadata": {},
            "validation_failures": [],
            "validation_pass_rate": 0.0,
            "parser_debug": [],
        },
        "universal_line_item_extractor": {
            "row_count": 0,
            "rows_found": 0,
            "rows_accepted": 0,
            "rows_discarded": 0,
            "rows": [],
            "detected_headers": [],
            "detected_columns": [],
            "geometry_debug": [],
            "discarded_rows": [],
            "confidence": 0,
            "validation_failures": [],
            "validation_pass_rate": 0.0,
        },
        "errors": [message],
        "traceback": trace,
        "needs_review": True,
    }


def result_filename(invoice_path):
    return RESULT_DIR / f"{safe_name(invoice_path.stem)}.json"


def geometry_debug_entries(parser):
    geometry_debug = (parser or {}).get("geometry_debug") or []
    if isinstance(geometry_debug, dict):
        return [geometry_debug]
    if isinstance(geometry_debug, list):
        return [entry for entry in geometry_debug if isinstance(entry, dict)]
    return []


def geometry_summary_metrics(results):
    files_with_geometry_debug = 0
    files_with_table_region_detected = 0
    files_with_no_table_region = 0
    geometry_detection_errors = 0
    confidence_values = []

    for item in results:
        extractor = item.get("universal_line_item_extractor") or {}
        entries = geometry_debug_entries(extractor)
        if not entries:
            continue

        files_with_geometry_debug += 1
        detected = any(entry.get("table_region_detected") is True for entry in entries)
        has_detection_error = False

        for entry in entries:
            confidence = entry.get("table_confidence")
            if isinstance(confidence, (int, float)):
                confidence_values.append(float(confidence))

            failure = entry.get("failure")
            if failure and failure != "no_table_regions_detected":
                has_detection_error = True

        if detected:
            files_with_table_region_detected += 1
        else:
            files_with_no_table_region += 1
        if has_detection_error:
            geometry_detection_errors += 1

    average_table_confidence = (
        round(sum(confidence_values) / len(confidence_values), 3)
        if confidence_values else 0.0
    )

    return {
        "files_with_geometry_debug": files_with_geometry_debug,
        "files_with_table_region_detected": files_with_table_region_detected,
        "files_with_no_table_region": files_with_no_table_region,
        "geometry_detection_errors": geometry_detection_errors,
        "average_table_confidence": average_table_confidence,
    }


def write_summary(results):
    def parser_int(parser, key, default_key=None):
        if key in parser:
            return int(parser.get(key) or 0)
        if default_key:
            return int(parser.get(default_key) or 0)
        return 0

    total_files = len(results)
    supplier_counts = Counter(item.get("detected_supplier") or "Unknown" for item in results)
    old_rows = sum(int((item.get("invoice_table_parser") or {}).get("row_count") or 0) for item in results)
    new_rows = sum(int((item.get("universal_line_item_extractor") or {}).get("row_count") or 0) for item in results)
    new_found = sum(parser_int(item.get("universal_line_item_extractor") or {}, "rows_found", "row_count") for item in results)
    new_accepted = sum(parser_int(item.get("universal_line_item_extractor") or {}, "rows_accepted", "row_count") for item in results)
    new_review = sum(parser_int(item.get("universal_line_item_extractor") or {}, "rows_recovered_needs_review") for item in results)
    new_discarded = sum(parser_int(item.get("universal_line_item_extractor") or {}, "rows_discarded") for item in results)
    old_failures = sum(len((item.get("invoice_table_parser") or {}).get("validation_failures") or []) for item in results)
    new_failures = sum(len((item.get("universal_line_item_extractor") or {}).get("validation_failures") or []) for item in results)
    old_pass_rate = pass_rate(old_rows, old_failures)
    new_pass_rate = pass_rate(new_accepted, new_failures)
    review_denominator = new_accepted + new_review
    review_rate = round((new_review / review_denominator) * 100, 1) if review_denominator else 0.0
    universal_improved = [
        item for item in results
        if int((item.get("universal_line_item_extractor") or {}).get("row_count") or 0) > 0
        and int((item.get("invoice_table_parser") or {}).get("row_count") or 0) == 0
    ]
    both_failed = [
        item for item in results
        if int((item.get("universal_line_item_extractor") or {}).get("row_count") or 0) == 0
        and int((item.get("invoice_table_parser") or {}).get("row_count") or 0) == 0
    ]
    review_files = [item for item in results if item.get("needs_review")]
    universal_failure_reasons = failure_reason_counts(results, "universal_line_item_extractor")
    universal_review_reasons = review_reason_counts(results)
    universal_review_reasons_by_supplier = review_reason_counts_by_supplier(results)
    universal_discard_reasons = discard_reason_counts(results)
    geometry_metrics = geometry_summary_metrics(results)
    proposal_metrics = proposal_summary_metrics(results)
    
    # Benchmark metrics for geometric analysis
    avg_column_confidence = 0.0
    total_rows_with_confidence = 0
    total_confidence_sum = 0.0
    for item in results:
        extractor = item.get("universal_line_item_extractor") or {}
        for row in extractor.get("rows") or []:
            if isinstance(row, dict) and row.get("column_confidence"):
                total_confidence_sum += row.get("column_confidence", 0.0)
                total_rows_with_confidence += 1
    if total_rows_with_confidence > 0:
        avg_column_confidence = round(total_confidence_sum / total_rows_with_confidence, 3)
    
    # Count rows with high confidence (>0.8)
    high_confidence_rows = 0
    for item in results:
        extractor = item.get("universal_line_item_extractor") or {}
        for row in extractor.get("rows") or []:
            if isinstance(row, dict) and row.get("column_confidence", 0) >= 0.8:
                high_confidence_rows += 1
    
    # Benchmark metric: percentage of rows with good column confidence
    confidence_quality_rate = round((high_confidence_rows / new_accepted * 100), 1) if new_accepted > 0 else 0.0
    
    # Benchmark metric: average extraction time (if available in results)
    avg_extraction_time_ms = 0
    extraction_times = []
    for item in results:
        extraction_engine = item.get("extraction_engine") or {}
        if isinstance(extraction_engine, dict) and extraction_engine.get("time_taken_ms"):
            extraction_times.append(extraction_engine.get("time_taken_ms"))
    if extraction_times:
        avg_extraction_time_ms = round(sum(extraction_times) / len(extraction_times), 1)
    
    # Benchmark metric: validation pass rate improvement
    validation_improvement = round(new_pass_rate - old_pass_rate, 1)
    lines = [
        "# Parser Test Results",
        "",
        f"Generated: {now_iso()}",
        "",
        "## Summary",
        "",
        f"- Total files tested: {total_files}",
        f"- InvoiceTableParser rows extracted: {old_rows}",
        f"- UniversalExtractor rows found: {new_found}",
        f"- UniversalExtractor validated rows: {new_accepted}",
        f"- UniversalExtractor recovered_needs_review rows: {new_review}",
        f"- UniversalExtractor recovered_needs_review rate: {review_rate:.1f}%",
        f"- UniversalExtractor rows discarded: {new_discarded}",
        f"- InvoiceTableParser validation pass rate: {old_pass_rate:.1f}%",
        f"- UniversalExtractor strict validation pass rate: {new_pass_rate:.1f}%",
        f"- Validation pass rate improvement: {validation_improvement:+.1f} percentage points",
        f"- Files where UniversalExtractor found rows but InvoiceTableParser found none: {len(universal_improved)}",
        f"- Files where both failed: {len(both_failed)}",
        f"- Files needing review: {len(review_files)}",
        "",
        "## Geometric Analysis Benchmarks",
        "",
        f"- Average column confidence: {avg_column_confidence}",
        f"- Rows with high column confidence (>=0.8): {high_confidence_rows}",
        f"- Confidence quality rate: {confidence_quality_rate}%",
        f"- Average extraction time: {avg_extraction_time_ms}ms",
        "",
        "## Geometry Shadow Mode Coverage",
        "",
        f"- Files with geometry debug: {geometry_metrics['files_with_geometry_debug']}",
        f"- Files with table region detected: {geometry_metrics['files_with_table_region_detected']}",
        f"- Files with no table region: {geometry_metrics['files_with_no_table_region']}",
        f"- Geometry detection errors: {geometry_metrics['geometry_detection_errors']}",
        f"- Average table confidence: {geometry_metrics['average_table_confidence']}",
        "",
        "## Ingredient Proposal Observation",
        "",
        f"- Accepted rows evaluated for ingredient proposals: {proposal_metrics['accepted_rows_evaluated']}",
        f"- Strong Ingredient Memory matches: {proposal_metrics['strong_memory_matches']}",
        f"- Proposals generated by type: {proposal_metrics['proposals_generated_by_type']}",
        f"- Duplicate proposals reused: {proposal_metrics['duplicate_proposals_reused']}",
        f"- Proposal errors: {proposal_metrics['proposal_errors']}",
        "",
        "## Supplier Breakdown",
        "",
    ]
    if supplier_counts:
        for supplier, count in supplier_counts.most_common():
            lines.append(f"- {supplier}: {count}")
    else:
        lines.append("- No invoices tested yet.")

    lines.extend(["", "## UniversalExtractor Strict Validation Failure Reasons", ""])
    if universal_failure_reasons:
        for reason, count in universal_failure_reasons.most_common(12):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None.")

    lines.extend(["", "## UniversalExtractor Review Reasons", ""])
    if universal_review_reasons:
        for reason, count in universal_review_reasons.most_common(12):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None.")

    lines.extend(["", "## UniversalExtractor Review Reasons By Supplier", ""])
    if universal_review_reasons_by_supplier:
        for supplier in sorted(universal_review_reasons_by_supplier):
            reason_counts = ", ".join(
                f"{reason}: {count}"
                for reason, count in universal_review_reasons_by_supplier[supplier].most_common()
            )
            lines.append(f"- {supplier}: {reason_counts}")
    else:
        lines.append("- None.")

    lines.extend(["", "## UniversalExtractor Discard Reasons", ""])
    if universal_discard_reasons:
        for reason, count in universal_discard_reasons.most_common(12):
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Files Needing Review", ""])
    if review_files:
        for item in review_files:
            reasons = []
            if item.get("errors"):
                reasons.append("extraction error")
            old_count = int((item.get("invoice_table_parser") or {}).get("row_count") or 0)
            new_count = int((item.get("universal_line_item_extractor") or {}).get("row_count") or 0)
            if not old_count and not new_count:
                reasons.append("no rows")
            old_issue_count = len((item.get("invoice_table_parser") or {}).get("validation_failures") or [])
            new_issue_count = len((item.get("universal_line_item_extractor") or {}).get("validation_failures") or [])
            review_count = int((item.get("universal_line_item_extractor") or {}).get("rows_recovered_needs_review") or 0)
            if old_issue_count:
                reasons.append(f"InvoiceTableParser {old_issue_count} validation issue(s)")
            if new_issue_count:
                reasons.append(f"UniversalExtractor {new_issue_count} strict validation issue(s)")
            if review_count:
                reasons.append(f"UniversalExtractor {review_count} recovered review row(s)")
            lines.append(f"- {item.get('filename')}: {', '.join(reasons)}")
    else:
        lines.append("- None.")

    lines.extend(["", "## UniversalExtractor Improvements", ""])
    if universal_improved:
        for item in universal_improved:
            new_count = int((item.get("universal_line_item_extractor") or {}).get("row_count") or 0)
            lines.append(f"- {item.get('filename')}: UniversalExtractor found {new_count} row(s).")
    else:
        lines.append("- None yet.")

    lines.extend(["", "## Both Failed", ""])
    if both_failed:
        for item in both_failed:
            reason = "; ".join(item.get("errors") or []) or "No rows extracted by either parser."
            lines.append(f"- {item.get('filename')}: {reason}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Files Tested", ""])
    for item in results:
        old_parser = item.get("invoice_table_parser") or {}
        new_parser = item.get("universal_line_item_extractor") or {}
        lines.append(
            f"- {item.get('filename')}: {item.get('detected_supplier')} | "
            f"InvoiceTableParser {old_parser.get('row_count', 0)} rows / {len(old_parser.get('validation_failures') or [])} issue(s) | "
            f"UniversalExtractor {new_parser.get('rows_accepted', new_parser.get('row_count', 0))} validated, "
            f"{new_parser.get('rows_recovered_needs_review', 0)} review, "
            f"{new_parser.get('rows_discarded', 0)} discarded / {len(new_parser.get('validation_failures') or [])} strict issue(s)"
        )

    (RESULT_DIR / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def invoice_files():
    TEST_INVOICE_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(
        path for path in TEST_INVOICE_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def main():
    files = invoice_files()
    results = []

    for invoice_path in files:
        print(f"Testing {invoice_path.name}...")
        result = run_one_with_timeout(invoice_path)
        result_filename(invoice_path).write_text(json.dumps(result, indent=2), encoding="utf-8")
        results.append(result)

    write_summary(results)
    print(f"Tested {len(results)} file(s).")
    print(f"Results: {RESULT_DIR}")
    print(f"Summary: {RESULT_DIR / 'summary.md'}")


if __name__ == "__main__":
    main()
