from __future__ import annotations

from pathlib import Path

from ..db import LIBRARY_DIR, PIPELINE_DIR, connect, dumps, loads, new_id, utc_now
from .drawing_pipeline import run_drawing_pipeline


ENGINE_NAME = "OpenCV + Shapely + YOLO + ezdxf"


def _run_payload(row) -> dict:
    page_id = row["page_id"]
    preview_name = f"{page_id}/preview.png"
    cleaned_name = f"{page_id}/cleaned.png"
    has_preview = bool(row["preview_path"]) and Path(row["preview_path"]).exists() if row["preview_path"] else False
    has_dxf = bool(row["dxf_path"]) and Path(row["dxf_path"]).exists() if row["dxf_path"] else False
    return {
        "id": row["id"],
        "segment_id": row["segment_id"],
        "page_id": page_id,
        "source_filename": row["source_filename"],
        "segment_filename": row["segment_filename"],
        "page_index": row["page_index"],
        "image_width": row["image_width"],
        "image_height": row["image_height"],
        "engine": row["engine"],
        "items": [],
        "item_count": 0,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "vectors": loads(row["vectors_json"]) if row["vectors_json"] else {"lines": [], "circles": [], "arcs": [], "symbols": []},
        "stages": loads(row["stages_json"]) if row["stages_json"] else [],
        "counts": loads(row["counts_json"]) if row["counts_json"] else {},
        "image_url": f"/media/library/Drawing/{row['segment_filename']}",
        "preview_url": f"/media/pipeline/{preview_name}" if has_preview else None,
        "cleaned_url": f"/media/pipeline/{cleaned_name}" if row["cleaned_path"] else None,
        "dxf_url": f"/api/drawings-ocr/{page_id}/export.dxf" if has_dxf else None,
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


def get_drawing_dxf_path(page_id: str) -> Path | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT dxf_path FROM drawing_ocr_runs WHERE page_id = ?",
            (page_id,),
        ).fetchone()
    if row is None or not row["dxf_path"]:
        return None
    path = Path(row["dxf_path"])
    return path if path.exists() else None


def ocr_drawing_segments(page_id: str | None = None) -> dict:
    """Run Stream B geometry pipeline on Drawing library segments (no OCR)."""
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
        work_dir = PIPELINE_DIR / seg["page_id"]
        try:
            result = run_drawing_pipeline(image_path, work_dir)
        except Exception as exc:  # noqa: BLE001
            errors.append({"segment_id": seg["id"], "error": str(exc)})
            continue

        with connect() as conn:
            existing = conn.execute(
                "SELECT id FROM drawing_ocr_runs WHERE segment_id = ?",
                (seg["id"],),
            ).fetchone()
            values = (
                seg["source_filename"],
                seg["filename"],
                seg["page_index"],
                result["image_width"],
                result["image_height"],
                result["engine"],
                dumps([]),
                0,
                dumps(result["vectors"]),
                dumps(result["stages"]),
                dumps(result["counts"]),
                result["cleaned_path"],
                result["preview_path"],
                result["dxf_path"],
                now,
                seg["id"],
            )
            if existing:
                conn.execute(
                    """
                    UPDATE drawing_ocr_runs
                    SET source_filename = ?, segment_filename = ?, page_index = ?,
                        image_width = ?, image_height = ?, engine = ?,
                        items_json = ?, item_count = ?, status = 'complete',
                        vectors_json = ?, stages_json = ?, counts_json = ?,
                        cleaned_path = ?, preview_path = ?, dxf_path = ?,
                        updated_at = ?
                    WHERE segment_id = ?
                    """,
                    values,
                )
                run_id = existing["id"]
            else:
                run_id = new_id("docr")
                conn.execute(
                    """
                    INSERT INTO drawing_ocr_runs
                    (id, segment_id, page_id, source_filename, segment_filename,
                     page_index, image_width, image_height, engine, items_json,
                     item_count, status, vectors_json, stages_json, counts_json,
                     cleaned_path, preview_path, dxf_path, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'complete', ?, ?, ?, ?, ?, ?, ?, ?)
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
                        dumps([]),
                        0,
                        dumps(result["vectors"]),
                        dumps(result["stages"]),
                        dumps(result["counts"]),
                        result["cleaned_path"],
                        result["preview_path"],
                        result["dxf_path"],
                        now,
                        now,
                    ),
                )

        processed.append(
            {
                "id": run_id,
                "page_id": seg["page_id"],
                "segment_filename": seg["filename"],
                "item_count": 0,
                "counts": result["counts"],
                "dxf_url": f"/api/drawings-ocr/{seg['page_id']}/export.dxf",
                "preview_url": f"/media/pipeline/{seg['page_id']}/preview.png",
            }
        )

    return {
        "engine": ENGINE_NAME,
        "pipeline": [
            "OpenCV — detect lines, circles and contours",
            "Shapely — join and clean geometry",
            "YOLO — recognise valves, equipment and symbols",
            "ezdxf — generate the DXF file",
        ],
        "processed": len(processed),
        "errors": errors,
        "runs": processed,
        "all_runs": list_drawing_ocr_runs(),
    }
