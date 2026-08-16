from __future__ import annotations

import re
from pathlib import Path

import pytesseract
from PIL import Image

from .render import extract_pdf_text_in_box


FIELD_PATTERNS = {
    "drawing_number": [
        r"(?:drawing\s*(?:no|number|#)|dwg\s*(?:no|#)|sheet\s*(?:no|#))\s*[:#]?\s*([A-Z0-9][A-Z0-9\-_/]+)",
        r"\b([A-Z]{1,4}[-_]\d{2,}(?:[-_]\d+)*)\b",
    ],
    "revision": [
        r"(?:^|\b)(?:rev(?:ision)?)\s*[:#]\s*([A-Z0-9]{1,3})\b",
        r"(?:^|\b)REV\s*[:#]?\s*([A-Z0-9])\b",
    ],
    "scale": [
        r"(?:scale)\s*[:#]?\s*([0-9]+(?:\s*:\s*[0-9]+)?)",
    ],
    "date": [
        r"(?:date)\s*[:#]?\s*(\d{1,4}[./\-]\d{1,2}[./\-]\d{1,4})",
        r"\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\b",
    ],
    "title": [
        r"(?:title|drawing\s*title)\s*[:#]?\s*(.+)",
    ],
    "company": [
        r"(?:company|drawn\s*by|prepared\s*by)\s*[:#]?\s*(.+)",
    ],
}


def crop_box(image_path: Path, box: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as img:
        width, height = img.size
        left = max(0, int(box["x"] * width))
        top = max(0, int(box["y"] * height))
        right = min(width, int((box["x"] + box["w"]) * width))
        bottom = min(height, int((box["y"] + box["h"]) * height))
        crop = img.crop((left, top, right, bottom)).convert("RGB")
        if out_path.suffix.lower() in {".jpg", ".jpeg"}:
            crop.save(out_path, format="JPEG", quality=92, optimize=True)
        else:
            crop.save(out_path)
    return out_path


def ocr_image(image_path: Path) -> str:
    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img)
    return text.strip()


def parse_fields(raw_text: str) -> dict[str, str | None]:
    fields: dict[str, str | None] = {key: None for key in FIELD_PATTERNS}
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    joined = "\n".join(lines)

    for key, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = re.search(pattern, joined, flags=re.IGNORECASE | re.MULTILINE)
            if match:
                value = match.group(1).strip(" :-\t")
                if value:
                    fields[key] = value
                    break

    if not fields["company"] and lines:
        # Heuristic: first short uppercase-ish line often is company/brand.
        for line in lines[:4]:
            if 3 <= len(line) <= 60 and sum(ch.isalpha() for ch in line) >= 3:
                fields["company"] = line
                break

    if not fields["title"]:
        for line in lines:
            if len(line) >= 8 and not re.search(r"rev|scale|date|dwg|drawing", line, re.I):
                fields["title"] = line
                break

    return fields


def extract_information_block(
    *,
    image_path: Path,
    box: dict,
    crop_path: Path,
    source_type: str,
    pdf_path: Path | None,
    page_index: int,
    page_width: int,
    page_height: int,
    reuse_crop: bool = False,
) -> dict:
    if not reuse_crop or not crop_path.exists():
        crop_box(image_path, box, crop_path)
    method = "ocr"
    raw_text = ""

    if source_type == "pdf" and pdf_path and pdf_path.exists():
        vector_text = extract_pdf_text_in_box(
            pdf_path, page_index, box, page_width, page_height
        )
        if len(vector_text) >= 8:
            raw_text = vector_text
            method = "pdf_text"

    if not raw_text:
        raw_text = ocr_image(crop_path)
        method = "ocr"

    return {
        "raw_text": raw_text,
        "fields": parse_fields(raw_text),
        "method": method,
        "crop_path": str(crop_path),
    }
