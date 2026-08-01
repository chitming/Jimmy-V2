from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PAGES_DIR = DATA_DIR / "pages"
CROPS_DIR = DATA_DIR / "crops"
LIBRARY_DIR = DATA_DIR / "library"
INFO_BLOCK_DIR = LIBRARY_DIR / "Info Block"
DRAWING_DIR = LIBRARY_DIR / "Drawing"
PIPELINE_DIR = DATA_DIR / "pipeline"
DB_PATH = DATA_DIR / "sheetsense.db"

for path in (UPLOADS_DIR, PAGES_DIR, CROPS_DIR, INFO_BLOCK_DIR, DRAWING_DIR, PIPELINE_DIR):
    path.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    with _lock:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS drawings (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                source_type TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pages (
                id TEXT PRIMARY KEY,
                drawing_id TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                phash TEXT,
                status TEXT NOT NULL DEFAULT 'unlabeled',
                created_at TEXT NOT NULL,
                FOREIGN KEY(drawing_id) REFERENCES drawings(id)
            );

            CREATE TABLE IF NOT EXISTS annotations (
                id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL UNIQUE,
                information_block TEXT NOT NULL,
                drawing_canvas TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(page_id) REFERENCES pages(id)
            );

            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL UNIQUE,
                raw_text TEXT NOT NULL,
                fields_json TEXT NOT NULL,
                method TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(page_id) REFERENCES pages(id)
            );

            CREATE TABLE IF NOT EXISTS segments (
                id TEXT PRIMARY KEY,
                page_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                folder TEXT NOT NULL,
                filename TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(page_id, kind),
                FOREIGN KEY(page_id) REFERENCES pages(id)
            );

            CREATE TABLE IF NOT EXISTS info_block_rows (
                id TEXT PRIMARY KEY,
                segment_id TEXT NOT NULL UNIQUE,
                page_id TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                segment_filename TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                raw_text TEXT NOT NULL,
                fields_json TEXT NOT NULL,
                field_count INTEGER NOT NULL,
                method TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(segment_id) REFERENCES segments(id),
                FOREIGN KEY(page_id) REFERENCES pages(id)
            );

            CREATE TABLE IF NOT EXISTS drawing_ocr_runs (
                id TEXT PRIMARY KEY,
                segment_id TEXT NOT NULL UNIQUE,
                page_id TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                segment_filename TEXT NOT NULL,
                page_index INTEGER NOT NULL,
                image_width INTEGER NOT NULL,
                image_height INTEGER NOT NULL,
                engine TEXT NOT NULL,
                items_json TEXT NOT NULL,
                item_count INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                vectors_json TEXT,
                stages_json TEXT,
                counts_json TEXT,
                cleaned_path TEXT,
                preview_path TEXT,
                dxf_path TEXT,
                FOREIGN KEY(segment_id) REFERENCES segments(id),
                FOREIGN KEY(page_id) REFERENCES pages(id)
            );
            """
        )
        _ensure_column(conn, "drawing_ocr_runs", "vectors_json", "TEXT")
        _ensure_column(conn, "drawing_ocr_runs", "stages_json", "TEXT")
        _ensure_column(conn, "drawing_ocr_runs", "counts_json", "TEXT")
        _ensure_column(conn, "drawing_ocr_runs", "cleaned_path", "TEXT")
        _ensure_column(conn, "drawing_ocr_runs", "preview_path", "TEXT")
        _ensure_column(conn, "drawing_ocr_runs", "dxf_path", "TEXT")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    names = {row["name"] for row in rows}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def dumps(obj: Any) -> str:
    return json.dumps(obj)


def loads(text: str) -> Any:
    return json.loads(text)
