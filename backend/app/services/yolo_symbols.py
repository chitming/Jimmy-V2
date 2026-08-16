from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np

from ..db import ROOT

# Optional custom fine-tuned weights for AEC P&ID / drawing symbols.
CUSTOM_WEIGHTS = ROOT / "data" / "models" / "aec_symbols.pt"
WORLD_WEIGHTS = ROOT / "data" / "models" / "yolov8s-world.pt"

AEC_CLASSES = [
    "valve",
    "gate valve",
    "ball valve",
    "check valve",
    "pump",
    "tank",
    "vessel",
    "equipment",
    "instrument",
    "flange",
    "reducer",
    "elbow",
    "tee",
    "motor",
    "symbol",
]

_model_lock = threading.Lock()
_model = None
_model_kind = "none"


def get_yolo_model():
    """Lazy-load YOLO model for valves / equipment / symbols.

    Preference order:
    1) custom trained weights at data/models/aec_symbols.pt
    2) YOLO-World open-vocabulary model with AEC class prompts
    """
    global _model, _model_kind
    if _model is not None:
        return _model, _model_kind

    with _model_lock:
        if _model is not None:
            return _model, _model_kind

        if CUSTOM_WEIGHTS.exists():
            from ultralytics import YOLO

            _model = YOLO(str(CUSTOM_WEIGHTS))
            _model_kind = "custom_aec_symbols"
            return _model, _model_kind

        from ultralytics import YOLOWorld

        ensure_models_dir()
        weights = str(WORLD_WEIGHTS) if WORLD_WEIGHTS.exists() else "yolov8s-world.pt"
        _model = YOLOWorld(weights)
        # If downloaded into CWD on first run, keep using cache next time via models dir.
        if not WORLD_WEIGHTS.exists():
            cwd_weights = Path("yolov8s-world.pt")
            if cwd_weights.exists():
                cwd_weights.replace(WORLD_WEIGHTS)
                _model = YOLOWorld(str(WORLD_WEIGHTS))
        _model.set_classes(AEC_CLASSES)
        _model_kind = "yolov8s-world"
        return _model, _model_kind


def recognise_symbols(image_bgr: np.ndarray, conf: float = 0.25) -> tuple[list[dict], dict[str, Any]]:
    """Run YOLO to recognise valves, equipment and drawing symbols."""
    model, kind = get_yolo_model()
    # Ultralytics accepts numpy BGR arrays.
    results = model.predict(source=image_bgr, conf=conf, verbose=False)
    symbols: list[dict] = []
    if not results:
        return symbols, {"model": kind, "count": 0}

    result = results[0]
    names = result.names or {}
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return symbols, {"model": kind, "count": 0}

    xyxy = boxes.xyxy.cpu().numpy()
    cls_ids = boxes.cls.cpu().numpy().astype(int)
    scores = boxes.conf.cpu().numpy()

    for index, (box, cls_id, score) in enumerate(zip(xyxy, cls_ids, scores)):
        x1, y1, x2, y2 = [float(v) for v in box]
        label = str(names.get(int(cls_id), f"class_{cls_id}"))
        symbols.append(
            {
                "id": f"yolo_{index + 1}",
                "type": "symbol",
                "label": label,
                "score": float(score),
                "shape": label,
                "x": x1,
                "y": y1,
                "w": max(1.0, x2 - x1),
                "h": max(1.0, y2 - y1),
                "area": max(1.0, (x2 - x1) * (y2 - y1)),
                "source": "yolo",
            }
        )

    return symbols, {"model": kind, "count": len(symbols), "classes": AEC_CLASSES}


def ensure_models_dir() -> Path:
    path = ROOT / "data" / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path
