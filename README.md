# TDR — Technical Drawing Reader (Jimmy-V2)

Teachable layout software for technical drawings.

## What it does

1. Upload a **vector PDF** or **JPG/PNG**
2. Teach only two regions:
   - **Information block** (title block / company info)
   - **Drawing canvas** (main geometry area)
3. TDR learns from your teaching and suggests those regions on the next similar sheet
4. Every taught region is saved as a **JPG** into a segment library:
   - `backend/data/library/Info Block/`
   - `backend/data/library/Drawing/`
5. Extract text from the information block (native PDF text when available, OCR otherwise)

## Quick start

### Windows installer

1. Download **`TDR-Windows-Setup.zip`** (from this agent’s artifacts, or build it below)
2. Unzip and open **`START_HERE.txt`**
3. Double-click **`setup.bat`**
4. Start TDR from the Desktop shortcut → opens http://127.0.0.1:8000/

Build the zip on a dev machine:

```bash
./scripts/build-windows-package.sh
# → dist/TDR-Windows-Setup.zip
```

### Backend (dev)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

System dependency for OCR: `tesseract-ocr`

### Frontend (dev)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

When `frontend/dist` (or `backend/app/static`) exists, the API also serves the UI at http://127.0.0.1:8000/

## Segment library

When you click **Accept**, TDR crops both boxes and stores:

```text
backend/data/library/
  Info Block/
    MyDrawing_p1_page_abc123.jpg
  Drawing/
    MyDrawing_p1_page_abc123.jpg
```

Browse them in the app at `/library`.

## Stream A — Info Block → Excel

On the Segment library page:

1. Click **OCR Info Blocks**
2. Text is stored as generic `Field1`, `Field2`, `Field3`, … (no assumed labels)
3. Click **Download Excel** → `tdr_info_blocks.xlsx`

On this VM, inspect Excel with LibreOffice Calc:
```bash
./scripts/open-excel.sh export-latest              # build + open latest export
./scripts/open-excel.sh inspect path/to/file.xlsx  # terminal preview
```

## Stream B — Drawing pipeline → DXF

One Drawing image runs one loop and exports one DXF:

```
Drawing image
    ↓
Image cleanup and deskew
    ↓
Raster-to-vector line detection
    ↓
PaddleOCR for annotations
    ↓
Circle, arc and symbol detection
    ↓
Export to DXF
```

1. Click **Run Drawing pipeline** (loops each Drawing JPG once)
2. Download the matching `.dxf` (vector preview is also generated)

Optional: place a fine-tuned weights file at `backend/data/models/aec_symbols.pt` to replace YOLO-World open-vocab detection.

## Sheet canvas — deconstruct worktop

After Stream A and Stream B:

1. Click **Compose deconstruct worktop**
2. Stream B is broken into editable **lines**, **circles**, and **text** on A3 landscape paper
3. Stream A Info Block fields are included as editable text
4. Drag parts, edit text, delete unwanted geometry; Save sheet when done

## How learning works (v1)

No cloud vision account required for the first version.

1. Machine selects Info Block + Drawing first (from prior accepts, or AEC default)
2. User corrects only if wrong
3. **Accept** = final agreement → save learning example + library JPGs
4. Next sheet uses that agreement to propose better boxes

## Project layout

```
backend/   FastAPI + SQLite + PyMuPDF + Tesseract
frontend/  React + Vite teach UI
```
