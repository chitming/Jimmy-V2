# CAD viewers installed on this VM

## DWF / DWFx
Native Autodesk Design Review is Windows-only.

Installed here:
- **Local DWF web viewer**: `tools/dwf-viewer`
  ```bash
  ./scripts/start-dwf-viewer.sh
  # open http://127.0.0.1:8787 and choose a .dwf / .dwfx file
  ```
- Online fallback: https://viewer.autodesk.com

## DXF (SheetSense export)
- **LibreCAD**: `librecad file.dxf`
- Convert DXF → PDF: `librecad dxf2pdf -o out.pdf file.dxf`
- **Inkscape**: can open/import many DXF/PDF files
- **ezdxf** (Python): already in SheetSense backend

## Helper
```bash
./scripts/open-cad.sh          # show help
./scripts/open-cad.sh dwf      # start DWF viewer
./scripts/open-cad.sh dxf path/to/file.dxf
./scripts/open-cad.sh dxf2pdf path/to/file.dxf
```

## Excel (SheetSense Info Block export)
- **LibreOffice Calc** is installed for `.xlsx` inspection:
  ```bash
  ./scripts/open-excel.sh path/to/file.xlsx          # open in Calc (GUI)
  ./scripts/open-excel.sh inspect path/to/file.xlsx  # terminal preview
  ./scripts/open-excel.sh html path/to/file.xlsx     # convert to HTML
  ./scripts/open-excel.sh export-latest              # build + open latest Info Block Excel
  ```
