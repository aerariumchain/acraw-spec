# AerariumChain Raw (`.acraw`)

**An open container format for raw 3D acquisition data.** Think DNG, but for 3D scanners.

Most 3D workflows keep only the final mesh. The raw data the scanner produced (individual frames, sensor-grid structure, per-frame textures, poses, edit history, calibration) stays locked in proprietary project files and is lost as soon as the vendor software is gone. AerariumChain Raw keeps it, in open formats, together with the original vendor files and a verifiable fingerprint.

| | |
|---|---|
| Specification | [SPEC.md](SPEC.md) (version 0.1, draft) |
| Media type | `application/vnd.aerariumchain.raw+zip` |
| Extension | `.acraw` |
| Schemas | [schemas/](schemas/) (JSON Schema 2020-12) |
| Reference tools | [tools/](tools/) (Python 3.8+, standard library) |
| License | [Apache 2.0](LICENSE) |

## What is inside an `.acraw` file

```
mimetype                  application/vnd.aerariumchain.raw+zip
manifest.json             version, units, every file with SHA-256, root hash
provenance.json           object, acquisition, software, conversions, rights
L0_vendor/<vendor>/       original vendor files, byte for byte (optional)
L1_raw/                   decoded raw data in open formats
  sensors.json            cameras, projectors, lasers, IMU... with calibration
  captures/<id>/          one folder per frame / photo / station / profile
  scene.json              groups as organized in the source project
  poses.json              current pose of every capture, kept separate from geometry
  history.json            edit history: earlier poses, deleted captures
  observations/           targets, tie points, matches
L2_derived/<id>/          fused meshes, dense clouds, QC reports, masks, each with its inputs
preview/                  thumbnail and glTF preview
```

It is a plain ZIP (ZIP64 for large projects). Payloads use formats every 3D tool already reads:

| Data | Format |
|---|---|
| Structured-light / ToF frames | PLY (binary) with per-vertex `grid_index`, `u`, `v`; PNG textures |
| Photographs | DNG or linear TIFF, EXIF kept; camera raw files in L0 |
| Terrestrial laser scans | E57 |
| Mobile and aerial LiDAR | LAZ 1.4 / COPC + trajectory CSV |
| Depth maps | OpenEXR |
| CT volumes | OME-Zarr or multi-page TIFF |
| Previews | glTF 2.0 (GLB) |

## Principles

1. **Raw first.** Geometry stays in the frame and resolution it was acquired in. Poses are stored separately, never baked in.
2. **Raw and derived never mix.** Anything computed later declares its inputs and lives in L2.
3. **Nothing is dropped silently.** Undecoded vendor data is kept, either as original files (L0) or as opaque properties (L1).
4. **Reuse open standards.** The container only adds the relations that existing formats lack.
5. **Verifiable.** One root hash fingerprints the whole archive. It can be timestamped or anchored on a ledger (AerariumChain or any other) without modifying the file. Anchoring is optional.

## Quick start

```bash
# Build the synthetic example and validate it
python3 tools/make_example.py
python3 tools/acraw_validate.py examples/minimal-structured-light.acraw

# Full JSON Schema validation (optional dependency)
pip install "jsonschema>=4.17"

# Seal your own directory (computes hashes and root hash) and pack it
python3 tools/acraw_pack.py path/to/my-archive -o my-archive.acraw
```

The validator accepts both the packed `.acraw` file and the unpacked directory, and returns exit code 0 when the archive is valid.

## Status

Version 0.1 is a working draft. The container, manifest, integrity rules and the structured-light profile are the most mature parts; photogrammetry observations (tie points, matches) are provisional. Feedback from people who build scanners, photogrammetry pipelines and digital archives is very welcome: please open an issue.

Planned for 0.2: normative layout for features and matches, a photogrammetry example, a reader library, detached signatures.

## Vendor importers

Importers from proprietary formats are separate projects and are not part of this repository. Product names mentioned in this repository identify formats only; trademarks belong to their owners, and no affiliation or endorsement is implied.

## Contributing

Issues and pull requests are welcome. For changes to the specification, describe the use case and the data you need to preserve; for new vendor ids, see [REGISTRY.md](REGISTRY.md). Changes are tracked in [CHANGELOG.md](CHANGELOG.md).

The format is stewarded by [AerariumChain](https://aerariumchain.com). The name comes from the *aerarium Saturni*, the treasury of ancient Rome that was also the state archive where original documents were deposited.
