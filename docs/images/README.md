---
search:
  exclude: true
---

# Documentation image capture record

## Capture sets

The [documentation refresh plan](https://github.com/TJZine/frame-compare/blob/eeaa0154bf5996c616b74ccf910d7cf1584e8297/docs/plans/2026-10-08-documentation-refresh.md)
defines capture sets 1 and 2, and the
[documentation site redesign plan](https://github.com/TJZine/frame-compare/blob/eeaa0154bf5996c616b74ccf910d7cf1584e8297/docs/plans/2026-10-12-documentation-site-redesign.md)
adds set 3:

1. Set 1 uses macOS, Docker, the official EBU/DVB streams, and headless Chrome
   for report, HDR, and terminal captures (U1).
2. Set 2 uses the physical Windows host for installer output and the VSView alignment
   panel (U10).
3. Set 3 derives the home page images from set 1 screenshots and generates the
   diagram, social card, and icons (2026-10-12 site redesign, unit U2).

## Provenance record

### Set 1: macOS

| Field | Recorded value |
| --- | --- |
| Source title | EBU/DVB HEVC Test Content: PQ10 and HLG10 natural harbour sequence |
| Rights basis | EBU-published media, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Attribution | Credit EBU; footage by Frans de Jong; HLG-to-PQ10 conversion by Andrew Cotton (BBC); link to the [EBU/DVB HEVC test-content page](https://dvb.org/specifications/verification-validation/hevc-test-content/) |
| Physical filenames and SHA-256 | `DVB_7680x4320_HEVC_50fps_PQ10.ts`, copied byte-for-byte as `pq10-reference.ts`: `33773E7275B83976B0D9A19D3AED47AA0FEDB1280BA2019FE3DD344A05DA8D83`; `DVB_7680x4320_HEVC_50fps_HLG10.ts`, copied byte-for-byte as `hlg10-comparison.ts`: `B9EA646565751BB41CFC1F954172FDF5162C890D35AAC22238F536F6CF425300` |
| Display labels | `EBU DVB PQ10 — Reference`; `EBU DVB HLG10 — Comparison` |
| Frame and category | Frame `1000`, `User`; 6 frames, 2 sources |
| Frame Compare commit | `e3f5681b6202645cd91ffd83f15d3788aec9dbfc` |
| Docker image ID | `sha256:c513ca2661974aa86d2eda0ed58e8bc88ae095d4422d4624cb89a5aa99faea2f` |
| Chrome and Node versions | Google Chrome `154.0.8037.99`; Node `v24.14.0` |
| Viewport | 1600 × 1000 at scale 1; Report Information dialog captured at 896 × 666 |
| Report theme | Viewer default, dark |
| Capture date | 2026-10-09 |
| Captured by | Codex U1 capture pass; maintainer accepted the full asset set on 2026-10-10 |

### Set 2: physical Windows

| Field | Recorded value |
| --- | --- |
| Source title | EBU/DVB HEVC Test Content: PQ10 and HLG10 natural harbour sequence |
| Rights basis | EBU-published media, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Attribution | Credit EBU; footage by Frans de Jong; HLG-to-PQ10 conversion by Andrew Cotton (BBC); link to the [EBU/DVB HEVC test-content page](https://dvb.org/specifications/verification-validation/hevc-test-content/) |
| Physical filenames and SHA-256 | Official `DVB_7680x4320_HEVC_50fps_PQ10.ts` bytes supplied as `pq10-reference.ts`: `33773E7275B83976B0D9A19D3AED47AA0FEDB1280BA2019FE3DD344A05DA8D83`; official `DVB_7680x4320_HEVC_50fps_HLG10.ts` bytes supplied as `hlg10-comparison.ts`: `B9EA646565751BB41CFC1F954172FDF5162C890D35AAC22238F536F6CF425300`; both copied byte-for-byte from `C:\FrameCompareDemo\source\` to `C:\FrameCompareDemo\comparison_videos\` |
| Display labels | `EBU DVB PQ10 — Reference`; `EBU DVB HLG10 — Comparison` |
| Frame and category | Frame `1000`, `User`; 6 frames, 2 sources; both panel positions captured at frame `1000` |
| Frame Compare commit | `9edf1a4c65ad3cb2da9a885c8b866447ac97da80` |
| Bundle SHA | SHA-256 of `frame-compare-portable-win-x64-capture.zip`: `2ed7d1770cd20f2ab1028644eed24bab9e1d0f8439f53cadbbc28cb989be4ed2` |
| Windows build | Windows 10 Home x64, version `10.0.19045`, build `19045` |
| Display scaling | 100%, confirmed by the maintainer |
| Report theme | Viewer default, dark; native VSView panel captured in dark theme |
| Capture date | 2026-10-10 |
| Captured by | Maintainer using Snipping Tool on the physical Windows desktop; Codex prepared the bundle and verified the assets |

### Set 3: derived and generated

| Field | Recorded value |
| --- | --- |
| Sources | Set 1 run folder screenshots at 3840 × 2160: frame 1000 for both sources, and frames 45, 83, 948, 1050, and 1080 of the PQ10 reference |
| Processing | Lanczos downscale to 1600 × 900 (hero) and 480 × 270 (strip); WebP quality 90, method 6, no metadata |
| Diagram | `diagram-audio-offset.svg`, generated from a fixed illustrative waveform; not measured data |
| Social card and icons | Rendered from HTML with headless Chrome at device scale 1; social card saved as JPEG quality 85 |
| Chrome version | Google Chrome 155.0.8059.40 |
| Date | 2026-10-12 |

## Asset policy

- Export viewer and photo captures as WebP at quality 90 with metadata stripped.
- Show terminal output as text blocks, not images.
- Keep Windows terminal captures as PNG.
- Never upscale a capture.
- Use the capture specification for every capture.

## Current asset set

| File | Role | Pages | Set |
| --- | --- | --- | --- |
| `report-overview.webp` | Slider mode at frame 1000 with the reference and comparison labels visible | `docs/index.md` (Report views tabs), `README.md`, `docs/guides/reports-and-overlays.md` | 1 |
| `report-grid.webp` | Grid view at frame 1000 | `docs/index.md` (Report views tabs), `docs/guides/reports-and-overlays.md` | 1 |
| `report-inspector.webp` | Slider mode with the **Inspector** open on the **Clips** tab | `docs/index.md` (Report views tabs), `docs/guides/reports-and-overlays.md` | 1 |
| `report-lens.webp` | Slider mode with the lens on and pointer at viewport (640, 470) | `docs/index.md` (Report views tabs), `docs/guides/reports-and-overlays.md` | 1 |
| `report-information.webp` | **Report Information** dialog clipped to its bounds | `docs/guides/reports-and-overlays.md` | 1 |
| `hdr-diagnostic-overlay.webp` | Top-left 1920 × 1080 crop of the frame-1000 HLG10 diagnostic screenshot | `docs/guides/hdr-tonemapping.md`, `docs/index.md` (How a comparison runs) | 1 |
| `windows-portable-install.png` | Checksum verification through the install script's final terminal instruction | `docs/getting-started/windows-portable.md` | 2 |
| `vsview-alignment-panel.webp` | VSView alignment panel with both sources captured at frame 1000 and ready to confirm | `docs/guides/vsview-review.md` | 2 |
| `home-frame-pq10.webp` | Frame 1000 of the PQ10 reference, left of the hero divider | `docs/index.md` (hero, through `overrides/home.html`), social card | 3 |
| `home-frame-hlg10.webp` | Frame 1000 of the HLG10 comparison, right of the hero divider | `docs/index.md` (hero), social card | 3 |
| `home-strip-<frame>.webp` | Six selected frames of the PQ10 reference | `docs/index.md` (Frame selection) | 3 |
| `diagram-audio-offset.svg` | Illustrative audio offset between two tracks | `docs/index.md`, `docs/guides/audio-alignment.md` | 3 |

## Deliberate capture decisions

- Use only the two official EBU/DVB transport streams, byte-for-byte under CC BY 4.0,
  with no remux, re-encode, derivative, synthetic, or private media.
- Use the PQ10 reference and HLG10 comparison, both tonemapped to SDR, so every view
  shows real HDR handling.
- Describe Diff in text only because natural PQ10/HLG10 presentation-transform colour
  changes fill the frame and mislead at documentation width.
- Generate the static report in Docker on macOS so generic `/workspace` paths reach
  the capture and the Mac browser renders the Windows bundle's viewer.
- Drive the five viewer states with the specified headless Chrome script to keep
  viewport, scale, frame, pair, and browser state consistent.
- Show terminal output as text copied from real runs,
  so readers can search and copy it.
- Capture installer output and the visible VSView alignment panel only on the
  physical Windows host in U10.

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

Set 1 privacy and integrity review completed on 2026-10-09:

| Asset | Review result |
| --- | --- |
| `report-overview.webp` | Frame 1000, User, correct pair, default Slider zoom, and visible source labels; no loading, error, or private strings |
| `report-grid.webp` | Frame 1000 and both official sources in Grid view; no loading, error, or private strings |
| `report-inspector.webp` | Correct pair at frame 1000 with **Clips** selected and source metadata readable; no loading, error, or private strings |
| `report-lens.webp` | Correct pair at frame 1000 with the lens on and pointer at (640, 470); no loading, error, or private strings |
| `report-information.webp` | Complete 896 × 666 dialog with correct pair, six frames, two sources, and generic filenames; no private strings |
| `hdr-diagnostic-overlay.webp` | Complete diagnostic block, including `Signal:` and `Tonemap:`, on the HLG10 source at frame 1000; no cut line or private strings |

The six WebP exports use quality 90 and contain no EXIF, XMP, or ICC metadata.
No release-group names, private server names, credentials, tokens, cookies, or
unintended subtitles or watermarks appear in set 1.

Set 2 privacy and integrity review completed on 2026-10-10:

| Asset | Review result |
| --- | --- |
| `windows-portable-install.png` | Full-size 1109 × 119 PNG; verified bundle checksum through the successful installer's final terminal instruction; all visible paths use `C:\FrameCompareDemo`; no private strings |
| `vsview-alignment-panel.webp` | Full-size 748 × 1142 panel capture; Reference and Comparison 1 captured at frame 1000; `2/2 positions captured — ready to confirm`; provisional `+0f` audio candidate marked `NOT APPLIED`; no private strings |

Both images were inspected at full resolution. Their alt text and captions match
the visible content; no user names, home-directory paths, private release or group
names, server or share names, API keys, webhook URLs, tokens, cookies, or private
environment values appear. No unintended subtitles, watermarks, spoilers, or
misleading UI states appear, and the labels and controls remain readable.
The WebP uses quality 90 with no EXIF, XMP, or ICC metadata. Neither capture was
scaled. The installer PNG retains only sRGB, gamma, and DPI metadata.
Uninstall removed the temporary shim and restored the user PATH exactly to its
starting value. VSView closed without saving; no alignment-result sidecar exists.

Set 3 privacy and integrity review completed on 2026-10-12:

| Asset | Review result |
| --- | --- |
| `home-frame-pq10.webp` | Full-size 1600 × 900 harbour sunset; EBU DVB PQ10 Reference label, frame 1000, B-frame, User, and source/output sizes; no private strings or unintended subtitles or watermarks |
| `home-frame-hlg10.webp` | Full-size 1600 × 900 harbour sunset with sailboat; EBU DVB HLG10 Comparison label, frame 1000, B-frame, User, and source/output sizes; no private strings or unintended subtitles or watermarks |
| `home-strip-45.webp` | Full-size 480 × 270 daylight harbour; PQ10 reference, frame 45, Bright; expected baked metadata inherited from the inspected source; no private strings or unintended subtitles or watermarks |
| `home-strip-83.webp` | Full-size 480 × 270 daylight harbour; PQ10 reference, frame 83, Random; expected baked metadata inherited from the inspected source; no private strings or unintended subtitles or watermarks |
| `home-strip-948.webp` | Full-size 480 × 270 sunset harbour; PQ10 reference, frame 948, Random; expected baked metadata inherited from the inspected source; no private strings or unintended subtitles or watermarks |
| `home-strip-1000.webp` | Full-size 480 × 270 sunset harbour; PQ10 reference, frame 1000, User; expected baked metadata inherited from the inspected source; no private strings or unintended subtitles or watermarks |
| `home-strip-1050.webp` | Full-size 480 × 270 sunset harbour; PQ10 reference, frame 1050, Dark; expected baked metadata inherited from the inspected source; no private strings or unintended subtitles or watermarks |
| `home-strip-1080.webp` | Full-size 480 × 270 sunset harbour; PQ10 reference, frame 1080, Random; expected baked metadata inherited from the inspected source; no private strings or unintended subtitles or watermarks |
| `diagram-audio-offset.svg` | Full-size 640 × 190 preview shows reference/comparison bars and the offset bracket and text; illustrative waveform, no private data |
| `social-card.jpg` | Full-size 1200 × 630 card shows the logo, Frame Compare, prescribed headline and subline, brass URL, and PQ10-left/HLG10-right harbour split with white divider; no fallback serif, missing glyph boxes, missing images, or private strings |
| `apple-touch-icon.png` | Full-size 180 × 180 mark centred on #111110; no other text or private data |
| `favicon-32.png` | Full-size 32 × 32 mark with transparent background; no other text or private data |
