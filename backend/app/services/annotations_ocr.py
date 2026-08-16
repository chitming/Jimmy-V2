from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from PIL import Image

# Avoid a slow hoster connectivity probe on every process start.
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

ENGINE_NAME = "PP-OCRv6"

_ocr_lock = threading.Lock()
_ocr_engine = None


def get_ocr_engine():
    """Lazy singleton for PP-OCRv6 (default medium models)."""
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine
    with _ocr_lock:
        if _ocr_engine is not None:
            return _ocr_engine
        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        return _ocr_engine


def _to_python(value: Any) -> Any:
    if hasattr(value, "tolist"):
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [_to_python(v) for v in value]
    return value


def _normalize_box(box_xyxy: list[float], width: int, height: int) -> dict[str, float]:
    x1, y1, x2, y2 = [float(v) for v in box_xyxy]
    x = max(0.0, min(x1 / width, 1.0))
    y = max(0.0, min(y1 / height, 1.0))
    w = max(0.001, min((x2 - x1) / width, 1.0 - x))
    h = max(0.001, min((y2 - y1) / height, 1.0 - y))
    return {"x": x, "y": y, "w": w, "h": h}


def run_ppocrv6_on_image(image_path: Path) -> dict:
    """Extract drawing annotations (labels / dimensions) with PP-OCRv6."""
    with Image.open(image_path) as img:
        width, height = img.size

    engine = get_ocr_engine()
    result = engine.predict(str(image_path))
    if not result:
        return {
            "engine": ENGINE_NAME,
            "image_width": width,
            "image_height": height,
            "items": [],
        }

    payload = result[0].json.get("res", {})
    texts = _to_python(payload.get("rec_texts") or [])
    scores = _to_python(payload.get("rec_scores") or [])
    boxes = _to_python(payload.get("rec_boxes") or [])
    polys = _to_python(payload.get("dt_polys") or payload.get("rec_polys") or [])

    items = []
    for index, text in enumerate(texts):
        score = float(scores[index]) if index < len(scores) else 0.0
        if index < len(boxes) and boxes[index] is not None:
            box = _normalize_box(boxes[index], width, height)
            pixel_box = [float(v) for v in boxes[index]]
        elif index < len(polys) and polys[index]:
            xs = [float(p[0]) for p in polys[index]]
            ys = [float(p[1]) for p in polys[index]]
            pixel_box = [min(xs), min(ys), max(xs), max(ys)]
            box = _normalize_box(pixel_box, width, height)
        else:
            continue
        items.append(
            {
                "id": f"ocr_{index + 1}",
                "text": str(text),
                "score": score,
                "box": box,
                "pixel_box": pixel_box,
                "edited": False,
            }
        )

    return {
        "engine": ENGINE_NAME,
        "image_width": width,
        "image_height": height,
        "items": items,
    }
