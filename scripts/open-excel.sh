#!/usr/bin/env bash
# Open / inspect Excel (.xlsx) files on this VM with LibreOffice Calc.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cmd="${1:-}"
file="${2:-}"

usage() {
  cat <<'EOF'
Usage:
  open-excel.sh <file.xlsx>           Open Excel in LibreOffice Calc (GUI)
  open-excel.sh inspect <file.xlsx>   Print sheet preview in the terminal
  open-excel.sh html <file.xlsx>      Convert to HTML for browser inspection
  open-excel.sh csv <file.xlsx>       Convert to CSV and print path
  open-excel.sh export-latest         Build TDR Info Block Excel, then open it

Installed tool:
  - LibreOffice Calc  : open / convert .xlsx .xls .ods
EOF
}

need_file() {
  [[ -n "${1:-}" ]] || { echo "Missing Excel file"; usage; exit 1; }
  [[ -f "$1" ]] || { echo "File not found: $1"; exit 1; }
}

open_gui() {
  need_file "$1"
  if command -v libreoffice >/dev/null; then
    exec libreoffice --calc "$1"
  fi
  if command -v soffice >/dev/null; then
    exec soffice --calc "$1"
  fi
  echo "LibreOffice Calc is not installed."
  exit 1
}

to_html() {
  need_file "$1"
  outdir="$(mktemp -d /tmp/tdr-xlsx-XXXXXX)"
  libreoffice --headless --convert-to html --outdir "$outdir" "$1" >/dev/null
  html="$(find "$outdir" -maxdepth 1 -name '*.html' | head -n 1)"
  [[ -n "$html" ]] || { echo "HTML conversion failed"; exit 1; }
  echo "$html"
}

to_csv() {
  need_file "$1"
  outdir="$(mktemp -d /tmp/tdr-xlsx-XXXXXX)"
  libreoffice --headless --convert-to csv --outdir "$outdir" "$1" >/dev/null
  csv="$(find "$outdir" -maxdepth 1 -name '*.csv' | head -n 1)"
  [[ -n "$csv" ]] || { echo "CSV conversion failed"; exit 1; }
  echo "$csv"
}

inspect_terminal() {
  need_file "$1"
  csv="$(to_csv "$1")"
  echo "=== $(basename "$1") ==="
  if command -v column >/dev/null; then
    column -t -s, "$csv" | head -n 40
  else
    head -n 40 "$csv"
  fi
  echo
  echo "(preview from $csv)"
}

export_latest() {
  local out="$ROOT/backend/data/exports/tdr_info_blocks.xlsx"
  mkdir -p "$(dirname "$out")"
  (
    cd "$ROOT/backend"
    PYTHONPATH=. .venv/bin/python - <<'PY'
from pathlib import Path
from app.services.info_block_excel import build_info_block_excel
out = Path("data/exports/tdr_info_blocks.xlsx")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(build_info_block_excel())
print(out.resolve())
PY
  )
  echo "Wrote $out"
  open_gui "$out"
}

case "$cmd" in
  ""|-h|--help|help)
    usage
    ;;
  inspect)
    inspect_terminal "$file"
    ;;
  html)
    html="$(to_html "$file")"
    echo "HTML: $html"
    if command -v xdg-open >/dev/null; then
      xdg-open "$html" >/dev/null 2>&1 || true
    fi
    ;;
  csv)
    csv="$(to_csv "$file")"
    echo "CSV: $csv"
    ;;
  export-latest)
    export_latest
    ;;
  *.xlsx|*.xls|*.ods)
    open_gui "$cmd"
    ;;
  *)
    # Allow: open-excel.sh path/to/file.xlsx
    if [[ -f "$cmd" ]]; then
      open_gui "$cmd"
    else
      usage
      exit 1
    fi
    ;;
esac
