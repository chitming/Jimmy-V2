from __future__ import annotations

from pathlib import Path

from ..db import LIBRARY_DIR, connect, dumps, loads, new_id, utc_now
from .drawing_ocr import get_drawing_ocr_run, list_drawing_ocr_runs
from .info_block_excel import list_info_block_rows, ocr_info_block_layout

# ISO A3 in millimetres. Default orientation is landscape (horizontal).
A3_PORTRAIT_MM = (297.0, 420.0)
A3_LANDSCAPE_MM = (420.0, 297.0)
PAPER_SIZE = "A3"


def _paper_mm(orientation: str) -> tuple[float, float]:
    return A3_LANDSCAPE_MM if orientation == "landscape" else A3_PORTRAIT_MM


def _contain_fit(content_w: float, content_h: float, frame_w: float, frame_h: float) -> dict:
    """Fit content into frame with letterboxing (normalized 0-1 frame coords)."""
    if content_w <= 0 or content_h <= 0:
        return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}
    scale = min(frame_w / content_w, frame_h / content_h)
    w = content_w * scale / frame_w
    h = content_h * scale / frame_h
    return {"x": (1.0 - w) / 2.0, "y": (1.0 - h) / 2.0, "w": w, "h": h}


def _page_context(page_id: str) -> dict | None:
    with connect() as conn:
        page = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
        if page is None:
            return None
        annotation = conn.execute(
            "SELECT information_block, drawing_canvas FROM annotations WHERE page_id = ?",
            (page_id,),
        ).fetchone()
    image_name = Path(page["image_path"]).name
    return {
        "page_id": page_id,
        "width": int(page["width"]),
        "height": int(page["height"]),
        "image_path": page["image_path"],
        "image_url": f"/media/pages/{image_name}",
        "information_block": loads(annotation["information_block"]) if annotation else None,
        "drawing_canvas": loads(annotation["drawing_canvas"]) if annotation else None,
    }


def _info_layout_items(info_row: dict) -> list[dict]:
    layout = info_row.get("layout") or []
    if layout:
        return layout

    # Re-OCR crop for layout if older rows have no boxes yet.
    image_path = LIBRARY_DIR / "Info Block" / info_row["segment_filename"]
    if image_path.exists():
        try:
            _raw, _fields, layout, _method = ocr_info_block_layout(image_path)
            return layout
        except Exception:
            pass

    fields = info_row.get("fields") or {}
    n = max(len(fields), 1)
    items = []
    for index, (key, value) in enumerate(fields.items(), start=1):
        items.append(
            {
                "key": key,
                "text": value,
                "box": {
                    "x": 0.04,
                    "y": 0.04 + (index - 1) * (0.9 / n),
                    "w": 0.92,
                    "h": max(0.04, 0.85 / n),
                },
            }
        )
    return items


def _map_drawing_point(
    px: float,
    py: float,
    *,
    draw_w: float,
    draw_h: float,
    draw_box: dict | None,
    fit: dict,
) -> tuple[float, float]:
    """Map a Stream B pixel into A3 paper-normalized coordinates."""
    nx = float(px) / max(draw_w, 1.0)
    ny = float(py) / max(draw_h, 1.0)
    if draw_box:
        page_x = float(draw_box["x"]) + nx * float(draw_box["w"])
        page_y = float(draw_box["y"]) + ny * float(draw_box["h"])
        return fit["x"] + page_x * fit["w"], fit["y"] + page_y * fit["h"]
    return fit["x"] + nx * fit["w"], fit["y"] + ny * fit["h"]


def _line_bounds(x1: float, y1: float, x2: float, y2: float) -> dict:
    pad = 0.004
    xmin, xmax = sorted((x1, x2))
    ymin, ymax = sorted((y1, y2))
    return {
        "x": max(0.0, xmin - pad),
        "y": max(0.0, ymin - pad),
        "w": max(0.008, xmax - xmin + 2 * pad),
        "h": max(0.008, ymax - ymin + 2 * pad),
    }


def _default_elements(
    *,
    page_id: str,
    info_row: dict | None,
    drawing_run: dict | None,
) -> list[dict]:
    """Build a deconstruct drawing worktop on A3 paper.

    Breaks Stream B into editable lines/circles/text, plus Stream A text,
    so the user can modify geometry and annotations on the sheet.
    """
    elements: list[dict] = []
    ctx = _page_context(page_id)
    paper_w, paper_h = A3_LANDSCAPE_MM

    # Fit frame: prefer full page when available, else drawing crop.
    if ctx:
        fit = _contain_fit(float(ctx["width"]), float(ctx["height"]), paper_w, paper_h)
        ref_url = ctx["image_url"]
        draw_box = ctx.get("drawing_canvas")
    elif drawing_run:
        dw = float(drawing_run.get("image_width") or 1)
        dh = float(drawing_run.get("image_height") or 1)
        fit = _contain_fit(dw, dh, paper_w, paper_h)
        ref_url = drawing_run.get("cleaned_url") or drawing_run.get("preview_url") or drawing_run.get("image_url")
        draw_box = None
    else:
        fit = {"x": 0.03, "y": 0.03, "w": 0.94, "h": 0.94}
        ref_url = None
        draw_box = None

    # Dim reference raster under deconstructed vectors.
    if ref_url:
        elements.append(
            {
                "id": "el_reference",
                "type": "page",
                "source": "original",
                "page_id": page_id,
                "label": "Reference raster",
                "image_url": ref_url,
                "x": fit["x"],
                "y": fit["y"],
                "w": fit["w"],
                "h": fit["h"],
                "locked": True,
                "opacity": 0.18,
            }
        )

    # --- Stream B deconstruction: lines, circles, annotation text ---
    if drawing_run:
        vectors = drawing_run.get("vectors") or {}
        dw = float(drawing_run.get("image_width") or 1)
        dh = float(drawing_run.get("image_height") or 1)
        map_kwargs = {"draw_w": dw, "draw_h": dh, "draw_box": draw_box, "fit": fit}

        for index, line in enumerate(vectors.get("lines") or [], start=1):
            x1, y1 = _map_drawing_point(line["x1"], line["y1"], **map_kwargs)
            x2, y2 = _map_drawing_point(line["x2"], line["y2"], **map_kwargs)
            bounds = _line_bounds(x1, y1, x2, y2)
            elements.append(
                {
                    "id": f"el_line_{index}",
                    "type": "line",
                    "source": "stream_b",
                    "page_id": page_id,
                    "label": f"Line {index}",
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "length": float(line.get("length") or 0),
                    **bounds,
                    "locked": False,
                    "editable": True,
                }
            )

        for index, circle in enumerate(vectors.get("circles") or [], start=1):
            cx, cy = _map_drawing_point(circle["cx"], circle["cy"], **map_kwargs)
            # Radius: map a point on the rim and take delta.
            rx, _ry = _map_drawing_point(
                float(circle["cx"]) + float(circle["r"]),
                float(circle["cy"]),
                **map_kwargs,
            )
            r = abs(rx - cx)
            elements.append(
                {
                    "id": f"el_circle_{index}",
                    "type": "circle",
                    "source": "stream_b",
                    "page_id": page_id,
                    "label": f"Circle {index}",
                    "cx": cx,
                    "cy": cy,
                    "r": r,
                    "x": max(0.0, cx - r),
                    "y": max(0.0, cy - r),
                    "w": min(1.0, 2 * r),
                    "h": min(1.0, 2 * r),
                    "locked": False,
                    "editable": True,
                }
            )

        for index, item in enumerate(drawing_run.get("items") or [], start=1):
            box = item.get("box") or {}
            # OCR boxes are already normalized to the drawing crop.
            if draw_box:
                page_x = float(draw_box["x"]) + float(box.get("x", 0)) * float(draw_box["w"])
                page_y = float(draw_box["y"]) + float(box.get("y", 0)) * float(draw_box["h"])
                page_w = float(box.get("w", 0.04)) * float(draw_box["w"])
                page_h = float(box.get("h", 0.02)) * float(draw_box["h"])
                x = fit["x"] + page_x * fit["w"]
                y = fit["y"] + page_y * fit["h"]
                w = max(0.02, page_w * fit["w"])
                h = max(0.015, page_h * fit["h"])
            else:
                x = fit["x"] + float(box.get("x", 0)) * fit["w"]
                y = fit["y"] + float(box.get("y", 0)) * fit["h"]
                w = max(0.02, float(box.get("w", 0.04)) * fit["w"])
                h = max(0.015, float(box.get("h", 0.02)) * fit["h"])
            elements.append(
                {
                    "id": f"el_btext_{index}",
                    "type": "text",
                    "source": "stream_b",
                    "page_id": page_id,
                    "label": f"Drawing text {index}",
                    "text": str(item.get("text") or ""),
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "locked": False,
                    "editable": True,
                }
            )

        if drawing_run.get("dxf_url"):
            elements.append(
                {
                    "id": "el_dxf_link",
                    "type": "meta",
                    "source": "stream_b",
                    "page_id": page_id,
                    "label": "DXF",
                    "text": "Stream B DXF linked",
                    "dxf_url": drawing_run.get("dxf_url"),
                    "x": 0.01,
                    "y": 0.01,
                    "w": 0.001,
                    "h": 0.001,
                    "locked": True,
                    "hidden": True,
                }
            )

    # --- Stream A Info Block text (original layout when available) ---
    if info_row and ctx and ctx.get("information_block"):
        info_box = ctx["information_block"]
        for index, item in enumerate(_info_layout_items(info_row), start=1):
            local = item["box"]
            page_x = float(info_box["x"]) + float(local["x"]) * float(info_box["w"])
            page_y = float(info_box["y"]) + float(local["y"]) * float(info_box["h"])
            page_bw = float(local["w"]) * float(info_box["w"])
            page_bh = float(local["h"]) * float(info_box["h"])
            elements.append(
                {
                    "id": f"el_info_{index}",
                    "type": "text",
                    "source": "stream_a",
                    "page_id": page_id,
                    "label": item.get("key") or f"Field{index}",
                    "field_key": item.get("key") or f"Field{index}",
                    "text": str(item.get("text") or ""),
                    "x": fit["x"] + page_x * fit["w"],
                    "y": fit["y"] + page_y * fit["h"],
                    "w": max(0.02, page_bw * fit["w"]),
                    "h": max(0.015, page_bh * fit["h"]),
                    "locked": False,
                    "editable": True,
                }
            )
    elif info_row:
        for index, item in enumerate(_info_layout_items(info_row), start=1):
            box = item["box"]
            elements.append(
                {
                    "id": f"el_info_{index}",
                    "type": "text",
                    "source": "stream_a",
                    "page_id": page_id,
                    "label": item.get("key") or f"Field{index}",
                    "field_key": item.get("key") or f"Field{index}",
                    "text": str(item.get("text") or ""),
                    "x": float(box["x"]),
                    "y": float(box["y"]),
                    "w": float(box["w"]),
                    "h": float(box["h"]),
                    "locked": False,
                    "editable": True,
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
    """Compose a deconstruct drawing worktop (lines + text) onto A3 paper."""
    if orientation not in {"landscape", "portrait"}:
        raise ValueError("orientation must be landscape or portrait")

    info_rows = list_info_block_rows()
    drawing_runs_by_page: dict[str, dict] = {}
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
        title = f"Deconstruct worktop · {title_bits[0]}"

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
