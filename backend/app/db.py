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
DB_PATH = DATA_DIR / "sheetsense.db"

for path in (UPLOADS_DIR, PAGES_DIR, CROPS_DIR, INFO_BLOCK_DIR, DRAWING_DIR):
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
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def dumps(obj: Any) -> str:
    return json.dumps(obj)


def loads(text: str) -> Any:
    return json.loads(text)
