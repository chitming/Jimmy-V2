from __future__ import annotations

from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

from ..db import connect, loads


CLASSES = ("information_block", "drawing_canvas")


def compute_phash(image_path: Path) -> str:
    with Image.open(image_path) as img:
        return str(imagehash.phash(img.convert("RGB")))


def _hamming(a: str, b: str) -> int:
    # imagehash hex strings
    try:
        return imagehash.hex_to_hash(a) - imagehash.hex_to_hash(b)
    except Exception:
        return 64


def _clamp_box(box: dict) -> dict:
    x = float(np.clip(box["x"], 0.0, 0.98))
    y = float(np.clip(box["y"], 0.0, 0.98))
    w = float(np.clip(box["w"], 0.02, 1.0 - x))
    h = float(np.clip(box["h"], 0.02, 1.0 - y))
    return {"x": x, "y": y, "w": w, "h": h}


def _average_boxes(boxes: list[dict], weights: list[float]) -> dict:
    wsum = sum(weights) or 1.0
    avg = {
        "x": sum(b["x"] * w for b, w in zip(boxes, weights)) / wsum,
        "y": sum(b["y"] * w for b, w in zip(boxes, weights)) / wsum,
        "w": sum(b["w"] * w for b, w in zip(boxes, weights)) / wsum,
        "h": sum(b["h"] * w for b, w in zip(boxes, weights)) / wsum,
    }
    return _clamp_box(avg)


def labeled_count() -> int:
    with connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM annotations").fetchone()
        return int(row["c"])


def predict_layout(page_id: str) -> dict | None:
    """Few-shot layout prediction from previously taught drawings.

    Uses perceptual-hash nearest neighbors and weighted-average boxes.
    Works from a single taught example.
    """
    with connect() as conn:
        page = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
        if page is None:
            return None

        examples = conn.execute(
            """
            SELECT p.id, p.width, p.height, p.phash, a.information_block, a.drawing_canvas
            FROM annotations a
            JOIN pages p ON p.id = a.page_id
            WHERE p.id != ?
            """
            ,
            (page_id,),
        ).fetchall()

    if not examples:
        return None

    target_hash = page["phash"] or ""
    target_aspect = page["width"] / max(page["height"], 1)

    scored: list[tuple[float, dict, dict]] = []
    for ex in examples:
        dist = _hamming(target_hash, ex["phash"] or "") if target_hash and ex["phash"] else 32
        aspect = ex["width"] / max(ex["height"], 1)
        aspect_penalty = abs(np.log((aspect + 1e-6) / (target_aspect + 1e-6))) * 8
        score = float(dist) + float(aspect_penalty)
        weight = 1.0 / (1.0 + score)
        scored.append(
            (
                weight,
                loads(ex["information_block"]),
                loads(ex["drawing_canvas"]),
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    top = scored[: min(5, len(scored))]
    weights = [item[0] for item in top]
    info_boxes = [item[1] for item in top]
    canvas_boxes = [item[2] for item in top]

    best_weight = weights[0]
    # With few-shot layout memory, even one close example should feel useful.
    confidence = float(np.clip(0.4 + 0.55 * best_weight, 0.25, 0.97))

    return {
        "information_block": _average_boxes(info_boxes, weights),
        "drawing_canvas": _average_boxes(canvas_boxes, weights),
        "confidence": confidence,
        "examples_used": len(top),
        "labeled_total": len(examples),
        "method": "few_shot_phash",
    }
