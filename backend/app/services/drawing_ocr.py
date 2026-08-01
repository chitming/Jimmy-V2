from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from PIL import Image

from ..db import LIBRARY_DIR, connect, dumps, loads, new_id, utc_now

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


def _run_payload(row) -> dict:
    return {
        "id": row["id"],
        "segment_id": row["segment_id"],
        "page_id": row["page_id"],
        "source_filename": row["source_filename"],
        "segment_filename": row["segment_filename"],
        "page_index": row["page_index"],
        "image_width": row["image_width"],
        "image_height": row["image_height"],
        "engine": row["engine"],
        "items": loads(row["items_json"]),
        "item_count": row["item_count"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "image_url": f"/media/library/Drawing/{row['segment_filename']}",
        "review_url": f"/drawing-review/{row['page_id']}",
    }


def list_drawing_ocr_runs() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM drawing_ocr_runs ORDER BY updated_at DESC"
        ).fetchall()
    return [_run_payload(row) for row in rows]


def get_drawing_ocr_run(page_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM drawing_ocr_runs WHERE page_id = ?",
            (page_id,),
        ).fetchone()
    return _run_payload(row) if row else None


def ocr_drawing_segments(page_id: str | None = None) -> dict:
    query = """
        SELECT s.*, p.page_index, d.filename AS source_filename
        FROM segments s
        JOIN pages p ON p.id = s.page_id
        JOIN drawings d ON d.id = p.drawing_id
        WHERE s.kind = 'drawing'
    """
    params: tuple = ()
    if page_id:
        query += " AND s.page_id = ?"
        params = (page_id,)
    query += " ORDER BY s.created_at ASC"

    with connect() as conn:
        segments = conn.execute(query, params).fetchall()

    processed = []
    errors = []
    now = utc_now()

    for seg in segments:
        image_path = LIBRARY_DIR / seg["relative_path"]
        if not image_path.exists():
            errors.append(
                {
                    "segment_id": seg["id"],
                    "error": f"Missing file: {seg['relative_path']}",
                }
            )
            continue
        try:
            result = run_ppocrv6_on_image(image_path)
        except Exception as exc:  # noqa: BLE001
            errors.append({"segment_id": seg["id"], "error": str(exc)})
            continue

        with connect() as conn:
            existing = conn.execute(
                "SELECT id FROM drawing_ocr_runs WHERE segment_id = ?",
                (seg["id"],),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE drawing_ocr_runs
                    SET source_filename = ?, segment_filename = ?, page_index = ?,
                        image_width = ?, image_height = ?, engine = ?,
                        items_json = ?, item_count = ?, status = 'pending_review',
                        updated_at = ?
                    WHERE segment_id = ?
                    """,
                    (
                        seg["source_filename"],
                        seg["filename"],
                        seg["page_index"],
                        result["image_width"],
                        result["image_height"],
                        result["engine"],
                        dumps(result["items"]),
                        len(result["items"]),
                        now,
                        seg["id"],
                    ),
                )
                run_id = existing["id"]
            else:
                run_id = new_id("docr")
                conn.execute(
                    """
                    INSERT INTO drawing_ocr_runs
                    (id, segment_id, page_id, source_filename, segment_filename,
                     page_index, image_width, image_height, engine, items_json,
                     item_count, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?)
                    """,
                    (
                        run_id,
                        seg["id"],
                        seg["page_id"],
                        seg["source_filename"],
                        seg["filename"],
                        seg["page_index"],
                        result["image_width"],
                        result["image_height"],
                        result["engine"],
                        dumps(result["items"]),
                        len(result["items"]),
                        now,
                        now,
                    ),
                )

        processed.append(
            {
                "id": run_id,
                "page_id": seg["page_id"],
                "segment_filename": seg["filename"],
                "item_count": len(result["items"]),
                "review_url": f"/drawing-review/{seg['page_id']}",
            }
        )

    return {
        "engine": ENGINE_NAME,
        "processed": len(processed),
        "errors": errors,
        "runs": processed,
        "all_runs": list_drawing_ocr_runs(),
    }


def update_drawing_ocr_items(page_id: str, items: list[dict], status: str = "reviewed") -> dict:
    if status not in {"pending_review", "reviewed"}:
        raise ValueError("status must be pending_review or reviewed")

    now = utc_now()
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM drawing_ocr_runs WHERE page_id = ?",
            (page_id,),
        ).fetchone()
        if row is None:
            raise KeyError("Drawing OCR run not found")
        conn.execute(
            """
            UPDATE drawing_ocr_runs
            SET items_json = ?, item_count = ?, status = ?, updated_at = ?
            WHERE page_id = ?
            """,
            (dumps(items), len(items), status, now, page_id),
        )
    result = get_drawing_ocr_run(page_id)
    assert result is not None
    return result
