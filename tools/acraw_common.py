"""Shared helpers for the AerariumChain Raw reference tools (stdlib only)."""
import hashlib
import json
import os
import zipfile

MIMETYPE = "application/vnd.aerariumchain.raw+zip"
SPEC_MAJOR = 0
EXCLUDED_FROM_MANIFEST = {"mimetype", "manifest.json", "anchors.json"}
ROOT_HASH_ALGORITHM = "acraw-root-sha256-v1"

MEDIA_TYPES = {
    ".json": "application/json",
    ".ply": "application/x-ply",
    ".png": "image/png",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".dng": "image/x-adobe-dng",
    ".e57": "application/x-e57",
    ".laz": "application/vnd.laszip",
    ".las": "application/vnd.las",
    ".exr": "image/x-exr",
    ".glb": "model/gltf-binary",
    ".csv": "text/csv",
    ".txt": "text/plain",
}

# Payloads that are already compressed or need random access: store, don't deflate.
STORED_EXTENSIONS = {".ply", ".png", ".tif", ".tiff", ".dng", ".e57", ".laz", ".las", ".exr", ".glb",
                     ".jpg", ".jpeg", ".zip"}


def layer_of(path):
    first = path.split("/", 1)[0]
    return {
        "L0_vendor": "L0",
        "L1_raw": "L1",
        "L2_derived": "L2",
        "preview": "preview",
        "extensions": "extension",
    }.get(first, "meta")


def media_type_of(path):
    return MEDIA_TYPES.get(os.path.splitext(path)[1].lower())


def sha256_stream(fh, chunk=1 << 20):
    h = hashlib.sha256()
    size = 0
    while True:
        block = fh.read(chunk)
        if not block:
            break
        h.update(block)
        size += len(block)
    return h.hexdigest(), size


def root_hash(files):
    """acraw-root-sha256-v1: SHA-256 over sorted '<sha256> <size> <path>\\n' lines."""
    ordered = sorted(files, key=lambda f: f["path"].encode("utf-8"))
    data = b"".join(("%s %d %s\n" % (f["sha256"], f["size"], f["path"])).encode("utf-8") for f in ordered)
    return hashlib.sha256(data).hexdigest()


class Archive:
    """Uniform read access to the packaged (ZIP) and directory forms."""

    def __init__(self, path):
        self.path = path
        self.is_zip = os.path.isfile(path)
        if self.is_zip:
            self.zip = zipfile.ZipFile(path)
            self.names = [i.filename for i in self.zip.infolist() if not i.filename.endswith("/")]
        else:
            self.zip = None
            names = []
            for root, _dirs, files in os.walk(path):
                for fn in files:
                    full = os.path.join(root, fn)
                    names.append(os.path.relpath(full, path).replace(os.sep, "/"))
            self.names = sorted(names)

    def exists(self, name):
        return name in self._name_set()

    def _name_set(self):
        if not hasattr(self, "_set"):
            self._set = set(self.names)
        return self._set

    def open(self, name):
        if self.is_zip:
            return self.zip.open(name)
        return open(os.path.join(self.path, *name.split("/")), "rb")

    def read(self, name):
        with self.open(name) as fh:
            return fh.read()

    def json(self, name):
        return json.loads(self.read(name).decode("utf-8"))

    def close(self):
        if self.zip:
            self.zip.close()
