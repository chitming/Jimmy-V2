from __future__ import annotations

from pathlib import Path

import cv2
import ezdxf
import numpy as np

def cleanup_and_deskew(image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict]:
    """Grayscale cleanup + deskew for AEC drawing rasters.

    Returns: deskewed_gray (OCR-friendly), cleaned_gray (binary look), binary_inv, meta
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    binary = cv2.adaptiveThreshold(
        blur,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        25,
        8,
    )

    coords = np.column_stack(np.where(binary > 0))
    angle = 0.0
    if len(coords) >= 50:
        _rect = cv2.minAreaRect(coords)
        angle = float(_rect[-1])
        # minAreaRect angle convention: normalize toward upright.
        if angle < -45:
            angle = 90.0 + angle
        elif angle > 45:
            angle = angle - 90.0
        # Only deskew modest skew; ignore near-zero noise.
        if abs(angle) < 0.3 or abs(angle) > 15:
            angle = 0.0

    deskewed_gray = gray
    if abs(angle) >= 0.3:
        h, w = gray.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        deskewed_gray = cv2.warpAffine(
            gray,
            matrix,
            (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        binary = cv2.warpAffine(
            binary,
            matrix,
            (w, h),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

    # Light morphology to reconnect broken linework.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    cleaned_bin = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    cleaned_gray = cv2.bitwise_not(cleaned_bin)

    meta = {
        "deskew_angle_deg": round(angle, 3),
        "width": int(cleaned_gray.shape[1]),
        "height": int(cleaned_gray.shape[0]),
    }
    return deskewed_gray, cleaned_gray, cleaned_bin, meta


def detect_lines(binary_inv: np.ndarray) -> list[dict]:
    """Raster-to-vector line detection via LSD."""
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    lines, _widths, _prec, _nfa = lsd.detect(binary_inv)
    results: list[dict] = []
    if lines is None:
        return results

    min_len = max(12.0, min(binary_inv.shape[:2]) * 0.01)
    for index, line in enumerate(lines):
        x1, y1, x2, y2 = [float(v) for v in line[0]]
        length = float(np.hypot(x2 - x1, y2 - y1))
        if length < min_len:
            continue
        results.append(
            {
                "id": f"line_{index + 1}",
                "type": "line",
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "length": length,
            }
        )
    return results


def detect_circles_and_arcs(binary_inv: np.ndarray) -> tuple[list[dict], list[dict]]:
    """Detect circles (Hough) and arc-like contours."""
    h, w = binary_inv.shape[:2]
    blur = cv2.GaussianBlur(binary_inv, (5, 5), 0)
    min_r = max(6, int(min(h, w) * 0.01))
    max_r = max(min_r + 1, int(min(h, w) * 0.25))

    circles_cv = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=max(20, min_r * 2),
        param1=80,
        param2=28,
        minRadius=min_r,
        maxRadius=max_r,
    )

    circles: list[dict] = []
    if circles_cv is not None:
        for index, (cx, cy, r) in enumerate(np.round(circles_cv[0]).astype(int)):
            circles.append(
                {
                    "id": f"circle_{index + 1}",
                    "type": "circle",
                    "cx": float(cx),
                    "cy": float(cy),
                    "r": float(r),
                }
            )

    arcs: list[dict] = []
    contours, _ = cv2.findContours(binary_inv, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    for index, contour in enumerate(contours):
        if len(contour) < 40:
            continue
        area = cv2.contourArea(contour)
        if area < 80 or area > (h * w * 0.2):
            continue
        peri = cv2.arcLength(contour, True)
        if peri <= 0:
            continue
        circularity = 4.0 * np.pi * area / (peri * peri)
        # Partial rings / arcs tend to be less closed/circular than full circles.
        if 0.2 <= circularity <= 0.85:
            (cx, cy), radius = cv2.minEnclosingCircle(contour)
            if radius < min_r or radius > max_r:
                continue
            # Approximate arc sweep from contour endpoints relative to center.
            pts = contour.reshape(-1, 2).astype(float)
            angles = np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx)
            start = float(np.degrees(angles.min()) % 360.0)
            end = float(np.degrees(angles.max()) % 360.0)
            if abs(end - start) < 25:
                continue
            arcs.append(
                {
                    "id": f"arc_{index + 1}",
                    "type": "arc",
                    "cx": float(cx),
                    "cy": float(cy),
                    "r": float(radius),
                    "start_angle": start,
                    "end_angle": end,
                    "circularity": float(circularity),
                }
            )
            if len(arcs) >= 80:
                break

    return circles, arcs


def detect_symbol_candidates(binary_inv: np.ndarray) -> list[dict]:
    """Heuristic symbol candidates from compact closed contours (AEC markers, etc.)."""
    h, w = binary_inv.shape[:2]
    contours, _ = cv2.findContours(binary_inv, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    symbols: list[dict] = []
    min_area = max(40.0, h * w * 0.00005)
    max_area = h * w * 0.02

    for index, contour in enumerate(contours):
        area = float(cv2.contourArea(contour))
        if area < min_area or area > max_area:
            continue
        x, y, bw, bh = cv2.boundingRect(contour)
        if bw < 6 or bh < 6:
            continue
        aspect = bw / float(bh)
        if aspect < 0.2 or aspect > 5.0:
            continue
        approx = cv2.approxPolyDP(contour, 0.04 * cv2.arcLength(contour, True), True)
        shape = "polygon"
        if len(approx) == 3:
            shape = "triangle"
        elif len(approx) == 4:
            shape = "rect"
        elif len(approx) > 6:
            shape = "complex"

        symbols.append(
            {
                "id": f"symbol_{index + 1}",
                "type": "symbol_candidate",
                "shape": shape,
                "x": float(x),
                "y": float(y),
                "w": float(bw),
                "h": float(bh),
                "area": area,
            }
        )
        if len(symbols) >= 120:
            break
    return symbols


def export_dxf(
    out_path: Path,
    *,
    width: int,
    height: int,
    lines: list[dict],
    circles: list[dict],
    arcs: list[dict],
    symbols: list[dict],
    ocr_items: list[dict],
) -> Path:
    """Export detected geometry + annotation text to DXF (Y flipped for CAD-like coords)."""
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    doc.layers.add("LINES", color=7)
    doc.layers.add("CIRCLES", color=3)
    doc.layers.add("ARCS", color=4)
    doc.layers.add("SYMBOLS", color=1)
    doc.layers.add("TEXT", color=2)

    def flip_y(y: float) -> float:
        return float(height - y)

    for line in lines:
        msp.add_line(
            (line["x1"], flip_y(line["y1"])),
            (line["x2"], flip_y(line["y2"])),
            dxfattribs={"layer": "LINES"},
        )

    for circle in circles:
        msp.add_circle(
            (circle["cx"], flip_y(circle["cy"])),
            circle["r"],
            dxfattribs={"layer": "CIRCLES"},
        )

    for arc in arcs:
        # ezdxf arc angles are CCW from +X; our image angles are similar after Y flip
        # by mirroring start/end around horizontal.
        start = (360.0 - float(arc["end_angle"])) % 360.0
        end = (360.0 - float(arc["start_angle"])) % 360.0
        msp.add_arc(
            (arc["cx"], flip_y(arc["cy"])),
            arc["r"],
            start,
            end,
            dxfattribs={"layer": "ARCS"},
        )

    for symbol in symbols:
        x, y, bw, bh = symbol["x"], symbol["y"], symbol["w"], symbol["h"]
        points = [
            (x, flip_y(y)),
            (x + bw, flip_y(y)),
            (x + bw, flip_y(y + bh)),
            (x, flip_y(y + bh)),
            (x, flip_y(y)),
        ]
        msp.add_lwpolyline(points, dxfattribs={"layer": "SYMBOLS"})

    for item in ocr_items:
        box = item.get("box") or {}
        # box is normalized; convert using source width/height
        px = float(box.get("x", 0)) * width
        py = float(box.get("y", 0)) * height
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        height_txt = max(8.0, float(box.get("h", 0.02)) * height * 0.8)
        msp.add_text(
            text,
            dxfattribs={
                "layer": "TEXT",
                "height": height_txt,
                "insert": (px, flip_y(py + float(box.get("h", 0)) * height)),
            },
        )

    # Frame for reference
    msp.add_lwpolyline(
        [(0, 0), (width, 0), (width, height), (0, height), (0, 0)],
        dxfattribs={"layer": "LINES"},
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(out_path)
    return out_path


def render_preview(
    cleaned_gray: np.ndarray,
    lines: list[dict],
    circles: list[dict],
    arcs: list[dict],
    symbols: list[dict],
    ocr_items: list[dict],
) -> np.ndarray:
    preview = cv2.cvtColor(cleaned_gray, cv2.COLOR_GRAY2BGR)
    h, w = cleaned_gray.shape[:2]

    for line in lines:
        cv2.line(
            preview,
            (int(line["x1"]), int(line["y1"])),
            (int(line["x2"]), int(line["y2"])),
            (80, 200, 255),
            1,
            cv2.LINE_AA,
        )
    for circle in circles:
        cv2.circle(
            preview,
            (int(circle["cx"]), int(circle["cy"])),
            int(circle["r"]),
            (80, 255, 120),
            2,
            cv2.LINE_AA,
        )
    for arc in arcs:
        cv2.ellipse(
            preview,
            (int(arc["cx"]), int(arc["cy"])),
            (int(arc["r"]), int(arc["r"])),
            0,
            float(arc["start_angle"]),
            float(arc["end_angle"]),
            (255, 180, 80),
            2,
            cv2.LINE_AA,
        )
    for symbol in symbols:
        x, y, bw, bh = int(symbol["x"]), int(symbol["y"]), int(symbol["w"]), int(symbol["h"])
        cv2.rectangle(preview, (x, y), (x + bw, y + bh), (90, 90, 255), 1)

    for item in ocr_items:
        box = item.get("box") or {}
        x1 = int(float(box.get("x", 0)) * w)
        y1 = int(float(box.get("y", 0)) * h)
        x2 = int((float(box.get("x", 0)) + float(box.get("w", 0))) * w)
        y2 = int((float(box.get("y", 0)) + float(box.get("h", 0))) * h)
        cv2.rectangle(preview, (x1, y1), (x2, y2), (0, 220, 255), 1)
        label = str(item.get("text") or "")[:40]
        if label:
            cv2.putText(
                preview,
                label,
                (x1, max(14, y1 - 4)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (0, 220, 255),
                1,
                cv2.LINE_AA,
            )
    return preview


def run_drawing_pipeline(image_path: Path, work_dir: Path) -> dict:
    """
    Drawing image
      → cleanup + deskew
      → raster-to-vector lines
      → PP-OCRv6 annotations
      → circle / arc / symbol detection
      → DXF export
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    image_bgr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image_bgr is None:
        raise ValueError(f"Could not read image: {image_path}")

    deskewed_gray, cleaned_gray, cleaned_bin, clean_meta = cleanup_and_deskew(image_bgr)
    cleaned_path = work_dir / "cleaned.png"
    ocr_input_path = work_dir / "ocr_input.png"
    cv2.imwrite(str(cleaned_path), cleaned_gray)
    cv2.imwrite(str(ocr_input_path), deskewed_gray)

    lines = detect_lines(cleaned_bin)
    circles, arcs = detect_circles_and_arcs(cleaned_bin)
    symbols = detect_symbol_candidates(cleaned_bin)

    # OCR on deskewed grayscale (keeps annotation readability better than hard binary).
    from .drawing_ocr import run_ppocrv6_on_image

    ocr = run_ppocrv6_on_image(ocr_input_path)
    ocr_items = ocr["items"]

    dxf_path = work_dir / "export.dxf"
    export_dxf(
        dxf_path,
        width=clean_meta["width"],
        height=clean_meta["height"],
        lines=lines,
        circles=circles,
        arcs=arcs,
        symbols=symbols,
        ocr_items=ocr_items,
    )

    preview = render_preview(cleaned_gray, lines, circles, arcs, symbols, ocr_items)
    preview_path = work_dir / "preview.png"
    cv2.imwrite(str(preview_path), preview)

    vectors = {
        "lines": lines,
        "circles": circles,
        "arcs": arcs,
        "symbols": symbols,
    }
    stages = [
        {"id": "cleanup_deskew", "label": "Image cleanup and deskew", "ok": True, "detail": clean_meta},
        {
            "id": "line_vectorization",
            "label": "Raster-to-vector line detection",
            "ok": True,
            "detail": {"count": len(lines)},
        },
        {
            "id": "paddleocr_annotations",
            "label": "PaddleOCR PP-OCRv6 for annotations",
            "ok": True,
            "detail": {"count": len(ocr_items)},
        },
        {
            "id": "circle_arc_symbol",
            "label": "Circle, arc and symbol detection",
            "ok": True,
            "detail": {
                "circles": len(circles),
                "arcs": len(arcs),
                "symbols": len(symbols),
            },
        },
        {
            "id": "dxf_export",
            "label": "Export to DXF",
            "ok": dxf_path.exists(),
            "detail": {"path": str(dxf_path)},
        },
    ]

    return {
        "engine": "PP-OCRv6 + OpenCV vector pipeline",
        "image_width": clean_meta["width"],
        "image_height": clean_meta["height"],
        "cleanup": clean_meta,
        "items": ocr_items,
        "vectors": vectors,
        "stages": stages,
        "cleaned_path": str(cleaned_path),
        "preview_path": str(preview_path),
        "dxf_path": str(dxf_path),
        "counts": {
            "lines": len(lines),
            "circles": len(circles),
            "arcs": len(arcs),
            "symbols": len(symbols),
            "texts": len(ocr_items),
        },
    }
