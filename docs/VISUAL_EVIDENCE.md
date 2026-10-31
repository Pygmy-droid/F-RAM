# Visual Evidence Ledger

FRAM treats the image corpus as first-class evidence. Images are never dropped merely because
their pixels duplicate another file: paths, timestamps, folder context, and repetition can all
carry provenance or sequence information.

## Lossless first pass

Run the dependency-light inventory before OCR, captioning, embedding, or interpretation:

```powershell
python -m fram_serving.visual_ingest `
  "C:\Games\FRAM_V22_Starter\fram_v22_starter" `
  --output-dir storage\visual_evidence
```

The command recursively inventories PNG, JPEG, GIF, WebP, BMP, TIFF, SVG, ICO, and ICNS files. It writes:

- `visual_evidence.jsonl`: one path-level record per discovered visual;
- `visual_evidence_summary.json`: completeness counts and the manifest hash;
- `visual_duplicates.json`: exact-content groups without suppressing any path.

Every readable file receives a SHA-256 content identity (`visual:sha256:<digest>`). AppleDouble
`._*` files copied from macOS are retained as `mac_metadata_sidecar` records but are not counted as
pixel images. Unknown image-suffixed payloads remain `visual_unverified`; they are never silently
dropped. File signatures are checked independently of extensions; a valid JPEG named `.png`, for
example, is indexed as a visual and recorded as an extension mismatch. The command returns a
non-zero status if any recognized visual or directory cannot be
read. Source files are never moved, renamed, transcoded, or modified.

## Reconstruction stages

1. **Account:** lossless path, hash, format, dimensions, timestamps, origin class, and errors.
2. **Observe:** contact sheets and image-by-image visual inspection, preserving the evidence ID.
3. **Transcribe:** OCR/text regions with coordinates, confidence, and engine provenance.
4. **Interpret:** bounded descriptions, concepts, relations, and uncertainty; never overwrite raw
   observations with inferred meaning.
5. **Link:** connect visual claims to code, documents, memory records, and other images.
6. **Promote:** quarantine new interpretations until corroborated; preserve corrections as new
   records rather than erasing history.

The first pass is deliberately independent of Pillow, OCR engines, GPU runtimes, or network
services so it can prove corpus completeness before higher-level tooling is available.

## Observation sheets

After the ledger is complete, install the lightweight `visual` extra and render deterministic
review sheets:

```powershell
python -m fram_serving.visual_contact_sheet `
  storage\visual_evidence\visual_evidence.jsonl `
  "C:\Games\FRAM_V22_Starter\fram_v22_starter" `
  --output-dir artifacts\visual_evidence\contact_sheets
```

The default renders one representative for every unique pixel identity and preserves every
duplicate source path in `visual_contact_sheet_index.json`. Use `--all-paths` when folder placement
itself needs visual review. SVG records receive explicit placeholders until a provenance-safe SVG
rasterizer is added; their source and dimensions remain present in the observation index.
