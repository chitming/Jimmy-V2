# AGENTS.md

## Cursor Cloud specific instructions

### Services
SheetSense is a two-service full-stack app (see `README.md` for the product overview and standard run commands):
- Backend: FastAPI + Uvicorn on port `8000` (`backend/app/main.py`). SQLite + local files under `backend/data/` (auto-created on startup, gitignored). No external DB/cache/queue and no secrets/API keys required.
- Frontend: React + Vite dev server on port `5173` (`frontend/`). Vite proxies `/api` and `/media` to `http://127.0.0.1:8000`, so start the backend too when testing the UI.

### Running (dev)
- Backend: `cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Frontend: `cd frontend && npm run dev`
- Lint (frontend only): `cd frontend && npm run lint` (oxlint). There is no backend/test framework configured.

### Non-obvious notes
- System dependency `tesseract-ocr` (apt) is required only for the OCR text-extraction path (`POST /api/pages/{id}/extract`) on image uploads or PDFs lacking vector text. It is installed in the VM image, not by the update script. Upload/teach/suggest/library flows work without it. Vector PDFs use native text extraction (`method: pdf_text`); images use tesseract (`method: ocr`).
- The Python venv lives at `backend/.venv` and is created/refreshed by the update script. The convenience scripts in `scripts/` assume that venv already exists.
- Backend hot-reload (`--reload`) watches Python source only; if you reinstall Python deps you must restart uvicorn to pick them up.
