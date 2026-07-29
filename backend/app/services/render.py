from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image

from ..db import PAGES_DIR


def render_pdf_pages(pdf_path: Path, drawing_id: str, dpi: int = 150) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages: list[dict] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for index, page in enumerate(doc):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        out_path = PAGES_DIR / f"{drawing_id}_p{index}.png"
        pix.save(out_path)
        pages.append(
            {
                "page_index": index,
                "width": pix.width,
                "height": pix.height,
                "image_path": str(out_path),
            }
        )
    doc.close()
    return pages


def save_image_as_page(image_path: Path, drawing_id: str) -> list[dict]:
    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        out_path = PAGES_DIR / f"{drawing_id}_p0.png"
        rgb.save(out_path, format="PNG")
        return [
            {
                "page_index": 0,
                "width": rgb.width,
                "height": rgb.height,
                "image_path": str(out_path),
            }
        ]


def extract_pdf_text_in_box(
    pdf_path: Path,
    page_index: int,
    box: dict,
    page_width: int,
    page_height: int,
) -> str:
    """Extract native PDF text inside a normalized box [0-1]."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_index]
        rect = page.rect
        x0 = box["x"] * rect.width
        y0 = box["y"] * rect.height
        x1 = (box["x"] + box["w"]) * rect.width
        y1 = (box["y"] + box["h"]) * rect.height
        clip = fitz.Rect(x0, y0, x1, y1)
        text = page.get_text("text", clip=clip)
        return text.strip()
    finally:
        doc.close()
