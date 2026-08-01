#!/usr/bin/env bash
# Helpers for opening CAD files on this VM.
set -euo pipefail

cmd="${1:-}"
file="${2:-}"

usage() {
  cat <<'EOF'
Usage:
  open-cad.sh dwf                 Start local DWF/DWFx web viewer
  open-cad.sh dxf <file.dxf>      Open DXF in LibreCAD
  open-cad.sh dxf2pdf <file.dxf>  Convert DXF to PDF with LibreCAD
  open-cad.sh pdf <file.pdf>      Open PDF (xdg-open / available viewer)

Installed tools:
  - LibreCAD      : DXF open / dxf2pdf
  - Inkscape      : DXF/SVG/PDF view & convert
  - DWF web viewer: tools/dwf-viewer (DWF/DWFx)
  - ezdxf         : Python DXF read/write (SheetSense backend)
EOF
}

case "$cmd" in
  dwf)
    exec "$(dirname "$0")/start-dwf-viewer.sh" "${3:-8787}"
    ;;
  dxf)
    [[ -n "$file" ]] || { echo "Missing DXF file"; exit 1; }
    exec librecad "$file"
    ;;
  dxf2pdf)
    [[ -n "$file" ]] || { echo "Missing DXF file"; exit 1; }
    out="${file%.dxf}.pdf"
    librecad dxf2pdf -o "$out" "$file"
    echo "Wrote $out"
    ;;
  pdf)
    [[ -n "$file" ]] || { echo "Missing PDF file"; exit 1; }
    if command -v xdg-open >/dev/null; then
      exec xdg-open "$file"
    fi
    exec inkscape "$file"
    ;;
  *)
    usage
    ;;
esac
