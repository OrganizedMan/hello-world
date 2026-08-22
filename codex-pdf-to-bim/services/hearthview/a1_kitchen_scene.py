"""Kitchen/family Blender scene spec, generated from the A-1 extraction.

This module is the bridge the checkpoint was missing: the approved 2D trace in,
a fully decomposed Blender build plan out. Every wall box, opening, appliance
station and camera in the emitted spec is derived from the PDF's own vectors
and text labels, so `build_scene.py` no longer needs a hand-transcribed layout.

Coordinates are metres in the established Blender scene convention: origin at
the inside north-west corner of the kitchen, +x east, +y south, +z up. The
manifest/browser (glTF, Y-up) variant of a point (x, y, z) is (x, z, -y).

Scope is deliberately the kitchen/family checkpoint region only: the main
kitchen + living rectangle plus the west kitchen arm that runs the printed
19'-7" down to the powder-room wall — the part the hand-built spike cut short,
which is what pushed the range and refrigerator ~3.5 ft and ~5 ft north of
where A-1 puts them.

Vertical opening dimensions do not exist in this drawing set (three plan
sheets, no elevation or section); sill and head heights below keep the spike's
conventional values and are declared as assumed in the emitted provenance.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hearthview.a1_extract import A1Extraction, extract_a1

FT = 0.3048
PT_PER_FT = 18.0

# --- interior faces of the checkpoint region, in PDF points (from the trace) ---
_N = 594.6     # north wall inside face
_W = 1462.2    # west wall inside face
_E = 1981.8    # family-room east wall inside face
_S_EAST = 877.7   # living south wall inside face
_S_ARM = 946.8    # kitchen arm south wall inside face
_ARM_E = 1658.9   # kitchen arm east boundary (pantry wall face)

# --- real wall thicknesses from the trace poche ---
_T_NORTH = 9.0 / PT_PER_FT * FT     # 6"
_T_WEST = 13.5 / PT_PER_FT * FT     # 9"
_T_EAST = 9.0 / PT_PER_FT * FT      # 6"
_T_SOUTH = 9.0 / PT_PER_FT * FT     # 6"
_T_ARM = 6.0 / PT_PER_FT * FT       # 4"

CEILING = 2.5654          # printed CLG HT 8'-5"
# Assumed (no elevations in the set); same conventions the spike used.
WINDOW_SILL = 0.95
WINDOW_HEAD = 2.05
DOOR_HEAD = 2.35
COUNTER_DEPTH = 0.6604    # 26" counter zone, printed-derived
_MIN_OPENING_FT = 1.5     # below this a gap is a drafting artifact, not an opening


def _mx(pdf_x: float) -> float:
    return (pdf_x - _W) / PT_PER_FT * FT


def _my(pdf_y: float) -> float:
    return (pdf_y - _N) / PT_PER_FT * FT


@dataclass(frozen=True)
class _Gap:
    start: float   # metres along the wall
    end: float
    kind: str      # window | door | cased


def _merge_1d(spans: list[tuple[float, float]]) -> list[list[float]]:
    ordered = sorted(spans)
    merged = [list(ordered[0])]
    for lo, hi in ordered[1:]:
        if lo <= merged[-1][1] + 1.5:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return merged


def _wall_gaps(
    extraction: A1Extraction,
    *,
    axis: str,
    band_lo: float,
    band_hi: float,
    run_lo: float,
    run_hi: float,
) -> list[tuple[float, float]]:
    """Gaps along one boundary wall, tolerant of subpaths on jittered bands."""
    spans: list[tuple[float, float]] = []
    for shape in extraction.layer("wall_new") + extraction.layer("wall_existing"):
        b = shape.bounds
        if axis == "h" and band_lo - 1 <= b.y0 and b.y1 <= band_hi + 1:
            lo, hi = max(b.x0, run_lo), min(b.x1, run_hi)
        elif axis == "v" and band_lo - 1 <= b.x0 and b.x1 <= band_hi + 1:
            lo, hi = max(b.y0, run_lo), min(b.y1, run_hi)
        else:
            continue
        if hi - lo > 1.0:
            spans.append((lo, hi))
    if not spans:
        return []
    merged = _merge_1d(spans)
    gaps: list[tuple[float, float]] = []
    if merged[0][0] - run_lo > _MIN_OPENING_FT * PT_PER_FT:
        gaps.append((run_lo, merged[0][0]))
    for left, right in zip(merged, merged[1:]):
        if right[0] - left[1] > _MIN_OPENING_FT * PT_PER_FT:
            gaps.append((left[1], right[0]))
    if run_hi - merged[-1][1] > _MIN_OPENING_FT * PT_PER_FT:
        gaps.append((merged[-1][1], run_hi))
    return gaps


def _station_labels(pdf_path: Path, page_number: int) -> dict[str, list[tuple[float, float]]]:
    """Appliance/cabinet stations from the PDF text layer, in region metres.

    These callouts are set in 6.5-8.5 pt italics, below the size floor the
    room-label extraction uses, so they are read directly from the page.
    """
    import pymupdf

    wanted = {"TOWER", "DW", "TRASH", '36" SINK', '36" REFR.', "UPPERS", '60" TV'}
    out: dict[str, list[tuple[float, float]]] = {}
    document = pymupdf.open(pdf_path)
    try:
        page = document.load_page(page_number - 1)
        for block in page.get_text("dict")["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    b = span["bbox"]
                    if text in wanted and 1440 < b[0] < 2000 and 580 < b[1] < 1000:
                        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                        out.setdefault(text, []).append((_mx(cx), _my(cy)))
    finally:
        document.close()
    return out


def build_kitchen_scene_spec(extraction: A1Extraction, pdf_path: Path) -> dict:
    span = _mx(_E)                 # 28.87 ft
    depth_east = _my(_S_EAST)      # 15.73 ft
    arm_east = _mx(_ARM_E)         # 10.93 ft
    arm_south = _my(_S_ARM)        # 19.57 ft (printed 19'-7")

    # ---- openings per boundary, typed from the drawn symbols ----
    # North: triple window unit (2'-0" | 4'-5" | 2'-0" over the 36" sink) then
    # the deck door + two windows east of it. Types verified against the sheet.
    north = _wall_gaps(extraction, axis="h", band_lo=585.6, band_hi=594.6, run_lo=_W, run_hi=_E)
    north_gaps: list[_Gap] = []
    for lo, hi in north:
        start, end = _mx(lo), _mx(hi)
        centre_ft = (start + end) / 2 / FT
        kind = "door" if 16.0 < centre_ft < 19.5 else "window"
        north_gaps.append(_Gap(start, end, kind))

    west = _wall_gaps(extraction, axis="v", band_lo=1448.7, band_hi=1462.2, run_lo=_N, run_hi=_S_ARM)
    west_gaps = [
        _Gap(_my(lo), _my(hi), "window")
        for lo, hi in west
        if (hi - lo) / PT_PER_FT >= _MIN_OPENING_FT
    ]

    east = _wall_gaps(extraction, axis="v", band_lo=1981.8, band_hi=1990.8, run_lo=_N, run_hi=_S_EAST)
    east_gaps: list[_Gap] = []
    for lo, hi in east:
        start, end = _my(lo), _my(hi)
        # The upper gap is the drawn window; the lower is the cased opening to
        # the mudroom (no sash, no swing on the sheet).
        east_gaps.append(_Gap(start, end, "window" if end < 2.0 else "cased"))

    south = _wall_gaps(extraction, axis="h", band_lo=877.7, band_hi=886.7, run_lo=_ARM_E + 6, run_hi=_E)
    south_gaps = [_Gap(_mx(lo), _mx(hi), "cased") for lo, hi in south]

    arm = _wall_gaps(extraction, axis="h", band_lo=946.8, band_hi=952.8, run_lo=_W, run_hi=_ARM_E)
    arm_gaps = [_Gap(_mx(lo), _mx(hi), "cased") for lo, hi in arm]

    # ---- decompose boundary walls into solid boxes + sills/headers ----
    boxes: list[dict] = []
    windows: list[dict] = []
    doors: list[dict] = []

    def emit_wall(name: str, *, axis: str, run: tuple[float, float], line: float,
                  thickness: float, outward: float, gaps: list[_Gap]) -> None:
        """One boundary wall: solid pieces between gaps, sill/header at gaps.

        ``line`` is the interior face position on the cross axis; ``outward``
        is -1 when the wall body sits at smaller cross values (north/west).
        """
        def seg(seg_name: str, lo: float, hi: float, z0: float, z1: float) -> None:
            if hi - lo <= 0.005 or z1 - z0 <= 0.005:
                return
            length = hi - lo
            centre_cross = line + outward * thickness / 2
            if axis == "h":
                size = (length, thickness, z1 - z0)
                loc = ((lo + hi) / 2, centre_cross, (z0 + z1) / 2)
            else:
                size = (thickness, length, z1 - z0)
                loc = (centre_cross, (lo + hi) / 2, (z0 + z1) / 2)
            boxes.append({"name": seg_name, "size": size, "loc": loc})

        cursor = run[0]
        for index, gap in enumerate(gaps):
            seg(f"{name}_SOLID_{index}", cursor, gap.start, 0.0, CEILING)
            if gap.kind == "window":
                seg(f"{name}_SILL_{index}", gap.start, gap.end, 0.0, WINDOW_SILL)
                seg(f"{name}_HEAD_{index}", gap.start, gap.end, WINDOW_HEAD, CEILING)
                windows.append({
                    "name": f"{name}_WINDOW_{index}",
                    "axis": axis, "start": gap.start, "end": gap.end,
                    "line": line, "outward": outward, "thickness": thickness,
                    "sill": WINDOW_SILL, "head": WINDOW_HEAD,
                })
            else:
                seg(f"{name}_HEAD_{index}", gap.start, gap.end, DOOR_HEAD, CEILING)
                doors.append({
                    "name": f"{name}_{gap.kind.upper()}_{index}",
                    "axis": axis, "start": gap.start, "end": gap.end,
                    "line": line, "outward": outward, "thickness": thickness,
                    "head": DOOR_HEAD, "kind": gap.kind,
                })
            cursor = gap.end
        seg(f"{name}_SOLID_END", cursor, run[1], 0.0, CEILING)

    emit_wall("HV_NORTH", axis="h", run=(0.0, span), line=0.0,
              thickness=_T_NORTH, outward=-1, gaps=north_gaps)
    emit_wall("HV_WEST", axis="v", run=(0.0, arm_south), line=0.0,
              thickness=_T_WEST, outward=-1, gaps=west_gaps)
    emit_wall("HV_EAST", axis="v", run=(0.0, depth_east), line=span,
              thickness=_T_EAST, outward=+1, gaps=east_gaps)
    emit_wall("HV_SOUTH_LIVING", axis="h", run=(arm_east + _T_ARM, span), line=depth_east,
              thickness=_T_SOUTH, outward=+1, gaps=south_gaps)
    emit_wall("HV_SOUTH_ARM", axis="h", run=(0.0, arm_east), line=arm_south,
              thickness=_T_ARM, outward=+1, gaps=arm_gaps)
    emit_wall("HV_ARM_EAST", axis="v", run=(depth_east, arm_south), line=arm_east,
              thickness=_T_ARM, outward=+1, gaps=[])

    # ---- floor and ceiling: main rectangle + the west arm ----
    slabs = [
        {"name": "MAIN", "rect": [0.0, 0.0, span, depth_east]},
        {"name": "ARM", "rect": [0.0, depth_east, arm_east, arm_south]},
    ]

    # ---- kitchen stations from the PDF labels + burner glyph ----
    labels = _station_labels(pdf_path, extraction.page_number)
    towers = sorted(x for x, y in labels.get("TOWER", []) if y < 1.0)
    dw_x = labels["DW"][0][0]
    trash_x = labels["TRASH"][0][0]
    sink_x = labels['36" SINK'][0][0]
    fridge_y = labels['36" REFR.'][0][1]
    uppers_y = sorted(y for x, y in labels.get("UPPERS", []))
    tv = labels.get('60" TV', [(span, _my(738.0))])[0]

    # Burner glyph centre measured from the drawing: 7.40 ft south (see
    # scripts/verify_kitchen_spec.py, which re-measures it from the PDF).
    range_y = _my(718.9)

    island_shapes = [s for s in extraction.layer("counter")
                     if 8.0 < (s.bounds.x1 - s.bounds.x0) / PT_PER_FT < 9.2]
    island_b = island_shapes[0].bounds
    island = [_mx(island_b.x0), _my(island_b.y0), _mx(island_b.x1), _my(island_b.y1)]

    kitchen = {
        "counter_depth": COUNTER_DEPTH,
        "north_run": {
            "towers": [{"center_x": x, "width": 0.61, "depth": 0.64} for x in towers],
            "dishwasher": {"center_x": dw_x, "width": 0.61},
            "sink": {"center_x": sink_x, "width": 0.9144},
            "trash": {"center_x": trash_x, "width": 0.46},
            "counter": {"start": min(towers) - 0.31 if towers else 0.05,
                         "end": max(towers) + 0.31 if towers else span / 3},
        },
        "west_run": {
            "counter": {"start": 0.61, "end": arm_south - 0.05},
            "uppers": [{"center_y": y, "width": 1.35} for y in uppers_y],
            "range": {"center_y": range_y, "width": 0.9144},
            "fridge": {"center_y": fridge_y, "width": 0.9144, "depth": 0.75},
        },
        "island": island,
    }

    living = {
        "clear_area": [max(island[2] + 0.55, arm_east + _T_ARM), 0.35, span - 0.35, depth_east - 0.35],
        "tv": {"wall": "east", "center_y": tv[1], "width": 1.524},
    }

    # ---- navigation + cameras (Blender coords; gltf = (x, z, -y)) ----
    island_cx = (island[0] + island[2]) / 2
    island_cy = (island[1] + island[3]) / 2
    live_cx = (living["clear_area"][0] + living["clear_area"][2]) / 2
    live_cy = (living["clear_area"][1] + living["clear_area"][3]) / 2
    envelope_cx, envelope_cy = span / 2, arm_south / 2
    cameras = [
        {"name": "PLAN", "kind": "ortho_top",
         "location": [envelope_cx, envelope_cy, 9.0],
         "target": [envelope_cx, envelope_cy, 0.0],
         "ortho_scale": max(span, arm_south) + 1.2},
        {"name": "AXONOMETRIC", "kind": "persp", "lens_mm": 45.0,
         "location": [span + 5.6, arm_south + 4.6, 6.4],
         "target": [envelope_cx, envelope_cy * 0.9, 0.8]},
        {"name": "KITCHEN", "kind": "persp", "lens_mm": 32.0,
         "location": [island_cx + 2.4, island_cy + 2.6, 1.72],
         "target": [island_cx, island_cy, 0.9]},
        {"name": "LIVING_ROOM", "kind": "persp", "lens_mm": 28.0,
         "location": [island[2] + 0.7, 0.85, 1.65],
         "target": [live_cx + 1.2, live_cy + 1.0, 1.0]},
    ]

    collision = [
        {"name": "island", "rect": island},
    ]
    walkable = {"min_x": 0.35, "max_x": span - 0.35, "min_y": 0.35, "max_y": arm_south - 0.35}

    def gltf(point: list[float]) -> list[float]:
        return [round(point[0], 4), round(point[2], 4), round(-point[1], 4)]

    manifest_cameras = [
        {"name": name, "position": gltf(c["location"]), "target": gltf(c["target"]), "up": [0, 1, 0]}
        for c, name in ((c, m) for c in cameras for m in [
            {"PLAN": "overhead", "AXONOMETRIC": "overhead", "KITCHEN": "kitchen_overview",
             "LIVING_ROOM": "walk_start"}[c["name"]]])
    ]
    # de-duplicate: overhead appears twice above; keep first occurrence per name
    seen: set[str] = set()
    manifest_cameras = [c for c in manifest_cameras if not (c["name"] in seen or seen.add(c["name"]))]

    return mirror_spec_for_blender({
        "schema": "hearthview-kitchen-scene/v1",
        "source": {
            "sheet": "A-1", "page": extraction.page_number,
            "view": "Proposed - First Floor",
            "region": "kitchen + family room + west kitchen arm",
        },
        "provenance": {
            "measured": [
                "wall positions and thicknesses (trace poche)",
                "opening positions and widths (gaps in wall runs)",
                "appliance stations (printed labels: DW, 36\" SINK, TRASH, TOWER, UPPERS, 36\" REFR.)",
                "range position (burner glyph on the west wall)",
                "island (printed 8'-7\" x 4'-3\")",
                "west run length (printed 19'-7\")",
                "ceiling 8'-5\" (printed)",
            ],
            "assumed": [
                "window sill 0.95 m / head 2.05 m, door head 2.35 m (no elevations in set)",
                "counter/appliance depths (industry standard)",
            ],
        },
        "units": "meters",
        "ceiling": CEILING,
        "envelope": {"span": round(span, 4), "depth_east": round(depth_east, 4),
                      "arm_east": round(arm_east, 4), "arm_south": round(arm_south, 4)},
        "wall_boxes": boxes,
        "windows": windows,
        "doors": doors,
        "slabs": slabs,
        "kitchen": kitchen,
        "living": living,
        "walkable": walkable,
        "collision": collision,
        "cameras": cameras,
        "manifest_cameras": manifest_cameras,
    })


def mirror_spec_for_blender(spec: dict) -> dict:
    """Reflect the spec in X so the exported world matches the plan.

    The scene is authored in plan terms: +x east, +y south. Blender exports
    Y-up as (x, y, z) -> (x, z, -y), which puts north on +Z. But a right-handed
    Y-up basis with X=east and Y=up requires Z=south, because east x up = south.
    Authoring in (east, south, up) is therefore left-handed, and the exported
    world comes out mirrored — ahead and left swap at every corner.

    Reflecting X once restores the correct chirality. Model +x then runs west,
    which is why the wall names swap with it: the geometry is what has to be
    right, and the names have to keep describing it truthfully.
    """
    span = spec["envelope"]["span"]

    def mx(value: float) -> float:
        return round(span - value, 6)

    def mirror_range(lo: float, hi: float) -> tuple[float, float]:
        return mx(hi), mx(lo)

    def rename(name: str) -> str:
        if "WEST" in name:
            return name.replace("WEST", "EAST")
        if "EAST" in name:
            return name.replace("EAST", "WEST")
        return name

    for box in spec["wall_boxes"]:
        box["name"] = rename(box["name"])
        # emit_wall builds these as tuples; normalise so the spec is JSON-shaped.
        box["size"] = list(box["size"])
        loc = list(box["loc"])
        loc[0] = mx(loc[0])
        box["loc"] = loc

    for item in [*spec["windows"], *spec["doors"]]:
        item["name"] = rename(item["name"])
        if item["axis"] == "h":
            item["start"], item["end"] = mirror_range(item["start"], item["end"])
        else:
            item["line"] = mx(item["line"])
            item["outward"] = -item["outward"]

    for slab in spec["slabs"]:
        slab["rect"][0], slab["rect"][2] = mirror_range(slab["rect"][0], slab["rect"][2])

    north = spec["kitchen"]["north_run"]
    for tower in north["towers"]:
        tower["center_x"] = mx(tower["center_x"])
    for station in ("dishwasher", "sink", "trash"):
        north[station]["center_x"] = mx(north[station]["center_x"])
    north["counter"]["start"], north["counter"]["end"] = mirror_range(
        north["counter"]["start"], north["counter"]["end"]
    )

    island = spec["kitchen"]["island"]
    island[0], island[2] = mirror_range(island[0], island[2])

    clear = spec["living"]["clear_area"]
    clear[0], clear[2] = mirror_range(clear[0], clear[2])
    spec["living"]["tv"]["wall"] = "west"

    for camera in spec["cameras"]:
        camera["location"][0] = mx(camera["location"][0])
        camera["target"][0] = mx(camera["target"][0])
    for camera in spec["manifest_cameras"]:
        camera["position"][0] = mx(camera["position"][0])
        camera["target"][0] = mx(camera["target"][0])

    walkable = spec["walkable"]
    walkable["min_x"], walkable["max_x"] = mirror_range(walkable["min_x"], walkable["max_x"])
    for item in spec["collision"]:
        item["rect"][0], item["rect"][2] = mirror_range(item["rect"][0], item["rect"][2])

    spec["envelope"]["arm_east"] = mx(spec["envelope"]["arm_east"])
    spec["mirrored_for_blender"] = True
    return spec


def main() -> int:
    import sys

    if len(sys.argv) != 3:
        print("usage: python -m hearthview.a1_kitchen_scene <a1.pdf> <out.json>")
        return 2
    source = Path(sys.argv[1])
    extraction = extract_a1(source)
    spec = build_kitchen_scene_spec(extraction, source)
    Path(sys.argv[2]).write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {sys.argv[2]}: {len(spec['wall_boxes'])} wall boxes, "
          f"{len(spec['windows'])} windows, {len(spec['doors'])} doors/cased")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
