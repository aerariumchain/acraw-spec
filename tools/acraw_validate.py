#!/usr/bin/env python3
"""Reference validator for AerariumChain Raw (.acraw) archives, spec version 0.1.

Usage:
    python3 tools/acraw_validate.py <archive.acraw | directory> [--json] [--no-hash]

Checks the container rules, the manifest (file list, sizes, SHA-256, root hash),
the JSON documents (with full JSON Schema validation if the `jsonschema` package
is installed, structural checks otherwise) and the cross references between
sensors, captures, poses, scene, history, products and anchors.

Exit code: 0 valid, 1 errors found, 2 unreadable input.
"""
import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acraw_common import (  # noqa: E402
    EXCLUDED_FROM_MANIFEST, MIMETYPE, ROOT_HASH_ALGORITHM, SPEC_MAJOR, Archive, root_hash, sha256_stream,
)

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schemas")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

try:
    import jsonschema  # type: ignore
except ImportError:  # optional dependency
    jsonschema = None


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = {}

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)


def load_schema(name):
    with open(os.path.join(SCHEMA_DIR, name)) as fh:
        return json.load(fh)


def check_schema(rep, doc, schema_name, where):
    if jsonschema is None:
        return
    try:
        validator = jsonschema.Draft202012Validator(load_schema(schema_name))
        for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
            loc = "/".join(str(p) for p in err.path) or "(root)"
            rep.error("%s: %s: %s" % (where, loc, err.message))
    except Exception as exc:  # schema problems must not crash validation
        rep.warn("%s: schema check skipped (%s)" % (where, exc))


def require_keys(rep, doc, keys, where):
    if not isinstance(doc, dict):
        rep.error("%s: must be a JSON object" % where)
        return False
    missing = [k for k in keys if k not in doc]
    for k in missing:
        rep.error("%s: missing required field '%s'" % (where, k))
    return not missing


def load_json(rep, arc, name, schema_name=None, required=()):
    if not arc.exists(name):
        return None
    try:
        doc = arc.json(name)
    except (ValueError, UnicodeDecodeError) as exc:
        rep.error("%s: invalid JSON (%s)" % (name, exc))
        return None
    if schema_name:
        check_schema(rep, doc, schema_name, name)
    if required:
        require_keys(rep, doc, required, name)
    return doc


# ─── Container ────────────────────────────────────────────

def check_container(rep, arc):
    if arc.is_zip:
        infos = arc.zip.infolist()
        if not infos or infos[0].filename != "mimetype":
            rep.error("container: first ZIP entry must be 'mimetype'")
        else:
            first = infos[0]
            if first.compress_type != zipfile.ZIP_STORED:
                rep.error("container: 'mimetype' must be stored without compression")
            if first.extra:
                rep.error("container: 'mimetype' entry must not have an extra field")
        seen = set()
        for info in infos:
            name = info.filename
            if info.flag_bits & 0x1:
                rep.error("container: encrypted entry %s" % name)
            if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
                rep.error("container: %s uses compression method %d (only 0 and 8 allowed)"
                          % (name, info.compress_type))
            if name in seen:
                rep.error("container: duplicate entry %s" % name)
            seen.add(name)
            _check_entry_name(rep, name)
    else:
        for name in arc.names:
            _check_entry_name(rep, name)

    if not arc.exists("mimetype"):
        rep.error("container: missing 'mimetype'")
    else:
        content = arc.read("mimetype")
        if content != MIMETYPE.encode("ascii"):
            rep.error("container: 'mimetype' must contain exactly %r, found %r" % (MIMETYPE, content[:80]))


def _check_entry_name(rep, name):
    if name.startswith("/") or "\\" in name or any(seg == ".." for seg in name.split("/")):
        rep.error("container: invalid entry name %r" % name)


# ─── Manifest and hashes ──────────────────────────────────

def check_manifest(rep, arc, verify_hashes):
    man = load_json(rep, arc, "manifest.json", "manifest.schema.json",
                    ("acraw_version", "id", "created", "profile", "units", "coordinate_system",
                     "files", "root_hash", "writer"))
    if man is None:
        if not arc.exists("manifest.json"):
            rep.error("manifest.json is missing")
        return None

    version = str(man.get("acraw_version", ""))
    m = re.match(r"^(\d+)\.(\d+)$", version)
    if not m:
        rep.error("manifest: acraw_version %r is not MAJOR.MINOR" % version)
    elif int(m.group(1)) != SPEC_MAJOR:
        rep.error("manifest: unsupported major version %s (validator supports %d.x)" % (version, SPEC_MAJOR))
    rep.info["acraw_version"] = version
    rep.info["profile"] = man.get("profile")

    files = man.get("files") or []
    listed = {}
    for i, f in enumerate(files):
        if not require_keys(rep, f, ("path", "size", "sha256", "layer"), "manifest.files[%d]" % i):
            continue
        if f["path"] in listed:
            rep.error("manifest: %s listed twice" % f["path"])
        listed[f["path"]] = f

    present = set(n for n in arc.names if n not in EXCLUDED_FROM_MANIFEST)
    for path in sorted(present - set(listed)):
        rep.error("manifest: file %s is in the archive but not listed" % path)
    for path in sorted(set(listed) - present):
        rep.error("manifest: listed file %s is missing from the archive" % path)
    for path in sorted(set(listed) & set(EXCLUDED_FROM_MANIFEST)):
        rep.error("manifest: %s must not be listed" % path)

    if verify_hashes:
        for path in sorted(set(listed) & present):
            with arc.open(path) as fh:
                digest, size = sha256_stream(fh)
            if size != listed[path]["size"]:
                rep.error("hash: %s size %d, manifest says %d" % (path, size, listed[path]["size"]))
            if digest != listed[path]["sha256"]:
                rep.error("hash: %s SHA-256 mismatch" % path)

    rh = man.get("root_hash") or {}
    if rh.get("algorithm") != ROOT_HASH_ALGORITHM:
        rep.error("manifest: root_hash.algorithm must be %s" % ROOT_HASH_ALGORITHM)
    elif files and all(isinstance(f, dict) and {"path", "size", "sha256"} <= set(f) for f in files):
        expected = root_hash(files)
        rep.info["root_hash"] = expected
        if rh.get("value") != expected:
            rep.error("manifest: root_hash.value does not match the file list (expected %s)" % expected)

    has_l0 = any(n.startswith("L0_vendor/") for n in arc.names)
    if man.get("profile") == "distribution" and has_l0:
        rep.error("profile 'distribution' must not contain L0_vendor/")
    if man.get("profile") == "full" and not has_l0:
        rep.warn("profile 'full' without L0_vendor/: fine only if the original vendor files were not available")
    return man


# ─── L0 ───────────────────────────────────────────────────

def check_l0(rep, arc):
    vendors = sorted(set(n.split("/")[1] for n in arc.names if n.startswith("L0_vendor/") and n.count("/") >= 2))
    for v in vendors:
        doc = load_json(rep, arc, "L0_vendor/%s/vendor.json" % v, "vendor.schema.json", ("vendor_id", "packaging"))
        if doc is None and not arc.exists("L0_vendor/%s/vendor.json" % v):
            rep.error("L0: vendor folder %s has no vendor.json" % v)
        elif doc and doc.get("vendor_id") != v:
            rep.warn("L0: vendor.json vendor_id %r differs from folder %r" % (doc.get("vendor_id"), v))
    rep.info["vendors"] = vendors


# ─── L1 ───────────────────────────────────────────────────

def check_ply(rep, arc, path, capture_kind):
    try:
        with arc.open(path) as fh:
            head = fh.read(65536)
    except KeyError:
        return
    end = head.find(b"end_header")
    if not head.startswith(b"ply") or end < 0:
        rep.error("%s: not a PLY file or header too long" % path)
        return
    header = head[:end].decode("ascii", "replace").splitlines()
    fmt = next((l.split() for l in header if l.startswith("format")), None)
    if not fmt or fmt[1] != "binary_little_endian":
        rep.error("%s: PLY must be binary_little_endian" % path)
    element, props = None, {}
    for line in header:
        parts = line.split()
        if parts[:1] == ["element"]:
            element = parts[1]
            props.setdefault(element, {})
        elif parts[:1] == ["property"] and element:
            if parts[1] == "list":
                props[element][parts[-1]] = "list " + " ".join(parts[2:4])
            else:
                props[element][parts[2]] = parts[1]
    vertex = props.get("vertex")
    if vertex is None:
        rep.error("%s: PLY has no vertex element" % path)
        return
    for axis in ("x", "y", "z"):
        if vertex.get(axis) not in ("float", "float32"):
            rep.error("%s: vertex property %s must be float32" % (path, axis))
    if capture_kind == "range_grid" and "grid_index" not in vertex:
        rep.warn("%s: range_grid geometry without grid_index (required when the source exposes the grid)" % path)


def check_l1(rep, arc):
    sensors_doc = load_json(rep, arc, "L1_raw/sensors.json", "sensors.schema.json", ("sensors",))
    if sensors_doc is None and not arc.exists("L1_raw/sensors.json"):
        rep.error("L1: L1_raw/sensors.json is missing")
    sensor_ids = set()
    for s in (sensors_doc or {}).get("sensors", []) if isinstance(sensors_doc, dict) else []:
        sid = s.get("id") if isinstance(s, dict) else None
        if not sid or not ID_RE.match(sid):
            rep.error("sensors: invalid id %r" % sid)
        elif sid in sensor_ids:
            rep.error("sensors: duplicate id %s" % sid)
        sensor_ids.add(sid)
    for s in (sensors_doc or {}).get("sensors", []) if isinstance(sensors_doc, dict) else []:
        if isinstance(s, dict) and s.get("rig") and s["rig"] not in sensor_ids:
            rep.error("sensors: %s references unknown rig %s" % (s.get("id"), s["rig"]))

    capture_dirs = sorted(set(n.split("/")[2] for n in arc.names
                              if n.startswith("L1_raw/captures/") and n.count("/") >= 3))
    captures = {}
    for cid in capture_dirs:
        base = "L1_raw/captures/%s/" % cid
        doc = load_json(rep, arc, base + "capture.json", "capture.schema.json", ("id", "kind", "sensors", "payloads"))
        if doc is None:
            if not arc.exists(base + "capture.json"):
                rep.error("captures: %s has no capture.json" % cid)
            continue
        if not ID_RE.match(cid):
            rep.error("captures: invalid folder id %r" % cid)
        if doc.get("id") != cid:
            rep.error("captures: %s/capture.json id %r differs from folder" % (cid, doc.get("id")))
        captures[cid] = doc
        for sid in doc.get("sensors") or []:
            if sid not in sensor_ids:
                rep.error("captures: %s references unknown sensor %s" % (cid, sid))
        if doc.get("kind") == "range_grid" and "grid" not in doc:
            rep.error("captures: %s is range_grid but has no grid" % cid)
        for p in doc.get("payloads") or []:
            if not isinstance(p, dict) or "path" not in p:
                continue
            full = base + p["path"]
            if not arc.exists(full):
                rep.error("captures: %s payload %s is missing" % (cid, p["path"]))
            elif full.lower().endswith(".ply"):
                check_ply(rep, arc, full, doc.get("kind"))
            if p.get("sensor") and p["sensor"] not in sensor_ids:
                rep.error("captures: %s payload %s references unknown sensor %s" % (cid, p["path"], p["sensor"]))
    rep.info["captures"] = len(captures)
    rep.info["sensors"] = len(sensor_ids)

    poses = load_json(rep, arc, "L1_raw/poses.json", "poses.schema.json", ("poses",))
    posed = set()
    for i, pose in enumerate((poses or {}).get("poses", []) if isinstance(poses, dict) else []):
        if not isinstance(pose, dict):
            continue
        c = pose.get("capture")
        if c not in captures:
            rep.error("poses[%d]: unknown capture %r" % (i, c))
        if c in posed:
            rep.error("poses: more than one current pose for %s" % c)
        posed.add(c)
        _check_matrix(rep, pose.get("matrix"), "poses[%d].matrix" % i)

    scene = load_json(rep, arc, "L1_raw/scene.json", "scene.schema.json", ("nodes",))
    node_ids = set()
    nodes = (scene or {}).get("nodes", []) if isinstance(scene, dict) else []
    for n in nodes:
        if isinstance(n, dict):
            node_ids.add(n.get("id"))
    for n in nodes:
        if not isinstance(n, dict):
            continue
        if n.get("parent") is not None and n.get("parent") not in node_ids:
            rep.error("scene: node %s has unknown parent %s" % (n.get("id"), n.get("parent")))
        for c in n.get("captures") or []:
            if c not in captures:
                rep.error("scene: node %s lists unknown capture %s" % (n.get("id"), c))
        if "matrix" in n:
            _check_matrix(rep, n["matrix"], "scene node %s matrix" % n.get("id"))

    history = load_json(rep, arc, "L1_raw/history.json", "history.schema.json", ("events",))
    last = 0
    for e in (history or {}).get("events", []) if isinstance(history, dict) else []:
        if isinstance(e, dict) and isinstance(e.get("seq"), int):
            if e["seq"] <= last:
                rep.error("history: seq %d is not strictly increasing" % e["seq"])
            last = e["seq"]
    return captures


def _check_matrix(rep, m, where):
    if not (isinstance(m, list) and len(m) == 16 and all(isinstance(v, (int, float)) for v in m)):
        rep.error("%s: must be 16 numbers" % where)
        return
    if [m[12], m[13], m[14], m[15]] != [0, 0, 0, 1]:
        rep.warn("%s: last row is not 0 0 0 1" % where)


# ─── L2, provenance, anchors ──────────────────────────────

def check_l2(rep, arc, captures):
    product_dirs = sorted(set(n.split("/")[1] for n in arc.names if n.startswith("L2_derived/") and n.count("/") >= 2))
    docs = {}
    for pid in product_dirs:
        base = "L2_derived/%s/" % pid
        doc = load_json(rep, arc, base + "product.json", "product.schema.json", ("id", "kind", "inputs", "software", "files"))
        if doc is None:
            if not arc.exists(base + "product.json"):
                rep.error("L2: %s has no product.json" % pid)
            continue
        if doc.get("id") != pid:
            rep.error("L2: %s/product.json id %r differs from folder" % (pid, doc.get("id")))
        docs[pid] = doc
        for f in doc.get("files") or []:
            if isinstance(f, dict) and "path" in f and not arc.exists(base + f["path"]):
                rep.error("L2: %s file %s is missing" % (pid, f["path"]))
    for pid, doc in docs.items():
        inputs = doc.get("inputs") or {}
        for c in inputs.get("captures") or []:
            if c not in captures:
                rep.error("L2: %s input capture %s does not exist" % (pid, c))
        for p in inputs.get("products") or []:
            if p not in docs:
                rep.error("L2: %s input product %s does not exist" % (pid, p))
    rep.info["products"] = len(docs)


def check_provenance_and_anchors(rep, arc, man):
    prov = load_json(rep, arc, "provenance.json", "provenance.schema.json", ("conversions",))
    if prov is None and not arc.exists("provenance.json"):
        rep.error("provenance.json is missing")
    anchors = load_json(rep, arc, "anchors.json", "anchors.schema.json", ("anchors",))
    if anchors and man:
        expected = (man.get("root_hash") or {}).get("value")
        for i, a in enumerate(anchors.get("anchors") or []):
            if isinstance(a, dict) and a.get("root_hash") != expected:
                rep.error("anchors[%d]: root_hash does not match the manifest" % i)


# ─── Main ─────────────────────────────────────────────────

def validate(path, verify_hashes=True):
    rep = Report()
    arc = Archive(path)
    try:
        check_container(rep, arc)
        man = check_manifest(rep, arc, verify_hashes)
        check_l0(rep, arc)
        captures = check_l1(rep, arc)
        check_l2(rep, arc, captures)
        check_provenance_and_anchors(rep, arc, man)
    finally:
        arc.close()
    if jsonschema is None:
        rep.warn("jsonschema not installed: only structural checks were run (pip install jsonschema)")
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("archive")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--no-hash", action="store_true", help="skip SHA-256 verification (fast)")
    args = ap.parse_args()
    if not os.path.exists(args.archive):
        print("not found: %s" % args.archive, file=sys.stderr)
        return 2
    try:
        rep = validate(args.archive, verify_hashes=not args.no_hash)
    except (zipfile.BadZipFile, OSError) as exc:
        print("unreadable archive: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps({"valid": not rep.errors, "errors": rep.errors, "warnings": rep.warnings,
                          "info": rep.info}, indent=2))
    else:
        for e in rep.errors:
            print("ERROR   " + e)
        for w in rep.warnings:
            print("WARNING " + w)
        summary = ", ".join("%s=%s" % kv for kv in sorted(rep.info.items()) if kv[0] != "root_hash")
        print("%s  %s" % ("VALID" if not rep.errors else "INVALID", summary))
        if "root_hash" in rep.info:
            print("root_hash %s" % rep.info["root_hash"])
    return 0 if not rep.errors else 1


if __name__ == "__main__":
    sys.exit(main())
