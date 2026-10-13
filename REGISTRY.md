# Registries

Identifiers reserved for use in AerariumChain Raw archives. To add an entry, open a pull request.

## Vendor ids (`L0_vendor/<vendor-id>/`)

Short ids for common acquisition and processing software. Any vendor not listed here may use a reverse-DNS id (e.g. `com.example`).

| Vendor id | Used for |
|---|---|
| `artec` | Artec Studio projects |
| `shining3d` | Shining 3D (EinScan, EXStar) projects |
| `creaform` | Creaform VXelements data |
| `faro` | FARO Scene and scanner files |
| `leica` | Leica Cyclone and scanner files |
| `riegl` | RIEGL RiSCAN and scanner files |
| `trimble` | Trimble RealWorks and scanner files |
| `zf` | Z+F LaserControl files |
| `agisoft` | Agisoft Metashape projects |
| `capturingreality` | RealityCapture projects |
| `colmap` | COLMAP workspaces |
| `meshroom` | AliceVision Meshroom projects |
| `camera-raw` | Original camera raw files (CR3, NEF, ARW, RAF, ...) |
| `generic` | Original files of unspecified origin |

Names in this table identify file formats only. Trademarks belong to their respective owners.

## Extension namespaces (`extensions/<namespace>/`)

| Namespace | Owner | Purpose |
|---|---|---|
| `aerariumchain` | AerariumChain | Certification metadata |

## Anchor services (`anchors.json` `service`)

| Service | Description |
|---|---|
| `aerariumchain` | AerariumChain registration |
| `rfc3161` | RFC 3161 trusted timestamp; `reference` is the base64 timestamp token |
