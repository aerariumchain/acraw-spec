#!/usr/bin/env python3
"""Generate the synthetic example archive in examples/ (no real scan data).

Usage:
    python3 tools/make_example.py

Builds examples/minimal-structured-light/ (directory form) with two active
range-grid frames on a sparse 4x4 sensor grid, one deleted frame kept for
history, a scan group, vendor poses, an edit history, a placeholder L0 vendor
folder, a fused-mesh product and a QC product; then seals it and packs
examples/minimal-structured-light.acraw.
"""
import json
import os
import shutil
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acraw_pack  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples")
NAME = "minimal-structured-light"
GRID_W, GRID_H = 4, 4
IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(path, mode) as fh:
        fh.write(data)


def write_json(path, doc):
    write(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def png(width, height, pixel):
    """Minimal 8-bit RGB PNG writer; pixel(x, y) -> (r, g, b), y = 0 is the top row."""
    raw = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width)) for y in range(height))

    def chunk(tag, body):
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def range_grid_ply(missing, z_offset):
    """Sparse 4x4 grid frame: present cells become vertices (x, y, z, u, v, grid_index)."""
    verts, slot_to_vertex = [], {}
    for row in range(GRID_H):
        for col in range(GRID_W):
            idx = row * GRID_W + col
            if idx in missing:
                continue
            slot_to_vertex[idx] = len(verts)
            x, y = col * 1.0, row * 1.0
            z = z_offset + 0.05 * (col - row)
            u, v = (col + 0.5) / GRID_W, 1.0 - (row + 0.5) / GRID_H  # v = 0 at the bottom (spec 6.1)
            verts.append((x, y, z, u, v, idx))
    faces = []
    for row in range(GRID_H - 1):
        for col in range(GRID_W - 1):
            a, b = row * GRID_W + col, row * GRID_W + col + 1
            c, d = (row + 1) * GRID_W + col, (row + 1) * GRID_W + col + 1
            for tri in ((a, c, b), (b, c, d)):
                if all(t in slot_to_vertex for t in tri):
                    faces.append(tuple(slot_to_vertex[t] for t in tri))
    header = "\n".join([
        "ply", "format binary_little_endian 1.0",
        "comment AerariumChain Raw synthetic example",
        "element vertex %d" % len(verts),
        "property float x", "property float y", "property float z",
        "property float u", "property float v",
        "property uint grid_index",
        "element face %d" % len(faces),
        "property list uchar uint vertex_indices",
        "end_header", "",
    ]).encode("ascii")
    body = b"".join(struct.pack("<fffffI", *v) for v in verts)
    body += b"".join(struct.pack("<BIII", 3, *f) for f in faces)
    return header + body


def capture(cid, missing, z_offset, ts, status="active", quality=None):
    base = os.path.join(OUT, "L1_raw", "captures", cid)
    write(os.path.join(base, "mesh.ply"), range_grid_ply(missing, z_offset))
    write(os.path.join(base, "texture.png"), png(8, 8, lambda x, y: (40 + x * 25, 60 + y * 20, 120)))
    doc = {
        "id": cid,
        "kind": "range_grid",
        "sensors": ["head", "head.tex"],
        "timestamp": ts,
        "status": status,
        "grid": {"width": GRID_W, "height": GRID_H},
        "payloads": [
            {"role": "geometry", "path": "mesh.ply"},
            {"role": "texture", "path": "texture.png", "sensor": "head.tex"},
        ],
        "ply_properties": {"grid_index": "row-major sensor grid cell (spec 6.3.2)"},
        "vendor_properties": {"name": "frame_%s" % cid},
        "vendor_raw_properties": [{"id": "0x0000002a", "encoding": "hex", "value": "01000000"}],
    }
    if quality is not None:
        doc["vendor_metrics"] = {"quality": quality}
    write_json(os.path.join(base, "capture.json"), doc)


def translation(tx, ty, tz):
    return [1, 0, 0, tx, 0, 1, 0, ty, 0, 0, 1, tz, 0, 0, 0, 1]


def main():
    global OUT
    OUT = os.path.join(ROOT, NAME)
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)

    write_json(os.path.join(OUT, "manifest.json"), {
        "acraw_version": "0.1",
        "id": "urn:uuid:3f1c2b6e-0d7a-4c49-9a0e-6b9f1e2d4c00",
        "title": "Synthetic structured-light example",
        "created": "2026-10-13T09:00:00Z",
        "profile": "full",
        "units": {"length": "mm"},
        "coordinate_system": {"handedness": "right", "up_axis": "+Z", "crs": None},
        "derived_from": None,
        "files": [],
        "root_hash": {"algorithm": "acraw-root-sha256-v1", "value": "0" * 64},
        "writer": {"name": "acraw-spec/make_example.py", "version": "0.1"},
    })

    write_json(os.path.join(OUT, "provenance.json"), {
        "subject": {"type": "test_object", "title": "Synthetic plate",
                    "identifiers": [{"scheme": "example", "value": "0001"}]},
        "acquisition": {"organization": "Example lab", "operator": "operator",
                        "start": "2026-10-13T08:00:00Z", "end": "2026-10-13T08:05:00Z"},
        "software": [{"name": "Example Studio", "version": "1.0", "role": "acquisition"}],
        "conversions": [{"tool": "acraw-spec/make_example.py", "version": "0.1",
                         "from": "synthetic data", "date": "2026-10-13T09:00:00Z"}],
        "rights": {"rights_holder": "AerariumChain Raw contributors", "license": "CC0-1.0"},
    })

    # L0: placeholder for the original vendor project, copied verbatim in a real archive.
    l0 = os.path.join(OUT, "L0_vendor", "examplevendor")
    write_json(os.path.join(l0, "vendor.json"), {
        "vendor_id": "examplevendor",
        "software": {"name": "Example Studio", "version": "1.0"},
        "packaging": "files",
        "original_root": "ExampleProject",
        "notes": "Synthetic placeholder: a real archive holds the original project files byte for byte.",
    })
    write(os.path.join(l0, "files", "ExampleProject", "project.txt"), "placeholder original vendor file\n")

    write_json(os.path.join(OUT, "L1_raw", "sensors.json"), {"sensors": [
        {"id": "head", "kind": "structured_light_rig", "make": "ExampleScan", "model": "Model S",
         "serial": "SN-0001", "calibration": {"source": "factory", "date": "2026-01-15"}},
        {"id": "head.tex", "kind": "camera", "rig": "head", "sensor_to_rig": translation(12.5, 0, 0),
         "intrinsics": {"model": "unknown"}},
    ]})

    capture("f0001", missing={0, 15}, z_offset=0.0, ts="2026-10-13T08:01:00Z", quality=0.91)
    capture("f0002", missing={3, 12}, z_offset=0.2, ts="2026-10-13T08:01:02Z", quality=0.88)
    capture("f0003", missing={5, 6, 9, 10}, z_offset=0.4, ts="2026-10-13T08:01:04Z", status="deleted")

    write_json(os.path.join(OUT, "L1_raw", "scene.json"), {"nodes": [
        {"id": "group-a", "name": "Scan 1", "parent": None, "matrix": translation(0, 0, 100),
         "captures": ["f0001", "f0002", "f0003"]},
    ]})
    write_json(os.path.join(OUT, "L1_raw", "poses.json"), {"poses": [
        {"capture": "f0001", "matrix": IDENTITY, "source": "vendor", "covariance": None},
        {"capture": "f0002", "matrix": translation(1.5, 0, 0), "source": "vendor", "covariance": None},
        {"capture": "f0003", "matrix": translation(3.0, 0, 0), "source": "vendor", "covariance": None},
    ]})
    write_json(os.path.join(OUT, "L1_raw", "history.json"), {"events": [
        {"seq": 1, "timestamp": "2026-10-13T08:01:00Z", "op": "create", "target": "f0001"},
        {"seq": 2, "timestamp": "2026-10-13T08:01:02Z", "op": "create", "target": "f0002"},
        {"seq": 3, "timestamp": "2026-10-13T08:01:04Z", "op": "create", "target": "f0003"},
        {"seq": 4, "op": "set_pose", "target": "f0001", "data": {"matrix": IDENTITY}},
        {"seq": 5, "op": "set_pose", "target": "f0002", "data": {"matrix": translation(1.4, 0.1, 0)}},
        {"seq": 6, "op": "set_pose", "target": "f0003", "data": {"matrix": translation(3.0, 0, 0)}},
        {"seq": 7, "op": "reparent", "target": "f0001", "data": {"parent": "group-a"}},
        {"seq": 8, "op": "reparent", "target": "f0002", "data": {"parent": "group-a"}},
        {"seq": 9, "op": "reparent", "target": "f0003", "data": {"parent": "group-a"}},
        {"seq": 10, "timestamp": "2026-10-13T08:03:00Z", "op": "set_pose", "target": "f0002",
         "data": {"matrix": translation(1.5, 0, 0), "note": "fine registration"}},
        {"seq": 11, "timestamp": "2026-10-13T08:04:00Z", "op": "delete", "target": "f0003"},
    ]})

    fusion = os.path.join(OUT, "L2_derived", "fusion-01")
    write(os.path.join(fusion, "fused.ply"), range_grid_ply(missing=set(), z_offset=0.1))
    write_json(os.path.join(fusion, "product.json"), {
        "id": "fusion-01", "kind": "fused_mesh",
        "inputs": {"captures": ["f0001", "f0002"], "products": []},
        "software": {"name": "Example Studio", "version": "1.0"},
        "parameters": {"resolution_mm": 1.0}, "created": "2026-10-13T08:05:00Z",
        "files": [{"role": "mesh", "path": "fused.ply"}],
    })
    qc = os.path.join(OUT, "L2_derived", "qc-01")
    write_json(os.path.join(qc, "report.json"), {"frames": [
        {"capture": "f0001", "registration_error_mm": 0.21},
        {"capture": "f0002", "registration_error_mm": 0.34},
    ], "method": "mean distance of sampled vertices to fusion-01"})
    write_json(os.path.join(qc, "product.json"), {
        "id": "qc-01", "kind": "qc_report",
        "inputs": {"captures": ["f0001", "f0002"], "products": ["fusion-01"]},
        "software": {"name": "example-qc", "version": "0.1"},
        "created": "2026-10-13T09:00:00Z",
        "files": [{"role": "report", "path": "report.json"}],
    })

    write(os.path.join(OUT, "preview", "thumbnail.png"),
          png(64, 64, lambda x, y: (30 + x * 3, 30 + y * 3, 160)))

    man = acraw_pack.seal(OUT)
    acraw_pack.pack(OUT, os.path.join(ROOT, NAME + ".acraw"), man)
    print("example written, root_hash %s" % man["root_hash"]["value"])


if __name__ == "__main__":
    main()
