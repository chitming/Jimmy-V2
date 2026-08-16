#!/usr/bin/env bash
# Build a Windows installer zip for TDR.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${TDR_VERSION:-0.1.0}"
OUT_DIR="${1:-$ROOT/dist}"
ARTIFACT_DIR="${TDR_ARTIFACT_DIR:-/opt/cursor/artifacts}"
STAGE="$OUT_DIR/TDR-Windows"
ZIP_NAME="TDR-Windows-Setup-v${VERSION}.zip"

echo "==> Building frontend"
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run build

echo "==> Staging Windows package"
rm -rf "$STAGE"
mkdir -p "$STAGE/app/backend" "$STAGE/app/frontend"

# Backend source (no venv / caches / local DB blobs)
rsync -a \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '*.pyc' \
  --exclude 'data/uploads' \
  --exclude 'data/pages' \
  --exclude 'data/crops' \
  --exclude 'data/pipeline' \
  --exclude 'data/*.db' \
  --exclude 'data/*.db-journal' \
  "$ROOT/backend/" "$STAGE/app/backend/"

# Keep empty data scaffold so runtime can create dirs
mkdir -p "$STAGE/app/backend/data/library/Info Block" \
         "$STAGE/app/backend/data/library/Drawing" \
         "$STAGE/app/backend/data/uploads" \
         "$STAGE/app/backend/data/pages" \
         "$STAGE/app/backend/data/crops" \
         "$STAGE/app/backend/data/pipeline" \
         "$STAGE/app/backend/data/models"
# Preserve library samples if present (small JPGs help first-run demos)
if [[ -d "$ROOT/backend/data/library" ]]; then
  rsync -a "$ROOT/backend/data/library/" "$STAGE/app/backend/data/library/" || true
fi

# Prebuilt UI
rsync -a "$ROOT/frontend/dist/" "$STAGE/app/frontend/dist/"
# Also place a copy where the packaged FastAPI static path expects after install
mkdir -p "$STAGE/app/backend/app/static"
rsync -a "$ROOT/frontend/dist/" "$STAGE/app/backend/app/static/"

# Installer scripts (START_HERE.txt is the first file to open after unzip)
cp -a "$ROOT/installer/windows/." "$STAGE/"

# Version stamp
cat > "$STAGE/VERSION.txt" <<EOF
TDR $VERSION
Built: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Commit: $(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)
EOF

echo "==> Creating zip"
mkdir -p "$OUT_DIR" "$ARTIFACT_DIR"
ZIP_PATH="$OUT_DIR/$ZIP_NAME"
rm -f "$ZIP_PATH"
(
  cd "$OUT_DIR"
  zip -r -q "$ZIP_NAME" "TDR-Windows"
)

cp -f "$ZIP_PATH" "$ARTIFACT_DIR/$ZIP_NAME"
# Stable name for docs / PR links
cp -f "$ZIP_PATH" "$ARTIFACT_DIR/TDR-Windows-Setup.zip"
cp -f "$ZIP_PATH" "$OUT_DIR/TDR-Windows-Setup.zip"

SIZE=$(du -h "$ZIP_PATH" | cut -f1)
echo "==> Done"
echo "    $ZIP_PATH ($SIZE)"
echo "    $ARTIFACT_DIR/TDR-Windows-Setup.zip"
echo
echo "On Windows: unzip, then double-click setup.bat"
