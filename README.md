# SheetSense (Jimmy-V2)

Teachable layout software for technical drawings.

## What it does

1. Upload a **vector PDF** or **JPG/PNG**
2. Teach only two regions:
   - **Information block** (title block / company info)
   - **Drawing canvas** (main geometry area)
3. SheetSense learns from your teaching and suggests those regions on the next similar sheet
4. Every taught region is saved as a **JPG** into a segment library:
   - `backend/data/library/Info Block/`
   - `backend/data/library/Drawing/`
5. Extract text from the information block (native PDF text when available, OCR otherwise)

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

System dependency for OCR: `tesseract-ocr`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Segment library

When you click **Save teaching**, SheetSense crops both boxes and stores:

```text
backend/data/library/
  Info Block/
    MyDrawing_p1_page_abc123.jpg
  Drawing/
    MyDrawing_p1_page_abc123.jpg
```

Browse them in the app at `/library`.

## How learning works (v1)

No cloud vision account required for the first version.

- Each taught page stores normalized boxes + a perceptual image hash
- New pages get a **few-shot suggestion** from the nearest previously taught sheets
- You accept or correct the boxes → the memory improves
- Corrected boxes overwrite the JPG segments in the library folders

## Project layout

```
backend/   FastAPI + SQLite + PyMuPDF + Tesseract
frontend/  React + Vite teach UI
```
