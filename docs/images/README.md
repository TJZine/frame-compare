---
search:
  exclude: true
---

# Documentation image capture record

This directory contains public-facing screenshots used by the README and documentation
site. The current V1 assets are temporary capture fixtures until the active
[V2 screenshot remediation plan](../plans/2026-08-17-documentation-v2-screenshot-remediation.md)
is completed.

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
│   ├── itunes-webdl.mkv
│   └── movies-anywhere-webdl.mkv
└── generated\
```

The physical filenames are deliberately generic. Do not capture original release names,
release groups, private download paths, usernames, server names, or collection paths.

Prefer explicit presentation labels:

```toml
[sources]
reference = "reference.mkv"
analysis_source = "reference"
label_mode = "stem"

[sources.overrides."reference.mkv"]
label = "UHD Blu-ray — Reference"

[sources.overrides."itunes-webdl.mkv"]
label = "iTunes WEB-DL"

[sources.overrides."movies-anywhere-webdl.mkv"]
label = "Movies Anywhere WEB-DL"
```

When the report does not present the title elsewhere, prefix each label with the
publication-safe title. When it does, source-only labels are cleaner and avoid repeating
the same title in every control.

## Provenance record

Complete this table during each capture pass:

| Field | Recorded value |
| --- | --- |
| Source title | |
| Rights basis | Personally authored / public domain / open license / explicit permission |
| Attribution requirement | |
| Physical filenames | |
| Display labels | |
| Frame number and category | |
| Frame Compare commit or release | |
| Media-runtime profile | |
| Capture host and OS | |
| Browser and version | |
| Display scaling and browser zoom | |
| Report theme | |
| Capture date | |
| Captured by | |

Do not publish a screenshot until the rights basis and required attribution are known.

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
| `hdr-diagnostic-overlay.webp` | Pending physical-Windows HDR diagnostic example |

Mark the active plan historical and replace the V1 note at the top of this file after the
V2 assets and rendered-site review are complete.
