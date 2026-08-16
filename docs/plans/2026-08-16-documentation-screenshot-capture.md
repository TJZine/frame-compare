---
search:
  exclude: true
---

Status: Reference-only capture handoff; not implementation authority
Scope: Documentation screenshots requested by the user-facing documentation overhaul
Owner: Maintainer or delegated Codex capture session

# Documentation Screenshot Capture Handoff

## Purpose

The documentation contains exact HTML comment markers named `SCREENSHOT_SLOT`. Replace
each marker only after a publication-safe asset has been captured and reviewed. The
current pages remain complete without the images; no broken image references should be
committed during the interim.

## Global capture rules

- Use synthetic, public-domain, or explicitly publication-approved media.
- Use generic source labels such as `Reference`, `Encode A`, and `Encode B`.
- Redact usernames, home directories, download locations, API keys, webhook URLs, TMDB
  keys, cookies, tokens, and private server names.
- Do not expose private release names unless the maintainer explicitly approves them.
- Keep terminal text readable at the rendered documentation width.
- Prefer WebP for full application captures and PNG for text-heavy terminal captures.
- Preserve the application’s real UI; do not create mock behavior that the product does
  not implement.
- Add useful alt text and a concise caption using the `fc-doc-figure` class.
- Verify every asset in light and dark documentation themes even when the application
  capture itself is dark.
- Keep the longest edge at roughly 1600–1920 pixels unless text readability requires a
  larger source.

## Replacement figure template

```html
<figure class="fc-doc-figure">
  <img src="../images/example.webp" alt="Specific description of the visible product state">
  <figcaption>What the screenshot demonstrates and why the user should inspect it.</figcaption>
</figure>
```

Adjust the relative path for the README or documentation home.

## Required assets

### `docs/images/report-viewer-overview.webp`

**Markers:**

- `README.md` — `SCREENSHOT_SLOT: report-viewer-overview`
- `docs/index.md` — `SCREENSHOT_SLOT: report-viewer-overview`
- `docs/guides/reports-and-overlays.md` — `SCREENSHOT_SLOT: report-viewer-overview`

**Capture:** completed three-source offline report in slider mode. Show filmstrip,
source labels, frame/category context, and primary controls. Use a visually informative
frame with no sensitive content.

**Recommended crop:** 16:9 or slightly wider, full viewer chrome visible.

### `docs/images/first-run-doctor.png`

**Marker:** `docs/guides/first-comparison.md` — `SCREENSHOT_SLOT: first-run-doctor`

**Capture:** successful human-readable `frame-compare doctor` output from the Windows
portable route. Include runtime profile, FFmpeg, VapourSynth, source plugin, and
tonemapping status. Redact paths.

### `docs/images/first-run-dry-run.png`

**Marker:** `docs/guides/first-comparison.md` — `SCREENSHOT_SLOT: first-run-dry-run`

**Capture:** the at-a-glance section of a three-source dry run. Annotate or crop so the
reference, comparisons, analysis mode, generated-data root, and upload state are easy to
identify.

### `docs/images/first-run-complete.png`

**Marker:** `docs/guides/first-comparison.md` — `SCREENSHOT_SLOT: first-run-complete`

**Capture:** completed run summary with report path, selected frame count, warning area,
and elapsed time. Redact the private prefix of the output path while keeping the
run-folder relationship understandable.

### `docs/images/report-slider.webp`

**Marker:** `docs/guides/reports-and-overlays.md` — `SCREENSHOT_SLOT: report-slider`

**Capture:** slider mode with the divider away from center, both source labels visible,
and a frame that demonstrates texture, crop, or scaling differences.

### `docs/images/report-diff.webp`

**Marker:** `docs/guides/reports-and-overlays.md` — `SCREENSHOT_SLOT: report-diff`

**Capture:** diff mode with pair identity and enough surrounding UI to establish the
current frame and comparison context.

### `docs/images/report-grid.webp`

**Marker:** `docs/guides/reports-and-overlays.md` — `SCREENSHOT_SLOT: report-grid`

**Capture:** at least three sources in grid mode with readable labels and the same frame
visible in every cell.

### `docs/images/report-inspector.webp`

**Marker:** `docs/guides/reports-and-overlays.md` — `SCREENSHOT_SLOT: report-inspector`

**Capture:** focused view of the inspector and review controls showing source, frame,
selection, and diagnostic metadata without obscuring all image content.

### `docs/images/vspreview-alignment.webp`

**Marker:** `docs/guides/audio-alignment.md` — `SCREENSHOT_SLOT: vspreview-alignment`

**Capture:** the Frame Compare-generated VSPreview session with reference and comparison
clips, proposed offset context, and the controls used to inspect alignment.

### `docs/images/windows-portable-install.png`

**Marker:** `docs/windows-portable.md` — `SCREENSHOT_SLOT: windows-portable-install`

**Capture:** checksum verification followed by successful `install.cmd` completion and
the new-terminal instruction. Redact the Windows username and download directory.

## Codex completion checklist

1. Search the repository for `SCREENSHOT_SLOT` and confirm every marker maps to this
   handoff.
2. Add `docs/images/` only when the first real asset is available.
3. Insert figures at the existing marker positions; do not move explanatory prose merely
   to fit a screenshot.
4. Reuse `report-viewer-overview.webp` across the README, site home, and report guide.
5. Confirm relative links from README and nested documentation paths.
6. Run the strict documentation build.
7. Inspect the rendered site at desktop and mobile widths in both themes.
8. Inspect the GitHub README rendering separately because repository CSS does not apply
   there.
9. Remove this handoff only after every marker is either fulfilled or deliberately
   rejected with maintainer approval.
