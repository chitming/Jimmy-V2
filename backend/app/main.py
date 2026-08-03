from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import (
    CROPS_DIR,
    LIBRARY_DIR,
    PAGES_DIR,
    PIPELINE_DIR,
    UPLOADS_DIR,
    connect,
    dumps,
    init_db,
    loads,
    new_id,
    row_to_dict,
    utc_now,
)
from .services.drawing_ocr import (
    get_drawing_dxf_path,
    get_drawing_ocr_run,
    list_drawing_ocr_runs,
    ocr_drawing_segments,
)
from .services.info_block_excel import (
    build_info_block_excel,
    list_info_block_rows,
    ocr_all_info_blocks,
)
from .services.sheet_canvas import (
    compose_sheet_canvas,
    get_sheet_canvas,
    list_sheet_canvases,
    update_sheet_canvas,
)
from .services.layout import compute_phash, labeled_count, predict_layout
from .services.library import get_segment_path, library_counts, list_library, save_page_segments
from .services.ocr import extract_information_block
from .services.render import render_pdf_pages, save_image_as_page

app = FastAPI(title="TDR API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media/pages", StaticFiles(directory=PAGES_DIR), name="pages")
app.mount("/media/crops", StaticFiles(directory=CROPS_DIR), name="crops")
app.mount("/media/library", StaticFiles(directory=LIBRARY_DIR), name="library")
app.mount("/media/pipeline", StaticFiles(directory=PIPELINE_DIR), name="pipeline")


class Box(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)


class AnnotationPayload(BaseModel):
    information_block: Box
    drawing_canvas: Box


class SheetCanvasUpdatePayload(BaseModel):
    elements: list[dict] | None = None
    title: str | None = None
    orientation: str | None = None
    status: str | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "labeled_pages": labeled_count()}


@app.get("/api/stats")
def stats() -> dict:
    with connect() as conn:
        drawings = conn.execute("SELECT COUNT(*) AS c FROM drawings").fetchone()["c"]
        pages = conn.execute("SELECT COUNT(*) AS c FROM pages").fetchone()["c"]
        labeled = conn.execute("SELECT COUNT(*) AS c FROM annotations").fetchone()["c"]
        extracted = conn.execute("SELECT COUNT(*) AS c FROM extractions").fetchone()["c"]
    counts = library_counts()
    return {
        "drawings": drawings,
        "pages": pages,
        "labeled": labeled,
        "extracted": extracted,
        "info_block_segments": counts["info_block"],
        "drawing_segments": counts["drawing"],
    }


@app.get("/api/library")
def get_library(kind: str | None = None) -> dict:
    if kind is not None and kind not in {"info_block", "drawing"}:
        raise HTTPException(400, "kind must be info_block or drawing")
    items = list_library(kind)
    return {
        "folders": ["Info Block", "Drawing"],
        "counts": library_counts(),
        "items": items,
    }


@app.get("/api/info-blocks")
def get_info_block_rows() -> dict:
    rows = list_info_block_rows()
    max_fields = max((row["field_count"] for row in rows), default=0)
    return {
        "count": len(rows),
        "max_fields": max_fields,
        "field_headers": [f"Field{i}" for i in range(1, max_fields + 1)],
        "rows": rows,
    }


@app.post("/api/info-blocks/ocr")
def run_info_block_ocr() -> dict:
    result = ocr_all_info_blocks()
    if result["processed"] == 0 and result["errors"]:
        raise HTTPException(400, detail=result)
    return result


@app.get("/api/info-blocks/export.xlsx")
def export_info_blocks_excel():
    rows = list_info_block_rows()
    if not rows:
        raise HTTPException(
            400,
            "No Info Block OCR rows yet. Run OCR on the Info Block library first.",
        )
    content = build_info_block_excel()
    headers = {
        "Content-Disposition": 'attachment; filename="tdr_info_blocks.xlsx"'
    }
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.get("/api/drawings-ocr")
def get_drawing_ocr_list() -> dict:
    runs = list_drawing_ocr_runs()
    return {
        "engine": "cleanup → lines → PP-OCRv6 → circles/arcs/symbols → DXF",
        "count": len(runs),
        "runs": runs,
    }


@app.post("/api/drawings-ocr/run")
def run_drawing_ocr(page_id: str | None = None) -> dict:
    result = ocr_drawing_segments(page_id=page_id)
    if result["processed"] == 0 and result["errors"]:
        raise HTTPException(400, detail=result)
    if result["processed"] == 0:
        raise HTTPException(400, "No Drawing segments found in the library yet.")
    return result


@app.get("/api/drawings-ocr/{page_id}")
def get_drawing_ocr(page_id: str) -> dict:
    run = get_drawing_ocr_run(page_id)
    if run is None:
        raise HTTPException(404, "No Drawing pipeline result for this page. Run the pipeline first.")
    return run


@app.get("/api/drawings-ocr/{page_id}/export.dxf")
def export_drawing_dxf(page_id: str):
    path = get_drawing_dxf_path(page_id)
    if path is None:
        raise HTTPException(404, "DXF not found. Run the Drawing pipeline first.")
    return FileResponse(
        path,
        media_type="application/dxf",
        filename=f"{page_id}.dxf",
    )


@app.get("/api/sheet-canvas")
def get_sheet_canvas_list() -> dict:
    sheets = list_sheet_canvases()
    return {
        "count": len(sheets),
        "paper_default": {
            "size": "A3",
            "orientation": "landscape",
            "width_mm": 420.0,
            "height_mm": 297.0,
        },
        "sheets": sheets,
    }


@app.post("/api/sheet-canvas/compose")
def post_compose_sheet_canvas(
    page_id: str | None = None,
    orientation: str = "landscape",
) -> dict:
    try:
        result = compose_sheet_canvas(page_id=page_id, orientation=orientation)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if result["processed"] == 0:
        raise HTTPException(400, "Nothing to compose. Run Stream A and/or Stream B first.")
    return result


@app.get("/api/sheet-canvas/{sheet_id}")
def get_one_sheet_canvas(sheet_id: str) -> dict:
    sheet = get_sheet_canvas(sheet_id)
    if sheet is None:
        raise HTTPException(404, "Sheet canvas not found")
    return sheet


@app.put("/api/sheet-canvas/{sheet_id}")
def put_sheet_canvas(sheet_id: str, payload: SheetCanvasUpdatePayload) -> dict:
    try:
        return update_sheet_canvas(
            sheet_id,
            elements=payload.elements,
            title=payload.title,
            orientation=payload.orientation,
            status=payload.status,
        )
    except KeyError:
        raise HTTPException(404, "Sheet canvas not found") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


@app.post("/api/drawings/upload")
async def upload_drawing(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(400, "Missing filename")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
        raise HTTPException(400, "Supported types: PDF, JPG, PNG, TIF, WEBP")

    drawing_id = new_id("dwg")
    saved_name = f"{drawing_id}{suffix}"
    dest = UPLOADS_DIR / saved_name
    content = await file.read()
    dest.write_bytes(content)

    source_type = "pdf" if suffix == ".pdf" else "image"
    if source_type == "pdf":
        rendered = render_pdf_pages(dest, drawing_id)
    else:
        rendered = save_image_as_page(dest, drawing_id)

    now = utc_now()
    page_rows = []
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO drawings (id, filename, source_type, page_count, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (drawing_id, file.filename, source_type, len(rendered), now),
        )
        for page in rendered:
            page_id = new_id("page")
            phash = compute_phash(Path(page["image_path"]))
            conn.execute(
                """
                INSERT INTO pages
                (id, drawing_id, page_index, width, height, image_path, phash, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'unlabeled', ?)
                """,
                (
                    page_id,
                    drawing_id,
                    page["page_index"],
                    page["width"],
                    page["height"],
                    page["image_path"],
                    phash,
                    now,
                ),
            )
            page_rows.append(
                {
                    "id": page_id,
                    "page_index": page["page_index"],
                    "width": page["width"],
                    "height": page["height"],
                    "image_url": f"/media/pages/{Path(page['image_path']).name}",
                    "status": "unlabeled",
                }
            )

    return {
        "id": drawing_id,
        "filename": file.filename,
        "source_type": source_type,
        "page_count": len(page_rows),
        "pages": page_rows,
    }


@app.get("/api/drawings")
def list_drawings() -> dict:
    with connect() as conn:
        drawings = conn.execute(
            "SELECT * FROM drawings ORDER BY created_at DESC"
        ).fetchall()
        result = []
        for drawing in drawings:
            pages = conn.execute(
                """
                SELECT p.*, a.id AS annotation_id, e.id AS extraction_id
                FROM pages p
                LEFT JOIN annotations a ON a.page_id = p.id
                LEFT JOIN extractions e ON e.page_id = p.id
                WHERE p.drawing_id = ?
                ORDER BY p.page_index
                """,
                (drawing["id"],),
            ).fetchall()
            result.append(
                {
                    **row_to_dict(drawing),
                    "pages": [
                        {
                            "id": p["id"],
                            "page_index": p["page_index"],
                            "width": p["width"],
                            "height": p["height"],
                            "image_url": f"/media/pages/{Path(p['image_path']).name}",
                            "status": p["status"],
                            "has_annotation": p["annotation_id"] is not None,
                            "has_extraction": p["extraction_id"] is not None,
                        }
                        for p in pages
                    ],
                }
            )
    return {"drawings": result}


@app.get("/api/pages/{page_id}")
def get_page(page_id: str) -> dict:
    with connect() as conn:
        page = conn.execute(
            """
            SELECT p.*, d.filename, d.source_type, d.id AS drawing_id
            FROM pages p
            JOIN drawings d ON d.id = p.drawing_id
            WHERE p.id = ?
            """,
            (page_id,),
        ).fetchone()
        if page is None:
            raise HTTPException(404, "Page not found")

        annotation = conn.execute(
            "SELECT * FROM annotations WHERE page_id = ?", (page_id,)
        ).fetchone()
        extraction = conn.execute(
            "SELECT * FROM extractions WHERE page_id = ?", (page_id,)
        ).fetchone()

    payload = {
        "id": page["id"],
        "drawing_id": page["drawing_id"],
        "filename": page["filename"],
        "source_type": page["source_type"],
        "page_index": page["page_index"],
        "width": page["width"],
        "height": page["height"],
        "image_url": f"/media/pages/{Path(page['image_path']).name}",
        "status": page["status"],
        "annotation": None,
        "extraction": None,
        "suggestion": predict_layout(page_id),
    }

    if annotation:
        with connect() as conn:
            segs = conn.execute(
                "SELECT kind, folder, filename, relative_path FROM segments WHERE page_id = ?",
                (page_id,),
            ).fetchall()
        segment_map = {
            row["kind"]: {
                "folder": row["folder"],
                "filename": row["filename"],
                "url": f"/media/library/{row['folder']}/{row['filename']}",
            }
            for row in segs
        }
        payload["annotation"] = {
            "information_block": loads(annotation["information_block"]),
            "drawing_canvas": loads(annotation["drawing_canvas"]),
            "updated_at": annotation["updated_at"],
            "segments": segment_map,
        }
    if extraction:
        info_seg = get_segment_path(page_id, "info_block")
        crop_url = (
            f"/media/library/Info Block/{info_seg.name}"
            if info_seg is not None
            else f"/media/crops/{page_id}.png"
        )
        payload["extraction"] = {
            "raw_text": extraction["raw_text"],
            "fields": loads(extraction["fields_json"]),
            "method": extraction["method"],
            "crop_url": crop_url,
            "created_at": extraction["created_at"],
        }
    return payload


@app.put("/api/pages/{page_id}/annotation")
def save_annotation(page_id: str, payload: AnnotationPayload) -> dict:
    now = utc_now()
    with connect() as conn:
        page = conn.execute(
            """
            SELECT p.*, d.filename AS source_filename
            FROM pages p
            JOIN drawings d ON d.id = p.drawing_id
            WHERE p.id = ?
            """,
            (page_id,),
        ).fetchone()
        if page is None:
            raise HTTPException(404, "Page not found")

        image_path = Path(page["image_path"])
        source_filename = page["source_filename"]
        page_index = int(page["page_index"])

        existing = conn.execute(
            "SELECT id FROM annotations WHERE page_id = ?", (page_id,)
        ).fetchone()
        info = payload.information_block.model_dump()
        canvas = payload.drawing_canvas.model_dump()

        if existing:
            conn.execute(
                """
                UPDATE annotations
                SET information_block = ?, drawing_canvas = ?, updated_at = ?
                WHERE page_id = ?
                """,
                (dumps(info), dumps(canvas), now, page_id),
            )
            annotation_id = existing["id"]
        else:
            annotation_id = new_id("ann")
            conn.execute(
                """
                INSERT INTO annotations
                (id, page_id, information_block, drawing_canvas, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (annotation_id, page_id, dumps(info), dumps(canvas), now, now),
            )

        conn.execute(
            "UPDATE pages SET status = 'labeled' WHERE id = ?",
            (page_id,),
        )

    segments = save_page_segments(
        page_id=page_id,
        image_path=image_path,
        original_filename=source_filename,
        page_index=page_index,
        information_block=info,
        drawing_canvas=canvas,
    )

    return {
        "id": annotation_id,
        "page_id": page_id,
        "information_block": info,
        "drawing_canvas": canvas,
        "labeled_total": labeled_count(),
        "library": {
            "info_block": segments["info_block"],
            "drawing": segments["drawing"],
        },
    }


@app.post("/api/pages/{page_id}/extract")
def extract_page(page_id: str) -> dict:
    with connect() as conn:
        page = conn.execute(
            """
            SELECT p.*, d.source_type, d.id AS drawing_id
            FROM pages p
            JOIN drawings d ON d.id = p.drawing_id
            WHERE p.id = ?
            """,
            (page_id,),
        ).fetchone()
        if page is None:
            raise HTTPException(404, "Page not found")

        annotation = conn.execute(
            "SELECT * FROM annotations WHERE page_id = ?", (page_id,)
        ).fetchone()
        if annotation is None:
            raise HTTPException(400, "Teach the information block before extracting")

        drawing = conn.execute(
            "SELECT * FROM drawings WHERE id = ?", (page["drawing_id"],)
        ).fetchone()

    info_box = loads(annotation["information_block"])
    upload_files = list(UPLOADS_DIR.glob(f"{page['drawing_id']}.*"))
    pdf_path = next((p for p in upload_files if p.suffix.lower() == ".pdf"), None)

    # Prefer the library JPG; fall back to a temporary crop path.
    library_info = get_segment_path(page_id, "info_block")
    if library_info is None:
        canvas_box = loads(annotation["drawing_canvas"])
        save_page_segments(
            page_id=page_id,
            image_path=Path(page["image_path"]),
            original_filename=drawing["filename"],
            page_index=page["page_index"],
            information_block=info_box,
            drawing_canvas=canvas_box,
        )
        library_info = get_segment_path(page_id, "info_block")

    crop_path = library_info if library_info is not None else CROPS_DIR / f"{page_id}.jpg"

    result = extract_information_block(
        image_path=Path(page["image_path"]),
        box=info_box,
        crop_path=crop_path,
        source_type=page["source_type"],
        pdf_path=pdf_path,
        page_index=page["page_index"],
        page_width=page["width"],
        page_height=page["height"],
        reuse_crop=library_info is not None,
    )

    now = utc_now()
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM extractions WHERE page_id = ?", (page_id,)
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE extractions
                SET raw_text = ?, fields_json = ?, method = ?, created_at = ?
                WHERE page_id = ?
                """,
                (
                    result["raw_text"],
                    dumps(result["fields"]),
                    result["method"],
                    now,
                    page_id,
                ),
            )
            extraction_id = existing["id"]
        else:
            extraction_id = new_id("ext")
            conn.execute(
                """
                INSERT INTO extractions
                (id, page_id, raw_text, fields_json, method, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    extraction_id,
                    page_id,
                    result["raw_text"],
                    dumps(result["fields"]),
                    result["method"],
                    now,
                ),
            )
        conn.execute(
            "UPDATE pages SET status = 'extracted' WHERE id = ?",
            (page_id,),
        )

    return {
        "id": extraction_id,
        "page_id": page_id,
        "raw_text": result["raw_text"],
        "fields": result["fields"],
        "method": result["method"],
        "crop_url": (
            f"/media/library/Info Block/{library_info.name}"
            if library_info is not None
            else f"/media/crops/{page_id}.jpg"
        ),
        "library_folder": "Info Block",
    }


@app.get("/api/pages/{page_id}/image")
def page_image(page_id: str):
    with connect() as conn:
        page = conn.execute(
            "SELECT image_path FROM pages WHERE id = ?", (page_id,)
        ).fetchone()
    if page is None:
        raise HTTPException(404, "Page not found")
    return FileResponse(page["image_path"])
