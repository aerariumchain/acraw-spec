#!/usr/bin/env python3
"""Seal an AerariumChain Raw directory and optionally pack it into an .acraw file.

Usage:
    python3 tools/acraw_pack.py <directory> [-o out.acraw]

The directory must contain a manifest.json with the descriptive fields
(acraw_version, id, title, created, profile, units, coordinate_system, writer).
This tool (re)computes `files` and `root_hash`, writes the `mimetype` file,
saves the updated manifest and, with -o, writes a ZIP that follows section 3
of the specification: `mimetype` first and stored, payloads stored, JSON deflated.
"""
import argparse
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from acraw_common import (  # noqa: E402
    EXCLUDED_FROM_MANIFEST, MIMETYPE, ROOT_HASH_ALGORITHM, STORED_EXTENSIONS, Archive, layer_of, media_type_of,
    root_hash, sha256_stream,
)


def seal(directory):
    with open(os.path.join(directory, "mimetype"), "wb") as fh:
        fh.write(MIMETYPE.encode("ascii"))
    man_path = os.path.join(directory, "manifest.json")
    with open(man_path) as fh:
        man = json.load(fh)

    arc = Archive(directory)
    files = []
    for name in arc.names:
        if name in EXCLUDED_FROM_MANIFEST or name.split("/")[-1] == ".DS_Store":
            continue
        with arc.open(name) as fh:
            digest, size = sha256_stream(fh)
        entry = {"path": name, "size": size, "sha256": digest, "layer": layer_of(name)}
        mt = media_type_of(name)
        if mt:
            entry["media_type"] = mt
        files.append(entry)
    files.sort(key=lambda f: f["path"].encode("utf-8"))

    man["files"] = files
    man["root_hash"] = {"algorithm": ROOT_HASH_ALGORITHM, "value": root_hash(files)}
    with open(man_path, "w") as fh:
        json.dump(man, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return man


def pack(directory, out_path, man):
    names = ["manifest.json"] + [f["path"] for f in man["files"]]
    if os.path.exists(os.path.join(directory, "anchors.json")):
        names.append("anchors.json")
    with zipfile.ZipFile(out_path, "w", allowZip64=True) as z:
        info = zipfile.ZipInfo("mimetype", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, MIMETYPE.encode("ascii"))
        for name in names:
            ext = os.path.splitext(name)[1].lower()
            method = zipfile.ZIP_STORED if ext in STORED_EXTENSIONS else zipfile.ZIP_DEFLATED
            z.write(os.path.join(directory, *name.split("/")), name, compress_type=method)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("directory")
    ap.add_argument("-o", "--output", help="write a packed .acraw file")
    args = ap.parse_args()
    man = seal(args.directory)
    print("sealed %d files, root_hash %s" % (len(man["files"]), man["root_hash"]["value"]))
    if args.output:
        pack(args.directory, args.output, man)
        print("wrote %s" % args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
