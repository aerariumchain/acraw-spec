# AerariumChain Raw (`.acraw`) Specification

**Version:** 0.1 (draft)
**Status:** Working draft, open for comments. Breaking changes are possible until 1.0.
**Media type:** `application/vnd.aerariumchain.raw+zip`
**File extension:** `.acraw`

---

## 1. Introduction

AerariumChain Raw is an open container format for **raw 3D acquisition data**: structured-light scanners, photogrammetry, terrestrial and mobile laser scanning, laser-line metrology and industrial CT.

It plays for 3D capture the role that DNG plays for digital photography:

- it keeps the **most raw data the acquisition system exposes**, not only the final model;
- it stores that data in **existing open formats** (PLY, PNG, TIFF/DNG, E57, LAZ, OpenEXR, JSON) wherever one fits;
- it can carry the **original vendor files byte for byte**, so nothing is lost even when part of the vendor data is not yet understood;
- it records **provenance and integrity** (SHA-256 of every file plus a single root hash) so that an archive can be verified, cited and anchored on a ledger.

The format is vendor neutral. Nothing in this specification depends on a specific scanner, software or ledger.

### 1.1 Design principles

1. **Raw first.** Keep data in the coordinate frame and resolution in which it was acquired. Do not pre-multiply poses into geometry, do not resample, do not discard sparse-grid structure.
2. **Raw and derived are separate.** Anything computed after acquisition (fusion, cleaning, registration error, masks) lives in a separate layer and declares its inputs.
3. **Reuse open standards.** The container adds what existing formats lack: the relations between sensors, captures, poses, history and products.
4. **Lossless migration.** A conforming writer never drops vendor data silently: undecoded data is either preserved verbatim (L0) or recorded as opaque properties (L1).
5. **Verifiable.** Every file is hashed; the archive has one reproducible fingerprint.

### 1.2 Conventions

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, RECOMMENDED, MAY and OPTIONAL are to be interpreted as described in RFC 2119 and RFC 8174.

JSON documents are UTF-8 encoded (RFC 8259). JSON Schemas for every document are provided in [`schemas/`](schemas/) (JSON Schema draft 2020-12). Where this text and a schema disagree, this text prevails.

---

## 2. Layers

An archive is organized in three layers plus optional previews.

| Layer | Folder | Content | Required |
|---|---|---|---|
| **L0** vendor | `L0_vendor/` | Original vendor files, byte for byte | No (see profiles) |
| **L1** raw | `L1_raw/` | Decoded raw data in open formats: sensors, captures, poses, observations, history | **Yes** |
| **L2** derived | `L2_derived/` | Products computed from L1 (or L0): fused meshes, dense clouds, QC reports, masks, alignments | No |
| Preview | `preview/` | Thumbnails and lightweight models for display | No |

### 2.1 Profiles

| Profile | `manifest.profile` | Rules |
|---|---|---|
| Full archive | `full` | L0 SHOULD be present whenever the writer had access to the original vendor files |
| Distribution | `distribution` | L0 is omitted. The manifest SHOULD reference the full archive it was derived from (`derived_from`) |

---

## 3. Container

### 3.1 Packaged form (ZIP)

An `.acraw` file is a ZIP archive (PKWARE APPNOTE 6.3.x). ZIP64 extensions MUST be supported by readers and SHOULD be used by writers when any limit of classic ZIP is exceeded (real projects routinely exceed 4 GB).

1. The first entry MUST be named `mimetype`, MUST be stored without compression, MUST NOT have an extra field and MUST contain exactly the ASCII bytes `application/vnd.aerariumchain.raw+zip` with no trailing newline. This makes the file recognizable at a fixed offset even when renamed.
2. Payload files that are already compressed or that benefit from random access (PLY, PNG, TIFF, DNG, E57, LAZ, EXR, GLB) SHOULD be stored without compression (method 0). JSON and text files MAY use Deflate (method 8). Other compression methods MUST NOT be used.
3. Entry names MUST be UTF-8 (general purpose flag bit 11 set), MUST use `/` as separator, MUST be relative, MUST NOT contain `..` segments, MUST be unique and are case sensitive.
4. Encryption MUST NOT be used at the ZIP level.

### 3.2 Directory form

An unpacked archive is a directory with the same tree, including the `mimetype` file. Readers SHOULD accept both forms. The two forms are equivalent: packing a directory and unpacking a file MUST yield the same root hash (section 11).

### 3.3 Top-level tree

```
mimetype                     REQUIRED
manifest.json                REQUIRED   section 4
provenance.json              REQUIRED   section 10
anchors.json                 OPTIONAL   section 11.3
L0_vendor/<vendor-id>/...    OPTIONAL   section 5
L1_raw/
  sensors.json               REQUIRED   section 6.2
  scene.json                 OPTIONAL   section 6.4
  poses.json                 REQUIRED if any capture has a pose   section 6.5
  history.json               OPTIONAL   section 6.6
  captures/<capture-id>/
    capture.json             REQUIRED per capture   section 6.3
    <payload files>
  observations/              OPTIONAL   section 6.7
L2_derived/<product-id>/
  product.json               REQUIRED per product   section 8
  <product files>
preview/                     OPTIONAL   section 9
extensions/<namespace>/      OPTIONAL   section 12
```

Identifiers used as folder names (`capture-id`, `product-id`, `vendor-id`, `namespace`) MUST match `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`.

---

## 4. Manifest (`manifest.json`)

Schema: [`schemas/manifest.schema.json`](schemas/manifest.schema.json)

```json
{
  "acraw_version": "0.1",
  "id": "urn:uuid:5b0f6c1e-8c1d-4c5e-9a57-0f6a3c2d1e10",
  "title": "Example object, inv. 0001",
  "created": "2026-10-13T09:30:00Z",
  "profile": "full",
  "units": { "length": "mm" },
  "coordinate_system": { "handedness": "right", "up_axis": "+Z", "crs": null },
  "derived_from": null,
  "files": [
    { "path": "provenance.json", "size": 812, "sha256": "…", "media_type": "application/json", "layer": "meta" },
    { "path": "L1_raw/captures/f0001/mesh.ply", "size": 59024, "sha256": "…", "media_type": "application/x-ply", "layer": "L1" }
  ],
  "root_hash": { "algorithm": "acraw-root-sha256-v1", "value": "…" },
  "writer": { "name": "example-writer", "version": "1.2.0" }
}
```

| Field | Rules |
|---|---|
| `acraw_version` | REQUIRED. `MAJOR.MINOR`. Readers MUST reject an unknown MAJOR and SHOULD read a newer MINOR, ignoring unknown fields |
| `id` | REQUIRED. A `urn:uuid:` URN, unique per archive. A new id is REQUIRED whenever L1 content changes |
| `profile` | REQUIRED. `full` or `distribution` |
| `units.length` | REQUIRED. `mm` or `m`. Applies to every length in L1 and L2 unless a document states otherwise |
| `coordinate_system` | REQUIRED. `handedness` MUST be `right`. `crs` is an optional EPSG code (e.g. `"EPSG:32632"`) for georeferenced data |
| `derived_from` | OPTIONAL. `{ "id", "root_hash" }` of the archive this one was produced from (e.g. a distribution copy of a full archive) |
| `files` | REQUIRED. Every file in the archive except `mimetype`, `manifest.json` and `anchors.json`, exactly once |
| `files[].layer` | `meta`, `L0`, `L1`, `L2`, `preview` or `extension` |
| `root_hash` | REQUIRED. See section 11 |
| `writer` | REQUIRED. Name and version of the software that wrote the archive |

---

## 5. L0: vendor layer

`L0_vendor/<vendor-id>/` holds original files exactly as produced by the acquisition or processing software.

1. Files in L0 MUST be byte-identical to the originals. Writers MUST NOT re-encode, re-compress, normalize or partially copy them.
2. Each vendor folder MUST contain a `vendor.json` (schema [`schemas/vendor.schema.json`](schemas/vendor.schema.json)):

```json
{
  "vendor_id": "examplevendor",
  "software": { "name": "Example Studio", "version": "20.0.1" },
  "packaging": "files",
  "original_root": "MyProject",
  "notes": "Complete project folder copied verbatim."
}
```

3. `packaging` is one of:
   - `files`: the original files and folders, verbatim, under `L0_vendor/<vendor-id>/files/`;
   - `kv-export`: for vendor formats that are embedded databases, each record stored as one file under `L0_vendor/<vendor-id>/kv/`, keys percent-encoded (RFC 3986 unreserved set kept as is), values stored exactly as read from the database, without decompression. Writers SHOULD prefer `files` when the database files themselves can be copied consistently;
   - `archive`: a single original container file stored as is.
4. Readers are not required to interpret L0. L0 exists so that future tools, or the original vendor software, can recover everything.
5. Registered `vendor-id` values are listed in [`REGISTRY.md`](REGISTRY.md). Unregistered vendors SHOULD use a reverse-DNS id (e.g. `com.example`).

---

## 6. L1: raw layer

### 6.1 Geometry conventions

- **Matrices** are 4x4, row-major, float64, for column vectors: `p' = M · p`, translation in the fourth column (`m[3]`, `m[7]`, `m[11]`), last row `0 0 0 1`. They are serialized as a flat JSON array of 16 numbers.
- **A pose** maps points from the local frame of a capture (or scene node) to the frame of its parent.
- **World coordinates** of a capture point are obtained by composing the scene chain from the root down to the capture: `p_world = N_root · … · N_parent · P_capture · p_local`.
- All lengths use `manifest.units.length`.
- **Texture coordinates** follow the OpenGL / PLY convention: `(0,0)` is the **bottom-left** corner of the image, `v` grows upwards. Image files are stored in their normal top-down row order; writers converting from bottom-up sources (e.g. BMP) MUST flip rows, not UVs.
- **Timestamps** are RFC 3339 strings in UTC. Sub-second precision MAY be added in `timestamp_ns` (integer nanoseconds since the Unix epoch) when the source provides it.

### 6.2 Sensors (`L1_raw/sensors.json`)

Schema: [`schemas/sensors.schema.json`](schemas/sensors.schema.json)

A sensor is any device that produced data: a camera, a projector, a structured-light head, a laser, an IMU, a GNSS receiver, a CT detector. A device made of several sensors is described as a `rig`, whose members carry their extrinsics relative to the rig.

```json
{
  "sensors": [
    {
      "id": "head",
      "kind": "structured_light_rig",
      "make": "ExampleScan", "model": "Model S", "serial": "SN-0001", "firmware": "4.2",
      "calibration": { "source": "factory", "date": "2026-01-15" }
    },
    {
      "id": "head.tex",
      "kind": "camera",
      "rig": "head",
      "sensor_to_rig": [1,0,0,12.5, 0,1,0,0, 0,0,1,0, 0,0,0,1],
      "intrinsics": {
        "model": "opencv",
        "width": 1280, "height": 1024,
        "fx": 1450.2, "fy": 1449.8, "cx": 640.1, "cy": 511.7,
        "distortion": { "k1": -0.12, "k2": 0.03, "p1": 0.0001, "p2": -0.0002, "k3": 0.0 }
      }
    }
  ]
}
```

| `kind` | Typical use |
|---|---|
| `camera` | RGB or monochrome camera (texture camera, photogrammetry camera) |
| `projector` | Pattern projector of a structured-light system |
| `structured_light_rig` | Handheld or fixed structured-light head |
| `laser_line` | Laser-line probe on an arm or tracker |
| `tls` | Terrestrial laser scanner |
| `lidar` | Mobile or aerial LiDAR unit |
| `imu`, `gnss` | Inertial and positioning units |
| `ct_source`, `ct_detector` | Industrial CT |
| `other` | Anything else (describe in `notes`) |

Intrinsic models: `pinhole`, `opencv` (k1, k2, p1, p2, k3, optional k4-k6), `opencv_fisheye` (k1-k4), `spherical` (for panoramic TLS imagery), `unknown`. Writers MUST NOT invent intrinsics: when the vendor does not expose them, use `"model": "unknown"` or omit `intrinsics`.

`calibration.source` is `factory`, `field`, `self_calibrated` (estimated during processing, e.g. bundle adjustment) or `unknown`.

### 6.3 Captures (`L1_raw/captures/<capture-id>/capture.json`)

Schema: [`schemas/capture.schema.json`](schemas/capture.schema.json)

A capture is one acquisition unit: one structured-light frame, one photograph, one TLS station, one laser-line profile, one CT projection set.

```json
{
  "id": "f0001",
  "kind": "range_grid",
  "sensors": ["head", "head.tex"],
  "timestamp": "2024-12-11T14:36:23Z",
  "status": "active",
  "grid": { "width": 640, "height": 480 },
  "payloads": [
    { "role": "geometry", "path": "mesh.ply" },
    { "role": "texture", "path": "texture.png", "sensor": "head.tex" }
  ],
  "vendor_metrics": { "quality": 0.87 },
  "vendor_properties": { "name": "frame_0001" },
  "vendor_raw_properties": [ { "id": "0x0000002a", "encoding": "hex", "value": "01000000" } ]
}
```

| Field | Rules |
|---|---|
| `id` | REQUIRED, equal to the folder name |
| `kind` | REQUIRED, see table below |
| `sensors` | REQUIRED, ids from `sensors.json` |
| `status` | `active` (default) or `deleted`. Captures deleted in the source project but still recoverable SHOULD be kept with `deleted` status rather than dropped |
| `payloads` | REQUIRED. Paths are relative to the capture folder |
| `vendor_metrics` | Values computed **by the acquisition software** and stored in the source. Values computed by the converter or later tools MUST NOT go here (they belong to L2) |
| `vendor_properties` | Decoded vendor properties without a defined field in this spec |
| `vendor_raw_properties` | Properties the writer could not decode, kept as opaque bytes with their vendor id. `encoding` is `hex` or `base64` |

#### 6.3.1 Capture kinds and payload formats

| `kind` | Description | Payload roles | Format |
|---|---|---|---|
| `range_grid` | Structured-light or ToF frame: geometry on a (possibly sparse) sensor grid | `geometry` REQUIRED, `texture`, `confidence`, `image_raw` | PLY (6.3.2), PNG or TIFF |
| `image` | Photograph | `image_raw` and/or `image_linear` REQUIRED, `mask`, `depth` | DNG or TIFF; OpenEXR for depth |
| `tls_scan` | Terrestrial laser scan station | `scan` REQUIRED, `panorama` | E57 (ASTM E2807); TIFF |
| `point_cloud` | Unstructured cloud (mobile LiDAR chunk, import) | `geometry` REQUIRED | LAZ 1.4 (COPC RECOMMENDED) or PLY |
| `line_profile` | Laser-line stripe or batch of stripes | `geometry` REQUIRED | PLY with `line_index` and `timestamp_ns` per vertex |
| `volume` | CT reconstruction or projection stack | `volume` or `projections` REQUIRED | OME-Zarr (inside the ZIP, stored) or multi-page TIFF |
| `trajectory` | Continuous pose stream (IMU/GNSS/SLAM) | `trajectory` REQUIRED | CSV (6.3.4) |

Payload `media_type` MAY be given explicitly; otherwise it is inferred from the extension. Other open formats MAY be used for a role when the listed one cannot represent the data, provided the format has a public specification.

#### 6.3.2 PLY payloads

- PLY MUST be `binary_little_endian 1.0`.
- Vertex element: `x`, `y`, `z` as `float` (float32) are REQUIRED, in the **local frame of the capture**, never pre-transformed.
- OPTIONAL standard vertex properties: `nx ny nz` (float), `red green blue alpha` (uchar), `u v` (float, texture coordinates per 6.1; a vertex without texture coordinates uses `u = v = -1`), `confidence` (float), `intensity` (float).
- `grid_index` (uint): for `range_grid` captures, the row-major index `row * grid.width + col` of the sensor grid cell that produced the vertex. It MUST be present when the source exposes grid structure. This preserves the sparse sensor layout that most mesh exports discard.
- Face element: `vertex_indices` as `list uchar uint`, indices into the vertex element, counter-clockwise winding for outward normals when known.
- Additional properties are allowed and SHOULD be documented in `capture.json` under `ply_properties`.

#### 6.3.3 Images

- The camera's original raw file (CR3, NEF, ARW, RAF, …) belongs in L0. In L1, `image_raw` SHOULD be DNG; when conversion to DNG is not possible, `image_linear` SHOULD be a linear 16-bit TIFF.
- Writers MUST preserve EXIF/XMP metadata present in the source.
- Textures extracted from range-grid systems SHOULD be stored as lossless PNG (8 or 16 bit) with pixel values identical to the source.

#### 6.3.4 Trajectory CSV

UTF-8, comma separated, header row REQUIRED. Columns: `timestamp_ns,tx,ty,tz,qw,qx,qy,qz`, optional `sigma_tx,sigma_ty,sigma_tz,sigma_rx,sigma_ry,sigma_rz`. Quaternions are unit, Hamilton convention, rotating local to parent.

### 6.4 Scene graph (`L1_raw/scene.json`)

Schema: [`schemas/scene.schema.json`](schemas/scene.schema.json)

Optional hierarchy of groups as organized in the source project (scan groups, stations, chunks). Each node has an `id`, a `name`, an optional `parent`, an optional `matrix` (node to parent) and the list of `captures` it contains. Captures not listed in any node are children of the root. Keeping the vendor hierarchy and its matrices separate from capture poses is REQUIRED when the source stores them separately.

### 6.5 Poses (`L1_raw/poses.json`)

Schema: [`schemas/poses.schema.json`](schemas/poses.schema.json)

```json
{
  "poses": [
    {
      "capture": "f0001",
      "matrix": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
      "source": "vendor",
      "covariance": null
    }
  ]
}
```

- At most one **current** pose per capture appears here. Earlier poses belong to `history.json`.
- `source` is `vendor` (as stored in the source project) or `imported` (from another tool's file, named in `notes`). Poses recomputed by later processing are L2 products (`alignment`, section 8).
- `covariance` is an optional 6x6 row-major matrix (translation then rotation as axis-angle, in units² and rad²).

### 6.6 History (`L1_raw/history.json`)

Schema: [`schemas/history.schema.json`](schemas/history.schema.json)

Many acquisition programs keep an edit history (registrations, deletions, regrouping). That history is raw information: it contains earlier poses and captures removed by the operator. When the source exposes it, writers SHOULD export it as an ordered list of events:

```json
{
  "events": [
    { "seq": 1, "timestamp": "2024-12-11T14:40:00Z", "author": null, "op": "create",   "target": "f0001" },
    { "seq": 2, "op": "set_pose", "target": "f0001", "data": { "matrix": [/* 16 numbers */] } },
    { "seq": 3, "op": "reparent", "target": "f0001", "data": { "parent": "group-a" } },
    { "seq": 4, "op": "delete",   "target": "f0002" }
  ]
}
```

`op` is one of `create`, `delete`, `set_pose`, `set_property`, `reparent`, `set_payload`, `other`. Replaying all events in order MUST yield the current state described by `scene.json`, `poses.json` and the capture `status` fields.

### 6.7 Observations (`L1_raw/observations/`)

Provisional in 0.1. Holds data needed to redo registration or bundle adjustment from scratch:

- `targets.json`: coded or uncoded targets and markers, with id, type and measured coordinates per capture;
- `features/` and `matches/`: keypoints and correspondences. In 0.1 writers MAY store them in the COLMAP binary database layout or as documented JSON; the chosen layout MUST be declared in `observations/observations.json` (`"layout": "colmap-db" | "json"`).

A normative compact layout is planned for 0.2.

---

## 7. Capture system profiles (informative)

How common acquisition systems map onto L0 and L1:

| System | L0 | L1 |
|---|---|---|
| Structured light (handheld or fixed) | Vendor project folder | One `range_grid` capture per frame, PLY with `grid_index` + PNG texture, scene groups, vendor poses, history |
| Photogrammetry | Camera raw files, photogrammetry software project | One `image` capture per photo (DNG + EXIF), camera sensors with intrinsics, poses from the SfM solution (`imported`), tie points in `observations/` |
| Terrestrial laser scanning | Vendor scan files | One `tls_scan` capture per station (E57), panoramas, station poses, targets |
| Mobile and aerial LiDAR | Vendor files | `point_cloud` captures (LAZ/COPC), `trajectory` capture, IMU/GNSS sensors |
| Laser-line metrology | Vendor files | `line_profile` captures, tracker poses |
| Industrial CT | Vendor files | `volume` capture (projections and/or reconstruction), source and detector sensors |

---

## 8. L2: derived layer

Schema: [`schemas/product.schema.json`](schemas/product.schema.json)

Each product lives in `L2_derived/<product-id>/` with a `product.json`:

```json
{
  "id": "fusion-01",
  "kind": "fused_mesh",
  "inputs": { "captures": ["f0001", "f0002"], "products": [] },
  "software": { "name": "example-fusion", "version": "3.1" },
  "parameters": { "resolution_mm": 0.2 },
  "created": "2026-10-13T10:00:00Z",
  "files": [ { "role": "mesh", "path": "fused.ply" }, { "role": "texture", "path": "fused.png" } ]
}
```

`kind` values: `fused_mesh`, `dense_cloud`, `sparse_cloud`, `textured_model`, `orthophoto`, `depth_maps`, `mask_set`, `alignment` (recomputed poses, same structure as `poses.json`), `qc_report`, `measurement`, `other`. Inputs MUST reference existing captures or products. Products imported from the source project (e.g. a fused model saved by the scanner software) use `software` to name the original program.

---

## 9. Previews

`preview/thumbnail.png` (RECOMMENDED, longest side 512 px) and `preview/model.glb` (glTF 2.0 binary, OPTIONAL) are for display only. Readers MUST NOT treat previews as data.

---

## 10. Provenance (`provenance.json`)

Schema: [`schemas/provenance.schema.json`](schemas/provenance.schema.json)

```json
{
  "subject": {
    "type": "artwork",
    "title": "Example object",
    "identifiers": [ { "scheme": "inventory", "value": "0001" } ],
    "holder": "Example Museum"
  },
  "acquisition": {
    "organization": "Example Digitization Lab",
    "operator": "Operator name or role",
    "location": "Conservation lab, room 2",
    "start": "2024-12-11T14:30:00Z",
    "end": "2024-12-11T16:05:00Z",
    "environment": { "temperature_c": 20.5, "relative_humidity": 48 }
  },
  "software": [
    { "name": "Example Studio", "version": "20.0.1", "role": "acquisition" }
  ],
  "conversions": [
    { "tool": "example-converter", "version": "0.3.0", "from": "examplevendor project", "date": "2026-10-13T09:30:00Z" }
  ],
  "rights": { "rights_holder": "Example Museum", "license": "All rights reserved" }
}
```

All fields except `conversions` are OPTIONAL but RECOMMENDED. `conversions` MUST list every tool that wrote or rewrote the archive, in order.

Provenance may contain personal data (operator names). Writers SHOULD allow replacing names with roles, and distribution copies SHOULD be reviewed before publication.

---

## 11. Integrity and anchoring

### 11.1 File hashes

Every file listed in `manifest.files` carries its size in bytes and its SHA-256 (lowercase hex). Readers that validate an archive MUST check both.

### 11.2 Root hash (`acraw-root-sha256-v1`)

The root hash is a single fingerprint of the archive content:

1. Take every entry of `manifest.files`.
2. Build one line per file: `<sha256> <size> <path>\n` (single spaces, LF).
3. Sort lines by `path` compared as UTF-8 byte strings.
4. Concatenate and compute SHA-256 of the result. The lowercase hex digest is `root_hash.value`.

`mimetype`, `manifest.json` and `anchors.json` are excluded, so the root hash does not depend on packaging and can be registered externally without modifying the archive.

### 11.3 Anchors (`anchors.json`)

Optional records that the root hash was registered on a ledger or timestamping service (RFC 3161 TSA, a blockchain, AerariumChain):

```json
{
  "anchors": [
    { "service": "aerariumchain", "network": "mainnet", "reference": "0x…", "root_hash": "…", "anchored_at": "2026-10-13T11:00:00Z" }
  ]
}
```

An anchor is valid only if its `root_hash` equals the manifest root hash. Anchoring is optional and independent of the format: an archive with no anchors is fully conformant.

---

## 12. Extensions

- Private or experimental data goes under `extensions/<namespace>/`, where `namespace` is a registered id or reverse DNS.
- Any JSON object defined by this specification MAY contain an `extras` object for additional fields.
- Readers MUST ignore unknown extensions, unknown `extras` and unknown fields, and SHOULD preserve them when rewriting an archive.

---

## 13. Conformance

**A conforming writer** MUST:

1. produce the container per section 3 and a manifest whose `files`, sizes, hashes and root hash are correct;
2. write `sensors.json`, one `capture.json` per capture and `poses.json` when poses exist, valid against the schemas;
3. keep geometry in capture-local coordinates with poses separate;
4. never place converter-computed values in `vendor_metrics` or L1;
5. record itself in `provenance.conversions` and `manifest.writer`.

**A conforming reader** MUST:

1. recognize the `mimetype` entry and reject unknown MAJOR versions;
2. accept ZIP64 and both container forms;
3. ignore unknown fields, extensions and payload roles without failing.

A reference validator is provided in [`tools/acraw_validate.py`](tools/acraw_validate.py).

---

## 14. Vendor importers (informative)

Importers that read proprietary formats (L0 to L1) are separate projects and are not part of this specification. Product names used in documentation of importers identify the source format only; trademarks belong to their owners and their use does not imply affiliation or endorsement.

---

## 15. Versioning and change process

- `MAJOR.MINOR`. MINOR versions add optional fields, kinds and roles; MAJOR versions may break compatibility.
- Changes are proposed as issues and pull requests on this repository. See [`CHANGELOG.md`](CHANGELOG.md).
- Registration of the media type `application/vnd.aerariumchain.raw+zip` with IANA is planned for version 1.0.
