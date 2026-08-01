from __future__ import annotations

import math
from typing import Iterable

from shapely.geometry import LineString, Point
from shapely.ops import linemerge, snap, unary_union
from shapely.strtree import STRtree


def _line_angle(line: LineString) -> float:
    x1, y1, x2, y2 = line.coords[0][0], line.coords[0][1], line.coords[-1][0], line.coords[-1][1]
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0


def _angle_diff(a: float, b: float) -> float:
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def _to_linestring(item: dict) -> LineString:
    return LineString([(float(item["x1"]), float(item["y1"])), (float(item["x2"]), float(item["y2"]))])


def _from_linestring(line: LineString, index: int) -> dict:
    (x1, y1), (x2, y2) = line.coords[0], line.coords[-1]
    length = float(line.length)
    return {
        "id": f"line_{index + 1}",
        "type": "line",
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "length": length,
    }


def join_and_clean_lines(
    lines: list[dict],
    *,
    snap_tol: float = 4.0,
    merge_gap: float = 6.0,
    angle_tol_deg: float = 8.0,
    min_length: float = 10.0,
) -> list[dict]:
    """Join and clean OpenCV line segments with Shapely.

    - snap nearby endpoints
    - merge nearly-colinear connected segments
    - drop tiny fragments
    """
    if not lines:
        return []

    geoms = [_to_linestring(item) for item in lines if item.get("length", 0) >= min_length * 0.5]
    if not geoms:
        return []

    # Snap all geometries to each other to close tiny gaps.
    snapped: list[LineString] = []
    tree = STRtree(geoms)
    for geom in geoms:
        candidates = [geoms[i] for i in tree.query(geom.buffer(snap_tol))]
        others = unary_union([g for g in candidates if g is not geom]) if candidates else None
        if others is None or others.is_empty:
            snapped.append(geom)
        else:
            snapped.append(snap(geom, others, snap_tol))

    # Greedy merge of colinear neighbors.
    used = [False] * len(snapped)
    merged: list[LineString] = []

    for i, base in enumerate(snapped):
        if used[i] or base.length < min_length * 0.5:
            continue
        used[i] = True
        current = base
        angle = _line_angle(current)
        changed = True
        while changed:
            changed = False
            for j, other in enumerate(snapped):
                if used[j]:
                    continue
                if _angle_diff(angle, _line_angle(other)) > angle_tol_deg:
                    continue
                # Endpoints close enough?
                a0, a1 = Point(current.coords[0]), Point(current.coords[-1])
                b0, b1 = Point(other.coords[0]), Point(other.coords[-1])
                pairs = [
                    (a0, b0),
                    (a0, b1),
                    (a1, b0),
                    (a1, b1),
                ]
                if min(p.distance(q) for p, q in pairs) > merge_gap:
                    continue
                try:
                    combo = linemerge(unary_union([current, other]))
                except Exception:
                    continue
                if combo.geom_type == "LineString" and combo.length >= current.length:
                    current = combo
                    angle = _line_angle(current)
                    used[j] = True
                    changed = True
        if current.length >= min_length:
            merged.append(current)

    # Final cleanup: remove near-duplicates.
    cleaned: list[LineString] = []
    for line in sorted(merged, key=lambda g: g.length, reverse=True):
        if any(line.buffer(1.5).contains(existing) or existing.buffer(1.5).contains(line) for existing in cleaned):
            continue
        # Also skip almost identical short overlaps.
        duplicate = False
        for existing in cleaned:
            if line.distance(existing) <= 1.0 and abs(line.length - existing.length) < 4:
                if _angle_diff(_line_angle(line), _line_angle(existing)) < angle_tol_deg:
                    duplicate = True
                    break
        if not duplicate:
            cleaned.append(line)

    return [_from_linestring(line, index) for index, line in enumerate(cleaned)]


def clean_circles(circles: Iterable[dict], *, min_r: float = 4.0, dedupe_tol: float = 6.0) -> list[dict]:
    """Drop tiny/duplicate circles."""
    kept: list[dict] = []
    for index, circle in enumerate(circles):
        r = float(circle.get("r", 0))
        if r < min_r:
            continue
        cx, cy = float(circle["cx"]), float(circle["cy"])
        duplicate = False
        for prev in kept:
            if abs(cx - float(prev["cx"])) <= dedupe_tol and abs(cy - float(prev["cy"])) <= dedupe_tol:
                if abs(r - float(prev["r"])) <= dedupe_tol:
                    duplicate = True
                    break
        if duplicate:
            continue
        kept.append(
            {
                "id": f"circle_{len(kept) + 1}",
                "type": "circle",
                "cx": cx,
                "cy": cy,
                "r": r,
            }
        )
    return kept
