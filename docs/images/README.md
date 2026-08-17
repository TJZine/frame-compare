---
search:
  exclude: true
---

# Documentation image capture record

This directory contains the V2 public-facing screenshots used by the README and
documentation site. The capture follows the active
[V2 screenshot remediation plan](../plans/2026-08-17-documentation-v2-screenshot-remediation.md)
and uses one rights-cleared natural-image source set.

This record exists to keep future recaptures consistent, publication-safe, and
reproducible. It is not a second documentation workflow or a product contract.

## Canonical capture workspace

Use a clean workspace outside the repository and outside the installed portable bundle:

```text
C:\FrameCompareDemo\
├── config\
│   └── config.toml
├── comparison_videos\
│   ├── reference.mkv
│   ├── hlg10-encode.mkv
│   └── pq10-encode.mkv
└── generated\
```

The physical filenames are deliberately generic. Do not capture original release names,
release groups, private download paths, usernames, server names, or collection paths.

Use explicit presentation labels:

```toml
[sources]
reference = "reference.mkv"
analysis_source = "reference"
label_mode = "stem"

[sources.overrides."reference.mkv"]
label = "EBU DVB PQ10 — Reference"

[sources.overrides."hlg10-encode.mkv"]
label = "EBU DVB HLG10 — Comparison"

[sources.overrides."pq10-encode.mkv"]
label = "EBU DVB PQ10 — SDR Presentation"
```

When the report does not present the title elsewhere, prefix each label with the
publication-safe title. When it does, source-only labels are cleaner and avoid repeating
the same title in every control.

## Provenance record

Complete this table during each capture pass:

| Field | Recorded value |
| --- | --- |
| Source title | EBU/DVB HEVC Test Content: PQ10 and HLG10 natural harbour sequence |
| Rights basis | EBU-published media, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Attribution requirement | Credit EBU; footage by Frans de Jong; HLG-to-PQ10 conversion by Andrew Cotton (BBC); link to the [EBU/DVB HEVC test-content page](https://dvb.org/specifications/verification-validation/hevc-test-content/) |
| Physical filenames | `reference.mkv` (PQ10 remux), `hlg10-encode.mkv` (HLG10 remux), `pq10-encode.mkv` (FFmpeg SDR presentation derivative) |
| Display labels | `EBU DVB PQ10 — Reference`; `EBU DVB HLG10 — Comparison`; `EBU DVB PQ10 — SDR Presentation` |
| Frame number and category | Frame `1000`, `User`; 1 selected frame, 3 clips |
| Frame Compare commit or release | `ac9b2fa24c83558af28105b895c5893ae9f48a95` on `dev/v0.2.0` |
| Media-runtime profile | Windows portable bundle from the same commit; VapourSynth R79/API 4.2, L-SMASH-Works, vs-placebo 2.0.4, FFmpeg n8.1.2-34-g9b6c8969e0-20260731, Vulkan-capable path |
| Capture host and OS | One physical Windows 10 Home 22H2 host, build 19045; display scaling 100% |
| Browser and version | Codex In-app Browser (IAB production build; exact embedded engine version is not surfaced by the connector) |
| Display scaling and browser zoom | Windows 100%; browser zoom 100%; report capture viewport 1683×1080 (exact visible IAB surface, 1080p height) |
| Report theme | Dark |
| Capture date | 2026-08-17 |
| Captured by | Codex capture pass; maintainer review pending |

Do not publish a screenshot until the rights basis and required attribution are known.

The downloaded source hashes were `33773E7275B83976B0D9A19D3AED47AA0FEDB1280BA2019FE3DD344A05DA8D83`
(PQ10) and `B9EA646565751BB41CFC1F954172FDF5162C890D35AAC22238F536F6CF425300`
(HLG10). The capture-workspace hashes were `32E1632D0D32EDE7A1D806505422908338CDB75A303C8146D389BC8302A83CAC`
(`reference.mkv`), `EC7C29952B75B291C603DA7D16A9C1549385297BBB970A436B80178D5AEA8A0E`
(`hlg10-encode.mkv`), and `271AB130410462CEE6EA19B9D69FA2E3CEADD7E1AA856E51ED1DAA74AE32E9FC`
(`pq10-encode.mkv`).

## Asset policy

- Capture a lossless PNG first.
- Do not upscale.
- Use WebP for report and VSPreview imagery when text and fine detail remain sharp.
- Keep terminal captures as PNG.
- Strip EXIF and unrelated metadata during export.
- Preserve one canonical report overview and reuse it in the README, documentation home,
  and report guide.
- Keep source labels, selected pair, frame/category context, and visible controls
  consistent across the report overview, slider, grid, diff, and inspector assets.
- Use one browser, one zoom level, and one Windows display-scaling setting for the
  complete report-viewer set.
- Record any deliberate exception in this file.

## Deliberate capture decisions

- `report-diff.webp` retains the controlled-pattern locator. The natural PQ/HLG/SDR
  difference flooded the frame with presentation-transform colour changes and was
  misleading at normal documentation width; the retained caption explicitly describes
  the pattern as a changed-region locator, not source footage.
- `report-grid.webp` keeps the inspector's Clips tab open so all three full labels and
  their HDR/SDR roles remain readable while the three natural frames are visible.
- The report overview, slider, grid, and inspector assets were recaptured after the
  report-viewer HUD fixes in commit `ac9b2fa24c83558af28105b895c5893ae9f48a95`.
  The capture host exposes a 1683×1080 visible in-app-browser surface; a 1920-wide
  CSS override clipped the report controls, so the exact visible 1080p-height surface
  is recorded and no upscaling is used.
- `report-inspector.webp` uses the same report and frame with the Align tab open;
  `report-grid.webp` uses the Clips tab as described above.
- `hdr-diagnostic-overlay.webp` is a readability crop of the real physical-Windows
  diagnostic render. Its label card repeats only values proved by ffprobe, the selected
  run, and the portable runtime proof; it does not claim calibrated luminance or missing
  mastering metadata.
- The one-off VSPreview capture uses `C:\FrameCompareDemo\alignment.py` as an external
  fixture so the window title contains no generated-script path or username. The fresh
  bundle's optional launcher emitted FC-4019 during the CLI run; direct VSPreview opened
  successfully on the same physical runtime after the known external dependency-
  compatibility workaround. No repository production code was changed.
- The capture config deliberately keeps `report.auto_open = false`, `slowpics.auto_upload =
  false`, `--skip-metadata`, and one explicit user frame so the public example performs no
  network publication and stays deterministic.

## Privacy and integrity review

Before committing an image, inspect the full-resolution file for:

- original release-group names;
- raw source filenames;
- usernames and home-directory paths;
- private server, share, or volume names;
- API keys, webhook URLs, tokens, cookies, or environment values;
- subtitles, watermarks, or spoilers not intended for publication;
- UI states that imply behavior the current product does not provide;
- inaccurate captions, alt text, or diagnostic metadata;
- compression artifacts that make labels or controls hard to read.

Redaction should be the last resort. Prefer clean source copies, generic physical
filenames, explicit display labels, and a dedicated capture workspace so sensitive
information is never rendered into the image.

## Current asset set

| Asset | Intended role |
| --- | --- |
| `report-viewer-overview.webp` | Shared README/site/report-guide hero |
| `report-slider.webp` | Natural-image pair comparison |
| `report-diff.webp` | Difference-location example |
| `report-grid.webp` | Three-source triage |
| `report-inspector.webp` | Metadata and review controls |
| `vspreview-alignment.webp` | Interactive alignment verification |
| `first-run-doctor.png` | Successful runtime diagnosis |
| `first-run-dry-run.png` | Pre-render intent validation |
| `first-run-complete.png` | Cropped final run summary |
| `windows-portable-install.png` | Checksum and shim installation |
| `hdr-diagnostic-overlay.webp` | Physical-Windows HDR diagnostic example |

The active plan remains Active until the maintainer reviews the final assets and the
browser-version limitation is either accepted or replaced with a browser capture whose
exact embedded version is available.
