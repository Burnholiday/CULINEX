import atexit
try:
    import cgi
except ImportError:
    import sys
    import types
    cgi_mock = types.ModuleType("cgi")
    def parse_header(line):
        parts = [p.strip() for p in line.split(';')]
        key = parts[0].lower()
        pdict = {}
        for p in parts[1:]:
            if '=' in p:
                k, v = p.split('=', 1)
                pdict[k.strip().lower()] = v.strip('"\'')
        return key, pdict
    class FieldStorage:
        def __init__(self, fp, headers, environ=None):
            self.fields = {}
            content_length = int(headers.get('content-length', 0) or 0)
            body = fp.read(content_length)
            import email.parser
            header_bytes = b"".join(f"{k}: {v}\r\n".encode('utf-8') for k, v in headers.items())
            full_bytes = header_bytes + b"\r\n" + body
            parsed_msg = email.parser.BytesParser().parsebytes(full_bytes)
            if parsed_msg.is_multipart():
                for part in parsed_msg.get_payload():
                    cdisp = part.get('content-disposition', '')
                    if not cdisp:
                        continue
                    params = {}
                    for p in cdisp.split(';'):
                        if '=' in p:
                            k, v = p.split('=', 1)
                            params[k.strip().lower()] = v.strip('"\' ')
                    name = params.get('name')
                    if not name:
                        continue
                    filename = params.get('filename')
                    if filename is not None:
                        class FileUpload:
                            def __init__(self, fname, content):
                                self.filename = fname
                                import io
                                self.file = io.BytesIO(content)
                        self.fields[name] = FileUpload(filename, part.get_payload(decode=True))
                    else:
                        self.fields[name] = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        def __contains__(self, key):
            return key in self.fields
        def __getitem__(self, key):
            return self.fields[key]
        def getfirst(self, key, default=None):
            val = self.fields.get(key, default)
            if val is None:
                return default
            if hasattr(val, 'filename'):
                return val
            return str(val)
    cgi_mock.parse_header = parse_header
    cgi_mock.FieldStorage = FieldStorage
    sys.modules["cgi"] = cgi_mock
    cgi = cgi_mock
import csv
import http.server
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import webbrowser
import zipfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent
OCR_ROOT_CANDIDATES = [
    ROOT / "recipe-vault-paddle-ocr",
    ROOT / "legacy" / "recipe-vault-paddle-ocr",
]
OCR_ROOT = next((path for path in OCR_ROOT_CANDIDATES if path.exists()), OCR_ROOT_CANDIDATES[0])
PYTHON = OCR_ROOT / ".venv" / "Scripts" / "python.exe"
APP_FILE = ROOT / "restaurant-costing-app.html"
PID_FILE = ROOT / ".recipe-vault-local.json"
LAUNCHER_LOG = ROOT / "recipe-vault-launcher.log"
OCR_PORT = 8765
APP_PORT_START = 8766
APP_PORT_END = 8785
UPLOAD_ROOT = ROOT / "data" / "uploads"
EXTRACT_ROOT = ROOT / "data" / "extracted"
CORRECTION_LOG = ROOT / "data" / "corrections" / "review-corrections.jsonl"
EXTRACTION_ENGINE_LOG = ROOT / "data" / "logs" / "extraction-engine.log"
ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".csv", ".txt"}
AI_PROVIDER = os.environ.get("RECIPE_VAULT_AI_PROVIDER", "ollama").strip().lower() or "ollama"
OLLAMA_MODEL = os.environ.get("RECIPE_VAULT_OLLAMA_MODEL", "qwen3:latest")
OLLAMA_URL = os.environ.get("RECIPE_VAULT_OLLAMA_URL", "http://localhost:11434/api/generate")
OPENAI_MODEL = os.environ.get("RECIPE_VAULT_OPENAI_MODEL", "gpt-4.1-mini")


def port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.35)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def wait_for_port(port, timeout=25):
    started = time.time()
    while time.time() - started < timeout:
        if port_open(port):
            return True
        time.sleep(0.35)
    return False


def first_free_port(start_port):
    for port in range(start_port, start_port + 20):
        if not port_open(port):
            return port
    raise RuntimeError("No local app port is available.")


def listener_pids(port):
    if os.name != "nt":
        return []
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return []
    pids = []
    marker = f":{port}"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid = parts[4]
        if local_address.endswith(marker) and state == "LISTENING" and pid.isdigit():
            pids.append(int(pid))
    return sorted(set(pids))


def stop_pid(pid):
    if not pid:
        return
    if os.name == "nt":
        subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.kill(int(pid), 15)
        except OSError:
            pass


def safe_id(value):
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or ""))[:80]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def extract_dir(file_id):
    safe_file_id = safe_id(file_id)
    folder = EXTRACT_ROOT / safe_file_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def append_extraction_log(file_id, message):
    folder = extract_dir(file_id)
    with (folder / "extraction.log").open("a", encoding="utf-8") as handle:
        handle.write(f"{now_iso()} {message}\n")


def append_engine_log(entry):
    EXTRACTION_ENGINE_LOG.parent.mkdir(parents=True, exist_ok=True)
    safe_entry = {
        "timestamp": now_iso(),
        **(entry or {}),
    }
    with EXTRACTION_ENGINE_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_entry, ensure_ascii=True, default=str) + "\n")


def extracted_content_object(file_id, path, file_type, status, text="", tables=None, errors=None, engine="", fallback_used=False, invoice_rows=None, invoice_metadata=None, line_item_extraction=None, extraction_engine=None):
    return {
        "file_id": safe_id(file_id),
        "filename": Path(path).name if path else "",
        "file_type": file_type,
        "extraction_status": status,
        "extracted_text": text or "",
        "extracted_tables": tables or [],
        "invoice_table_rows": invoice_rows or [],
        "invoice_metadata": invoice_metadata or {},
        "line_item_extraction": line_item_extraction or {},
        "extraction_engine": extraction_engine or {},
        "errors": errors or [],
        "created_at": now_iso(),
        "engine": engine,
        "fallback_used": bool(fallback_used),
    }


def save_extracted_content(content):
    folder = extract_dir(content.get("file_id"))
    (folder / "extracted_content.json").write_text(json.dumps(content, indent=2), encoding="utf-8")
    (folder / "extracted_text.txt").write_text(content.get("extracted_text", ""), encoding="utf-8")
    (folder / "tables.json").write_text(json.dumps(content.get("extracted_tables", []), indent=2), encoding="utf-8")
    (folder / "invoice_table_rows.json").write_text(json.dumps(content.get("invoice_table_rows", []), indent=2), encoding="utf-8")
    (folder / "line_item_extraction.json").write_text(json.dumps(content.get("line_item_extraction", {}), indent=2), encoding="utf-8")


def append_correction_log(entry):
    CORRECTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    safe_entry = {
        "created_at": now_iso(),
        "app": "CULINEX",
        **(entry or {}),
    }
    with CORRECTION_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe_entry, ensure_ascii=True) + "\n")


def friendly_extraction_error(exc):
    if isinstance(exc, FileNotFoundError):
        return "The uploaded file could not be found."
    if isinstance(exc, zipfile.BadZipFile):
        return "This Excel file looks corrupt or unreadable."
    return f"{type(exc).__name__}: {exc}"


def detect_file_type(path):
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "PDF"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "IMAGE"
    if suffix == ".xlsx":
        return "XLSX"
    if suffix == ".csv":
        return "CSV"
    if suffix == ".txt":
        return "TXT"
    return "Unsupported"


def extract_content(path, file_id="manual"):
    path = Path(path)
    file_id = safe_id(file_id or path.stem)
    file_type = detect_file_type(path)
    started_at = time.time()
    if not path.exists():
        return extracted_content_object(file_id, path, file_type, "failed", errors=["The uploaded file could not be found."])
    append_extraction_log(file_id, f"extraction started filename={path.name}")
    append_extraction_log(file_id, f"extractor selected type={file_type}")
    if file_type == "Unsupported":
        content = extracted_content_object(
            file_id,
            path,
            file_type,
            "failed",
            errors=[f"Unsupported file type: {path.suffix or 'unknown'}"],
        )
        save_extracted_content(content)
        append_extraction_log(file_id, "extraction failed unsupported_file_type")
        return content
    try:
        fallback_used = False
        if file_type == "PDF":
            text = extract_pdf_text(path)
            tables = extract_pdf_tables(path)
            engine = "pdfplumber"
            if not text.strip() and not tables:
                fallback = extract_with_paddleocr(path)
                text = fallback.get("text", "")
                tables = fallback.get("tables", [])
                engine = fallback.get("engine", "PaddleOCR")
                fallback_used = True
        elif file_type == "IMAGE":
            result = extract_image_with_paddleocr(path)
            text = result.get("text", "")
            tables = result.get("tables", [])
            engine = result.get("engine", "PaddleOCR")
        elif file_type == "XLSX":
            result = extract_excel(path)
            text = result.get("text", "")
            tables = result.get("tables", [])
            engine = result.get("engine", "pandas/openpyxl")
            fallback_used = result.get("fallback_used", False)
        elif file_type == "CSV":
            result = extract_csv(path)
            text = result.get("text", "")
            tables = result.get("tables", [])
            engine = result.get("engine", "csv")
        elif file_type == "TXT":
            result = extract_txt(path)
            text = result.get("text", "")
            tables = result.get("tables", [])
            engine = result.get("engine", "plain text")
        else:
            raise ValueError(f"Unsupported file type: {path.suffix}")

        doc_type, _, _ = classify_document(text, tables)
        line_item_extraction = {}
        universal_rows = []
        fallback_reason = ""
        universal_error = ""
        try:
            line_item_extraction = LineItemExtractor().extract(text, tables)
            universal_rows = [universal_row_to_invoice_row(row) for row in (line_item_extraction.get("extracted_rows") or [])]
            if not universal_rows:
                fallback_reason = "Universal Extractor returned zero accepted rows."
        except Exception as exc:
            line_item_extraction = {"extracted_rows": [], "discarded_rows": [], "confidence": 0, "error": friendly_extraction_error(exc)}
            universal_error = friendly_extraction_error(exc)
            fallback_reason = f"Universal Extractor failed: {universal_error}"
        append_extraction_log(
            file_id,
            "line item extractor rows="
            f"{len(line_item_extraction.get('extracted_rows', []))} "
            f"confidence={line_item_extraction.get('confidence', 0)}",
        )

        invoice_parse = InvoiceTableParser(text, tables).parse()
        legacy_rows = invoice_parse.get("rows", [])
        invoice_metadata = invoice_parse.get("metadata", {})
        if legacy_rows:
            append_extraction_log(file_id, f"invoice table parser rows={len(legacy_rows)}")
        if doc_type == "supplier_invoice" and universal_rows:
            invoice_rows = universal_rows
            engine_summary = extraction_engine_summary("universal_extractor", line_item_extraction, invoice_rows, "", invoice_parse, started_at)
        elif doc_type == "supplier_invoice":
            invoice_rows = legacy_rows
            fallback_reason = fallback_reason or "Universal Extractor did not return accepted invoice rows."
            engine_summary = extraction_engine_summary("legacy_parser_fallback", line_item_extraction, invoice_rows, fallback_reason, invoice_parse, started_at)
        else:
            invoice_rows = legacy_rows
            engine_summary = extraction_engine_summary("universal_extractor", line_item_extraction, universal_rows, "", invoice_parse, started_at)

        status = "completed"
        errors = []
        if not (text or "").strip() and not tables:
            status = "failed"
            errors.append("No readable content was found. Try a clearer scan, a different export, or paste the text manually.")
        content = extracted_content_object(
            file_id,
            path,
            file_type,
            status,
            text=text,
            tables=tables,
            invoice_rows=invoice_rows,
            invoice_metadata=invoice_metadata,
            line_item_extraction=line_item_extraction,
            extraction_engine=engine_summary,
            errors=errors,
            engine=engine,
            fallback_used=fallback_used,
        )
        save_extracted_content(content)
        append_engine_log({
            "filename": path.name,
            "detected_supplier": invoice_metadata.get("supplier"),
            "document_type": doc_type,
            "extraction_source_used": engine_summary.get("source_label"),
            "rows_found": engine_summary.get("rows_found"),
            "rows_accepted": engine_summary.get("rows_accepted"),
            "rows_discarded": engine_summary.get("rows_discarded"),
            "validation_pass_rate": engine_summary.get("validation_pass_rate"),
            "fallback_reason": engine_summary.get("fallback_reason"),
            "time_taken_ms": engine_summary.get("time_taken_ms"),
        })
        append_extraction_log(file_id, f"extraction {'completed' if status == 'completed' else 'failed empty_result'}")
        return content
    except Exception as exc:
        message = friendly_extraction_error(exc)
        content = extracted_content_object(file_id, path, file_type, "failed", errors=[message])
        save_extracted_content(content)
        append_extraction_log(file_id, f"extraction failed {message}")
        return content


def parse_money_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "--"}:
        return None
    text = re.sub(r"(?i)zar|r", "", text)
    text = text.replace(" ", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    parts = text.split(".")
    if len(parts) > 2:
        text = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(text)
    except ValueError:
        return None


def normalize_header_cell(value):
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def clean_cell(value):
    return re.sub(r"\s+", " ", str(value or "").replace("\n", " ")).strip()


def extract_purchase_unit(description):
    desc = clean_cell(description)
    if not desc:
        return None
    if re.search(r"\b(each|ea|punnet|pun|bunch|bag|box|pocket|head|tray|tub|tin|pkt|pack)\b", desc, re.I):
        return desc
    match = re.search(r"\b\d+(?:[.,]\d+)?\s*(kg|g|ml|l|lt|ltr)\b(?:\s+\w+)?", desc, re.I)
    if match:
        return desc
    if re.fullmatch(r"kg|g|ml|l|lt|ltr", desc, re.I):
        return desc.upper() if len(desc) <= 3 else desc
    return desc


def extract_line_item_unit(value):
    text = clean_cell(value)
    if not text:
        return ""
    match = re.search(r"\b(each|ea|kg|g|ml|l|lt|ltr|box|bag|punnet|pun|bunch|head|tray|tub|tin|pkt|pack)\b", text, re.I)
    if not match:
        return ""
    unit = match.group(1)
    aliases = {"ea": "Each", "lt": "L", "ltr": "L", "l": "L", "pun": "Punnet", "pkt": "Packet"}
    return aliases.get(unit.lower(), unit.upper() if unit.lower() in {"kg", "g", "ml"} else unit.title())


def clean_invoice_ingredient_name(supplier_code, description=""):
    code = clean_cell(supplier_code)
    desc = clean_cell(description)
    text = re.sub(r"^\s*(who|stk|stock|item)\s*[-:]\s*", "", code, flags=re.I).strip()
    text = text or desc
    text = re.sub(r"\bkg\b|\beach\b|\bea\b|\bpunnet\b|\bpun\b|\bbag\b|\bbox\b|\bpocket\b|\blarge\b|\bmedium\b|\bsmall\b|\bheads?\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -")
    if not text and desc:
        text = desc
    return text.title() if text else None


def validate_invoice_math(quantity, unit_price, line_total):
    if quantity is None:
        return {"status": "missing", "message": "Missing quantity", "affected_field": "quantity"}
    if unit_price is None:
        return {"status": "missing", "message": "Missing unit price", "affected_field": "unit_price"}
    if line_total is None:
        return {"status": "missing", "message": "Missing line total", "affected_field": "line_total"}
    expected = round(quantity * unit_price, 2)
    difference = round(line_total - expected, 2)
    tolerance = max(0.05, abs(line_total) * 0.02)
    if abs(difference) <= tolerance:
        return {"status": "ok", "expected_total": expected, "actual_total": line_total, "difference": difference, "affected_field": ""}
    return {
        "status": "failed",
        "message": f"Expected {expected:.2f}, got {line_total:.2f}",
        "expected_total": expected,
        "actual_total": line_total,
        "difference": difference,
        "affected_field": "line_total",
    }


def validation_pass_rate(rows):
    rows = rows or []
    if not rows:
        return 0.0
    passed = sum(1 for row in rows if (row.get("validation") or {}).get("status") == "ok")
    return round(passed / len(rows), 4)


def universal_row_to_invoice_row(row):
    description = clean_cell(row.get("description") or row.get("raw_text") or "")
    supplier_code = clean_cell(row.get("supplier_code") or "")
    raw_text = clean_cell(row.get("raw_text") or description)
    quantity_raw = row.get("quantity")
    unit_price_raw = row.get("unit_price")
    line_total_raw = row.get("line_total", row.get("total"))
    quantity = parse_money_number(quantity_raw)
    unit_price = parse_money_number(unit_price_raw)
    line_total = parse_money_number(line_total_raw)
    validation = row.get("validation") or validate_invoice_math(quantity, unit_price, line_total)
    ingredient = clean_invoice_ingredient_name(supplier_code or description, description)
    purchase_unit = clean_cell(row.get("purchase_unit") or row.get("unit") or extract_purchase_unit(description) or extract_line_item_unit(raw_text) or "")
    return {
        "supplier_code": supplier_code or None,
        "ingredient": ingredient,
        "description": description or None,
        "quantity": quantity if quantity is not None else quantity_raw,
        "purchase_unit": purchase_unit or None,
        "unit": purchase_unit or None,
        "unit_price": unit_price if unit_price is not None else unit_price_raw,
        "vat": parse_money_number(row.get("vat")) if parse_money_number(row.get("vat")) is not None else row.get("vat"),
        "line_total": line_total if line_total is not None else line_total_raw,
        "validation": validation,
        "confidence": row.get("confidence", 0),
        "field_confidence": {
            "ingredient": row.get("confidence", 0.7),
            "quantity": 0.98 if quantity is not None else 0.35,
            "unit": 0.85 if purchase_unit else 0.45,
            "unit_price": 0.98 if unit_price is not None else 0.35,
            "line_total": 0.98 if line_total is not None else 0.35,
        },
        "parser_debug": {
            "source": row.get("source") or "universal_extractor",
            "role": row.get("role"),
            "raw_text": raw_text,
        },
    }


def extraction_engine_summary(source, line_item_extraction=None, rows=None, fallback_reason="", legacy_parse=None, started_at=None):
    line_item_extraction = line_item_extraction or {}
    rows = rows or []
    discarded = line_item_extraction.get("discarded_rows") or []
    rows_found = len(rows) + len(discarded)
    if line_item_extraction:
        rows_found = len(line_item_extraction.get("extracted_rows") or []) + len(discarded)
    if source == "legacy_parser_fallback":
        rows_found = max(rows_found, len(rows))
    return {
        "source": source,
        "source_label": "Universal Extractor" if source == "universal_extractor" else "Legacy Parser Fallback",
        "rows_found": rows_found,
        "rows_accepted": len(rows),
        "rows_discarded": len(discarded),
        "validation_pass_rate": validation_pass_rate(rows),
        "overall_confidence": line_item_extraction.get("confidence", 0) if source == "universal_extractor" else (0.65 if rows else 0),
        "fallback_reason": fallback_reason or "",
        "time_taken_ms": int((time.time() - started_at) * 1000) if started_at else None,
        "legacy_row_count": len((legacy_parse or {}).get("rows") or []),
    }


def is_numeric_cell(value):
    return parse_money_number(value) is not None and re.fullmatch(r"\s*(?:R|ZAR)?\s*-?\d[\d\s,]*(?:\.\d+)?\s*", str(value or ""), re.I)


def invoice_stop_line(value):
    return bool(re.search(r"number of items|extra charges|subtotal|discount|rounding|currency|banking details|created:", clean_cell(value), re.I))


def line_item_stop_line(value):
    return bool(re.search(
        r"subtotal|sub\s*total|total\s+(?:nett|net|incl|excl|due)|amount\s+excl|vat\s*$|tax\s*$|discount|rounding|"
        r"banking details|terms|conditions|signature|signed|received in good order|cash collected|created:|currency|"
        r"page\s+\d+\s+of\s+\d+|number of items|extra charges|please note",
        clean_cell(value),
        re.I,
    ))


def line_item_header_key(value):
    header = normalize_header_cell(value)
    if not header:
        return None
    if header in {"description", "product", "item", "details", "productdescription"} or "description" in header:
        return "description"
    if header in {"qty", "quantity", "shipquantity", "shipqty", "orderedqty", "orderqty"} or "quantity" in header:
        return "quantity"
    if header in {"unit", "uom", "pack", "purchaseunit"}:
        return "unit"
    if header in {"price", "unitprice", "unitcost"} or ("unit" in header and "price" in header):
        return "unit_price"
    if (
        header in {"amount", "total", "linetotal", "netamount", "nettamount", "netvalue", "nettvalue", "nettprice", "netprice", "nett", "net"}
        or "linetotal" in header
        or "netamount" in header
        or "nettamount" in header
        or "netvalue" in header
        or "nettvalue" in header
        or "nettprice" in header
        or "netprice" in header
        or ("nett" in header and "price" in header)
        or ("net" in header and "price" in header)
        or ("amount" in header and ("excl" in header or "incl" in header))
        or ("excl" in header and "vat" in header and "amount" in header)
    ):
        return "total"
    if header in {"vat", "tax", "vatamt", "vatamnt", "vatamount"} or header.startswith("vat"):
        return "vat"
    if header in {"code", "itemcode", "stockcode", "productcode", "sku"} or ("code" in header and len(header) <= 16):
        return "code"
    return None


class ColumnDetector:
    REQUIRED_ANY = {"description", "quantity", "unit_price", "total"}

    def detect(self, rows):
        best = None
        for index, row in enumerate(rows or []):
            columns = {}
            detected_headers = []
            for cell_index, cell in enumerate(row or []):
                key = line_item_header_key(cell)
                if key and key not in columns:
                    columns[key] = cell_index
                    detected_headers.append({"header": clean_cell(cell), "field": key, "index": cell_index})
            score = len(set(columns) & self.REQUIRED_ANY) + (1 if "vat" in columns else 0) + (1 if "code" in columns else 0)
            if score >= 3 and (best is None or score > best["score"]):
                best = {
                    "header_index": index,
                    "columns": columns,
                    "detected_headers": detected_headers,
                    "score": score,
                }
        return best or {"header_index": None, "columns": {}, "detected_headers": [], "score": 0}


class TableDetector:
    def __init__(self):
        self.column_detector = ColumnDetector()

    def detect_tables(self, extracted_text="", tables=None):
        detected = []
        discarded = []
        for table_index, table in enumerate(tables or [], 1):
            if table.get("type") == "ocr_items":
                text_rows = self.ocr_items_to_text_rows(table.get("items") or [])
                if text_rows:
                    detected.append({
                        "source": "ocr_items",
                        "page": table.get("page"),
                        "table": table_index,
                        "rows": text_rows,
                        "items": table.get("items") or [],
                    })
                continue
            rows = [[clean_cell(cell) for cell in row] for row in (table.get("rows") or []) if any(clean_cell(cell) for cell in row)]
            if rows:
                detected.append({
                    "source": "structured_table",
                    "page": table.get("page"),
                    "table": table.get("table") or table_index,
                    "sheet": table.get("sheet"),
                    "rows": rows,
                })
        text_rows = self.text_to_rows(extracted_text)
        if text_rows and not detected:
            detected.append({"source": "extracted_text", "page": None, "table": None, "rows": text_rows})
        return detected, discarded

    def text_to_rows(self, extracted_text):
        rows = []
        for line in (extracted_text or "").splitlines():
            value = clean_cell(line)
            if value:
                rows.append([value])
        return rows

    def ocr_items_to_text_rows(self, items):
        clean_items = [item for item in items if isinstance(item, dict) and clean_cell(item.get("text"))]
        if not clean_items:
            return []
        heights = [float(item.get("h", 0) or 0) for item in clean_items if float(item.get("h", 0) or 0) > 0]
        tolerance = max(12.0, (sorted(heights)[len(heights) // 2] if heights else 16.0) * 0.75)
        clusters = []
        for item in sorted(clean_items, key=lambda value: float(value.get("y", 0) or 0) + float(value.get("h", 0) or 0) / 2):
            y = float(item.get("y", 0) or 0) + float(item.get("h", 0) or 0) / 2
            if not clusters or abs(y - clusters[-1]["y"]) > tolerance:
                clusters.append({"y": y, "items": [item]})
            else:
                clusters[-1]["items"].append(item)
                clusters[-1]["y"] = sum(float(member.get("y", 0) or 0) + float(member.get("h", 0) or 0) / 2 for member in clusters[-1]["items"]) / len(clusters[-1]["items"])
        rows = []
        for cluster in clusters:
            values = [clean_cell(item.get("text")) for item in sorted(cluster["items"], key=lambda value: float(value.get("x", 0) or 0))]
            if values:
                rows.append(values)
        return rows


class LineItemExtractor:
    def __init__(self):
        self.table_detector = TableDetector()
        self.column_detector = ColumnDetector()

    def extract(self, extracted_text="", tables=None):
        detected_tables, discarded_rows = self.table_detector.detect_tables(extracted_text, tables)
        extracted_rows = []
        detected_headers = []
        detected_columns = []
        for table_index, table in enumerate(detected_tables, 1):
            if table.get("source") == "ocr_items" and table.get("items"):
                parsed, discarded, positioned_debug = self.extract_from_positioned_items(table)
                extracted_rows.extend(parsed)
                discarded_rows.extend(discarded)
                if positioned_debug.get("detected_headers"):
                    detected_headers.append(positioned_debug["detected_headers"])
                if positioned_debug.get("detected_columns"):
                    detected_columns.append(positioned_debug["detected_columns"])
                continue
            rows = table.get("rows") or []
            detection = self.column_detector.detect(rows)
            if detection.get("header_index") is None:
                parsed, discarded = self.extract_from_plain_rows(rows, table)
                extracted_rows.extend(parsed)
                discarded_rows.extend(discarded)
                continue
            detected_headers.append({
                "source": table.get("source"),
                "page": table.get("page"),
                "table": table.get("table") or table_index,
                "headers": detection.get("detected_headers", []),
            })
            detected_columns.append({
                "source": table.get("source"),
                "page": table.get("page"),
                "table": table.get("table") or table_index,
                "columns": detection.get("columns", {}),
                "header_index": detection.get("header_index"),
            })
            parsed, discarded = self.extract_from_column_rows(rows, detection, table)
            extracted_rows.extend(parsed)
            discarded_rows.extend(discarded)
        confidence = round(sum(row.get("confidence", 0) for row in extracted_rows) / len(extracted_rows), 2) if extracted_rows else 0.0
        validated_rows = [row for row in extracted_rows if row.get("review_status") == "validated" or (row.get("validation") or {}).get("status") == "ok"]
        recovered_needs_review = [row for row in extracted_rows if row.get("review_status") == "recovered_needs_review"]
        rejected_rows = [row for row in discarded_rows if row.get("status") == "rejected" or row.get("reason")]
        return {
            "detected_headers": detected_headers,
            "detected_columns": detected_columns,
            "extracted_rows": extracted_rows,
            "validated_rows": validated_rows,
            "recovered_needs_review": recovered_needs_review,
            "rejected_rows": rejected_rows[:250],
            "discarded_rows": discarded_rows[:250],
            "confidence": confidence,
        }

    def item_text(self, item):
        return clean_cell(item.get("text") if isinstance(item, dict) else "")

    def item_x(self, item):
        return float(item.get("x", 0) or 0) + (float(item.get("w", 0) or 0) / 2)

    def item_y(self, item):
        return float(item.get("y", 0) or 0) + (float(item.get("h", 0) or 0) / 2)

    def detect_positioned_headers(self, items):
        header_candidates = []
        for item in items:
            key = line_item_header_key(self.item_text(item))
            if key:
                header_candidates.append({"item": item, "key": key, "x": self.item_x(item), "y": self.item_y(item)})
        if not header_candidates:
            return {}, {}, []

        header_candidates.sort(key=lambda value: value["y"])
        heights = [float(candidate["item"].get("h", 0) or 0) for candidate in header_candidates if float(candidate["item"].get("h", 0) or 0) > 0]
        tolerance = max(18.0, (sorted(heights)[len(heights) // 2] if heights else 18.0) * 1.2)
        clusters = []
        for candidate in header_candidates:
            if not clusters or abs(candidate["y"] - clusters[-1]["y"]) > tolerance:
                clusters.append({"y": candidate["y"], "candidates": [candidate]})
            else:
                clusters[-1]["candidates"].append(candidate)
                clusters[-1]["y"] = sum(member["y"] for member in clusters[-1]["candidates"]) / len(clusters[-1]["candidates"])

        best = None
        for cluster in clusters:
            fields = {candidate["key"] for candidate in cluster["candidates"]}
            required_score = len(fields & {"description", "quantity", "unit_price", "total"})
            if "description" not in fields or "quantity" not in fields or required_score < 3:
                continue
            score = required_score + (1 if "code" in fields else 0) + (1 if "vat" in fields else 0)
            # Prefer the first strong header row. Later "Total" labels in footer boxes can otherwise
            # overwrite the real line-total column.
            rank = (score, -cluster["y"])
            if best is None or rank > best["rank"]:
                best = {"rank": rank, "cluster": cluster}
        if not best:
            return {}, {}, []

        headers = {}
        header_items = {}
        detected_headers = []
        for candidate in sorted(best["cluster"]["candidates"], key=lambda value: value["x"]):
            key = candidate["key"]
            if key in headers:
                continue
            headers[key] = candidate["x"]
            header_items[key] = candidate["item"]
            detected_headers.append({"header": self.item_text(candidate["item"]), "field": key, "x": round(candidate["x"], 2)})
        if not {"description", "quantity"}.issubset(headers) or not ({"unit_price", "total"} <= set(headers)):
            return {}, {}, []
        return headers, header_items, detected_headers

    def cluster_positioned_rows(self, items):
        numeric_items = [item for item in items if is_numeric_cell(self.item_text(item))]
        if not numeric_items:
            return []
        heights = [float(item.get("h", 0) or 0) for item in numeric_items if float(item.get("h", 0) or 0) > 0]
        tolerance = max(12.0, (sorted(heights)[len(heights) // 2] if heights else 16.0) * 0.75)
        clusters = []
        for item in sorted(numeric_items, key=self.item_y):
            y = self.item_y(item)
            if not clusters or abs(y - clusters[-1]["y"]) > tolerance:
                clusters.append({"y": y, "items": [item]})
            else:
                clusters[-1]["items"].append(item)
                clusters[-1]["y"] = sum(self.item_y(member) for member in clusters[-1]["items"]) / len(clusters[-1]["items"])
        return clusters

    def cluster_physical_lines(self, items):
        clean_items = [item for item in items if isinstance(item, dict) and self.item_text(item)]
        heights = [float(item.get("h", 0) or 0) for item in clean_items if float(item.get("h", 0) or 0) > 0]
        median_height = sorted(heights)[len(heights) // 2] if heights else 16.0
        line_tolerance = max(8.0, median_height * 0.35)
        lines = []
        for item in sorted(clean_items, key=self.item_y):
            y = self.item_y(item)
            matched = False
            for line in lines:
                if abs(y - line["y"]) <= line_tolerance:
                    line["items"].append(item)
                    line["y"] = sum(self.item_y(member) for member in line["items"]) / len(line["items"])
                    matched = True
                    break
            if not matched:
                lines.append({"y": y, "items": [item]})
        for line in lines:
            line["items"].sort(key=self.item_x)
        return lines

    def cluster_numeric_columns(self, numeric_items):
        if not numeric_items:
            return []
        widths = [float(item.get("w", 0) or 0) for item in numeric_items if float(item.get("w", 0) or 0) > 0]
        median_width = sorted(widths)[len(widths) // 2] if widths else 20.0
        tolerance = max(18.0, median_width * 0.85)
        clusters = []
        for item in sorted(numeric_items, key=self.item_x):
            x = self.item_x(item)
            if not clusters or abs(x - clusters[-1]["x"]) > tolerance:
                clusters.append({"x": x, "items": [item]})
            else:
                clusters[-1]["items"].append(item)
                clusters[-1]["x"] = sum(self.item_x(member) for member in clusters[-1]["items"]) / len(clusters[-1]["items"])
        return clusters

    def infer_positioned_headers(self, items):
        clean_items = [item for item in items if isinstance(item, dict) and self.item_text(item)]
        numeric_items = [item for item in clean_items if is_numeric_cell(self.item_text(item))]
        numeric_columns = self.cluster_numeric_columns(numeric_items)
        if len(numeric_columns) < 3:
            return {}, {}, []

        evidence_rows = []
        for line in self.cluster_physical_lines(clean_items):
            raw_text = " ".join(self.item_text(item) for item in line["items"])
            if self.row_role(raw_text) != "line_item":
                continue
            text_items = [item for item in line["items"] if not is_numeric_cell(self.item_text(item))]
            numeric_cells = [
                {
                    "text": self.item_text(item),
                    "value": parse_money_number(self.item_text(item)),
                    "x": self.item_x(item),
                    "column": None,
                }
                for item in line["items"]
                if is_numeric_cell(self.item_text(item))
            ]
            if len(numeric_cells) < 3 or not any(re.search(r"[A-Za-z]{3,}", self.item_text(item)) for item in text_items):
                continue
            roles = self.choose_numeric_role_cells(numeric_cells)
            if roles:
                evidence_rows.append({"line": line, "text_items": text_items, "roles": roles})

        required_evidence = 1 if len(evidence_rows) <= 2 else 2
        if len(evidence_rows) < required_evidence:
            return {}, {}, []

        def median(values):
            ordered = sorted(values)
            return ordered[len(ordered) // 2] if ordered else None

        quantity_x = median([row["roles"]["quantity"]["x"] for row in evidence_rows])
        unit_price_x = median([row["roles"]["unit_price"]["x"] for row in evidence_rows])
        total_x = median([row["roles"]["total"]["x"] for row in evidence_rows])
        description_x_values = []
        for row in evidence_rows:
            first_number_x = min(cell["x"] for cell in row["roles"].values())
            left_text = [self.item_x(item) for item in row["text_items"] if self.item_x(item) < first_number_x]
            if left_text:
                description_x_values.append(min(left_text))
        description_x = median(description_x_values) or min(self.item_x(item) for item in clean_items)
        if not (description_x < quantity_x < unit_price_x < total_x):
            return {}, {}, []

        headers = {
            "description": description_x,
            "quantity": quantity_x,
            "unit_price": unit_price_x,
            "total": total_x,
        }
        header_items = {
            key: min(clean_items, key=lambda item, target=x: abs(self.item_x(item) - target))
            for key, x in headers.items()
        }
        detected_headers = [
            {"header": "inferred description zone", "field": "description", "x": round(description_x, 2)},
            {"header": "inferred quantity zone", "field": "quantity", "x": round(quantity_x, 2)},
            {"header": "inferred unit price zone", "field": "unit_price", "x": round(unit_price_x, 2)},
            {"header": "inferred total zone", "field": "total", "x": round(total_x, 2)},
        ]
        return headers, header_items, detected_headers

    def nearest_header(self, item, headers, allowed=None):
        allowed = allowed or headers.keys()
        candidates = [(key, abs(self.item_x(item) - headers[key])) for key in allowed if key in headers]
        return sorted(candidates, key=lambda pair: pair[1])[0][0] if candidates else None

    def is_percentage_cell(self, text):
        return bool(re.search(r"%\s*$", clean_cell(text)))

    def is_pack_size_cell(self, text):
        value = clean_cell(text)
        return bool(re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:g|kg|ml|l|lt|ltr|x|pack|packs?|punnet|punnets?)s?", value, re.I))

    def is_obvious_item_code_cell(self, cell):
        text = clean_cell(cell.get("text", ""))
        value = cell.get("value")
        if value is None:
            return False
        if cell.get("nearest_column") == "code":
            return True
        if cell.get("x") is not None and cell.get("quantity_x") is not None and cell["x"] < (cell["quantity_x"] - 40):
            return True
        if re.fullmatch(r"\d{5,}", text) and value >= 1000:
            return True
        return False

    def is_numeric_noise_for_role(self, cell, role):
        text = clean_cell(cell.get("text", ""))
        if role in {"unit_price", "total"} and (self.is_percentage_cell(text) or self.is_pack_size_cell(text)):
            return True
        if role == "quantity" and self.is_obvious_item_code_cell(cell):
            return True
        if role in {"unit_price", "total"} and self.is_obvious_item_code_cell(cell):
            return True
        return False

    def same_vertical_band(self, cells):
        y_values = [cell.get("y") for cell in cells if cell.get("y") is not None]
        if len(y_values) < 2:
            return True
        heights = [float(cell.get("h", 0) or 0) for cell in cells if float(cell.get("h", 0) or 0) > 0]
        tolerance = max(12.0, (sorted(heights)[len(heights) // 2] if heights else 16.0) * 0.85)
        return max(y_values) - min(y_values) <= tolerance

    def classify_review_reason(self, row):
        validation = row.get("validation") or {}
        affected = validation.get("affected_field") or ""
        status = validation.get("status") or ""
        raw_text = clean_cell(row.get("raw_text") or "")
        numeric_texts = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?%?", raw_text)

        if status == "missing" or affected in {"quantity", "unit_price", "line_total"}:
            return "missing_same_band_total"

        quantity = parse_money_number(row.get("quantity"))
        unit_price = parse_money_number(row.get("unit_price"))
        total = parse_money_number(row.get("total"))
        vat = parse_money_number(row.get("vat"))

        if quantity is not None and unit_price is not None and total is not None:
            expected = round(quantity * unit_price, 2)
            if vat is not None:
                gross_total = round(expected + vat, 2)
                tolerance = max(0.05, abs(total) * 0.02)
                if abs(total - gross_total) <= tolerance:
                    return "gross_total_includes_vat"

            if unit_price:
                implied_quantity = round(total / unit_price, 2)
                if (
                    implied_quantity > 0
                    and abs(implied_quantity - quantity) > 0.05
                    and abs(round(implied_quantity) - implied_quantity) <= 0.05
                    and abs(implied_quantity) <= max(abs(quantity), 1)
                ):
                    return "ambiguous_quantity_ocr"

        if len(numeric_texts) >= 6:
            return "merged_row_candidate"

        return "neighboring_total_mismatch"

    def mark_row_status(self, row):
        validation = row.get("validation") or {}
        if validation.get("status") == "ok":
            row["extraction_status"] = "validated"
            row["review_status"] = "validated"
            return
        row["extraction_status"] = "recovered_needs_review"
        row["review_status"] = "recovered_needs_review"
        row["review_reason"] = self.classify_review_reason(row)
        row["confidence"] = min(row.get("confidence", 0), 0.62)

    def is_items_complete(self, items, headers):
        desc_parts = []
        limit_x = min(headers.get("quantity", 10**9), headers.get("unit_price", 10**9))
        numeric_values = []
        for item in items:
            text = clean_cell(item.get("text") if isinstance(item, dict) else "")
            if not text:
                continue
            x = float(item.get("x", 0) or 0) + (float(item.get("w", 0) or 0) / 2)
            is_desc = (x <= limit_x or 
                       self.nearest_header(item, headers, {"description", "code"}) in {"description", "code"})
            if is_desc and not is_numeric_cell(text):
                desc_parts.append(text)
            elif is_numeric_cell(text):
                val = parse_money_number(text)
                if val is not None:
                    numeric_values.append(val)
        if not desc_parts:
            return False
        for q in numeric_values:
            if q <= 0:
                continue
            for p in numeric_values:
                if p <= 0:
                    continue
                for t in numeric_values:
                    if t <= 0:
                        continue
                    val_res = validate_invoice_math(q, p, t)
                    if val_res.get("status") == "ok":
                        return True
        return False

    def reconstruct_ocr_rows(self, data_items, headers):
        heights = [float(item.get("h", 0) or 0) for item in data_items if float(item.get("h", 0) or 0) > 0]
        median_height = sorted(heights)[len(heights) // 2] if heights else 16.0
        physical_lines = self.cluster_physical_lines(data_items)
            
        limit_x = min(headers.get("quantity", 10**9), headers.get("unit_price", 10**9))
        
        def has_desc(line_items):
            for item in line_items:
                text = clean_cell(item.get("text", ""))
                if not text:
                    continue
                x = float(item.get("x", 0) or 0) + float(item.get("w", 0) or 0) / 2
                is_desc_col = (x <= limit_x or 
                               self.nearest_header(item, headers, {"description", "code"}) in {"description", "code"})
                if is_desc_col and re.search(r'[A-Za-z]{3,}', text):
                    return True
            return False
            
        def has_nums(line_items):
            return any(is_numeric_cell(clean_cell(item.get("text", ""))) for item in line_items)
            
        for line in physical_lines:
            line["has_desc"] = has_desc(line["items"])
            line["has_nums"] = has_nums(line["items"])
            line["raw_text"] = " ".join(clean_cell(item.get("text", "")) for item in line["items"])
            
        logical_rows = []
        max_merge_gap = max(45.0, median_height * 1.1)
        
        for line in physical_lines:
            if not logical_rows:
                logical_rows.append({
                    "y": line["y"],
                    "items": list(line["items"]),
                    "has_desc": line["has_desc"],
                    "has_nums": line["has_nums"],
                })
                continue
                
            last_row = logical_rows[-1]
            gap = line["y"] - last_row["y"]
            
            is_complete = self.is_items_complete(last_row["items"], headers)
            
            should_merge = False
            if gap <= max_merge_gap:
                if not last_row["has_desc"]:
                    should_merge = True
                elif not last_row["has_nums"] and line["has_nums"]:
                    should_merge = True
                elif not line["has_nums"]:
                    should_merge = True
                elif not is_complete and gap <= (median_height * 0.75):
                    should_merge = True
                    
            if should_merge:
                last_row["items"].extend(line["items"])
                last_row["items"].sort(key=lambda it: (float(it.get("y", 0) or 0), float(it.get("x", 0) or 0)))
                last_row["y"] = line["y"]
                last_row["has_desc"] = last_row["has_desc"] or line["has_desc"]
                last_row["has_nums"] = last_row["has_nums"] or line["has_nums"]
            else:
                logical_rows.append({
                    "y": line["y"],
                    "items": list(line["items"]),
                    "has_desc": line["has_desc"],
                    "has_nums": line["has_nums"],
                })
                
        return logical_rows

    def extract_from_positioned_items(self, table):
        def print_safe(msg):
            try:
                enc = sys.stdout.encoding or 'utf-8'
                sys.stdout.write(msg.encode(enc, errors='replace').decode(enc) + "\n")
                sys.stdout.flush()
            except Exception:
                pass

        items = [item for item in (table.get("items") or []) if isinstance(item, dict) and self.item_text(item)]
        headers, header_items, detected_headers = self.detect_positioned_headers(items)
        inferred_headers = False
        if not headers:
            headers, header_items, detected_headers = self.infer_positioned_headers(items)
            inferred_headers = bool(headers)
        debug = {
            "source": "ocr_items",
            "page": table.get("page"),
            "table": table.get("table"),
            "detected_headers": {"source": "ocr_items", "page": table.get("page"), "table": table.get("table"), "headers": detected_headers},
            "detected_columns": {"source": "ocr_items", "page": table.get("page"), "table": table.get("table"), "columns": headers},
        }
        if not headers:
            return [], [{"reason": "headers_not_detected", "raw_text": "OCR positioned table did not expose enough invoice headers."}], debug
        if inferred_headers:
            data_items = items
        else:
            header_bottom = max(float(item.get("y", 0) or 0) + float(item.get("h", 0) or 0) for item in header_items.values())
            data_items = [item for item in items if self.item_y(item) > header_bottom]
        
        reconstructed_groups = self.reconstruct_ocr_rows(data_items, headers)
        
        # Detailed debug logging
        print_safe(f"\n[OCR RECONSTRUCTION] Processing table {table.get('table')} on page {table.get('page')}")
        print_safe("--- Original OCR fragments ---")
        for item in items:
            print_safe(f"  - Box: text={self.item_text(item)!r} x={self.item_x(item):.1f} y={self.item_y(item):.1f} w={float(item.get('w',0)):.1f} h={float(item.get('h',0)):.1f}")
            
        print_safe("--- Reconstructed candidate rows ---")
        for i, group in enumerate(reconstructed_groups, 1):
            group_texts = [self.item_text(it) for it in sorted(group["items"], key=self.item_x)]
            print_safe(f"  - Candidate Row {i} (Y center: {group['y']:.1f}): {' '.join(group_texts)}")
            
        parsed = []
        discarded = []
        active = None
        
        for group in reconstructed_groups:
            row_items = group["items"]
            raw_text = " ".join(self.item_text(item) for item in sorted(row_items, key=self.item_x))
            role = self.row_role(raw_text)
            if role != "line_item":
                discarded.append({"reason": role, "raw_text": raw_text})
                if role in {"subtotal", "vat", "payment", "footer", "banking"}:
                    break
                continue
            text_items = [item for item in row_items if not is_numeric_cell(self.item_text(item))]
            description = self.positioned_description(text_items, headers)
            numeric_cells = []
            mapped = {}
            for item in row_items:
                text = self.item_text(item)
                if not is_numeric_cell(text):
                    continue
                value = parse_money_number(text)
                nearest_column = self.nearest_header(item, headers)
                numeric_cells.append({
                    "text": text,
                    "value": value,
                    "x": self.item_x(item),
                    "y": self.item_y(item),
                    "h": float(item.get("h", 0) or 0),
                    "column": self.nearest_header(item, headers, {"quantity", "unit_price", "vat", "total"}),
                    "nearest_column": nearest_column,
                    "quantity_x": headers.get("quantity"),
                })
                column = self.nearest_header(item, headers, {"quantity", "unit_price", "vat", "total"})
                if column and self.is_numeric_noise_for_role(numeric_cells[-1], column):
                    continue
                if column and column not in mapped:
                    mapped[column] = text
            math_roles = self.choose_numeric_roles(numeric_cells)
            if math_roles:
                mapped.update(math_roles)
            row = {
                "description": description,
                "quantity": mapped.get("quantity", ""),
                "unit": extract_line_item_unit(description),
                "unit_price": mapped.get("unit_price", ""),
                "total": mapped.get("total", ""),
                "vat": mapped.get("vat", ""),
                "raw_text": raw_text,
                "confidence": 0.0,
                "role": role,
                "source": "ocr_items",
                "page": table.get("page"),
                "table": table.get("table"),
            }
            if self.is_wrapped_normalized_row(row):
                if active:
                    active["description"] = clean_cell(f"{active['description']} {description}")
                    active["raw_text"] = clean_cell(f"{active['raw_text']} {raw_text}")
                    active["confidence"] = max(0.1, round(active["confidence"] - 0.04, 2))
                else:
                    discarded.append({"reason": "wrapped_without_previous_row", "raw_text": raw_text})
                continue
            if self.has_line_values(row):
                self.finalize_row(row, role, structured=True)
                row["confidence"] = self.score_row(row, structured=True)
                self.mark_row_status(row)
                parsed.append(row)
                active = row
            else:
                discarded.append({"reason": "not_enough_line_values", "status": "rejected", "raw_text": raw_text})
                
        print_safe("--- Final rows passed to validation ---")
        for i, row in enumerate(parsed, 1):
            print_safe(f"  - Parsed Row {i}: desc={row.get('description')!r} qty={row.get('quantity')} price={row.get('unit_price')} total={row.get('total')} vat={row.get('vat')} confidence={row.get('confidence')} status={row.get('validation', {}).get('status')}")
            
        return parsed, discarded, debug

    def positioned_description(self, items, headers):
        parts = []
        limit_x = min(headers.get("quantity", 10**9), headers.get("unit_price", 10**9))
        for item in sorted(items, key=lambda value: (self.item_x(value), self.item_y(value))):
            text = self.item_text(item)
            if self.item_x(item) <= limit_x or self.nearest_header(item, headers, {"description", "code"}) in {"description", "code"}:
                parts.append(text)
        return clean_cell(" ".join(parts))

    def extract_from_column_rows(self, rows, detection, table):
        columns = detection.get("columns") or {}
        start = int(detection.get("header_index") or 0) + 1
        parsed = []
        discarded = []
        active = None
        for raw_row in rows[start:]:
            raw_text = " ".join(clean_cell(cell) for cell in raw_row if clean_cell(cell))
            if not raw_text:
                discarded.append({"reason": "empty", "raw_text": ""})
                continue
            role = self.row_role(raw_text)
            if role != "line_item":
                discarded.append({"reason": role, "raw_text": raw_text})
                if role in {"subtotal", "vat", "payment", "footer", "banking"}:
                    break
                continue
            if line_item_stop_line(raw_text):
                discarded.append({"reason": "footer", "raw_text": raw_text})
                break
            row = self.normalize_column_row(raw_row, columns, raw_text)
            if self.is_wrapped_description(row, raw_row):
                if active:
                    active["description"] = clean_cell(f"{active['description']} {raw_text}")
                    active["raw_text"] = clean_cell(f"{active['raw_text']} {raw_text}")
                    active["confidence"] = max(0.1, round(active["confidence"] - 0.04, 2))
                else:
                    discarded.append({"reason": "wrapped_without_previous_row", "raw_text": raw_text})
                continue
            if self.has_line_values(row):
                self.finalize_row(row, role, structured=True)
                self.mark_row_status(row)
                row["source"] = table.get("source")
                row["page"] = table.get("page")
                row["table"] = table.get("table")
                parsed.append(row)
                active = row
            else:
                discarded.append({"reason": "not_enough_line_values", "raw_text": raw_text})
        return parsed, discarded

    def extract_from_plain_rows(self, rows, table):
        parsed = []
        discarded = []
        active = None
        in_table = False
        for raw_row in rows:
            raw_text = " ".join(clean_cell(cell) for cell in raw_row if clean_cell(cell))
            if not raw_text:
                discarded.append({"reason": "empty", "raw_text": ""})
                continue
            if not in_table:
                header_hits = [line_item_header_key(token) for token in re.split(r"\s{2,}|\||,", raw_text)]
                if len([hit for hit in header_hits if hit]) >= 3:
                    in_table = True
                    continue
                role = self.row_role(raw_text)
                if role in {"header"}:
                    in_table = True
                    continue
                if role != "line_item":
                    discarded.append({"reason": role if role != "noise" else "before_table", "raw_text": raw_text})
                    continue
                in_table = True
            role = self.row_role(raw_text)
            if role != "line_item":
                discarded.append({"reason": role, "raw_text": raw_text})
                if role in {"subtotal", "vat", "payment", "footer", "banking"}:
                    break
                continue
            if line_item_stop_line(raw_text):
                discarded.append({"reason": "footer", "raw_text": raw_text})
                break
            row = self.normalize_plain_row(raw_text)
            if self.is_plain_wrap(row, raw_text):
                if active:
                    active["description"] = clean_cell(f"{active['description']} {raw_text}")
                    active["raw_text"] = clean_cell(f"{active['raw_text']} {raw_text}")
                    active["confidence"] = max(0.1, round(active["confidence"] - 0.06, 2))
                else:
                    discarded.append({"reason": "plain_wrap_without_previous_row", "raw_text": raw_text})
                continue
            if self.has_line_values(row):
                self.finalize_row(row, role, structured=False)
                self.mark_row_status(row)
                row["source"] = table.get("source")
                row["page"] = table.get("page")
                row["table"] = table.get("table")
                parsed.append(row)
                active = row
            else:
                discarded.append({"reason": "not_enough_line_values", "raw_text": raw_text})
        return parsed, discarded

    def normalize_column_row(self, raw_row, columns, raw_text):
        description_parts = []
        for key in ("code", "description"):
            index = columns.get(key)
            if index is not None and index < len(raw_row):
                value = clean_cell(raw_row[index])
                if value:
                    description_parts.append(value)
        description = clean_cell(" ".join(description_parts))
        unit = self.cell_by_column(raw_row, columns, "unit")
        if not unit:
            unit = extract_line_item_unit(description)
        row = {
            "description": description,
            "quantity": self.cell_by_column(raw_row, columns, "quantity"),
            "unit": unit,
            "unit_price": self.cell_by_column(raw_row, columns, "unit_price"),
            "total": self.cell_by_column(raw_row, columns, "total"),
            "vat": self.cell_by_column(raw_row, columns, "vat"),
            "raw_text": raw_text,
            "confidence": 0.0,
        }
        numeric_cells = []
        for cell in raw_row:
            text = clean_cell(cell)
            if is_numeric_cell(text):
                numeric_cells.append({"text": text, "value": parse_money_number(text)})
        math_roles = self.choose_numeric_roles(numeric_cells)
        if math_roles:
            for key, value in math_roles.items():
                if not row.get(key):
                    row[key] = value
        row["confidence"] = self.score_row(row, structured=True)
        return row

    def normalize_plain_row(self, raw_text):
        numeric_matches = list(re.finditer(r"(?:R|ZAR)?\s*-?\d+(?:[ ,.]\d{3})*(?:[.,]\d+)?", raw_text, re.I))
        numeric_values = [clean_cell(match.group(0)) for match in numeric_matches]
        description = raw_text[:numeric_matches[0].start()].strip(" ,-") if numeric_matches else raw_text
        numeric_cells = [{"text": value, "value": parse_money_number(value)} for value in numeric_values]
        roles = self.choose_numeric_roles(numeric_cells) or {}
        quantity = roles.get("quantity", "")
        unit_price = roles.get("unit_price", "")
        total = roles.get("total", "")
        vat = roles.get("vat", "")
        unit = ""
        unit = extract_line_item_unit(raw_text)
        row = {
            "description": clean_cell(description),
            "quantity": quantity,
            "unit": unit,
            "unit_price": unit_price,
            "total": total,
            "vat": vat,
            "raw_text": raw_text,
            "confidence": 0.0,
        }
        row["confidence"] = self.score_row(row, structured=False)
        return row

    def cell_by_column(self, row, columns, key):
        index = columns.get(key)
        if index is None or index >= len(row):
            return ""
        return clean_cell(row[index])

    def has_line_values(self, row):
        return bool(row.get("description")) and bool(row.get("quantity")) and bool(row.get("unit_price")) and bool(row.get("total"))

    def is_wrapped_description(self, row, raw_row):
        numeric_count = sum(1 for cell in raw_row if is_numeric_cell(cell))
        return bool(row.get("description")) and numeric_count == 0

    def is_plain_wrap(self, row, raw_text):
        return bool(row.get("description")) and len(re.findall(r"\d", raw_text)) <= 1 and not row.get("unit_price") and not row.get("total")

    def is_wrapped_normalized_row(self, row):
        return bool(row.get("description")) and not row.get("quantity") and not row.get("unit_price") and not row.get("total")

    def row_role(self, raw_text):
        text = clean_cell(raw_text)
        lower = text.lower()
        normalized = normalize_header_cell(text)
        if not text:
            return "empty"
        header_hits = [line_item_header_key(token) for token in re.split(r"\s{2,}|\||,", text)]
        header_hits = [hit for hit in header_hits if hit]
        if len(set(header_hits)) >= 3 or ({"description", "quantity"} <= set(header_hits) and ({"unit_price", "total"} & set(header_hits))):
            return "header"
        if re.search(r"\b(bank|banking|branch|account|acc\s*no|swift|iban|payment)\b", lower):
            return "banking"
        if re.search(r"\b(cash collected|signed by|signature|customer signature|received in good order|terms|conditions|please note|claims|returned goods)\b", lower):
            return "footer"
        if re.search(r"\b(discount|rounding|currency|currencyrate|number of items|extra charges)\b", lower):
            return "payment"
        if re.search(r"\b(subtotal|sub total|total nett|total net|total incl|total excl|amount excl|amount incl|grand total|^total\b)\b", lower):
            return "subtotal"
        if re.search(r"\b(vat|tax)\b", lower) and len(re.findall(r"\d", text)) <= 8 and not re.search(r"\b(vatamt|vatamnt|vat amount)\b", lower):
            return "vat"
        if re.search(r"\b(page\s+\d+\s+of\s+\d+|invoice from|invoice to|deliver to|sold to|customer vat|telephone|email|fax|document no|invoice number|invoice date|order number|representative)\b", lower):
            return "footer"
        numeric_count = len(re.findall(r"(?:R|ZAR)?\s*-?\d+(?:[ ,.]\d{3})*(?:[.,]\d+)?", text, re.I))
        if numeric_count >= 3 and re.search(r"[A-Za-z]{2,}", text) and not re.fullmatch(r"[\d\s.,RZAR-]+", text, re.I):
            return "line_item"
        if numeric_count == 0:
            return "noise"
        if len(normalized) <= 2:
            return "noise"
        return "noise"

    def choose_numeric_role_cells(self, numeric_cells):
        values = []
        for index, cell in enumerate(numeric_cells or []):
            value = cell.get("value")
            if value is None:
                continue
            values.append({
                "index": index,
                "text": cell.get("text", ""),
                "value": value,
                "column": cell.get("column"),
                "nearest_column": cell.get("nearest_column"),
                "quantity_x": cell.get("quantity_x"),
                "x": cell.get("x"),
                "y": cell.get("y"),
                "h": cell.get("h"),
            })
        if len(values) < 3:
            return {}
        candidates = []
        for q in values:
            if q["value"] <= 0 or self.is_numeric_noise_for_role(q, "quantity"):
                continue
            for price in values:
                if price["index"] == q["index"] or price["value"] < 0 or self.is_numeric_noise_for_role(price, "unit_price"):
                    continue
                for total in values:
                    if total["index"] in {q["index"], price["index"]} or total["value"] < 0 or self.is_numeric_noise_for_role(total, "total"):
                        continue
                    if not self.same_vertical_band([q, price, total]):
                        continue
                    if q.get("x") is not None and price.get("x") is not None and q["x"] > price["x"]:
                        continue
                    if price.get("x") is not None and total.get("x") is not None and price["x"] > total["x"]:
                        continue
                    validation = validate_invoice_math(q["value"], price["value"], total["value"])
                    if validation.get("status") != "ok":
                        continue
                    order_penalty = 0
                    if q["index"] > price["index"]:
                        order_penalty += 2
                    if price["index"] > total["index"]:
                        order_penalty += 2
                    if q.get("x") is not None and price.get("x") is not None and q["x"] > price["x"]:
                        order_penalty += 2
                    if price.get("x") is not None and total.get("x") is not None and price["x"] > total["x"]:
                        order_penalty += 2
                    column_bonus = 0
                    if q.get("column") == "quantity":
                        column_bonus -= 2
                    if price.get("column") == "unit_price":
                        column_bonus -= 2
                    if total.get("column") == "total":
                        column_bonus -= 2
                    wrong_column_penalty = 0
                    if q.get("column") in {"unit_price", "vat", "total"}:
                        wrong_column_penalty += 3
                    if price.get("column") in {"quantity", "vat", "total"}:
                        wrong_column_penalty += 3
                    if total.get("column") in {"quantity", "unit_price", "vat"}:
                        wrong_column_penalty += 3
                    candidates.append({
                        "quantity": q,
                        "unit_price": price,
                        "total": total,
                        "score": abs(validation.get("difference", 0)) + order_penalty + column_bonus + wrong_column_penalty,
                    })
        if not candidates:
            return {}
        best = sorted(candidates, key=lambda item: item["score"])[0]
        used = {best["quantity"]["index"], best["unit_price"]["index"], best["total"]["index"]}
        vat = None
        for item in values:
            if item["index"] not in used and (item.get("column") == "vat" or item["value"] >= 0):
                vat = item
                break
        result = {
            "quantity": best["quantity"],
            "unit_price": best["unit_price"],
            "total": best["total"],
        }
        if vat:
            result["vat"] = vat
        return result

    def choose_numeric_roles(self, numeric_cells):
        role_cells = self.choose_numeric_role_cells(numeric_cells)
        if not role_cells:
            return {}
        result = {
            "quantity": role_cells["quantity"]["text"],
            "unit_price": role_cells["unit_price"]["text"],
            "total": role_cells["total"]["text"],
        }
        if role_cells.get("vat"):
            result["vat"] = role_cells["vat"]["text"]
        return result

    def finalize_row(self, row, role, structured=False):
        row["role"] = role
        quantity = parse_money_number(row.get("quantity"))
        unit_price = parse_money_number(row.get("unit_price"))
        total = parse_money_number(row.get("total"))
        row["validation"] = validate_invoice_math(quantity, unit_price, total)
        row["confidence"] = self.score_row(row, structured=structured)

    def score_row(self, row, structured=False):
        score = 0.2
        if structured:
            score += 0.25
        if row.get("description"):
            score += 0.2
        if row.get("quantity"):
            score += 0.15
        if row.get("unit_price"):
            score += 0.15
        if row.get("total"):
            score += 0.15
        if row.get("unit"):
            score += 0.05
        return round(min(1.0, score), 2)


class InvoiceTableParser:
    def __init__(self, extracted_text="", tables=None):
        self.extracted_text = extracted_text or ""
        self.tables = tables or []

    def parse(self):
        rows = []
        for table in self.tables:
            if table.get("type") == "ocr_items" and isinstance(table.get("items"), list):
                rows.extend(self.parse_positioned_items(table.get("items") or []))
                continue
            table_rows = table.get("rows") or []
            header_index, column_map = self.detect_columns(table_rows)
            if header_index is None:
                continue
            for raw_row in table_rows[header_index + 1:]:
                parsed = self.parse_row(raw_row, column_map)
                if parsed:
                    parsed["page"] = table.get("page")
                    parsed["table"] = table.get("table")
                    parsed["sheet"] = table.get("sheet")
                    rows.append(parsed)
        if not rows:
            rows.extend(self.parse_text_rows())
        return {
            "rows": self.dedupe_rows(rows),
            "metadata": self.extract_metadata(),
        }

    def item_text(self, item):
        return clean_cell(item.get("text") if isinstance(item, dict) else "")

    def item_x(self, item):
        return float(item.get("x", 0) or 0) + (float(item.get("w", 0) or 0) / 2)

    def item_y(self, item):
        return float(item.get("y", 0) or 0) + (float(item.get("h", 0) or 0) / 2)

    def detect_positioned_headers(self, items):
        headers = {}
        header_items = {}
        for item in items:
            text = self.item_text(item)
            header = normalize_header_cell(text)
            if not header:
                continue
            key = None
            if header in {"itemcode", "stockcode", "code"} or ("item" in header and "code" in header):
                key = "supplier_code"
            elif "description" in header:
                key = "description"
            elif "quantity" in header or header in {"qty", "shipquantity", "shipqty"}:
                key = "quantity"
            elif "unitprice" in header or "unitcost" in header or header == "unitprice":
                key = "unit_price"
            elif "vatamnt" in header or header == "vat" or (header.startswith("vat") and "registration" not in header):
                key = "vat"
            elif "linetotal" in header or "netvalue" in header or "netamount" in header:
                key = "line_total"
            if key:
                headers[key] = self.item_x(item)
                header_items[key] = item
        required = {"quantity", "unit_price", "line_total"}
        if not required.issubset(headers):
            return {}, {}
        return headers, header_items

    def nearest_column(self, item, headers, allowed=None):
        allowed = allowed or headers.keys()
        x = self.item_x(item)
        candidates = [(key, abs(x - headers[key])) for key in allowed if key in headers]
        if not candidates:
            return None
        return sorted(candidates, key=lambda pair: pair[1])[0][0]

    def cluster_y_rows(self, items):
        numeric_items = [item for item in items if is_numeric_cell(self.item_text(item))]
        if not numeric_items:
            return []
        heights = [float(item.get("h", 0) or 0) for item in numeric_items if float(item.get("h", 0) or 0) > 0]
        tolerance = max(12.0, (sorted(heights)[len(heights) // 2] if heights else 16.0) * 0.75)
        clusters = []
        for item in sorted(numeric_items, key=self.item_y):
            y = self.item_y(item)
            if not clusters or abs(y - clusters[-1]["y"]) > tolerance:
                clusters.append({"y": y, "items": [item]})
            else:
                clusters[-1]["items"].append(item)
                clusters[-1]["y"] = sum(self.item_y(member) for member in clusters[-1]["items"]) / len(clusters[-1]["items"])
        return clusters

    def parse_positioned_items(self, items):
        clean_items = [item for item in items if isinstance(item, dict) and self.item_text(item)]
        headers, header_items = self.detect_positioned_headers(clean_items)
        if not headers:
            return []
        header_bottom = max(
            float(item.get("y", 0) or 0) + float(item.get("h", 0) or 0)
            for item in header_items.values()
        )
        data_items = []
        for item in clean_items:
            text = self.item_text(item)
            if self.item_y(item) <= header_bottom:
                continue
            if invoice_stop_line(text):
                continue
            data_items.append(item)
        row_clusters = self.cluster_y_rows(data_items)
        parsed = []
        for cluster in row_clusters:
            row = self.parse_positioned_row(cluster, data_items, headers)
            if row:
                parsed.append(row)
        return parsed

    def parse_positioned_row(self, cluster, all_items, headers):
        row_y = cluster["y"]
        all_row_ys = sorted({round(self.item_y(item), 1) for item in all_items if is_numeric_cell(self.item_text(item))})
        gaps = [abs(value - row_y) for value in all_row_ys if abs(value - row_y) > 0]
        y_window = max(18.0, min(gaps) * 0.48 if gaps else 22.0)
        row_items = [item for item in all_items if abs(self.item_y(item) - row_y) <= y_window]
        numeric_columns = {"quantity", "unit_price", "vat", "line_total"}
        mapped_cells = {}
        raw_numeric = {}
        for item in row_items:
            text = self.item_text(item)
            if not is_numeric_cell(text):
                continue
            column = self.nearest_column(item, headers, numeric_columns)
            if not column:
                continue
            distance = abs(self.item_x(item) - headers[column])
            existing = mapped_cells.get(column)
            if existing is None or distance < existing["distance"]:
                mapped_cells[column] = {
                    "value": parse_money_number(text),
                    "text": text,
                    "distance": distance,
                    "x": self.item_x(item),
                    "y": self.item_y(item),
                }
                raw_numeric[column] = text
        quantity = mapped_cells.get("quantity", {}).get("value")
        unit_price = mapped_cells.get("unit_price", {}).get("value")
        line_total = mapped_cells.get("line_total", {}).get("value")
        vat = mapped_cells.get("vat", {}).get("value")
        if quantity is None and unit_price is None and line_total is None:
            return None
        text_tokens = [item for item in row_items if not is_numeric_cell(self.item_text(item))]
        supplier_code, description = self.positioned_code_and_description(text_tokens, headers)
        if not supplier_code and not description:
            return None
        if re.search(r"subtotal|discount|rounding|total|currency|number of items", f"{supplier_code} {description}", re.I):
            return None
        ingredient = clean_invoice_ingredient_name(supplier_code, description)
        purchase_unit = extract_purchase_unit(description)
        validation = validate_invoice_math(quantity, unit_price, line_total)
        debug = {
            "source": "ocr_positioned",
            "header_x": headers,
            "raw_row": [self.item_text(item) for item in sorted(row_items, key=lambda item: (self.item_x(item), self.item_y(item)))],
            "raw_numeric_cells": raw_numeric,
            "mapped_quantity": quantity,
            "mapped_unit_price": unit_price,
            "mapped_vat": vat,
            "mapped_line_total": line_total,
            "row_y": row_y,
            "validation": validation,
        }
        if validation.get("status") == "failed":
            debug["warning"] = "Validation failed. Numeric values were assigned by nearest header x-position and were not corrected."
            print("InvoiceTableParser validation failed " + json.dumps(debug, default=str), file=sys.stderr)
        return {
            "supplier_code": supplier_code or None,
            "ingredient": ingredient,
            "description": description or None,
            "quantity": quantity,
            "purchase_unit": purchase_unit,
            "unit": purchase_unit,
            "unit_price": unit_price,
            "line_total": line_total,
            "vat": vat,
            "validation": validation,
            "parser_debug": debug,
            "field_confidence": {
                "ingredient": 0.82 if ingredient else 0.35,
                "quantity": 0.98 if quantity is not None else 0.35,
                "unit": 0.9 if purchase_unit else 0.45,
                "unit_price": 0.98 if unit_price is not None else 0.35,
                "line_total": 0.98 if line_total is not None else 0.35,
            },
        }

    def positioned_code_and_description(self, items, headers):
        code_parts = []
        description_parts = []
        for item in sorted(items, key=lambda item: (self.item_x(item), self.item_y(item))):
            text = self.item_text(item)
            column = self.nearest_column(item, headers, {"supplier_code", "description"})
            if column == "supplier_code" or self.looks_like_supplier_code(text):
                code_parts.append(text)
            elif column == "description":
                description_parts.append(text)
        if not code_parts and description_parts:
            for index, text in enumerate(list(description_parts)):
                if self.looks_like_supplier_code(text):
                    code_parts.append(text)
                    description_parts.pop(index)
                    break
        return clean_cell(" ".join(code_parts)), clean_cell(" ".join(description_parts))

    def detect_columns(self, rows):
        for index, row in enumerate(rows):
            normalized = [normalize_header_cell(cell) for cell in row]
            column_map = {}
            for cell_index, header in enumerate(normalized):
                if not header:
                    continue
                if header in {"itemcode", "stockcode", "code"} or ("item" in header and "code" in header):
                    column_map["supplier_code"] = cell_index
                elif "description" in header or header in {"item", "product", "details"}:
                    column_map["description"] = cell_index
                elif "quantity" in header or header in {"qty", "shipquantity", "shipqty"}:
                    column_map["quantity"] = cell_index
                elif "unitprice" in header or "unitcost" in header or header in {"price", "unit"}:
                    column_map["unit_price"] = cell_index
                elif "vat" in header:
                    column_map["vat"] = cell_index
                elif "linetotal" in header or "netvalue" in header or "netamount" in header or header in {"total", "nettprice"}:
                    column_map["line_total"] = cell_index
            if {"supplier_code", "description", "quantity", "unit_price", "line_total"}.issubset(column_map):
                return index, column_map
        return None, {}

    def cell(self, row, column_map, key):
        index = column_map.get(key)
        if index is None or index >= len(row):
            return ""
        return clean_cell(row[index])

    def parse_row(self, row, column_map):
        supplier_code = self.cell(row, column_map, "supplier_code")
        description = self.cell(row, column_map, "description")
        quantity_cell = self.cell(row, column_map, "quantity")
        unit_price_cell = self.cell(row, column_map, "unit_price")
        line_total_cell = self.cell(row, column_map, "line_total")
        vat_cell = self.cell(row, column_map, "vat")
        quantity = parse_money_number(quantity_cell)
        unit_price = parse_money_number(unit_price_cell)
        line_total = parse_money_number(line_total_cell)
        vat = parse_money_number(vat_cell)
        if not supplier_code and not description:
            return None
        if quantity is None and unit_price is None and line_total is None:
            return None
        if re.search(r"subtotal|discount|rounding|total|currency|number of items", f"{supplier_code} {description}", re.I):
            return None
        ingredient = clean_invoice_ingredient_name(supplier_code, description)
        purchase_unit = extract_purchase_unit(description)
        validation = validate_invoice_math(quantity, unit_price, line_total)
        return {
            "supplier_code": supplier_code or None,
            "ingredient": ingredient,
            "description": description or None,
            "quantity": quantity,
            "purchase_unit": purchase_unit,
            "unit": purchase_unit,
            "unit_price": unit_price,
            "line_total": line_total,
            "vat": vat,
            "validation": validation,
            "parser_debug": {
                "source": "table",
                "raw_row": [clean_cell(cell) for cell in row],
                "column_map": column_map,
                "mapped_quantity": quantity,
                "mapped_unit_price": unit_price,
                "mapped_line_total": line_total,
                "raw_quantity_cell": quantity_cell,
                "raw_unit_price_cell": unit_price_cell,
                "raw_line_total_cell": line_total_cell,
                "raw_vat_cell": vat_cell,
                "validation": validation,
            },
            "field_confidence": {
                "ingredient": 0.82 if ingredient else 0.35,
                "quantity": 0.98 if quantity is not None else 0.35,
                "unit": 0.9 if purchase_unit else 0.45,
                "unit_price": 0.98 if unit_price is not None else 0.35,
                "line_total": 0.98 if line_total is not None else 0.35,
            },
        }

    def parse_text_rows(self):
        lines = [clean_cell(line) for line in self.extracted_text.splitlines()]
        lines = [line for line in lines if line]
        start = self.text_table_start(lines)
        if start is None:
            return []
        data_lines = []
        for line in lines[start:]:
            if invoice_stop_line(line):
                break
            data_lines.append(line)
        groups = self.group_text_invoice_rows(data_lines)
        parsed = []
        for group in groups:
            row = self.parse_text_group(group)
            if row:
                parsed.append(row)
        return parsed

    def text_table_start(self, lines):
        header_hits = {"item": None, "description": None, "quantity": None, "unit_price": None, "line_total": None}
        for index, line in enumerate(lines):
            header = normalize_header_cell(line)
            if header in {"itemcode", "stockcode", "code"} or ("item" in header and "code" in header):
                header_hits["item"] = index
            elif "description" in header:
                header_hits["description"] = index
            elif "quantity" in header or header in {"qty", "shipquantity", "shipqty"}:
                header_hits["quantity"] = index
            elif "unitprice" in header or "unitcost" in header:
                header_hits["unit_price"] = index
            elif "linetotal" in header or "netvalue" in header or "netamount" in header:
                header_hits["line_total"] = index
            if all(value is not None for value in header_hits.values()):
                return index + 1
        return None

    def group_text_invoice_rows(self, lines):
        groups = []
        current = []
        seen_code = False
        for line in lines:
            starts_new_numeric_row = bool(current and seen_code and is_numeric_cell(line))
            if starts_new_numeric_row:
                groups.append(current)
                current = [line]
                seen_code = False
                continue
            current.append(line)
            if self.looks_like_supplier_code(line):
                seen_code = True
        if current:
            groups.append(current)
        return groups

    def looks_like_supplier_code(self, line):
        text = clean_cell(line)
        return bool(re.search(r"\b(?:who|stk|stock|item)\s*-", text, re.I) or re.fullmatch(r"[A-Z0-9]{3,}[-A-Z0-9 ]*", text))

    def parse_text_group(self, group):
        raw = [clean_cell(item) for item in group if clean_cell(item)]
        if len(raw) < 4:
            return None
        numeric_items = [(index, parse_money_number(value), value) for index, value in enumerate(raw) if is_numeric_cell(value)]
        numeric_values = [value for _, value, _ in numeric_items if value is not None]
        text_items = [(index, value) for index, value in enumerate(raw) if not is_numeric_cell(value)]
        if len(numeric_values) < 3 or not text_items:
            return None
        mapped = self.choose_numeric_mapping(numeric_items)
        if not mapped:
            return None
        supplier_code, description = self.text_code_and_description(text_items)
        if not supplier_code and not description:
            return None
        if re.search(r"subtotal|discount|rounding|total|currency|number of items", f"{supplier_code} {description}", re.I):
            return None
        quantity = mapped["quantity"]
        unit_price = mapped["unit_price"]
        line_total = mapped["line_total"]
        vat = mapped.get("vat")
        ingredient = clean_invoice_ingredient_name(supplier_code, description)
        purchase_unit = extract_purchase_unit(description)
        validation = validate_invoice_math(quantity, unit_price, line_total)
        return {
            "supplier_code": supplier_code or None,
            "ingredient": ingredient,
            "description": description or None,
            "quantity": quantity,
            "purchase_unit": purchase_unit,
            "unit": purchase_unit,
            "unit_price": unit_price,
            "line_total": line_total,
            "vat": vat,
            "validation": validation,
            "parser_debug": {
                "source": "ocr_text",
                "raw_row": raw,
                "mapped_quantity": quantity,
                "mapped_unit_price": unit_price,
                "mapped_line_total": line_total,
                "mapped_vat": vat,
                "validation": validation,
            },
            "field_confidence": {
                "ingredient": 0.78 if ingredient else 0.35,
                "quantity": 0.9 if quantity is not None else 0.35,
                "unit": 0.85 if purchase_unit else 0.45,
                "unit_price": 0.9 if unit_price is not None else 0.35,
                "line_total": 0.9 if line_total is not None else 0.35,
            },
        }

    def choose_numeric_mapping(self, numeric_items):
        candidates = []
        for quantity_index, quantity, _ in numeric_items:
            for unit_index, unit_price, _ in numeric_items:
                if unit_index == quantity_index:
                    continue
                for total_index, line_total, _ in numeric_items:
                    if total_index in {quantity_index, unit_index}:
                        continue
                    if quantity is None or unit_price is None or line_total is None:
                        continue
                    validation = validate_invoice_math(quantity, unit_price, line_total)
                    difference = abs(validation.get("difference", line_total - (quantity * unit_price)))
                    status_bonus = 0 if validation.get("status") == "ok" else 1000
                    zero_penalty = 100 if quantity == 0 or unit_price == 0 or line_total == 0 else 0
                    order_penalty = 0
                    if total_index < unit_index:
                        order_penalty += 0.5
                    if quantity_index < unit_index and quantity > unit_price:
                        order_penalty += 0.25
                    candidates.append({
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "line_total": line_total,
                        "quantity_index": quantity_index,
                        "unit_index": unit_index,
                        "total_index": total_index,
                        "score": status_bonus + difference + zero_penalty + order_penalty,
                        "validation": validation,
                    })
        if not candidates:
            return None
        best = sorted(candidates, key=lambda item: item["score"])[0]
        used = {best["quantity_index"], best["unit_index"], best["total_index"]}
        vat_candidates = [value for index, value, _ in numeric_items if index not in used]
        best["vat"] = vat_candidates[0] if vat_candidates else None
        return best

    def text_code_and_description(self, text_items):
        values = [value for _, value in text_items]
        code_index = None
        for index, value in enumerate(values):
            if self.looks_like_supplier_code(value):
                code_index = index
                break
        if code_index is None:
            return None, " ".join(values).strip()
        code_parts = [values[code_index]]
        description_parts = []
        before = values[:code_index]
        after = values[code_index + 1:]
        if before:
            description_parts.extend(before)
            code_parts.extend(after)
        else:
            description_parts.extend(after)
        return clean_cell(" ".join(code_parts)), clean_cell(" ".join(description_parts))

    def dedupe_rows(self, rows):
        seen = set()
        deduped = []
        for row in rows:
            key = (row.get("supplier_code"), row.get("description"), row.get("quantity"), row.get("unit_price"), row.get("line_total"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return deduped

    def extract_metadata(self):
        text = self.extracted_text
        metadata = {
            "supplier": None,
            "invoice_number": None,
            "invoice_date": None,
            "customer": None,
            "total": None,
            "currency": "ZAR" if re.search(r"\bzar\b|r\d", text, re.I) else None,
        }
        supplier_patterns = [
            r"Invoice From\s+([^\n]+)",
            r"^([A-Z][A-Za-z0-9 &().'-]{2,60})\s+(?:Tax Invoice|TAX INVOICE)",
            r"Farm Fresh Direct",
            r"Morningside Eggs",
            r"Grocery Express",
            r"SO-CA Foods",
            r"Robberg",
        ]
        for pattern in supplier_patterns:
            match = re.search(pattern, text, re.I | re.M)
            if match:
                metadata["supplier"] = clean_cell(match.group(1) if match.groups() else match.group(0))
                break
        number_match = re.search(r"(?:invoice\s*(?:number|no\.?)|document\s*no\.?|no)\s*[:#]?\s*([A-Z0-9-]{4,})", text, re.I)
        if number_match:
            metadata["invoice_number"] = clean_cell(number_match.group(1))
        date_match = re.search(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b", text)
        if date_match:
            metadata["invoice_date"] = date_match.group(1)
        customer_match = re.search(r"(?:Invoice To|Sold To|Customer)\s+([^\n]+)", text, re.I)
        if customer_match:
            metadata["customer"] = clean_cell(customer_match.group(1))
        totals = [parse_money_number(match.group(1)) for match in re.finditer(r"(?:total|nett price)\s*[: ]+\s*(?:R|ZAR)?\s*([0-9][0-9 ,.]*)", text, re.I)]
        totals = [value for value in totals if value is not None]
        if totals:
            metadata["total"] = max(totals)
        return metadata


def extract_pdf_text(path):
    import pdfplumber

    page_text = []
    with pdfplumber.open(path) as pdf:
        for index, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            if text.strip():
                page_text.append(f"--- Page {index} ---\n{text.strip()}")
    return "\n\n".join(page_text)


def extract_pdf_tables(path):
    import pdfplumber

    tables = []
    with pdfplumber.open(path) as pdf:
        for page_index, page in enumerate(pdf.pages, 1):
            for table_index, table in enumerate(page.extract_tables() or [], 1):
                rows = [[cell if cell is not None else "" for cell in row] for row in table if row]
                if rows:
                    tables.append({"page": page_index, "table": table_index, "rows": rows})
    return tables


def extract_image_with_paddleocr(path):
    result = extract_with_paddleocr(path)
    return {
        "file_type": "IMAGE",
        "text": result.get("text", ""),
        "tables": result.get("tables", []),
        "engine": result.get("engine", "PaddleOCR"),
        "fallback_used": False,
    }


def extract_txt(path):
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return {"file_type": "TXT", "text": text, "tables": [], "engine": "plain text", "fallback_used": False}


def extract_with_paddleocr(path):
    if not port_open(OCR_PORT):
        start_ocr_helper()
    boundary = f"----RecipeVault{int(time.time() * 1000)}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{boundary}--\r\n".encode("utf-8")
    body = header + path.read_bytes() + footer
    request = urllib.request.Request(
        f"http://127.0.0.1:{OCR_PORT}/extract",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    tables = []
    if isinstance(payload.get("ocr_items"), list) and payload.get("ocr_items"):
        tables.append({"type": "ocr_items", "items": payload.get("ocr_items")})
    return {"text": payload.get("text", ""), "tables": tables, "engine": payload.get("engine", "PaddleOCR")}


def extract_csv(path):
    rows = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(handle, dialect)
        rows = [[cell for cell in row] for row in reader]
    text = "\n".join([", ".join(row) for row in rows])
    return {"file_type": "CSV", "text": text, "tables": [{"page": 1, "table": 1, "rows": rows}] if rows else [], "engine": "csv", "fallback_used": False}


def extract_excel(path):
    try:
        import pandas as pd

        sheets = pd.read_excel(path, sheet_name=None, header=None)
        tables = []
        text_parts = []
        for sheet_index, (sheet_name, frame) in enumerate(sheets.items(), 1):
            rows = frame.fillna("").astype(str).values.tolist()
            rows = trim_empty_rows(rows)
            if not rows:
                continue
            tables.append({"page": sheet_index, "table": 1, "sheet": sheet_name, "rows": rows})
            text_parts.append(f"--- {sheet_name} ---\n" + "\n".join([" | ".join(row) for row in rows]))
        return {"file_type": "XLSX", "text": "\n\n".join(text_parts), "tables": tables, "engine": "pandas/openpyxl", "fallback_used": False}
    except Exception as exc:
        tables = extract_xlsx_with_stdlib(path)
        text = "\n\n".join([f"--- {table.get('sheet', 'Sheet')} ---\n" + "\n".join([" | ".join(row) for row in table["rows"]]) for table in tables])
        return {
            "file_type": "XLSX",
            "text": text,
            "tables": tables,
            "engine": f"stdlib xlsx fallback after pandas/openpyxl error: {type(exc).__name__}",
            "fallback_used": True,
        }


def trim_empty_rows(rows):
    cleaned = []
    for row in rows:
        values = [str(cell).strip() for cell in row]
        if any(values):
            cleaned.append(values)
    return cleaned


def extract_xlsx_with_stdlib(path):
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("main:si", ns):
                text = "".join(node.text or "" for node in item.findall(".//main:t", ns))
                shared_strings.append(text)
        sheet_names = workbook_sheet_names(archive)
        tables = []
        for name in sorted(n for n in archive.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")):
            sheet_number = int("".join(ch for ch in Path(name).stem if ch.isdigit()) or "1")
            sheet_name = sheet_names.get(sheet_number, f"Sheet{sheet_number}")
            root = ET.fromstring(archive.read(name))
            rows = []
            for row in root.findall(".//main:row", ns):
                cells = []
                for cell in row.findall("main:c", ns):
                    cell_type = cell.attrib.get("t", "")
                    value_node = cell.find("main:v", ns)
                    inline_node = cell.find(".//main:t", ns)
                    value = value_node.text if value_node is not None else (inline_node.text if inline_node is not None else "")
                    if cell_type == "s" and value.isdigit():
                        value = shared_strings[int(value)] if int(value) < len(shared_strings) else value
                    cells.append(value or "")
                if any(str(cell).strip() for cell in cells):
                    rows.append(cells)
            if rows:
                tables.append({"page": sheet_number, "table": 1, "sheet": sheet_name, "rows": rows})
    return tables


def workbook_sheet_names(archive):
    names = {}
    try:
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        root = ET.fromstring(archive.read("xl/workbook.xml"))
        for index, sheet in enumerate(root.findall(".//main:sheet", ns), 1):
            sheet_id = int(sheet.attrib.get("sheetId", index))
            names[sheet_id] = sheet.attrib.get("name", f"Sheet{sheet_id}")
    except Exception:
        pass
    return names


def openai_api_key():
    key = os.environ.get("OPENAI_API_KEY") or os.environ.get("RECIPE_VAULT_OPENAI_API_KEY")
    if key:
        return key.strip()
    config_path = ROOT / "openai-config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            return str(config.get("api_key") or config.get("OPENAI_API_KEY") or "").strip()
        except Exception:
            return ""
    return ""


DOCUMENT_TYPE_LABELS = {
    "supplier_invoice": "Supplier Invoice",
    "recipe": "Recipe",
    "stock_list": "Stock List",
    "prep_sheet": "Prep Sheet",
    "menu_costing_sheet": "Menu Costing Sheet",
}


def compact_tables_for_prompt(tables, limit_tables=6, limit_rows=24):
    compact = []
    for table in (tables or [])[:limit_tables]:
        rows = []
        for row in (table.get("rows") or [])[:limit_rows]:
            rows.append([str(cell or "").strip() for cell in row])
        if rows:
            compact.append({
                "page": table.get("page"),
                "table": table.get("table"),
                "sheet": table.get("sheet"),
                "rows": rows,
            })
    return compact


def table_text(tables):
    parts = []
    for table in compact_tables_for_prompt(tables, limit_tables=8, limit_rows=40):
        label = table.get("sheet") or f"Page {table.get('page') or 1} Table {table.get('table') or 1}"
        parts.append(f"--- {label} ---")
        parts.extend([" | ".join(row) for row in table.get("rows", [])])
    return "\n".join(parts)


def classify_document(extracted_text="", tables=None):
    combined = f"{table_text(tables)}\n{extracted_text or ''}".lower()
    score = {
        "supplier_invoice": 0,
        "recipe": 0,
        "stock_list": 0,
        "prep_sheet": 0,
        "menu_costing_sheet": 0,
    }
    invoice_terms = ["tax invoice", "invoice number", "invoice date", "unitprice", "unit price", "line total", "vatamt", "net amount", "subtotal", "supplier", "invoice from"]
    recipe_terms = ["costing sheet", "ingredients", "quantity item", "item cost", "menu price", "california", "recipe"]
    stock_terms = ["stock sheet", "par level", "total stock", "last invoice", "supplier", "unit price"]
    prep_terms = ["yield in gram", "yield in kg", "portion volume", "cost per portion", "bulk prep", "prep item", "sauce", "batter"]
    menu_terms = ["menu costing", "menu price", "food cost", "cost percentage", "gross profit", "selling price"]
    for term in invoice_terms:
        score["supplier_invoice"] += 1 if term in combined else 0
    for term in recipe_terms:
        score["recipe"] += 1 if term in combined else 0
    for term in stock_terms:
        score["stock_list"] += 1 if term in combined else 0
    for term in prep_terms:
        score["prep_sheet"] += 1 if term in combined else 0
    for term in menu_terms:
        score["menu_costing_sheet"] += 1 if term in combined else 0
    if tables:
        score["supplier_invoice"] += 1
        score["stock_list"] += 1
    priority = {
        "supplier_invoice": 5,
        "menu_costing_sheet": 4,
        "prep_sheet": 3,
        "stock_list": 2,
        "recipe": 1,
    }
    doc_type = max(score, key=lambda key: (score[key], priority[key]))
    if score[doc_type] <= 0:
        doc_type = "recipe"
    confidence = min(0.95, max(0.35, score[doc_type] / max(4, sum(1 for value in score.values() if value))))
    return doc_type, round(confidence, 2), score


def extraction_schema(document_type):
    common = {
        "document_type": {"type": "string"},
        "confidence": {"type": ["number", "null"]},
        "notes": {"type": ["string", "null"]},
    }
    ingredient_item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ingredient": {"type": ["string", "null"]},
            "quantity": {"type": ["number", "null"]},
            "unit": {"type": ["string", "null"]},
            "item_cost": {"type": ["string", "null"]},
            "supplier": {"type": ["string", "null"]},
            "unit_price": {"type": ["number", "null"]},
            "line_total": {"type": ["number", "null"]},
            "field_confidence": {"type": ["object", "null"]},
        },
        "required": ["ingredient", "quantity", "unit", "item_cost", "supplier", "unit_price", "line_total", "field_confidence"],
    }
    schemas = {
        "supplier_invoice": {
            "supplier_name": {"type": ["string", "null"]},
            "invoice_number": {"type": ["string", "null"]},
            "invoice_date": {"type": ["string", "null"]},
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "supplier_code": {"type": ["string", "null"]},
                        "ingredient": {"type": ["string", "null"]},
                        "description": {"type": ["string", "null"]},
                        "quantity": {"type": ["number", "null"]},
                        "unit": {"type": ["string", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "line_total": {"type": ["number", "null"]},
                        "vat": {"type": ["number", "null"]},
                        "field_confidence": {"type": ["object", "null"]},
                    },
                    "required": ["supplier_code", "ingredient", "description", "quantity", "unit", "unit_price", "line_total", "vat", "field_confidence"],
                },
            },
            "total_excl_vat": {"type": ["number", "null"]},
            "vat_total": {"type": ["number", "null"]},
            "total_incl_vat": {"type": ["number", "null"]},
        },
        "recipe": {
            "recipe_name": {"type": ["string", "null"]},
            "ingredients": {"type": "array", "items": ingredient_item},
            "yield": {"type": ["string", "null"]},
            "total_cost": {"type": ["string", "null"]},
            "cost_per_portion": {"type": ["string", "null"]},
        },
        "stock_list": {
            "supplier_name": {"type": ["string", "null"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "supplier_code": {"type": ["string", "null"]},
                        "ingredient": {"type": ["string", "null"]},
                        "unit": {"type": ["string", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "category": {"type": ["string", "null"]},
                        "field_confidence": {"type": ["object", "null"]},
                    },
                    "required": ["supplier_code", "ingredient", "unit", "unit_price", "category", "field_confidence"],
                },
            },
        },
        "prep_sheet": {
            "prep_item_name": {"type": ["string", "null"]},
            "section": {"type": ["string", "null"]},
            "ingredients": {"type": "array", "items": ingredient_item},
            "yield": {"type": ["string", "null"]},
            "total_cost": {"type": ["string", "null"]},
            "cost_per_unit": {"type": ["string", "null"]},
        },
        "menu_costing_sheet": {
            "menu_item_name": {"type": ["string", "null"]},
            "category": {"type": ["string", "null"]},
            "ingredients": {"type": "array", "items": ingredient_item},
            "menu_price": {"type": ["string", "null"]},
            "total_cost": {"type": ["string", "null"]},
            "cost_percentage": {"type": ["string", "null"]},
        },
    }
    properties = {**common, **schemas.get(document_type, schemas["recipe"])}
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties.keys()),
    }


def schema_template(document_type):
    templates = {
        "supplier_invoice": {
            "document_type": "supplier_invoice",
            "confidence": None,
            "supplier_name": None,
            "invoice_number": None,
            "invoice_date": None,
            "lines": [{
                "supplier_code": None,
                "ingredient": None,
                "description": None,
                "quantity": None,
                "unit": None,
                "unit_price": None,
                "line_total": None,
                "vat": None,
                "field_confidence": {
                    "ingredient": None,
                    "quantity": None,
                    "unit": None,
                    "unit_price": None,
                    "line_total": None,
                },
            }],
            "total_excl_vat": None,
            "vat_total": None,
            "total_incl_vat": None,
            "notes": None,
        },
        "recipe": {
            "document_type": "recipe",
            "confidence": None,
            "recipe_name": None,
            "ingredients": [{"ingredient": None, "quantity": None, "unit": None, "item_cost": None, "supplier": None, "unit_price": None, "line_total": None, "field_confidence": None}],
            "yield": None,
            "total_cost": None,
            "cost_per_portion": None,
            "notes": None,
        },
        "stock_list": {
            "document_type": "stock_list",
            "confidence": None,
            "supplier_name": None,
            "items": [{"supplier_code": None, "ingredient": None, "unit": None, "unit_price": None, "category": None, "field_confidence": None}],
            "notes": None,
        },
        "prep_sheet": {
            "document_type": "prep_sheet",
            "confidence": None,
            "prep_item_name": None,
            "section": None,
            "ingredients": [{"ingredient": None, "quantity": None, "unit": None, "item_cost": None, "supplier": None, "unit_price": None, "line_total": None, "field_confidence": None}],
            "yield": None,
            "total_cost": None,
            "cost_per_unit": None,
            "notes": None,
        },
        "menu_costing_sheet": {
            "document_type": "menu_costing_sheet",
            "confidence": None,
            "menu_item_name": None,
            "category": None,
            "ingredients": [{"ingredient": None, "quantity": None, "unit": None, "item_cost": None, "supplier": None, "unit_price": None, "line_total": None, "field_confidence": None}],
            "menu_price": None,
            "total_cost": None,
            "cost_percentage": None,
            "notes": None,
        },
    }
    return templates.get(document_type, templates["recipe"])


def build_recipe_prompt(extracted_text):
    schema = {
        "recipe_name": None,
        "ingredients": [
            {
                "ingredient": None,
                "quantity": None,
                "unit": None,
                "item_cost": None,
            }
        ],
        "yield": None,
        "total_cost": None,
        "cost_per_portion": None,
        "notes": None,
        "confidence": None,
    }
    return (
        "You are AIRecipeExtractor for Recipe Vault.\n"
        "Convert raw OCR or extracted recipe text into one structured recipe JSON object.\n"
        "Return JSON only. Do not wrap it in markdown. Do not explain.\n"
        "If a field cannot be found, return null for that field instead of guessing.\n"
        "Do not normalize ingredient names. Do not match stock items. Do not calculate missing costs.\n"
        "Do not merge duplicates. Do not validate the recipe.\n"
        "Ingredient quantities must be numbers when clearly present, otherwise null.\n"
        "Keep money fields as the original value if present, for example \"R55.44\".\n"
        f"Required JSON shape:\n{json.dumps(schema, indent=2)}\n\n"
        "Raw extracted text:\n"
        f"{extracted_text[:24000]}"
    )


def build_document_prompt(document_type, extracted_text="", tables=None, classifier_confidence=None):
    label = DOCUMENT_TYPE_LABELS.get(document_type, "Recipe")
    compact_tables = compact_tables_for_prompt(tables)
    schema = extraction_schema(document_type)
    template = schema_template(document_type)
    table_instruction = (
        "Structured table rows are provided. Prefer them over plain OCR text when they contain rows or columns.\n"
        if compact_tables else
        "No structured table rows were available. Use the extracted text only.\n"
    )
    type_instructions = {
        "supplier_invoice": (
            "Extract supplier invoice data. Keep supplier prefixes such as WHO - in supplier_code. "
            "Do not include supplier prefixes in ingredient when a cleaner ingredient name is obvious. "
            "Do not calculate missing totals."
        ),
        "recipe": "Extract a recipe or costing card. Do not calculate missing costs.",
        "stock_list": "Extract stock list or supplier price list rows. Do not normalize ingredient names.",
        "prep_sheet": "Extract a prep item, sauce, batter, batch, or bulk prep sheet.",
        "menu_costing_sheet": "Extract menu costing data, menu price, total cost, and costing percentage if present.",
    }
    return (
        "You are the CULINEX Smart Extraction Engine.\n"
        f"Document type selected: {document_type} ({label}).\n"
        f"Classifier confidence: {classifier_confidence if classifier_confidence is not None else 'unknown'}.\n"
        f"{type_instructions.get(document_type, type_instructions['recipe'])}\n"
        "Return valid JSON only. Do not use markdown. Do not explain.\n"
        "If a field cannot be found, return null. Do not guess.\n"
        "Do not normalize ingredients. Do not merge duplicates. Do not validate. Do not save anything.\n"
        "For every extracted line, include field_confidence values from 0.00 to 1.00 for ingredient, quantity, unit, unit_price, and line_total when possible.\n"
        "Return the exact requested document_type and an overall confidence score from 0.00 to 1.00.\n"
        f"{table_instruction}"
        f"JSON schema:\n{json.dumps(schema, indent=2)}\n\n"
        f"Required JSON template:\n{json.dumps(template, indent=2)}\n\n"
        f"Structured table rows:\n{json.dumps(compact_tables, indent=2)[:18000]}\n\n"
        f"Extracted text:\n{(extracted_text or '')[:18000]}"
    )


def parse_ai_response(text):
    raw = (text or "").strip()
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.IGNORECASE | re.DOTALL).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end >= start:
        raw = raw[start:end + 1]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("AI response was not a JSON object.")
    if data.get("document_type") and (
        "lines" in data or "items" in data or "prep_item_name" in data or "menu_item_name" in data
    ):
        if data.get("confidence") is not None:
            try:
                data["confidence"] = max(0, min(1, float(data.get("confidence"))))
            except Exception:
                data["confidence"] = None
        return data
    ingredients = data.get("ingredients")
    if ingredients is None:
        data["ingredients"] = []
    elif not isinstance(ingredients, list):
        data["ingredients"] = []
    cleaned = {
        "recipe_name": data.get("recipe_name"),
        "ingredients": [],
        "yield": data.get("yield"),
        "total_cost": data.get("total_cost"),
        "cost_per_portion": data.get("cost_per_portion"),
        "notes": data.get("notes"),
        "confidence": data.get("confidence"),
    }
    for item in data.get("ingredients", []):
        if not isinstance(item, dict):
            continue
        cleaned["ingredients"].append({
            "ingredient": item.get("ingredient"),
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
            "item_cost": item.get("item_cost"),
            "supplier": item.get("supplier"),
            "unit_price": item.get("unit_price"),
            "line_total": item.get("line_total"),
            "field_confidence": item.get("field_confidence"),
        })
    return cleaned


def friendly_ollama_error(exc):
    if isinstance(exc, urllib.error.URLError):
        return "Ollama is not running. Start Ollama, then try Extract recipe JSON again."
    if isinstance(exc, TimeoutError):
        return "Ollama took too long to respond. Make sure the local model is loaded and try again."
    return f"{type(exc).__name__}: {exc}"


def call_ollama(prompt, model=OLLAMA_MODEL):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
        },
    }
    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        if exc.code == 404 or "not found" in body.lower() or "model" in body.lower():
            raise RuntimeError(f"Ollama model '{model}' is missing. Run: ollama pull {model}") from exc
        raise RuntimeError(f"Ollama request failed: {body or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama is not installed or not running. Start Ollama, then run: ollama pull qwen3:latest") from exc
    text = str(data.get("response") or "").strip()
    if not text:
        raise ValueError("Ollama returned an empty response.")
    return {
        "id": data.get("created_at") or "",
        "model": data.get("model") or model,
        "output_text": text,
        "provider": "ollama",
    }


def call_openai(prompt):
    key = openai_api_key()
    if not key:
        raise RuntimeError("OpenAI API key is not configured. Set OPENAI_API_KEY or add outputs/openai-config.json.")
    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": "You extract restaurant recipe data and return valid JSON only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "recipe_extraction",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "recipe_name": {"type": ["string", "null"]},
                        "ingredients": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "ingredient": {"type": ["string", "null"]},
                                    "quantity": {"type": ["number", "null"]},
                                    "unit": {"type": ["string", "null"]},
                                    "item_cost": {"type": ["string", "null"]},
                                },
                                "required": ["ingredient", "quantity", "unit", "item_cost"],
                            },
                        },
                        "yield": {"type": ["string", "null"]},
                        "total_cost": {"type": ["string", "null"]},
                        "cost_per_portion": {"type": ["string", "null"]},
                        "notes": {"type": ["string", "null"]},
                        "confidence": {"type": ["number", "null"]},
                    },
                    "required": [
                        "recipe_name",
                        "ingredients",
                        "yield",
                        "total_cost",
                        "cost_per_portion",
                        "notes",
                        "confidence",
                    ],
                },
            }
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def response_output_text(payload):
    if isinstance(payload, dict) and payload.get("output_text"):
        return str(payload.get("output_text") or "")
    parts = []
    for item in (payload or {}).get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                parts.append(str(content.get("text") or ""))
    return "\n".join(parts).strip()


def invoice_cleanup_prompt(rows):
    safe_rows = [
        {
            "row_index": index,
            "supplier_code": row.get("supplier_code"),
            "description": row.get("description"),
            "current_ingredient": row.get("ingredient"),
            "current_purchase_unit": row.get("purchase_unit"),
        }
        for index, row in enumerate(rows)
    ]
    return (
        "You are cleaning supplier invoice product names for CULINEX.\n"
        "Return JSON only with a rows array.\n"
        "You may clean ingredient names and purchase unit wording only.\n"
        "Never return or change quantity, unit_price, line_total, vat, or totals.\n"
        "Remove supplier prefixes like WHO - from ingredient names, but preserve meaning.\n"
        "Examples:\n"
        "WHO - PINEAPPLE + Each => ingredient Pineapple, purchase_unit Each\n"
        "WHO - APPLES GRANNY kg Green => ingredient Apples, purchase_unit kg\n"
        "WHO - BROCCOLI HEADS + Heads-kg => ingredient Broccoli, purchase_unit Heads-kg\n"
        "Required shape: {\"rows\":[{\"row_index\":0,\"ingredient\":\"...\",\"purchase_unit\":\"...\",\"confidence\":0.00}]}\n"
        f"Rows:\n{json.dumps(safe_rows, indent=2)}"
    )


def cleanup_invoice_rows_with_ai(rows, provider=AI_PROVIDER, model=None):
    if not rows:
        return rows, {"used": False, "error": ""}
    try:
        prompt = invoice_cleanup_prompt(rows)
        response = call_openai(prompt) if provider == "openai" else call_ollama(prompt, model or OLLAMA_MODEL)
        text = response_output_text(response)
        raw = re.sub(r"<think>.*?</think>", "", text or "", flags=re.IGNORECASE | re.DOTALL).strip()
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end >= start:
            raw = raw[start:end + 1]
        data = json.loads(raw)
        cleanup_rows = data.get("rows") if isinstance(data, dict) else []
        if not isinstance(cleanup_rows, list):
            raise ValueError("AI cleanup did not return a rows array.")
        by_index = {int(item.get("row_index")): item for item in cleanup_rows if isinstance(item, dict) and item.get("row_index") is not None}
        cleaned = []
        for index, row in enumerate(rows):
            item = by_index.get(index, {})
            next_row = dict(row)
            if item.get("ingredient"):
                next_row["ingredient"] = clean_cell(item.get("ingredient"))
            if item.get("purchase_unit"):
                next_row["purchase_unit"] = clean_cell(item.get("purchase_unit"))
                next_row["unit"] = next_row["purchase_unit"]
            confidence = parse_money_number(item.get("confidence"))
            if confidence is not None:
                confidence = max(0, min(1, confidence if confidence <= 1 else confidence / 100))
                next_row.setdefault("field_confidence", {})["ingredient"] = confidence
                next_row.setdefault("field_confidence", {})["unit"] = max(next_row.get("field_confidence", {}).get("unit", 0), confidence)
            cleaned.append(next_row)
        return cleaned, {"used": True, "error": "", "model": response.get("model") or model or OLLAMA_MODEL}
    except Exception as exc:
        return rows, {"used": False, "error": friendly_ollama_error(exc)}


def supplier_invoice_from_table_rows(rows, metadata=None, provider=AI_PROVIDER, model=None, extraction_engine=None):
    cleaned_rows, cleanup = cleanup_invoice_rows_with_ai(rows, provider=provider, model=model)
    extraction_engine = extraction_engine or {}
    source = extraction_engine.get("source") or "legacy_parser_fallback"
    source_label = extraction_engine.get("source_label") or ("Universal Extractor" if source == "universal_extractor" else "Legacy Parser Fallback")
    return {
        "recipe": {
            "document_type": "supplier_invoice",
            "confidence": extraction_engine.get("overall_confidence", 0.94 if rows else 0.5),
            "supplier_name": (metadata or {}).get("supplier"),
            "invoice_number": (metadata or {}).get("invoice_number"),
            "invoice_date": (metadata or {}).get("invoice_date"),
            "customer": (metadata or {}).get("customer"),
            "currency": (metadata or {}).get("currency"),
            "invoice_rows": cleaned_rows,
            "lines": cleaned_rows,
            "extraction_source": source,
            "extraction_source_label": source_label,
            "extraction_summary": extraction_engine,
            "total_excl_vat": None,
            "vat_total": None,
            "total_incl_vat": (metadata or {}).get("total"),
            "notes": f"{source_label} parsed invoice rows deterministically. AI used only for name cleanup." if cleanup.get("used") else f"{source_label} parsed invoice rows deterministically. AI cleanup unavailable or skipped.",
        },
        "document_type": "supplier_invoice",
        "invoice_rows": cleaned_rows,
        "confidence": extraction_engine.get("overall_confidence", 0.94 if rows else 0.5),
        "classifier_confidence": 0.94,
        "classifier_scores": {"supplier_invoice": 1},
        "extraction_source": source,
        "extraction_source_label": source_label,
        "extraction_summary": extraction_engine,
        "provider": provider,
        "model": cleanup.get("model") or model or (OLLAMA_MODEL if provider == "ollama" else OPENAI_MODEL),
        "response_id": None,
        "created_at": now_iso(),
        "table_parser": {
            "used": True,
            "row_count": len(rows),
            "source": source,
            "source_label": source_label,
            "ai_cleanup": cleanup,
        },
    }


class AIRecipeExtractor:
    def __init__(self, provider=AI_PROVIDER, model=None):
        self.provider = (provider or "ollama").strip().lower()
        if self.provider not in {"ollama", "openai"}:
            raise ValueError(f"Unsupported AI provider: {provider}")
        if model:
            self.model = model
        elif self.provider == "openai":
            self.model = OPENAI_MODEL
        else:
            self.model = OLLAMA_MODEL

    def call_model(self, prompt):
        if self.provider == "openai":
            return call_openai(prompt)
        return call_ollama(prompt, model=self.model)

    def provider_label(self):
        return self.provider

    def __repr__(self):
        return f"AIRecipeExtractor(provider={self.provider!r}, model={self.model!r})"

    def model_label(self):
        return self.model

    def extract(self, extracted_text, tables=None, requested_document_type=None):
        if not (extracted_text or "").strip() and not tables:
            raise ValueError("No extracted text was provided for recipe extraction.")
        if not (extracted_text or "").strip() and tables:
            extracted_text = table_text(tables)
        document_type, classifier_confidence, classifier_scores = classify_document(extracted_text, tables)
        if requested_document_type in DOCUMENT_TYPE_LABELS:
            document_type = requested_document_type
        prompt = build_document_prompt(document_type, extracted_text, tables, classifier_confidence)
        response = self.call_model(prompt)
        text = response_output_text(response)
        try:
            extracted = parse_ai_response(text)
        except Exception as exc:
            raise ValueError(f"AI response was not valid JSON: {exc}") from exc
        extracted["document_type"] = extracted.get("document_type") or document_type
        if extracted.get("confidence") is None:
            extracted["confidence"] = classifier_confidence
        return {
            "recipe": extracted,
            "document_type": extracted.get("document_type") or document_type,
            "confidence": extracted.get("confidence"),
            "classifier_confidence": classifier_confidence,
            "classifier_scores": classifier_scores,
            "provider": response.get("provider") or self.provider_label(),
            "model": response.get("model") or self.model_label(),
            "response_id": response.get("id"),
            "created_at": now_iso(),
        }


class OpenAIRecipeExtractor:
    def __init__(self, model=OPENAI_MODEL):
        self.model = model

    def extract(self, extracted_text):
        if not (extracted_text or "").strip():
            raise ValueError("No extracted text was provided for recipe extraction.")
        prompt = build_recipe_prompt(extracted_text)
        response = call_openai(prompt)
        text = response_output_text(response)
        recipe = parse_ai_response(text)
        return {
            "recipe": recipe,
            "model": response.get("model") or self.model,
            "response_id": response.get("id"),
            "created_at": now_iso(),
        }


def start_ocr_helper():
    if port_open(OCR_PORT):
        return None
    if not PYTHON.exists():
        raise RuntimeError(f"Python environment not found: {PYTHON}")

    log_path = ROOT / "recipe-vault-ocr.log"
    log_file = open(log_path, "a", encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [
            str(PYTHON),
            "-m",
            "uvicorn",
            "server:app",
            "--app-dir",
            str(OCR_ROOT),
            "--host",
            "127.0.0.1",
            "--port",
            str(OCR_PORT),
        ],
        cwd=str(OCR_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    if not wait_for_port(OCR_PORT, timeout=35):
        raise RuntimeError("OCR helper did not start. Check recipe-vault-ocr.log.")
    return process


def write_state(app_port, ocr_process):
    state = {
        "appPid": os.getpid(),
        "appPort": app_port,
        "ocrPid": ocr_process.pid if ocr_process else None,
        "ocrPort": OCR_PORT,
    }
    PID_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def remove_state():
    try:
        PID_FILE.unlink()
    except OSError:
        pass


def remove_stale_state():
    if not PID_FILE.exists():
        return
    try:
        state = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except Exception:
        remove_state()
        return
    app_port = int(state.get("appPort") or 0)
    if not app_port or not port_open(app_port):
        remove_state()


def stop_from_state():
    state = {}
    if not PID_FILE.exists():
        print("Recipe Vault does not look like it is running from this launcher.")
    else:
        state = json.loads(PID_FILE.read_text(encoding="utf-8"))
    for pid in [state.get("appPid"), state.get("ocrPid")]:
        stop_pid(pid)
    fallback_ports = [OCR_PORT, *range(APP_PORT_START, APP_PORT_END + 1)]
    ports = [state.get("appPort"), state.get("ocrPort"), *fallback_ports]
    for port in ports:
        for pid in listener_pids(int(port or 0)):
            stop_pid(pid)
    remove_state()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        if self.path.rstrip("/") == "/api/uploads":
            self.handle_upload()
            return
        if self.path.rstrip("/") == "/api/extract-content":
            self.handle_extract_content()
            return
        if self.path.rstrip("/") == "/api/extract-recipe-ai":
            self.handle_extract_recipe_ai()
            return
        if self.path.rstrip("/") == "/api/review-correction":
            self.handle_review_correction()
            return
        self.send_error(404, "Not found")

    def send_json(self, status, payload):
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_upload(self):
        ctype, pdict = cgi.parse_header(self.headers.get("content-type", ""))
        if ctype != "multipart/form-data":
            self.send_json(400, {"ok": False, "error": "Expected multipart/form-data."})
            return
        pdict["boundary"] = bytes(pdict.get("boundary", ""), "utf-8")
        pdict["CONTENT-LENGTH"] = int(self.headers.get("content-length", 0))
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": self.headers.get("content-type", ""),
        })
        upload = form["file"] if "file" in form else None
        if upload is None or not getattr(upload, "filename", ""):
            self.send_json(400, {"ok": False, "error": "No file was uploaded."})
            return
        original_name = Path(upload.filename).name
        suffix = Path(original_name).suffix.lower()
        if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
            self.send_json(400, {"ok": False, "error": f"Unsupported file type: {suffix}"})
            return

        file_id = (form.getfirst("file_id") or "").strip() or f"file_{int(time.time() * 1000)}"
        safe_file_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in file_id)[:80]
        upload_dir = UPLOAD_ROOT / safe_file_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_path = upload_dir / original_name
        with saved_path.open("wb") as target:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)

        uploaded_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        size = saved_path.stat().st_size
        log_path = upload_dir / "upload.log"
        log_path.write_text(
            "\n".join([
                f"file_id={safe_file_id}",
                f"filename={original_name}",
                f"file_type={suffix.lstrip('.').upper()}",
                f"file_size={size}",
                f"uploaded_at={uploaded_at}",
                f"status=Ready for Import",
            ]) + "\n",
            encoding="utf-8",
        )
        self.send_json(200, {
            "ok": True,
            "file_id": safe_file_id,
            "filename": original_name,
            "file_size": size,
            "file_type": suffix.lstrip(".").upper(),
            "uploaded_at": uploaded_at,
            "status": "Ready for Import",
            "saved_path": str(saved_path),
            "log_path": str(log_path),
        })

    def read_json_body(self):
        length = int(self.headers.get("content-length", 0))
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body or "{}")

    def handle_extract_content(self):
        try:
            payload = self.read_json_body()
            file_id = safe_id(payload.get("file_id") or "")
            if not file_id:
                content = extracted_content_object("", None, "Unknown", "failed", errors=["Missing file_id."])
                self.send_json(400, {"ok": False, **content, "error": content["errors"][0]})
                return
            upload_dir = UPLOAD_ROOT / file_id
            if not upload_dir.exists():
                content = extracted_content_object(file_id, None, "Unknown", "failed", errors=["Uploaded file was not found."])
                save_extracted_content(content)
                append_extraction_log(file_id, "extraction failed missing_upload_folder")
                self.send_json(404, {"ok": False, **content, "error": content["errors"][0]})
                return
            files = [path for path in upload_dir.iterdir() if path.is_file() and path.name != "upload.log"]
            if not files:
                content = extracted_content_object(file_id, None, "Unknown", "failed", errors=["Upload folder has no file to extract."])
                save_extracted_content(content)
                append_extraction_log(file_id, "extraction failed missing_uploaded_file")
                self.send_json(404, {"ok": False, **content, "error": content["errors"][0]})
                return
            result = extract_content(files[0], file_id=file_id)
            status_code = 200 if result.get("extraction_status") == "completed" else 422
            self.send_json(status_code, {
                "ok": result.get("extraction_status") == "completed",
                **result,
                "error": "; ".join(result.get("errors", [])),
            })
        except Exception as exc:
            message = friendly_extraction_error(exc)
            self.send_json(500, {
                "ok": False,
                "file_id": "",
                "filename": "",
                "file_type": "Unknown",
                "extraction_status": "failed",
                "extracted_text": "",
                "extracted_tables": [],
                "errors": [message],
                "created_at": now_iso(),
                "error": message,
            })

    def handle_extract_recipe_ai(self):
        try:
            payload = self.read_json_body()
            extracted_text = str(payload.get("extracted_text") or "").strip()
            extracted_tables = payload.get("extracted_tables") if isinstance(payload.get("extracted_tables"), list) else []
            invoice_table_rows = payload.get("invoice_table_rows") if isinstance(payload.get("invoice_table_rows"), list) else []
            invoice_metadata = payload.get("invoice_metadata") if isinstance(payload.get("invoice_metadata"), dict) else {}
            line_item_extraction = payload.get("line_item_extraction") if isinstance(payload.get("line_item_extraction"), dict) else {}
            extraction_engine = payload.get("extraction_engine") if isinstance(payload.get("extraction_engine"), dict) else {}
            file_id = safe_id(payload.get("file_id") or "")
            provider = str(payload.get("provider") or AI_PROVIDER).strip().lower()
            model = str(payload.get("model") or "").strip() or None
            requested_document_type = str(payload.get("document_type") or "").strip().lower() or None
            if not invoice_table_rows and line_item_extraction.get("extracted_rows"):
                invoice_table_rows = [universal_row_to_invoice_row(row) for row in (line_item_extraction.get("extracted_rows") or [])]
                extraction_engine = extraction_engine or extraction_engine_summary("universal_extractor", line_item_extraction, invoice_table_rows)
            if not invoice_table_rows and extracted_tables:
                parsed_invoice = InvoiceTableParser(extracted_text, extracted_tables).parse()
                invoice_table_rows = parsed_invoice.get("rows", [])
                invoice_metadata = {**parsed_invoice.get("metadata", {}), **invoice_metadata}
                extraction_engine = extraction_engine or extraction_engine_summary(
                    "legacy_parser_fallback",
                    line_item_extraction,
                    invoice_table_rows,
                    "Universal Extractor returned zero accepted rows during structured extraction.",
                    parsed_invoice,
                )
            if invoice_table_rows and (requested_document_type in {None, "", "supplier_invoice"} or classify_document(extracted_text, extracted_tables)[0] == "supplier_invoice"):
                result = supplier_invoice_from_table_rows(invoice_table_rows, invoice_metadata, provider=provider, model=model, extraction_engine=extraction_engine)
                self.send_json(200, {
                    "ok": True,
                    "file_id": file_id,
                    **result,
                })
                return
            if not extracted_text and not extracted_tables:
                self.send_json(400, {
                    "ok": False,
                    "error": "No extracted text was provided for recipe extraction.",
                    "recipe": None,
                    "file_id": file_id,
                })
                return
            if not extracted_text and extracted_tables:
                extracted_text = table_text(extracted_tables)
            result = AIRecipeExtractor(provider=provider, model=model).extract(
                extracted_text,
                tables=extracted_tables,
                requested_document_type=requested_document_type,
            )
            self.send_json(200, {
                "ok": True,
                "file_id": file_id,
                **result,
            })
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            self.send_json(exc.code or 500, {
                "ok": False,
                "error": f"OpenAI request failed: {body or exc.reason}",
                "recipe": None,
            })
        except Exception as exc:
            self.send_json(500, {
                "ok": False,
                "error": friendly_extraction_error(exc),
                "provider": AI_PROVIDER,
                "model": OLLAMA_MODEL if AI_PROVIDER == "ollama" else OPENAI_MODEL,
                "recipe": None,
            })

    def handle_review_correction(self):
        try:
            payload = self.read_json_body()
            append_correction_log(payload)
            self.send_json(200, {"ok": True, "log_path": str(CORRECTION_LOG)})
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": friendly_extraction_error(exc)})


def run_app_server(app_port):
    handler = lambda *args, **kwargs: QuietHandler(*args, directory=str(ROOT), **kwargs)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", app_port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    atexit.register(server.shutdown)
    return server


def main():
    if "--stop" in sys.argv:
        stop_from_state()
        return
    remove_stale_state()
    if not APP_FILE.exists():
        raise RuntimeError(f"App file not found: {APP_FILE}")

    ocr_process = start_ocr_helper()
    app_port = first_free_port(APP_PORT_START)
    run_app_server(app_port)
    write_state(app_port, ocr_process)
    atexit.register(remove_state)
    if ocr_process:
        atexit.register(lambda: stop_pid(ocr_process.pid))
    url = f"http://127.0.0.1:{app_port}/restaurant-costing-app.html"

    try:
        urllib.request.urlopen(url, timeout=2).close()
    except Exception:
        pass
    webbrowser.open(url)

    print("Recipe Vault is running locally.")
    print(f"App: {url}")
    print(f"OCR helper: http://127.0.0.1:{OCR_PORT}")
    print("Close this window or run stop-recipe-vault.bat to stop the local app.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        LAUNCHER_LOG.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        raise
