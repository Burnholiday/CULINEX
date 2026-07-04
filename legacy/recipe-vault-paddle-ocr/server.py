from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path


def choose_paddle_cache() -> Path:
    override = os.environ.get("RECIPE_VAULT_PADDLE_CACHE")
    if override:
        return Path(override)

    legacy_cache = Path(__file__).with_name(".paddle-cache")
    model_probe = legacy_cache / "official_models" / "PP-OCRv6_medium_det" / "inference.yml"
    try:
        if (legacy_cache / "official_models").exists():
            with model_probe.open("r", encoding="utf-8"):
                pass
    except FileNotFoundError:
        return legacy_cache
    except OSError:
        return Path(__file__).with_name(".paddle-cache-v2")
    return legacy_cache


LOCAL_CACHE = choose_paddle_cache()
LOCAL_HOME = Path(__file__).with_name(".paddle-home")
LOCAL_CACHE.mkdir(parents=True, exist_ok=True)
LOCAL_HOME.mkdir(parents=True, exist_ok=True)
os.environ["HOME"] = str(LOCAL_HOME)
os.environ["USERPROFILE"] = str(LOCAL_HOME)
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(LOCAL_CACHE))
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")

import pdfplumber
import pypdfium2 as pdfium
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from paddleocr import PaddleOCR

try:
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
except ImportError:  # pragma: no cover - handled at runtime by /extract-prep.
    cv2 = None
    np = None
    Image = None
    ImageOps = None


app = FastAPI(title="Recipe Vault Local OCR")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr_engine: PaddleOCR | None = None


def get_ocr() -> PaddleOCR:
    global ocr_engine
    if ocr_engine is None:
        ocr_engine = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
    return ocr_engine


def lines_from_result(result: object) -> list[str]:
    lines: list[str] = []
    for page in result or []:
        if hasattr(page, "get"):
            page_lines = page.get("rec_texts", [])
        else:
            page_lines = []
        for text in page_lines:
            text = str(text).strip()
            if text:
                lines.append(text)
    return lines


def ocr_image(image_path: Path) -> list[str]:
    result = get_ocr().predict(str(image_path))
    return lines_from_result(result)


def first_ocr_boxes(page: object) -> object:
    for key in ("rec_boxes", "rec_polys", "dt_polys"):
        value = page.get(key) if hasattr(page, "get") else None
        if value is None:
            continue
        try:
            if len(value) == 0:
                continue
        except TypeError:
            continue
        return value
    return []


def ocr_items(image_path: Path) -> list[dict[str, object]]:
    result = get_ocr().predict(str(image_path))
    items: list[dict[str, object]] = []
    for page in result or []:
        if not hasattr(page, "get"):
            continue
        texts = list(page.get("rec_texts", []) or [])
        boxes = first_ocr_boxes(page)
        for index, text in enumerate(texts):
            text = str(text).strip()
            if not text:
                continue
            bounds = ocr_box_bounds(boxes[index]) if index < len(boxes) else None
            item: dict[str, object] = {"text": text}
            if bounds:
                item.update(bounds)
            items.append(item)
    return items


def ocr_box_bounds(box: object) -> dict[str, float] | None:
    if np is None:
        return None
    try:
        array = np.asarray(box, dtype=float)
    except (TypeError, ValueError):
        return None
    if array.size < 4:
        return None
    if array.ndim == 1 and array.size >= 4:
        x0, y0, x1, y1 = array[:4]
        return {
            "x": float(min(x0, x1)),
            "y": float(min(y0, y1)),
            "w": float(abs(x1 - x0)),
            "h": float(abs(y1 - y0)),
        }
    array = array.reshape(-1, array.shape[-1])
    if array.shape[1] < 2:
        return None
    xs = array[:, 0]
    ys = array[:, 1]
    return {
        "x": float(xs.min()),
        "y": float(ys.min()),
        "w": float(xs.max() - xs.min()),
        "h": float(ys.max() - ys.min()),
    }


def render_pdf(pdf_path: Path, folder: Path) -> list[Path]:
    document = pdfium.PdfDocument(str(pdf_path))
    pages: list[Path] = []
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil()
            image_path = folder / f"page-{index + 1}.png"
            try:
                image.save(image_path)
                pages.append(image_path)
            finally:
                image.close()
                bitmap.close()
                page.close()
    finally:
        document.close()
    return pages


def table_cell(row: list[object], index: int) -> str:
    if index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).replace("\n", " ").strip()


def parse_number(value: str) -> float | None:
    try:
        return float(value.replace("R", "").replace(",", "").strip())
    except ValueError:
        return None


def is_platter_recipe_name(name: str) -> bool:
    upper = name.upper()
    return any(
        word in upper
        for word in ("PLATTER", "PLATTERS", "BRENTON", "GARDEN OF EDEN", "SPECIALITY")
    )


def infer_recipe_category(name: str) -> str:
    upper = name.upper()
    if is_platter_recipe_name(upper):
        return "PLATTERS"
    if upper.startswith(("AVO ", "AVOCADO ", "VEG ", "VEGETARIAN ")) or " VEG " in f" {upper} ":
        return "AVO"
    for category in ("SALMON", "TUNA", "PRAWN", "HAMACHI"):
        if category in f" {upper} ":
            return category
    if upper.startswith("SUNSET"):
        return "SUNSET"
    return upper.split()[0] if upper.split() else "RECIPE"


def normalize_recipe_category(category: str, name: str) -> str:
    raw = " ".join(str(category or "").split())
    upper = raw.upper()
    if is_platter_recipe_name(name) or upper in {"BRENTON", "GARDEN"}:
        return "PLATTERS"
    if upper in {"AVOCADO", "VEG", "VEGETARIAN"}:
        return "AVO"
    return upper or infer_recipe_category(name)


def is_recipe_category_candidate(value: str) -> bool:
    candidate = " ".join(str(value or "").split())
    if not candidate or len(candidate) > 34:
        return False
    upper = candidate.upper()
    if upper in {"COSTING SHEET", "MENU PRICE", "INGREDIENTS"}:
        return False
    if any(token.isdigit() for token in candidate) or "R" in upper and any(ch.isdigit() for ch in upper):
        return False
    return any(ch.isalpha() for ch in candidate)


def infer_recipe_unit(name: str, quantity: float, bulk_size: str) -> str:
    bulk = parse_number(bulk_size)
    name_upper = name.upper()
    liquid_words = ("SAUCE", "MAYO", "OIL", "VINEGAR", "MIRIN", "JUICE", "CREAM", "MILK")
    if bulk is not None and bulk <= 20:
        return "EACH"
    if bulk == 1 and quantity < 1:
        return "EACH"
    if any(word in name_upper for word in liquid_words):
        return "ml"
    return "g"


def parse_costing_sheet_pdf(pdf_path: Path) -> list[dict[str, object]]:
    recipes: list[dict[str, object]] = []
    seen: set[tuple[str, int]] = set()

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables() or []
            if not tables:
                continue
            table = max(tables, key=len)
            if not table:
                continue

            starts = [
                index
                for index in range(len(table[0]))
                if any(table_cell(row, index) == "COSTING SHEET" for row in table)
                and index + 4 < len(table[0])
            ]

            for start in starts:
                row_index = 0
                while row_index < len(table):
                    if table_cell(table[row_index], start) != "COSTING SHEET":
                        row_index += 1
                        continue

                    title = ""
                    for next_row in range(row_index + 1, min(len(table), row_index + 7)):
                        candidate = table_cell(table[next_row], start)
                        if candidate and candidate not in {"COSTING SHEET", "Ingredients"}:
                            title = candidate
                            break

                    category = ""
                    for prev_row in range(row_index - 1, max(-1, row_index - 8), -1):
                        candidate = table_cell(table[prev_row], start)
                        if is_recipe_category_candidate(candidate):
                            category = candidate
                            break

                    ingredient_start = None
                    for next_row in range(row_index + 1, min(len(table), row_index + 12)):
                        if table_cell(table[next_row], start) == "Ingredients":
                            ingredient_start = next_row + 1
                            break

                    if not title or ingredient_start is None:
                        row_index += 1
                        continue

                    recipe_key = (title.upper(), page_number)
                    if recipe_key in seen:
                        row_index += 1
                        continue
                    seen.add(recipe_key)

                    ingredients: list[dict[str, object]] = []
                    selling_price = 0.0
                    next_index = ingredient_start
                    while next_index < len(table):
                        name = table_cell(table[next_index], start)
                        if name == "COSTING SHEET":
                            break
                        if name == "MENU PRICE":
                            selling_price = (
                                parse_number(table_cell(table[next_index], start + 3))
                                or parse_number(table_cell(table[next_index], start + 4))
                                or 0.0
                            )
                            next_index += 1
                            continue
                        if name.startswith(("WASTAGE", "TOTAL COST", "VAT", "TOTAL INCLUDING")):
                            next_index += 1
                            continue

                        quantity = parse_number(table_cell(table[next_index], start + 1))
                        bulk_size = table_cell(table[next_index], start + 2)
                        source_price = table_cell(table[next_index], start + 3)
                        if name and quantity is not None:
                            ingredients.append(
                                {
                                    "ingredient": name,
                                    "qty": quantity,
                                    "unit": infer_recipe_unit(name, quantity, bulk_size),
                                    "source_bulk_size": bulk_size,
                                    "source_unit_price": source_price,
                                }
                            )
                        next_index += 1

                    if ingredients:
                        recipes.append(
                            {
                                "name": title,
                                "category": normalize_recipe_category(category, title),
                                "sellingPrice": selling_price,
                                "ingredients": ingredients,
                                "page": page_number,
                            }
                        )
                    row_index = next_index if next_index > row_index else row_index + 1

    return recipes


def detect_prep_card_boxes(image: object) -> list[tuple[int, int, int, int]]:
    if cv2 is None or np is None:
        return []

    cv_image = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
    page_height, page_width = gray.shape
    candidates: list[tuple[int, int, int, int]] = []

    for threshold in range(20, 131, 10):
        mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)[1]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if not is_prep_card_box(width, height, page_width, page_height):
                continue
            candidates.append((x, y, width, height))

    boxes = dedupe_boxes(candidates)
    boxes = complete_regular_prep_grid(boxes)
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def detect_prep_card_boxes_from_black_bands(
    image: object, split_columns: bool = False
) -> list[tuple[int, int, int, int]]:
    if cv2 is None or np is None:
        return []

    gray = np.asarray(image.convert("L"))
    page_height, page_width = gray.shape
    column_ranges = prep_content_column_ranges(gray, split_columns)

    boxes: list[tuple[int, int, int, int]] = []
    for left, right in column_ranges:
        if right - left < max(80, int(page_width * 0.045)):
            continue
        column = gray[:, left:right]
        dark_fraction = (column < 80).mean(axis=1)
        bands: list[tuple[int, int, int, int]] = []
        start: int | None = None
        for row_index, fraction in enumerate(dark_fraction):
            if fraction > 0.30 and start is None:
                start = row_index
            elif (fraction <= 0.30 or row_index == page_height - 1) and start is not None:
                end = row_index - 1 if fraction <= 0.30 else row_index
                height = end - start + 1
                if max(8, int(page_height * 0.003)) <= height <= max(110, int(page_height * 0.08)):
                    bands.append((left, start, right - left, height))
                start = None

        if not bands:
            continue

        min_card_height = max(240, int(page_height * 0.075))
        tall_bands = [band for band in bands if band[3] >= max(55, int(page_height * 0.012))]
        if len(tall_bands) >= 2:
            for _, y, width, height in tall_bands:
                pad = max(8, int(height * 0.08))
                top = max(0, y - pad)
                bottom = min(page_height, y + height + pad)
                if bottom - top >= min_card_height // 3:
                    boxes.append((left, top, width, bottom - top))
            continue

        for index, band in enumerate(bands):
            _, y, width, height = band
            next_band = bands[index + 1] if index + 1 < len(bands) else None
            top = max(0, y - max(42, int(height * 2.2)))
            bottom = next_band[1] if next_band else page_height
            if bottom - top < min_card_height:
                continue
            boxes.append((left, top, width, bottom - top))

    return sorted(dedupe_boxes(boxes), key=lambda box: (box[1], box[0]))


def prep_content_column_ranges(gray: object, split_columns: bool) -> list[tuple[int, int]]:
    page_height, page_width = gray.shape
    dark_fraction = (gray < 60).mean(axis=0)
    groups: list[tuple[int, int]] = []
    start: int | None = None
    threshold = 0.08

    for column_index, fraction in enumerate(dark_fraction):
        if fraction > threshold and start is None:
            start = column_index
        elif (fraction <= threshold or column_index == page_width - 1) and start is not None:
            end = column_index - 1 if fraction <= threshold else column_index
            if end - start + 1 >= max(40, int(page_width * 0.035)):
                groups.append((max(0, start - 8), min(page_width, end + 9)))
            start = None

    if groups and sum(right - left for left, right in groups) < page_width * 0.78:
        return groups

    if split_columns and page_width >= 900:
        gutter = max(10, int(page_width * 0.025))
        middle = page_width // 2
        return [(0, middle - gutter), (middle + gutter, page_width)]

    return [(0, page_width)]


def horizontal_overlap_ratio(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    ax0, _, aw, _ = first
    bx0, _, bw, _ = second
    ax1 = ax0 + aw
    bx1 = bx0 + bw
    overlap = max(0, min(ax1, bx1) - max(ax0, bx0))
    return overlap / max(1, min(aw, bw))


def is_prep_card_box(width: int, height: int, page_width: int, page_height: int) -> bool:
    if page_width < 3000:
        if width < max(90, int(page_width * 0.22)):
            return False
        if height < max(95, int(page_height * 0.04)):
            return False
        if width > int(page_width * 0.98) or height > int(page_height * 0.94):
            return False
        ratio = height / max(width, 1)
        return 0.45 <= ratio <= 3.40

    if width < max(130, int(page_width * 0.018)):
        return False
    if height < max(120, int(page_height * 0.012)):
        return False
    if width > int(page_width * 0.16) or height > int(page_height * 0.13):
        return False
    ratio = height / max(width, 1)
    return 0.50 <= ratio <= 1.40


def dedupe_boxes(boxes: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
    unique: list[tuple[int, int, int, int]] = []
    for box in sorted(boxes, key=lambda item: item[2] * item[3], reverse=True):
        match_index = None
        for index, existing in enumerate(unique):
            if box_overlap_ratio(box, existing) > 0.72 or (
                abs(box[0] - existing[0]) < max(28, int(existing[2] * 0.12))
                and abs(box[1] - existing[1]) < max(34, int(existing[3] * 0.18))
            ):
                match_index = index
                break
        if match_index is None:
            unique.append(box)
        elif box[2] * box[3] > unique[match_index][2] * unique[match_index][3]:
            unique[match_index] = box
    return unique


def box_overlap_ratio(
    first: tuple[int, int, int, int], second: tuple[int, int, int, int]
) -> float:
    ax0, ay0, aw, ah = first
    bx0, by0, bw, bh = second
    ax1, ay1 = ax0 + aw, ay0 + ah
    bx1, by1 = bx0 + bw, by0 + bh
    overlap_width = max(0, min(ax1, bx1) - max(ax0, bx0))
    overlap_height = max(0, min(ay1, by1) - max(ay0, by0))
    overlap = overlap_width * overlap_height
    return overlap / max(1, min(aw * ah, bw * bh))


def cluster_numbers(values: list[int], tolerance: int) -> list[int]:
    clusters: list[list[int]] = []
    for value in sorted(values):
        for cluster in clusters:
            if abs(sum(cluster) / len(cluster) - value) <= tolerance:
                cluster.append(value)
                break
        else:
            clusters.append([value])
    return [round(sum(cluster) / len(cluster)) for cluster in clusters]


def median_int(values: list[int], fallback: int) -> int:
    values = sorted(value for value in values if value > 0)
    if not values:
        return fallback
    return int(values[len(values) // 2])


def complete_regular_prep_grid(
    boxes: list[tuple[int, int, int, int]]
) -> list[tuple[int, int, int, int]]:
    if len(boxes) < 8:
        return boxes

    median_width = median_int([box[2] for box in boxes], boxes[0][2])
    if median_width < 450:
        return boxes

    x_positions = cluster_numbers([box[0] for box in boxes], max(40, median_width // 12))
    y_positions = cluster_numbers([box[1] for box in boxes], max(45, median_int([box[3] for box in boxes], 500) // 8))
    if len(x_positions) < 3 or len(y_positions) < 2:
        return boxes

    x_diffs = [b - a for a, b in zip(x_positions, x_positions[1:]) if b - a > median_width * 0.75]
    if not x_diffs:
        return boxes

    x_step = median_int(x_diffs, median_width)
    if x_step <= 0:
        return boxes

    filled_x: list[int] = []
    current = min(x_positions)
    stop = max(x_positions)
    while current <= stop + int(x_step * 0.25):
        filled_x.append(round(current))
        current += x_step

    median_height = median_int([box[3] for box in boxes], boxes[0][3])
    completed = boxes[:]
    for x in filled_x:
        for y in y_positions:
            if any(abs(x - box[0]) < 50 and abs(y - box[1]) < 55 for box in completed):
                continue
            completed.append((x, y, median_width, median_height))
    return dedupe_boxes(completed)


def crop_prep_card(
    image: object,
    box: tuple[int, int, int, int],
    folder: Path,
    page_number: int,
    card_number: int,
) -> Path:
    x, y, width, height = box
    page_width, page_height = image.size
    pad_x = max(36, int(width * 0.12))
    pad_top = max(90, int(height * 0.30))
    pad_bottom = max(46, int(height * 0.14))
    left = max(0, x - pad_x)
    top = max(0, y - pad_top)
    right = min(page_width, x + width + pad_x)
    bottom = min(page_height, y + height + pad_bottom)

    crop = image.crop((left, top, right, bottom))
    if crop.width < 850:
        scale = min(4, max(2, round(900 / max(crop.width, 1))))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        crop = crop.resize((crop.width * scale, crop.height * scale), resample)
    crop = ImageOps.autocontrast(crop.convert("L")).convert("RGB")
    crop_path = folder / f"prep-page-{page_number}-card-{card_number}.png"
    crop.save(crop_path)
    crop.close()
    return crop_path


def crop_prep_card_region(
    image: object,
    box: tuple[int, int, int, int],
    folder: Path,
    page_number: int,
    card_number: int,
) -> Path:
    x, y, width, height = box
    page_width, page_height = image.size
    left = max(0, x)
    top = max(0, y)
    right = min(page_width, x + width)
    bottom = min(page_height, y + height)

    crop = image.crop((left, top, right, bottom))
    if crop.width < 850:
        scale = min(4, max(2, round(900 / max(crop.width, 1))))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        crop = crop.resize((crop.width * scale, crop.height * scale), resample)
    crop = ImageOps.autocontrast(crop.convert("L")).convert("RGB")
    crop_path = folder / f"prep-page-{page_number}-card-{card_number}.png"
    crop.save(crop_path)
    crop.close()
    return crop_path


def clean_text(value: object) -> str:
    return " ".join(str(value or "").replace("|", " ").split()).strip()


def prep_header_text(value: str) -> bool:
    return bool(
        re.search(
            r"\b(COSTING SHEET|INGREDIENTS|QUANTITY ITEM|BULK ITEM|PRICE PER|ITEM COST|"
            r"INSERT ABOVE|TOTAL COST|YIELD IN|PORTION VOLUME|COST PER PORTION|"
            r"USED IN|ML/GRAM|WEIGHT OR UNIT|UNIT/ML/GRAM)\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def parse_ocr_number(value: object) -> float | None:
    text = clean_text(value)
    if not text or re.search(r"[A-Za-z]", text.replace("R", ""), flags=re.IGNORECASE):
        text = re.sub(r"R\s*", "", text, flags=re.IGNORECASE)
    match = re.search(r"-?\d+(?:[.,]\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def parse_ocr_money(value: object) -> float | None:
    text = clean_text(value)
    match = re.search(r"R\s*(\d+(?:[.,]\d+)?)", text, flags=re.IGNORECASE)
    if not match:
        return None
    return parse_ocr_number(match.group(1))


def round_invoice_number(value: float | None, places: int = 2) -> float:
    return round(float(value or 0), places)


def invoice_number_token(value: object) -> bool:
    return bool(re.fullmatch(r"R?\d+(?:[.,]\d+)?", clean_text(value).replace(" ", "")))


def invoice_totals_match(qty: float, unit_price: float, line_total: float | None) -> bool:
    if not line_total:
        return True
    expected = round_invoice_number(qty * unit_price)
    tolerance = max(0.2, abs(line_total) * 0.04)
    return abs(expected - line_total) <= tolerance


def invoice_pack_measure(raw_name: str) -> dict[str, object] | None:
    text = raw_name.lower()
    text = re.sub(r"\b\d+\s*/\s*\d+\s*kg\b", "", text)
    multi_litre_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)\s*(?:ltr|lt|l|it)\b", text)
    if multi_litre_match:
        return {
            "qty": float(parse_ocr_number(multi_litre_match.group(1)) or 0)
            * float(parse_ocr_number(multi_litre_match.group(2)) or 0),
            "unit": "LTR",
        }
    multi_ml_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)\s*ml\b", text)
    if multi_ml_match:
        return {
            "qty": float(parse_ocr_number(multi_ml_match.group(1)) or 0)
            * float(parse_ocr_number(multi_ml_match.group(2)) or 0)
            / 1000,
            "unit": "LTR",
        }
    multi_kg_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)\s*kgs?\b", text)
    if multi_kg_match:
        return {
            "qty": float(parse_ocr_number(multi_kg_match.group(1)) or 0)
            * float(parse_ocr_number(multi_kg_match.group(2)) or 0),
            "unit": "KG",
        }
    multi_g_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*x\s*(\d+(?:[.,]\d+)?)\s*(?:g|gr|grams?)\b", text)
    if multi_g_match:
        return {
            "qty": float(parse_ocr_number(multi_g_match.group(1)) or 0)
            * float(parse_ocr_number(multi_g_match.group(2)) or 0)
            / 1000,
            "unit": "KG",
        }
    kg_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*kgs?\b", text)
    if kg_match:
        return {"qty": float(parse_ocr_number(kg_match.group(1)) or 0), "unit": "KG"}
    g_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:g|gr|grams?)\b", text)
    if g_match:
        return {"qty": float(parse_ocr_number(g_match.group(1)) or 0) / 1000, "unit": "KG"}
    litre_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*(?:ltr|lt|l|it)\b", text)
    if litre_match:
        return {"qty": float(parse_ocr_number(litre_match.group(1)) or 0), "unit": "LTR"}
    ml_match = re.search(r"\b(\d+(?:[.,]\d+)?)\s*ml\b", text)
    if ml_match:
        return {"qty": float(parse_ocr_number(ml_match.group(1)) or 0) / 1000, "unit": "LTR"}
    return None


def clean_invoice_item_name(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"\b\d+\s*/\s*\d+\s*kgs?\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^(?:\d{3,}|[A-Z]{1,6}\d[A-Z0-9]*|CBMBC|BEL\d+|AGT\d+|SAL)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(?\b\d+(?:[.,]\d+)?\s*x\s*\d+(?:[.,]\d+)?\s*(kg|kgs|g|gr|gram|grams|ml|ltr|lt|l|it)\b\)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\(?\b\d+(?:[.,]\d+)?\s*(kg|kgs|g|gr|gram|grams|ml|ltr|lt|l|it)\b\)?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(kg|each)\b", "", text, flags=re.IGNORECASE)
    return clean_text(text)


def infer_invoice_unit(raw_name: str) -> str:
    upper = raw_name.upper()
    if re.search(r"\bPUNNET|PUN\b", upper):
        return "PUN"
    if re.search(r"\b(KG|KGS|KILOGRAM|KILO)\b|\b\d+(?:[.,]\d+)?\s*KGS?\b", upper):
        return "KG"
    if re.search(r"\b(ML|LTR|LT|LITRE|LITER)\b|\b\d+(?:[.,]\d+)?\s*(?:ML|LTR|LT|L|IT)\b", upper):
        return "LTR"
    if re.search(r"\bPOCKET|PACK|PKT|BAG\b", upper):
        return "PKT"
    return "EACH"


def parse_invoice_table_line(value: object) -> dict[str, object] | None:
    text = clean_text(value)
    if not text:
        return None
    tokens = text.split()
    if len(tokens) < 6:
        return None

    tail_start = len(tokens)
    while tail_start > 0 and invoice_number_token(tokens[tail_start - 1]):
        tail_start -= 1

    tail = [parse_ocr_number(token) for token in tokens[tail_start:]]
    tail = [number for number in tail if number is not None]
    if len(tail) < 4:
        return None

    if len(tail) >= 5:
        qty = tail[-5]
        unit_price = tail[-4]
        vat_amount = tail[-2]
        line_total = tail[-1]
    else:
        qty = tail[-4]
        unit_price = tail[-3]
        vat_amount = tail[-2]
        line_total = tail[-1]

    raw_name = clean_text(" ".join(tokens[:tail_start]))
    name = clean_invoice_item_name(raw_name)
    if not name or not qty or not unit_price:
        return None
    if not invoice_totals_match(qty, unit_price, line_total):
        return None

    pack = invoice_pack_measure(raw_name)
    converted_qty = round_invoice_number(qty * float(pack["qty"]), 3) if pack else qty
    converted_unit_price = round_invoice_number(unit_price / float(pack["qty"])) if pack and pack["qty"] else unit_price
    return {
        "raw": name,
        "qty": converted_qty,
        "unit": str(pack["unit"]) if pack else infer_invoice_unit(raw_name),
        "unitPrice": converted_unit_price,
        "vatAmount": round_invoice_number(vat_amount),
        "lineTotal": round_invoice_number(line_total or qty * unit_price),
    }


def ocr_items_to_invoice_lines(items: list[dict[str, object]]) -> list[str]:
    positioned = [
        item
        for item in items
        if "x" in item and "y" in item and clean_text(item.get("text"))
    ]
    if not positioned:
        return [clean_text(item.get("text")) for item in items if clean_text(item.get("text"))]

    heights = [int(float(item.get("h") or 0)) for item in positioned]
    tolerance = max(10, int(median_int(heights, 16) * 0.9))
    groups: list[dict[str, object]] = []
    for item in sorted(positioned, key=lambda entry: (float(entry["y"]), float(entry["x"]))):
        center_y = float(item["y"]) + float(item.get("h") or 0) / 2
        for group in groups:
            if abs(float(group["center_y"]) - center_y) <= tolerance:
                group["items"].append(item)
                group["center_y"] = (
                    float(group["center_y"]) * (len(group["items"]) - 1) + center_y
                ) / len(group["items"])
                break
        else:
            groups.append({"center_y": center_y, "items": [item]})

    lines: list[str] = []
    for group in sorted(groups, key=lambda entry: float(entry["center_y"])):
        row_items = sorted(group["items"], key=lambda entry: float(entry["x"]))
        text = clean_text(" ".join(str(item["text"]) for item in row_items))
        if text:
            lines.append(text)
    return lines


def invoice_item_center_y(item: dict[str, object]) -> float:
    return float(item.get("y") or 0) + float(item.get("h") or 0) / 2


def invoice_item_center_x(item: dict[str, object]) -> float:
    return float(item.get("x") or 0) + float(item.get("w") or 0) / 2


def positioned_invoice_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        item
        for item in items
        if "x" in item and "y" in item and clean_text(item.get("text"))
    ]


def invoice_stock_code_text(value: object) -> bool:
    return bool(re.search(r"\b0{5,}\d{3,}\b", clean_text(value)))


def invoice_table_vertical_bounds(items: list[dict[str, object]]) -> tuple[float, float]:
    if not items:
        return 0.0, 0.0

    header_markers = []
    footer_markers = []
    for item in items:
        text = clean_text(item.get("text"))
        center_y = invoice_item_center_y(item)
        if re.search(r"\b(STOCK\s*CODE|DESCRIPTION|SHIP\s*QUANTITY|UNIT\s*PRICE|NETT\s*VALUE)\b", text, flags=re.IGNORECASE):
            header_markers.append(center_y)
        if re.search(r"\b(NOTES|CUSTOMER\s+SIGNATURE|SUB\s*TOTAL|TOTAL\s+DISCOUNT|AMOUNT\s+EXCL|NO\s+FROZEN|VERY\s+IMPORTANT)\b", text, flags=re.IGNORECASE):
            footer_markers.append(center_y)

    code_positions = [invoice_item_center_y(item) for item in items if invoice_stock_code_text(item.get("text"))]
    min_y = min(invoice_item_center_y(item) for item in items)
    max_y = max(invoice_item_center_y(item) for item in items)
    header_y = max(header_markers) if header_markers else (min(code_positions) - 35 if code_positions else min_y)
    footer_candidates = [value for value in footer_markers if value > header_y]
    footer_y = min(footer_candidates) if footer_candidates else max_y + 35
    return header_y, footer_y


def invoice_table_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    positioned = positioned_invoice_items(items)
    if not positioned:
        return []
    top, bottom = invoice_table_vertical_bounds(positioned)
    return [
        item
        for item in positioned
        if invoice_item_center_y(item) >= top - 8 and invoice_item_center_y(item) <= bottom + 8
    ]


def invoice_line_from_items(items: list[dict[str, object]]) -> str:
    return clean_text(" ".join(str(item["text"]) for item in sorted(items, key=lambda entry: float(entry["x"]))))


def dedupe_structured_invoice_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    unique: list[dict[str, object]] = []
    for row in rows:
        key = f"{row['raw'].lower()}|{row['qty']}|{row['unitPrice']}|{row['lineTotal']}"
        numeric_key = f"{row['qty']}|{row['unitPrice']}|{row['lineTotal']}"
        duplicate_index = next(
            (
                index
                for index, existing in enumerate(unique)
                if f"{existing['qty']}|{existing['unitPrice']}|{existing['lineTotal']}" == numeric_key
                and invoice_row_names_overlap(str(existing.get("raw") or ""), str(row.get("raw") or ""))
            ),
            None,
        )
        if duplicate_index is not None:
            existing = unique[duplicate_index]
            existing_vat = float(existing.get("vatAmount") or 0)
            row_vat = float(row.get("vatAmount") or 0)
            if (row_vat and not existing_vat) or len(str(row.get("raw") or "")) > len(str(existing.get("raw") or "")):
                seen.discard(f"{existing['raw'].lower()}|{existing['qty']}|{existing['unitPrice']}|{existing['lineTotal']}")
                seen.add(key)
                unique[duplicate_index] = row
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def invoice_row_names_overlap(first: str, second: str) -> bool:
    first_tokens = invoice_row_name_tokens(first)
    second_tokens = invoice_row_name_tokens(second)
    if not first_tokens or not second_tokens:
        return False
    smaller = first_tokens if len(first_tokens) <= len(second_tokens) else second_tokens
    overlap = len(first_tokens.intersection(second_tokens))
    return overlap >= max(2, int(len(smaller) * 0.75))


def invoice_row_name_tokens(value: str) -> set[str]:
    text = re.sub(r"[^a-z0-9]+", " ", value.lower())
    ignored = {"and", "the", "with", "plain", "fresh"}
    return {token for token in text.split() if len(token) > 2 and token not in ignored}


def invoice_rows_from_stock_code_anchors(items: list[dict[str, object]]) -> list[dict[str, object]]:
    table_items = invoice_table_items(items)
    if not table_items:
        return []

    code_items = [
        item
        for item in table_items
        if invoice_stock_code_text(item.get("text"))
    ]
    code_items.sort(key=lambda item: (invoice_item_center_y(item), float(item.get("x") or 0)))
    if not code_items:
        return []

    centers = [invoice_item_center_y(item) for item in code_items]
    gaps = [
        centers[index + 1] - centers[index]
        for index in range(len(centers) - 1)
        if centers[index + 1] > centers[index]
    ]
    row_gap = median_int([int(gap) for gap in gaps], median_int([int(float(item.get("h") or 0)) for item in table_items], 18) * 2)
    rows: list[dict[str, object]] = []

    for index, code_item in enumerate(code_items):
        center_y = centers[index]
        top = (centers[index - 1] + center_y) / 2 if index > 0 else center_y - row_gap * 0.55
        bottom = (center_y + centers[index + 1]) / 2 if index + 1 < len(centers) else center_y + row_gap * 0.55
        band_items = [
            item
            for item in table_items
            if invoice_item_center_y(item) >= top and invoice_item_center_y(item) < bottom
        ]
        line = invoice_line_from_items(band_items)
        row = parse_invoice_table_line(line)
        if row:
            rows.append(row)

    return dedupe_structured_invoice_rows(rows)


def invoice_rows_from_numeric_bands(items: list[dict[str, object]]) -> list[dict[str, object]]:
    table_items = invoice_table_items(items)
    if not table_items:
        return []

    min_x = min(float(item.get("x") or 0) for item in table_items)
    max_x = max(float(item.get("x") or 0) + float(item.get("w") or 0) for item in table_items)
    width = max(1.0, max_x - min_x)
    anchors = [
        item
        for item in table_items
        if invoice_number_token(item.get("text"))
        and (invoice_item_center_x(item) - min_x) / width > 0.48
    ]
    anchors.sort(key=lambda item: invoice_item_center_y(item))
    if not anchors:
        return []

    centers: list[float] = []
    for item in anchors:
        center_y = invoice_item_center_y(item)
        if not centers or abs(centers[-1] - center_y) > 8:
            centers.append(center_y)
        else:
            centers[-1] = (centers[-1] + center_y) / 2

    gaps = [
        centers[index + 1] - centers[index]
        for index in range(len(centers) - 1)
        if centers[index + 1] > centers[index]
    ]
    row_gap = median_int([int(gap) for gap in gaps], 22)
    rows: list[dict[str, object]] = []
    for index, center_y in enumerate(centers):
        top = (centers[index - 1] + center_y) / 2 if index > 0 else center_y - row_gap * 0.55
        bottom = (center_y + centers[index + 1]) / 2 if index + 1 < len(centers) else center_y + row_gap * 0.55
        band_items = [
            item
            for item in table_items
            if invoice_item_center_y(item) >= top and invoice_item_center_y(item) < bottom
        ]
        line = invoice_line_from_items(band_items)
        row = parse_invoice_table_line(line)
        if row:
            rows.append(row)

    return dedupe_structured_invoice_rows(rows)


def invoice_rows_from_positioned_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    anchored_rows = invoice_rows_from_stock_code_anchors(items)
    numeric_rows = invoice_rows_from_numeric_bands(items)
    return dedupe_structured_invoice_rows([*anchored_rows, *numeric_rows])


def invoice_rows_from_text_lines(lines: list[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in lines:
        if not re.search(r"\b0{5,}\d{3,}\b", line):
            continue
        row = parse_invoice_table_line(line)
        if not row:
            continue
        rows.append(row)
    return dedupe_structured_invoice_rows(rows)


def infer_structured_invoice_supplier(text: str) -> str:
    if re.search(r"\bgrocery\s*express\b", text, flags=re.IGNORECASE):
        return "Grocery Express"
    if re.search(r"\brobberg\b", text, flags=re.IGNORECASE):
        return "Robberg"
    if re.search(r"farm\s*fresh\s*direct|farmfreshdirect", text, flags=re.IGNORECASE):
        return "Farm Fresh Direct"
    if re.search(r"\bSO\s*[- ]?\s*CA\b|\bSOCA\b", text, flags=re.IGNORECASE):
        return "SO-CA Foods"
    return ""


def infer_structured_invoice_number(text: str) -> str:
    match = re.search(r"\bGE\d{5,}\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    match = re.search(r"\bID\d{5,}\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    match = re.search(r"\bIQINV\s*\d+\b|\bINV\s*\d+\b", text, flags=re.IGNORECASE)
    return match.group(0).replace(" ", "").upper() if match else ""


def infer_structured_invoice_date(text: str) -> str:
    match = re.search(r"\b\d{4}[\/.-]\d{1,2}[\/.-]\d{1,2}\b|\b\d{1,2}[\/.-]\d{1,2}[\/.-]\d{2,4}\b", text)
    return match.group(0) if match else ""


def crop_invoice_table(image_path: Path, folder: Path, suffix: str) -> Path | None:
    if Image is None:
        return None
    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    left = int(width * 0.01)
    top = int(height * 0.385)
    right = int(width * 0.99)
    bottom = int(height * 0.70)
    crop = image.crop((left, top, right, bottom))
    scale = max(2, min(4, int(3000 / max(1, crop.width)) + 1))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    crop = crop.resize((crop.width * scale, crop.height * scale), resample)
    crop = ImageOps.autocontrast(crop.convert("L")).convert("RGB")
    crop_path = folder / f"invoice-table-{suffix}.png"
    crop.save(crop_path)
    image.close()
    crop.close()
    return crop_path


def crop_grocery_express_invoice_columns(image_path: Path, folder: Path, suffix: str) -> dict[str, Path]:
    if Image is None or ImageOps is None:
        return {}

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    left = int(width * 0.02)
    top = int(height * 0.385)
    right = int(width * 0.985)
    bottom = int(height * 0.595)
    table = image.crop((left, top, right, bottom))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    table = table.resize((table.width * 2, table.height * 2), resample)
    table = ImageOps.autocontrast(table.convert("L")).convert("RGB")

    column_boxes = {
        "code_desc": (0.00, 0.00, 0.50, 1.00),
        "qty": (0.49, 0.00, 0.64, 1.00),
        "unit_price": (0.62, 0.00, 0.76, 1.00),
        "vat": (0.80, 0.00, 0.92, 1.00),
    }
    paths: dict[str, Path] = {}
    for name, (left_rel, top_rel, right_rel, bottom_rel) in column_boxes.items():
        crop = table.crop(
            (
                int(table.width * left_rel),
                int(table.height * top_rel),
                int(table.width * right_rel),
                int(table.height * bottom_rel),
            )
        )
        crop_path = folder / f"grocery-express-{suffix}-{name}.png"
        crop.save(crop_path)
        crop.close()
        paths[name] = crop_path

    image.close()
    table.close()
    return paths


def crop_robberg_invoice_columns(image_path: Path, folder: Path, suffix: str) -> dict[str, Path]:
    if Image is None or ImageOps is None:
        return {}

    image = Image.open(image_path).convert("RGB")
    width, height = image.size
    left = int(width * 0.03)
    top = int(height * 0.325)
    right = int(width * 0.965)
    bottom = int(height * 0.56)
    table = image.crop((left, top, right, bottom))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    table = table.resize((table.width * 2, table.height * 2), resample)
    table = ImageOps.autocontrast(table.convert("L")).convert("RGB")

    column_boxes = {
        "code": (0.00, 0.00, 0.17, 1.00),
        "desc": (0.15, 0.00, 0.51, 1.00),
        "qty": (0.45, 0.00, 0.62, 1.00),
        "unit_price": (0.61, 0.00, 0.75, 1.00),
        "vat": (0.76, 0.00, 0.90, 1.00),
    }
    paths: dict[str, Path] = {}
    for name, (left_rel, top_rel, right_rel, bottom_rel) in column_boxes.items():
        crop = table.crop(
            (
                int(table.width * left_rel),
                int(table.height * top_rel),
                int(table.width * right_rel),
                int(table.height * bottom_rel),
            )
        )
        crop_path = folder / f"robberg-{suffix}-{name}.png"
        crop.save(crop_path)
        crop.close()
        paths[name] = crop_path

    image.close()
    table.close()
    return paths


def grocery_express_description_names(lines: list[str]) -> list[str]:
    names: list[str] = []
    for line in lines:
        text = clean_text(line)
        if not text:
            continue
        if re.search(r"\b(STOCK\s*CODE|DESCRIPTION)\b", text, flags=re.IGNORECASE):
            text = re.sub(r"\b(STOCK\s*CODE|DESCRIPTION)\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\b0{5,}\d{3,}\b", "", text).strip()
        text = clean_text(text)
        if not text or len(text) <= 1:
            continue
        if re.fullmatch(r"[A-Z]", text, flags=re.IGNORECASE):
            continue
        names.append(text)
    return names


def invoice_column_numbers(lines: list[str]) -> list[float]:
    numbers: list[float] = []
    for line in lines:
        text = clean_text(line)
        if re.search(r"\b(SHIP|QUANTITY|UNIT|PRICE|DISC|VAT|NETT|VALUE)\b", text, flags=re.IGNORECASE):
            text = re.sub(r"\b(SHIP|QUANTITY|UNIT|PRICE|DISC|VAT|NETT|VALUE)\b", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"(?<=\d)\s+(?=\d{3}(?:[.,]\d{2})\b)", "", text)
        for match in re.finditer(r"\d+(?:[.,]\d+)?", text):
            number = parse_ocr_number(match.group(0))
            if number is not None:
                numbers.append(number)
    return numbers


def robberg_codes(lines: list[str]) -> list[str]:
    codes: list[str] = []
    for line in lines:
        for match in re.finditer(r"\b[A-Z]{3,4}\d{3,4}\b", clean_text(line), flags=re.IGNORECASE):
            codes.append(match.group(0).upper())
    return codes


def robberg_quantity_marker(value: str) -> bool:
    text = clean_text(value).replace("â‚¬", "").replace("€", "")
    text = re.sub(r"[^A-Za-z0-9., ]+", "", text).strip()
    return bool(re.fullmatch(r"\d+(?:[.,]\d+)?\s*(?:ea|box|bag|kg|g|gr|500g)?", text, flags=re.IGNORECASE))


def robberg_description_names(lines: list[str]) -> list[str]:
    groups: list[str] = []
    current: list[str] = []
    for line in lines:
        text = clean_text(line)
        if not text or re.search(r"\b(QUANTITY|UANTITY|DESCRIPTION)\b", text, flags=re.IGNORECASE):
            continue
        if robberg_quantity_marker(text):
            if current:
                groups.append(clean_text(" ".join(current)))
                current = []
            continue
        current.append(text)
    if current:
        groups.append(clean_text(" ".join(current)))
    return groups


def robberg_quantities(lines: list[str]) -> list[float]:
    quantities: list[float] = []
    for line in lines:
        text = clean_text(line)
        if not text or re.search(r"\b(QUANTITY|UANTITY)\b", text, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"\d+", text):
            continue
        text = re.sub(r"^100(\s+(?:ea|box|bag|kg)\b)", r"1.00\1", text, flags=re.IGNORECASE)
        match = re.search(r"\d+(?:[.,]\d+)?", text)
        if not match:
            continue
        quantity = parse_ocr_number(match.group(0))
        if quantity is not None:
            quantities.append(quantity)
    return quantities


def invoice_row_from_name_qty_price(
    raw_name: str,
    qty: float,
    unit_price: float,
    vat_amount: float | None = None,
) -> dict[str, object] | None:
    name = clean_invoice_item_name(raw_name)
    if not name or qty <= 0 or unit_price <= 0:
        return None

    pack = invoice_pack_measure(raw_name)
    converted_qty = round_invoice_number(qty * float(pack["qty"]), 3) if pack else round_invoice_number(qty, 3)
    converted_unit_price = round_invoice_number(unit_price / float(pack["qty"])) if pack and pack["qty"] else round_invoice_number(unit_price)
    return {
        "raw": name,
        "qty": converted_qty,
        "unit": str(pack["unit"]) if pack else infer_invoice_unit(raw_name),
        "unitPrice": converted_unit_price,
        "vatAmount": round_invoice_number(vat_amount) if vat_amount is not None else None,
        "lineTotal": round_invoice_number(qty * unit_price),
    }


def grocery_express_rows_from_column_crops(image_path: Path, folder: Path, suffix: str) -> list[dict[str, object]]:
    paths = crop_grocery_express_invoice_columns(image_path, folder, suffix)
    if not paths:
        return []

    names = grocery_express_description_names(ocr_image(paths["code_desc"]))
    quantities = invoice_column_numbers(ocr_image(paths["qty"]))
    unit_prices = invoice_column_numbers(ocr_image(paths["unit_price"]))
    vat_amounts = invoice_column_numbers(ocr_image(paths["vat"]))
    if min(len(names), len(quantities), len(unit_prices)) < 8:
        return []

    rows: list[dict[str, object]] = []
    for index in range(min(len(names), len(quantities), len(unit_prices))):
        vat_amount = vat_amounts[index] if index < len(vat_amounts) else None
        row = invoice_row_from_name_qty_price(names[index], quantities[index], unit_prices[index], vat_amount)
        if row:
            rows.append(row)
    return dedupe_structured_invoice_rows(rows)


def robberg_rows_from_column_crops(image_path: Path, folder: Path, suffix: str) -> list[dict[str, object]]:
    paths = crop_robberg_invoice_columns(image_path, folder, suffix)
    if not paths:
        return []

    codes = robberg_codes(ocr_image(paths["code"]))
    descriptions = robberg_description_names(ocr_image(paths["desc"]))
    quantities = robberg_quantities(ocr_image(paths["qty"]))
    unit_prices = invoice_column_numbers(ocr_image(paths["unit_price"]))
    vat_amounts = invoice_column_numbers(ocr_image(paths["vat"]))
    count = min(len(codes), len(descriptions), len(quantities), len(unit_prices))
    if count < 6:
        return []

    rows: list[dict[str, object]] = []
    for index in range(count):
        raw_name = clean_text(f"{codes[index]} {descriptions[index]}")
        vat_amount = vat_amounts[index] if index < len(vat_amounts) else None
        row = invoice_row_from_name_qty_price(raw_name, quantities[index], unit_prices[index], vat_amount)
        if row:
            row["source"] = "robberg"
            rows.append(row)
    return dedupe_structured_invoice_rows(rows)


def parse_invoice_image(image_path: Path, folder: Path, page_index: int) -> dict[str, object]:
    items = ocr_items(image_path)
    lines = ocr_items_to_invoice_lines(items)
    positioned_rows = invoice_rows_from_positioned_items(items)
    rows = positioned_rows if len(positioned_rows) >= 2 else invoice_rows_from_text_lines(lines)

    crop_path = crop_invoice_table(image_path, folder, str(page_index + 1))
    if crop_path and len(rows) < 12:
        crop_items = ocr_items(crop_path)
        crop_lines = ocr_items_to_invoice_lines(crop_items)
        crop_positioned_rows = invoice_rows_from_positioned_items(crop_items)
        crop_text_rows = invoice_rows_from_text_lines(crop_lines)
        crop_rows = crop_positioned_rows if len(crop_positioned_rows) >= len(crop_text_rows) else crop_text_rows
        if len(crop_rows) > len(rows):
            lines = lines + crop_lines
            rows = crop_rows

    text = "\n".join(lines)
    if len(rows) < 12 and re.search(r"\bgrocery\s*express\b|\bGE\d{5,}\b", text, flags=re.IGNORECASE):
        column_rows = grocery_express_rows_from_column_crops(image_path, folder, str(page_index + 1))
        if len(column_rows) > len(rows):
            rows = column_rows
    if re.search(r"\brobberg\b|\bID\d{5,}\b", text, flags=re.IGNORECASE):
        column_rows = robberg_rows_from_column_crops(image_path, folder, str(page_index + 1))
        if len(column_rows) >= 6:
            rows = column_rows

    return {"text": text, "rows": dedupe_structured_invoice_rows(rows)}


def ocr_items_to_rows(items: list[dict[str, object]]) -> list[dict[str, object]]:
    positioned = [
        item
        for item in items
        if "x" in item and "y" in item and clean_text(item.get("text"))
    ]
    if not positioned:
        return [{"text": clean_text(item.get("text")), "cells": [clean_text(item.get("text"))]} for item in items]

    heights = [int(float(item.get("h") or 0)) for item in positioned]
    tolerance = max(10, median_int(heights, 18))
    groups: list[dict[str, object]] = []

    for item in sorted(positioned, key=lambda entry: (float(entry["y"]), float(entry["x"]))):
        center_y = float(item["y"]) + float(item.get("h") or 0) / 2
        for group in groups:
            if abs(float(group["center_y"]) - center_y) <= tolerance:
                group["items"].append(item)
                group["center_y"] = (
                    float(group["center_y"]) * (len(group["items"]) - 1) + center_y
                ) / len(group["items"])
                break
        else:
            groups.append({"center_y": center_y, "items": [item]})

    max_x = max(float(item["x"]) + float(item.get("w") or 0) for item in positioned)
    min_x = min(float(item["x"]) for item in positioned)
    width = max(1.0, max_x - min_x)
    rows: list[dict[str, object]] = []

    for group in sorted(groups, key=lambda entry: float(entry["center_y"])):
        cells = ["", "", "", "", ""]
        row_items = sorted(group["items"], key=lambda entry: float(entry["x"]))
        for item in row_items:
            center_x = float(item["x"]) + float(item.get("w") or 0) / 2
            rel = (center_x - min_x) / width
            column = 0 if rel < 0.39 else 1 if rel < 0.55 else 2 if rel < 0.70 else 3 if rel < 0.86 else 4
            cells[column] = clean_text(f"{cells[column]} {item['text']}")
        text = clean_text(" ".join(str(item["text"]) for item in row_items))
        rows.append({"text": text, "cells": cells, "y": group["center_y"]})

    return rows


def clean_prep_title(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"\bCOSTING\s+SHEET\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+\d+(?:[.,]\d+)?\s*(g|kg|ml|ltr|l|each|pc|pcs|pkt|box)\b", "", text, flags=re.IGNORECASE)
    return clean_text(text)


def is_prep_title_candidate(value: object) -> bool:
    text = clean_prep_title(value)
    if not text or len(text) > 60:
        return False
    if prep_header_text(text):
        return False
    if re.search(r"R\s*\d|\d{3,}", text, flags=re.IGNORECASE):
        return False
    return bool(re.search(r"[A-Za-z]", text))


def clean_prep_ingredient(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"\(NO STOCK\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"R\s*\d+(?:[.,]\d+)?", "", text, flags=re.IGNORECASE)
    return clean_text(text)


def is_prep_ingredient_candidate(name: str) -> bool:
    if not name or len(name) > 56:
        return False
    if prep_header_text(name):
        return False
    if re.search(r"^\[\d+\]|\b(SEASON|SOURCE|REFERENCE|KONG YEN)\b", name, flags=re.IGNORECASE):
        return False
    if re.search(r"\d\s*$", name):
        return False
    return bool(re.search(r"[A-Za-z]", name))


def infer_prep_category(name: str, fallback: str = "Prep") -> str:
    upper = name.upper()
    if fallback.upper() in {"SAUCE", "SAUCES"}:
        return "Sauce"
    if fallback.upper() in {"SUSHI", "SEAFOOD", "PREPPED ITEMS", "BAKED GOODS", "DESSERTS", "BREAKFASTS"}:
        return fallback.title()
    if re.search(r"\b(SAUCE|TERIYAKI|MAYO|DRESSING|GLAZE|PONZU|TIKKA|MIGNONETTE)\b", upper):
        return "Sauce"
    if re.search(r"\b(BATTER|CRUMB|CRUMBS|PANKO)\b", upper):
        return "Batter"
    if re.search(r"\b(MIX|PASTE|GARNISH|SPRINKLE)\b", upper):
        return "Mix"
    return fallback or "Prep"


def infer_prep_unit(name: str, quantity: float, bulk_size: str) -> str:
    bulk_text = clean_text(bulk_size).upper()
    if "EACH" in bulk_text:
        return "EACH"
    if "ML" in bulk_text or "LTR" in bulk_text or "LT" in bulk_text:
        return "ml"
    if "KG" in bulk_text or "G" in bulk_text:
        return "g"
    upper = name.upper()
    if re.search(r"\b(SAUCE|VINEGAR|OIL|MIRIN|JUICE|CREAM|MILK|WATER|DRESSING|MAYO|PUREE)\b", upper):
        return "ml"
    if quantity <= 20 and re.search(r"\b(EGG|LEMON|LIME|AVO|AVOCADO|BUN|ROLL|WRAP)\b", upper):
        return "EACH"
    return "g"


def parse_prep_row_fallback(text: str) -> dict[str, object] | None:
    cleaned = clean_text(text)
    match = re.match(
        r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s+(?:\d+(?:[.,]\d+)?|1\s*EACH|EACH)\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        match = re.match(r"^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(g|kg|ml|ltr|l|each|pc|pcs|pkt|box)\b", cleaned, flags=re.IGNORECASE)
    if not match:
        return None
    name = clean_prep_ingredient(match.group(1))
    quantity = parse_ocr_number(match.group(2))
    if quantity is None or not is_prep_ingredient_candidate(name):
        return None
    unit = infer_prep_unit(name, quantity, "")
    return {"ingredient": name, "qty": quantity, "unit": unit}


def parse_prep_card_ocr(
    items: list[dict[str, object]], page_number: int, card_number: int
) -> dict[str, object] | None:
    rows = ocr_items_to_rows(items)
    if not rows:
        return None

    costing_index = next(
        (index for index, row in enumerate(rows) if re.search(r"\bCOSTING\s+SHEET\b", str(row["text"]), re.IGNORECASE)),
        -1,
    )
    if costing_index < 0:
        return None

    category = "Prep"
    for index in range(max(0, costing_index - 3), costing_index):
        candidate = clean_prep_title(rows[index]["text"])
        if is_prep_title_candidate(candidate):
            category = candidate
            break

    header_index = next(
        (
            index
            for index, row in enumerate(rows[costing_index + 1 :], costing_index + 1)
            if re.search(r"\bIngredients\b", str(row["text"]), re.IGNORECASE)
        ),
        -1,
    )

    title_stop = header_index if header_index > costing_index else min(len(rows), costing_index + 7)
    name = ""
    for index in range(costing_index + 1, title_stop):
        candidate = clean_prep_title(rows[index]["text"])
        if is_prep_title_candidate(candidate):
            name = candidate
            break
    if not name:
        return None

    ingredients: list[dict[str, object]] = []
    start_index = header_index + 1 if header_index >= 0 else costing_index + 2
    for row in rows[start_index:]:
        text = clean_text(row["text"])
        if re.search(r"\b(INSERT ABOVE|TOTAL COST|YIELD IN|PORTION VOLUME|COST PER PORTION)\b", text, re.IGNORECASE):
            break
        if prep_header_text(text):
            continue
        cells = [clean_text(cell) for cell in row.get("cells", [])]
        ingredient_name = clean_prep_ingredient(cells[0] if cells else "")
        quantity = parse_ocr_number(cells[1] if len(cells) > 1 else "")
        if not ingredient_name or quantity is None:
            fallback = parse_prep_row_fallback(text)
            if fallback:
                ingredients.append(fallback)
            continue
        if not is_prep_ingredient_candidate(ingredient_name):
            continue
        ingredients.append(
            {
                "ingredient": ingredient_name,
                "qty": quantity,
                "unit": infer_prep_unit(ingredient_name, quantity, cells[2] if len(cells) > 2 else ""),
                "source_bulk_size": cells[2] if len(cells) > 2 else "",
                "source_unit_price": cells[3] if len(cells) > 3 else "",
            }
        )

    ingredients = dedupe_prep_ingredients(ingredients)
    if not ingredients:
        return None

    yield_qty, yield_unit = infer_prep_yield_from_rows(rows, ingredients)
    return {
        "name": name,
        "category": infer_prep_category(name, category),
        "yieldQty": yield_qty,
        "yieldUnit": yield_unit,
        "ingredients": ingredients,
        "page": page_number,
        "card": card_number,
    }


def dedupe_prep_ingredients(ingredients: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[tuple[str, float, str]] = set()
    clean_items: list[dict[str, object]] = []
    for ingredient in ingredients:
        name = clean_prep_ingredient(ingredient.get("ingredient"))
        quantity = float(ingredient.get("qty") or 0)
        unit = str(ingredient.get("unit") or "g")
        key = (name.upper(), quantity, unit.upper())
        if not name or quantity <= 0 or key in seen:
            continue
        seen.add(key)
        clean_items.append({**ingredient, "ingredient": name, "qty": quantity, "unit": unit})
    return clean_items


def infer_prep_yield_from_rows(
    rows: list[dict[str, object]], ingredients: list[dict[str, object]]
) -> tuple[float, str]:
    for row in rows:
        text = clean_text(row["text"])
        if not re.search(r"\bYIELD\b", text, re.IGNORECASE):
            continue
        cells = [clean_text(cell) for cell in row.get("cells", [])]
        candidates = [parse_ocr_number(cell) for cell in reversed(cells)] + [parse_ocr_number(text)]
        quantity = next((candidate for candidate in candidates if candidate and candidate > 0), None)
        if quantity:
            unit = "ml" if re.search(r"\b(ML|LTR|LITRE|VOLUME)\b", text, re.IGNORECASE) else "g"
            return round(float(quantity), 2), unit

    totals: dict[str, float] = {}
    for ingredient in ingredients:
        unit = str(ingredient.get("unit") or "g").lower()
        quantity = float(ingredient.get("qty") or 0)
        if unit == "kg":
            totals["g"] = totals.get("g", 0) + quantity * 1000
        elif unit in {"g", "ml"}:
            totals[unit] = totals.get(unit, 0) + quantity
        elif unit in {"ltr", "l"}:
            totals["ml"] = totals.get("ml", 0) + quantity * 1000
    if totals.get("ml"):
        return round(totals["ml"], 2), "ml"
    if totals.get("g"):
        return round(totals["g"], 2), "g"
    return 1, "EACH"


def parse_prep_card_pdf(pdf_path: Path, folder: Path) -> tuple[list[dict[str, object]], int]:
    if cv2 is None or np is None or Image is None or ImageOps is None:
        raise HTTPException(status_code=500, detail="The local prep reader needs OpenCV and Pillow.")

    max_cards = int(os.environ.get("RECIPE_VAULT_MAX_PREP_CARDS", "220"))
    prep_items: list[dict[str, object]] = []
    detected_cards = 0
    attempted_cards = 0
    seen: set[str] = set()
    document = pdfium.PdfDocument(str(pdf_path))

    try:
        for page_index in range(len(document)):
            page = document[page_index]
            bitmap = page.render(scale=12)
            image = bitmap.to_pil().convert("RGB")
            try:
                boxes = detect_prep_card_boxes(image)
                detected_cards += len(boxes)
                for card_index, box in enumerate(boxes, 1):
                    if attempted_cards >= max_cards:
                        return prep_items, detected_cards
                    attempted_cards += 1
                    crop_path = crop_prep_card(image, box, folder, page_index + 1, card_index)
                    items = ocr_items(crop_path)
                    prep_item = parse_prep_card_ocr(items, page_index + 1, card_index)
                    if not prep_item:
                        continue
                    key = str(prep_item["name"]).upper()
                    if key in seen:
                        continue
                    seen.add(key)
                    prep_items.append(prep_item)
            finally:
                image.close()
                bitmap.close()
                page.close()
    finally:
        document.close()

    return prep_items, detected_cards


def normalize_prep_source_image(image: object) -> object:
    width, height = image.size
    if width < 1200:
        scale = min(10, max(2, round(1200 / max(width, 1))))
        resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
        image = image.resize((width * scale, height * scale), resample)
    return ImageOps.autocontrast(image.convert("RGB"))


def parse_prep_card_image(image_path: Path, folder: Path) -> tuple[list[dict[str, object]], int]:
    if cv2 is None or np is None or Image is None or ImageOps is None:
        raise HTTPException(status_code=500, detail="The local prep reader needs OpenCV and Pillow.")

    with Image.open(image_path) as source:
        source_width = source.width
        image = normalize_prep_source_image(source.convert("RGB"))

    try:
        boxes = detect_prep_card_boxes(image)
        use_direct_crop = False
        if not boxes:
            boxes = detect_prep_card_boxes_from_black_bands(image, split_columns=source_width > 200)
            use_direct_crop = True
        detected_cards = len(boxes)
        if not boxes and image.width >= 700 and image.height >= 700:
            boxes = [(0, 0, image.width, image.height)]
            detected_cards = 1
            use_direct_crop = True

        prep_items: list[dict[str, object]] = []
        seen: set[str] = set()
        max_cards = int(os.environ.get("RECIPE_VAULT_MAX_PREP_CARDS", "220"))
        for card_index, box in enumerate(boxes[:max_cards], 1):
            crop_path = (
                crop_prep_card_region(image, box, folder, 1, card_index)
                if use_direct_crop
                else crop_prep_card(image, box, folder, 1, card_index)
            )
            items = ocr_items(crop_path)
            prep_item = parse_prep_card_ocr(items, 1, card_index)
            if not prep_item:
                continue
            key = str(prep_item["name"]).upper()
            if key in seen:
                continue
            seen.add(key)
            prep_items.append(prep_item)
        return prep_items, detected_cards
    finally:
        image.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="Use a PDF or image file.")

    with tempfile.TemporaryDirectory(prefix="recipe-vault-ocr-") as temp_dir:
        work_dir = Path(temp_dir)
        input_path = work_dir / f"upload{suffix}"
        input_path.write_bytes(await file.read())

        if suffix == ".pdf":
            image_paths = render_pdf(input_path, work_dir)
        else:
            image_paths = [input_path]

        pages = []
        positioned_items = []
        for page_index, image_path in enumerate(image_paths, 1):
            items = ocr_items(image_path)
            pages.append("\n".join(str(item.get("text") or "") for item in items if str(item.get("text") or "").strip()))
            for item in items:
                enriched = dict(item)
                enriched["page"] = page_index
                positioned_items.append(enriched)
        text = "\n\n".join(page for page in pages if page).strip()
        return {"text": text, "ocr_items": positioned_items, "pages": len(image_paths), "engine": "PaddleOCR"}


@app.post("/extract-invoice")
async def extract_invoice(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or "invoice"
    suffix = Path(filename).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}:
        raise HTTPException(status_code=400, detail="Use an invoice PDF or image file.")

    with tempfile.TemporaryDirectory(prefix="recipe-vault-invoice-") as temp_dir:
        work_dir = Path(temp_dir)
        input_path = work_dir / f"invoice{suffix}"
        input_path.write_bytes(await file.read())

        if suffix == ".pdf":
            image_paths = render_pdf(input_path, work_dir)
        else:
            image_paths = [input_path]

        all_text: list[str] = []
        all_rows: list[dict[str, object]] = []
        seen: set[str] = set()
        for page_index, image_path in enumerate(image_paths):
            parsed = parse_invoice_image(image_path, work_dir, page_index)
            page_text = str(parsed.get("text") or "").strip()
            if page_text:
                all_text.append(page_text)
            for row in parsed.get("rows") or []:
                key = f"{str(row.get('raw', '')).lower()}|{row.get('qty')}|{row.get('unitPrice')}|{row.get('lineTotal')}"
                if key in seen:
                    continue
                seen.add(key)
                all_rows.append(row)

        text = "\n".join(all_text).strip()
        return {
            "text": text,
            "rows": all_rows,
            "count": len(all_rows),
            "supplier": infer_structured_invoice_supplier(text),
            "invoiceNumber": infer_structured_invoice_number(text),
            "invoiceDate": infer_structured_invoice_date(text),
            "pages": len(image_paths),
            "engine": "PaddleOCR structured invoice reader",
        }


@app.post("/extract-recipes")
async def extract_recipes(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or "recipes.pdf"
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Use a costing-sheet PDF.")

    with tempfile.TemporaryDirectory(prefix="recipe-vault-pdf-") as temp_dir:
        pdf_path = Path(temp_dir) / "recipes.pdf"
        pdf_path.write_bytes(await file.read())
        recipes = parse_costing_sheet_pdf(pdf_path)
        return {"recipes": recipes, "count": len(recipes), "engine": "Structured PDF reader"}


@app.post("/extract-prep")
async def extract_prep(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or "prep.pdf"
    suffix = Path(filename).suffix.lower()
    image_suffixes = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    if suffix != ".pdf" and suffix not in image_suffixes:
        raise HTTPException(status_code=400, detail="Use a bulk-prep PDF or image.")

    with tempfile.TemporaryDirectory(prefix="recipe-vault-prep-") as temp_dir:
        work_dir = Path(temp_dir)
        input_path = work_dir / f"prep{suffix}"
        input_path.write_bytes(await file.read())
        if suffix == ".pdf":
            prep_items, detected_cards = parse_prep_card_pdf(input_path, work_dir)
        else:
            prep_items, detected_cards = parse_prep_card_image(input_path, work_dir)
        return {
            "prepItems": prep_items,
            "count": len(prep_items),
            "detectedCards": detected_cards,
            "engine": "Local prep-card reader",
        }
