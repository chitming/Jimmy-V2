from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from ..db import LIBRARY_DIR, connect, new_id, utc_now

INFO_BLOCK_FOLDER = "Info Block"
DRAWING_FOLDER = "Drawing"

KIND_TO_FOLDER = {
    "info_block": INFO_BLOCK_FOLDER,
    "drawing": DRAWING_FOLDER,
}


def ensure_library_folders() -> None:
    for folder in KIND_TO_FOLDER.values():
        (LIBRARY_DIR / folder).mkdir(parents=True, exist_ok=True)


def _safe_stem(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^\w.\-]+", "_", stem).strip("._")
    return cleaned[:80] or "drawing"


def crop_to_jpg(image_path: Path, box: dict, out_path: Path, quality: int = 92) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        left = max(0, int(box["x"] * width))
        top = max(0, int(box["y"] * height))
        right = min(width, int((box["x"] + box["w"]) * width))
        bottom = min(height, int((box["y"] + box["h"]) * height))
        if right <= left:
            right = min(width, left + 1)
        if bottom <= top:
            bottom = min(height, top + 1)
        crop = rgb.crop((left, top, right, bottom))
        crop.save(out_path, format="JPEG", quality=quality, optimize=True)
    return out_path


def segment_filename(original_filename: str, page_index: int, page_id: str) -> str:
    return f"{_safe_stem(original_filename)}_p{page_index + 1}_{page_id}.jpg"


def save_page_segments(
    *,
    page_id: str,
    image_path: Path,
    original_filename: str,
    page_index: int,
    information_block: dict,
    drawing_canvas: dict,
) -> dict:
    """Crop taught regions and store JPGs in the segment library folders."""
    ensure_library_folders()
    filename = segment_filename(original_filename, page_index, page_id)

    saved = {}
    specs = [
        ("info_block", information_block),
        ("drawing", drawing_canvas),
    ]

    now = utc_now()
    with connect() as conn:
        for kind, box in specs:
            folder = KIND_TO_FOLDER[kind]
            rel_path = f"{folder}/{filename}"
            abs_path = LIBRARY_DIR / folder / filename
            crop_to_jpg(image_path, box, abs_path)

            existing = conn.execute(
                "SELECT id, relative_path FROM segments WHERE page_id = ? AND kind = ?",
                (page_id, kind),
            ).fetchone()

            if existing:
                # Remove previous file if the name changed.
                old = LIBRARY_DIR / existing["relative_path"]
                if old.exists() and old != abs_path:
                    old.unlink(missing_ok=True)
                conn.execute(
                    """
                    UPDATE segments
                    SET folder = ?, filename = ?, relative_path = ?, created_at = ?
                    WHERE id = ?
                    """,
                    (folder, filename, rel_path, now, existing["id"]),
                )
                segment_id = existing["id"]
            else:
                segment_id = new_id("seg")
                conn.execute(
                    """
                    INSERT INTO segments
                    (id, page_id, kind, folder, filename, relative_path, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (segment_id, page_id, kind, folder, filename, rel_path, now),
                )

            saved[kind] = {
                "id": segment_id,
                "kind": kind,
                "folder": folder,
                "filename": filename,
                "relative_path": rel_path,
                "path": str(abs_path),
                "url": f"/media/library/{folder}/{filename}",
            }

    return saved


def list_library(kind: str | None = None) -> list[dict]:
    ensure_library_folders()
    query = """
        SELECT s.*, p.page_index, p.drawing_id, d.filename AS source_filename
        FROM segments s
        JOIN pages p ON p.id = s.page_id
        JOIN drawings d ON d.id = p.drawing_id
    """
    params: tuple = ()
    if kind:
        query += " WHERE s.kind = ?"
        params = (kind,)
    query += " ORDER BY s.created_at DESC"

    with connect() as conn:
        rows = conn.execute(query, params).fetchall()

    items = []
    for row in rows:
        abs_path = LIBRARY_DIR / row["relative_path"]
        items.append(
            {
                "id": row["id"],
                "page_id": row["page_id"],
                "drawing_id": row["drawing_id"],
                "kind": row["kind"],
                "folder": row["folder"],
                "filename": row["filename"],
                "source_filename": row["source_filename"],
                "page_index": row["page_index"],
                "created_at": row["created_at"],
                "exists": abs_path.exists(),
                "url": f"/media/library/{row['folder']}/{row['filename']}",
            }
        )
    return items


def library_counts() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT kind, COUNT(*) AS c FROM segments GROUP BY kind"
        ).fetchall()
    counts = {"info_block": 0, "drawing": 0}
    for row in rows:
        counts[row["kind"]] = int(row["c"])
    return counts


def get_segment_path(page_id: str, kind: str) -> Path | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT relative_path FROM segments WHERE page_id = ? AND kind = ?",
            (page_id, kind),
        ).fetchone()
    if row is None:
        return None
    path = LIBRARY_DIR / row["relative_path"]
    return path if path.exists() else None
