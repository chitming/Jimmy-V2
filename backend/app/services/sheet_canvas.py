from __future__ import annotations

from ..db import connect, dumps, loads, new_id, utc_now
from .drawing_ocr import get_drawing_ocr_run
from .info_block_excel import list_info_block_rows

# ISO A3 in millimetres. Default orientation is landscape (horizontal).
A3_PORTRAIT_MM = (297.0, 420.0)
A3_LANDSCAPE_MM = (420.0, 297.0)
PAPER_SIZE = "A3"


def _paper_mm(orientation: str) -> tuple[float, float]:
    return A3_LANDSCAPE_MM if orientation == "landscape" else A3_PORTRAIT_MM


def _default_elements(
    *,
    page_id: str,
    info_row: dict | None,
    drawing_run: dict | None,
) -> list[dict]:
    """Place Stream A (info) + Stream B (drawing) onto one A3 landscape sheet."""
    elements: list[dict] = []

    # Main drawing area (left ~72% of the sheet).
    if drawing_run:
        image_url = drawing_run.get("preview_url") or drawing_run.get("image_url")
        elements.append(
            {
                "id": "el_drawing",
                "type": "drawing",
                "source": "stream_b",
                "page_id": page_id,
                "label": "Drawing (Stream B)",
                "image_url": image_url,
                "dxf_url": drawing_run.get("dxf_url"),
                "x": 0.03,
                "y": 0.05,
                "w": 0.70,
                "h": 0.90,
                "locked": False,
            }
        )

    # Info Block title strip (right side) — Stream A fields as editable text.
    if info_row:
        fields = info_row.get("fields") or {}
        field_items = sorted(
            ((k, v) for k, v in fields.items() if str(v).strip()),
            key=lambda kv: int(kv[0].replace("Field", "") or 0),
        )
        if not field_items and info_row.get("raw_text"):
            field_items = [("Field1", str(info_row["raw_text"])[:240])]

        panel_x, panel_y, panel_w = 0.76, 0.05, 0.21
        header_h = 0.07
        elements.append(
            {
                "id": "el_info_header",
                "type": "label",
                "source": "stream_a",
                "page_id": page_id,
                "label": "Info Block",
                "text": "INFO BLOCK",
                "x": panel_x,
                "y": panel_y,
                "w": panel_w,
                "h": header_h,
                "locked": False,
            }
        )
        row_h = min(0.10, max(0.05, (0.90 - header_h) / max(len(field_items), 1)))
        for index, (key, value) in enumerate(field_items):
            elements.append(
                {
                    "id": f"el_info_{index + 1}",
                    "type": "text",
                    "source": "stream_a",
                    "page_id": page_id,
                    "label": key,
                    "field_key": key,
                    "text": str(value),
                    "x": panel_x,
                    "y": panel_y + header_h + index * row_h,
                    "w": panel_w,
                    "h": row_h * 0.92,
                    "locked": False,
                }
            )

    return elements


def _payload(row) -> dict:
    paper = loads(row["paper_json"]) if row["paper_json"] else {}
    elements = loads(row["elements_json"]) if row["elements_json"] else []
    return {
        "id": row["id"],
        "page_id": row["page_id"],
        "title": row["title"],
        "paper": paper,
        "elements": elements,
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "edit_url": f"/sheet-canvas/{row['id']}",
    }


def list_sheet_canvases() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM sheet_canvases ORDER BY updated_at DESC"
        ).fetchall()
    return [_payload(row) for row in rows]


def get_sheet_canvas(sheet_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM sheet_canvases WHERE id = ?",
            (sheet_id,),
        ).fetchone()
    return _payload(row) if row else None


def compose_sheet_canvas(
    page_id: str | None = None,
    *,
    orientation: str = "landscape",
) -> dict:
    """Compose Stream A + Stream B results onto one A3 sheet (landscape default)."""
    if orientation not in {"landscape", "portrait"}:
        raise ValueError("orientation must be landscape or portrait")

    info_rows = list_info_block_rows()
    drawing_runs_by_page: dict[str, dict] = {}
    from .drawing_ocr import list_drawing_ocr_runs

    for run in list_drawing_ocr_runs():
        drawing_runs_by_page[run["page_id"]] = run

    info_by_page = {row["page_id"]: row for row in info_rows}
    candidate_ids = sorted(set(info_by_page) | set(drawing_runs_by_page))
    if page_id:
        if page_id not in info_by_page and get_drawing_ocr_run(page_id) is None:
            raise KeyError(f"No Stream A or Stream B result for page {page_id}")
        target_ids = [page_id]
    else:
        if not candidate_ids:
            raise KeyError("No Stream A or Stream B results yet. Run Stream A and/or Stream B first.")
        target_ids = candidate_ids

    composed = []
    now = utc_now()
    width_mm, height_mm = _paper_mm(orientation)

    for pid in target_ids:
        info_row = info_by_page.get(pid)
        drawing_run = drawing_runs_by_page.get(pid) or get_drawing_ocr_run(pid)
        if info_row is None and drawing_run is None:
            continue

        title_bits = []
        if info_row:
            title_bits.append(info_row.get("source_filename") or pid)
        elif drawing_run:
            title_bits.append(drawing_run.get("source_filename") or pid)
        title = f"A3 sheet · {title_bits[0]}"

        paper = {
            "size": PAPER_SIZE,
            "orientation": orientation,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "unit": "mm",
        }
        elements = _default_elements(page_id=pid, info_row=info_row, drawing_run=drawing_run)

        with connect() as conn:
            existing = conn.execute(
                "SELECT id FROM sheet_canvases WHERE page_id = ?",
                (pid,),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE sheet_canvases
                    SET title = ?, paper_json = ?, elements_json = ?,
                        status = 'draft', updated_at = ?
                    WHERE page_id = ?
                    """,
                    (title, dumps(paper), dumps(elements), now, pid),
                )
                sheet_id = existing["id"]
            else:
                sheet_id = new_id("sheet")
                conn.execute(
                    """
                    INSERT INTO sheet_canvases
                    (id, page_id, title, paper_json, elements_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
                    """,
                    (sheet_id, pid, title, dumps(paper), dumps(elements), now, now),
                )

        sheet = get_sheet_canvas(sheet_id)
        assert sheet is not None
        composed.append(sheet)

    return {
        "paper_default": {
            "size": PAPER_SIZE,
            "orientation": "landscape",
            "width_mm": A3_LANDSCAPE_MM[0],
            "height_mm": A3_LANDSCAPE_MM[1],
        },
        "processed": len(composed),
        "sheets": composed,
        "all_sheets": list_sheet_canvases(),
    }


def update_sheet_canvas(
    sheet_id: str,
    *,
    elements: list[dict] | None = None,
    title: str | None = None,
    orientation: str | None = None,
    status: str | None = None,
) -> dict:
    sheet = get_sheet_canvas(sheet_id)
    if sheet is None:
        raise KeyError("Sheet canvas not found")

    paper = dict(sheet["paper"])
    paper["size"] = PAPER_SIZE
    if orientation is not None:
        if orientation not in {"landscape", "portrait"}:
            raise ValueError("orientation must be landscape or portrait")
        paper["orientation"] = orientation
        paper["width_mm"], paper["height_mm"] = _paper_mm(orientation)

    next_elements = elements if elements is not None else sheet["elements"]
    next_title = title if title is not None else sheet["title"]
    next_status = status if status is not None else sheet["status"]
    if next_status not in {"draft", "ready"}:
        raise ValueError("status must be draft or ready")

    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            UPDATE sheet_canvases
            SET title = ?, paper_json = ?, elements_json = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_title, dumps(paper), dumps(next_elements), next_status, now, sheet_id),
        )
    result = get_sheet_canvas(sheet_id)
    assert result is not None
    return result
