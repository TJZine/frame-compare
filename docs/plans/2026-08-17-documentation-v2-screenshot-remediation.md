---
search:
  exclude: true
---

Status: Active
Scope: V2 documentation screenshot recapture, image provenance, and rendered-site QA
Owner: Maintainer-directed Codex session on the physical Windows test machine

# Documentation V2 Screenshot Remediation Plan

## Purpose

Replace the temporary V1 documentation imagery with a coherent, publication-safe,
natural-image capture set that demonstrates Frame Compare as a real encode, remaster,
and archival comparison tool.

This plan is decision-complete for a Codex implementation session on the physical
Windows test machine. It does not authorize product-code changes, report-viewer redesign,
documentation information-architecture changes, or branding work.

## Repository and branch

Repository:

```text
TJZine/frame-compare
```

Required working branch:

```text
dev/v0.2.0
```

The branch is temporary and will later be proposed to `cleanup`. Fetch the actual current
remote state before beginning; do not assume a SHA from this plan remains current.

Do not:

- create or target a different development branch;
- modify the documentation workflow branch filters;
- merge the branch;
- modify production Python, JavaScript, HTML generation, report styling, or packaging;
- redesign the documentation navigation;
- start the logo or accent-color pass.

## Goal

Produce a visually coherent V2 documentation set that:

1. uses one rights-cleared natural-image comparison dataset for the product-facing
   report and alignment screenshots;
2. uses generic physical filenames and explicit readable display labels;
3. demonstrates real texture, shadows, gradients, edges, and source differences;
4. contains no private paths, original release-group names, secrets, or accidental
   identifying metadata;
5. remains legible at normal README and documentation-site widths;
6. accurately represents the current Frame Compare UI and behavior;
7. passes the strict documentation build and focused documentation tests.

## Non-goals

This plan does not include:

- changes to frame selection, alignment, rendering, HDR logic, or report behavior;
- screenshot automation or a new asset-generation pipeline;
- custom Zensical templates or JavaScript;
- a broader CSS/theme redesign;
- logo, favicon, or accent-color selection;
- documentation versioning;
- changes to release workflows;
- publication of source media or a complete generated report;
- a claim that commercial media is safe to publish without a documented rights basis.

## Allowed write boundary

The implementation may modify only:

```text
docs/images/**
README.md
docs/index.md
docs/guides/first-comparison.md
docs/guides/reports-and-overlays.md
docs/guides/audio-alignment.md
docs/guides/hdr-tonemapping.md
docs/plans/2026-08-17-documentation-v2-screenshot-remediation.md
```

Changes outside this boundary require explicit maintainer approval before editing.

The normal expected changes are:

- replacing existing image files in place;
- adding `docs/images/hdr-diagnostic-overlay.webp`;
- updating image alt text and captions when the final visible labels or evidence differ;
- completing the provenance record in `docs/images/README.md`;
- replacing the `SCREENSHOT_SLOT: hdr-diagnostic-overlay` comment with a figure;
- marking this plan historical after acceptance.

Do not rename existing image files unless a broken contract makes replacement in place
impossible. Reuse of `report-viewer-overview.webp` across the README, documentation
home, and report guide must remain intact.

## Product and documentation invariants

Preserve all of the following:

- The README and site describe the same current product.
- The report overview is one canonical asset reused in three locations.
- Slider, grid, inspector, and preferably diff come from the same generated report and
  selected frame.
- The visible source order and labels remain consistent across the report and VSPreview
  captures.
- Source identity is not confused with presentation labels.
- No screenshot implies that slider mode displays three simultaneous full source views.
- Diff is described as a locator, not a perceptual-quality verdict.
- Motion selection is not described as a direct temporal-quality metric.
- HDR screenshots are SDR presentation artifacts after the configured transform.
- An HDR diagnostic image contains only values the source and runtime actually prove.
- The normal report remains a portable folder unless image embedding is explicitly
  enabled.
- No broken image links or placeholder file references are committed.
- The current workflow strategy remains unchanged: the later PR to `cleanup` owns the
  strict documentation workflow run.

## Preconditions

Before capturing:

1. Confirm the current branch and clean worktree:

   ```powershell
   git fetch origin
   git switch dev/v0.2.0
   git pull --ff-only origin dev/v0.2.0
   git status --short
   ```

2. Read:

   ```text
   AGENTS.md
   docs/ENGINEERING_RUNBOOK.md
   docs/images/README.md
   docs/guides/first-comparison.md
   docs/guides/reports-and-overlays.md
   docs/guides/audio-alignment.md
   docs/guides/hdr-tonemapping.md
   ```

3. Confirm the physical Windows runtime to capture is the current supported bundle or a
   source-built bundle from the same branch.

4. Run the current route's health check:

   ```powershell
   frame-compare doctor
   ```

5. Confirm that the chosen media is personally authored, public-domain, openly licensed,
   or explicitly approved for these public documentation excerpts. Record the rights
   basis before capture.

6. Confirm no source contains a subtitle, watermark, spoiler, private identifier, or
   other element that should not appear publicly at the selected frame.

Stop before capture if any precondition cannot be satisfied.

## Canonical demo workspace

Create a dedicated workspace outside both the repository and portable bundle:

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

Use copies or safe links appropriate to the host. Do not use original release filenames
as the visible physical filenames in the capture workspace.

Do not capture from a path containing a username, release-group name, private server,
download client, network share, or collection name.

### Display labels

Use full human-readable provider names, not abbreviations such as `iT` or `MA`.

Preferred labels when the report already shows the title elsewhere:

```text
UHD Blu-ray — Reference
iTunes WEB-DL
Movies Anywhere WEB-DL
```

When the report does not display the title separately, prefix the publication-safe title:

```text
<Title> — UHD Blu-ray — Reference
<Title> — iTunes WEB-DL
<Title> — Movies Anywhere WEB-DL
```

Replace `<Title>` with the actual approved title before running. Do not leave placeholders
in captured UI.

Use explicit source labels:

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

If the actual source types differ, use truthful full labels. Do not label a WEB-DL as a
disc source or infer a provider that is not known.

### Suggested demonstration configuration

Use a report with enough categories for a useful filmstrip:

```toml
[paths]
input_dir = "comparison_videos"
generated_dir = "generated"
config_dir = "config"

[sources]
reference = "reference.mkv"
analysis_source = "reference"
label_mode = "stem"
match_fps = "disabled"

[sources.overrides."reference.mkv"]
label = "UHD Blu-ray — Reference"

[sources.overrides."itunes-webdl.mkv"]
label = "iTunes WEB-DL"

[sources.overrides."movies-anywhere-webdl.mkv"]
label = "Movies Anywhere WEB-DL"

[analysis]
performance_mode = "quality"
random_seed = 42
random_frame_count = 4
dark_frame_count = 1
bright_frame_count = 1
motion_frame_count = 2

[audio_alignment]
enable = true
use_vspreview = true

[screenshots]
overlay_mode = "standard"

[report]
enable = true
default_mode = "slider"
include_filmstrip = true
embed_images = false
auto_open = true

[slowpics]
auto_upload = false
```

Adjust only fields required by the selected media. Record every adjustment in
`docs/images/README.md`. Do not add an override merely to make a screenshot look
cleaner if it would misrepresent normal behavior.

## Source and frame selection criteria

Choose one natural frame for the report-viewer set that contains most of:

- fine texture or film grain;
- a meaningful shadow region;
- a smooth gradient;
- a high-contrast edge;
- facial or fabric detail;
- no subtitles;
- no watermark;
- no major spoiler;
- no overlaid title card;
- visible but realistic source differences.

Avoid:

- a frame so dark that the UI image reads as nearly black;
- a frame with only flat animation cels unless animation is the intended target audience;
- an exaggerated intentionally damaged encode;
- a frame whose most visible difference is a misleading crop or alignment failure;
- a promotional still unrelated to the actual compared source frames.

The selected frame must survive source trims and final alignment in all three sources.

## Capture environment

Use one consistent environment for the full report-viewer set:

- one physical Windows host;
- one browser and recorded exact version;
- one browser zoom level, normally 100%;
- one Windows display-scaling value;
- one report theme;
- one report window size;
- no browser developer tools;
- no unrelated tabs, notifications, overlays, or desktop content.

Record those values in `docs/images/README.md`.

Capture lossless PNG masters first. Do not upscale. Crop application content precisely
without removing context required to understand the UI.

Recommended final dimensions:

| Asset family | Target |
| --- | --- |
| Report overview, slider, diff, grid, inspector | Exact visible 1080p-height browser surface; 1683 × 1080 on the current capture host |
| VSPreview | Approximately 1600–1920 px wide; crop unused desktop chrome |
| Terminal captures | Approximately 1000–1200 px wide, tightly cropped to relevant output |
| HDR diagnostic | Approximately 1280 × 720 or the natural screenshot aspect ratio |

For the 2026-08-17 recapture, the maintainer requested a 1080p-height browser capture
so the documentation matches the intended full-screen local report. The current
in-app-browser surface is 1683 × 1080; a 1920-wide CSS viewport override clips report
controls on this host, so use the exact visible surface and do not upscale. Do not
force 1280 × 720 when that crop removes required controls. Preserve clarity over
uniformity, but keep the report-viewer set consistent.

The allowed controlled-pattern `report-diff.webp` exception remains the retained
1280 × 720 asset documented in the image record; the 1080p-height recapture applies
to the natural-image overview, slider, grid, and inspector assets.

## Asset tasks

### 1. `report-viewer-overview.webp` — required replacement

Capture the completed report in slider mode with:

- current frame and category;
- filmstrip;
- full source labels;
- selected comparison pair;
- primary viewer controls;
- enough of the natural frame to communicate the comparison use case;
- no raw paths or original filenames.

This file remains the shared hero for:

```text
README.md
docs/index.md
docs/guides/reports-and-overlays.md
```

Do not create separate near-duplicate hero assets.

### 2. `report-slider.webp` — required replacement

Use the same report and selected frame as the overview.

Place the reveal divider near one-third or two-thirds of the image rather than exactly
centered. Ensure both selected source identities remain readable and the divider crosses
useful texture, shadow, and edge detail.

### 3. `report-grid.webp` — required replacement

Use the same report and frame. Show all three sources at once with readable full labels.

The source differences should be visible enough to explain triage without looking
artificially exaggerated.

### 4. `report-inspector.webp` — required replacement

Use the same report and frame. Open the inspector or review area that best demonstrates:

- frame/category context;
- source-frame or alignment mapping;
- selected source/pair;
- review state or export/import controls where useful.

Inspect the full image for raw physical filenames or paths. If the inspector exposes
unsafe raw identity that cannot be hidden through supported presentation labels, stop and
ask the maintainer before redacting or changing product code.

### 5. `report-diff.webp` — conditional replacement

First attempt a natural-image diff from the same report and frame.

Accept it when changed regions remain understandable at normal documentation width.
Prefer the natural-image diff for visual coherence.

Retain the existing controlled-pattern diff only when the natural result is genuinely
unreadable or misleading. If retained:

- record the decision and reason in `docs/images/README.md`;
- keep the caption explicit that diff locates changed regions;
- do not imply the pattern is representative source footage.

### 6. `vspreview-alignment.webp` — required replacement

Use the same source set when practical. Show:

- reference and comparison identity;
- proposed or accepted frame offset;
- timeline/frame controls;
- enough image content to verify alignment;
- no private path, generated script location, username, or raw release filename.

Check text at 100% after WebP conversion. Use lossless WebP or a higher quality setting
when labels or controls show ringing or blur.

### 7. `first-run-complete.png` — required recrop or replacement

Capture only the final completion summary, not the complete terminal history.

The image should show:

- successful completion;
- matched source count;
- selected frame count;
- report or run-folder path;
- warnings summary when present;
- elapsed time.

Use a generic workspace path. Target a shallow landscape crop rather than the current
portrait-oriented capture.

Update its alt text if the actual frame count or visible fields differ.

### 8. `first-run-doctor.png` — validate, replace only if needed

Render the page at normal documentation width. Replace the image only when:

- text is not legible without zooming;
- critical runtime checks are cut off;
- paths or private data are visible;
- the capture no longer matches the current supported runtime.

Use a simple high-contrast terminal with a 16–18 px font and no decorative prompt theme.

### 9. `first-run-dry-run.png` — validate, replace when labels change

The final capture should use the same source labels and workspace as the report set.
Show reference, comparisons, frame intent, analysis mode, output root, and disabled
publishing state.

Update the alt text to describe the final visible labels without embedding unnecessary
release jargon.

### 10. `windows-portable-install.png` — validate, replace only if needed

Keep the current asset when checksum and installation output remain legible at normal
site width and contain no private path. Otherwise recapture with:

- checksum success;
- successful shim installation;
- instruction to open a new terminal;
- a generic bundle path.

### 11. `hdr-diagnostic-overlay.webp` — required new asset

Use a rights-cleared HDR source on the physical Windows/Vulkan path. Generate a
tonemapped screenshot with `screenshots.overlay_mode = "diagnostic"`.

The image may show only evidence actually available from that source/runtime, such as:

- transfer and primaries context;
- mastering luminance;
- MaxCLL/MaxFALL;
- target nits;
- range;
- selected category;
- Dolby Vision information only when genuinely present.

Do not:

- invent missing metadata;
- label an SDR browser screenshot as untonemapped native HDR;
- imply the overlay is a calibrated luminance measurement;
- use a screenshot from a failed or fallback path without disclosing it.

Replace the `SCREENSHOT_SLOT: hdr-diagnostic-overlay` comment in
`docs/guides/hdr-tonemapping.md` with a normal `fc-doc-figure` block and accurate alt
text/caption.

## Image export

Keep lossless masters outside the repository if desired. Commit only the final
documentation assets.

For WebP conversion, Pillow from the project environment is sufficient. Example:

```powershell
@'
from pathlib import Path

from PIL import Image

source = Path(r"C:\FrameCompareDemo\captures\report-viewer-overview.png")
target = Path(r"docs\images\report-viewer-overview.webp")

with Image.open(source) as image:
    image.save(target, "WEBP", quality=92, method=6)
'@ | uv run --no-sync python -
```

Use lossless WebP when UI text or diagnostic overlays are not acceptably sharp at
quality 92. Do not optimize repeatedly from an already compressed asset.

PNG and WebP exports must omit EXIF and unrelated metadata. Inspect final bytes rather
than assuming the exporter stripped everything.

## Alt text and captions

Alt text must describe the useful state, not every visible pixel. Avoid phrases such as
“image of” or “screenshot of.”

Captions should explain why the shown mode or stage matters.

When final source labels include a movie title:

- do not repeat the complete title and all three source labels in every alt attribute;
- describe the selected pair or source set at the level needed to understand the UI;
- keep the visible labels in the image itself readable.

Do not leave `synthetic`, `Encode-A`, or `Encode-B` in an alt attribute after replacing
that asset with a natural-image provider-labeled capture.

## Provenance and privacy closeout

Complete `docs/images/README.md` with:

- title;
- rights basis;
- attribution requirement;
- physical filenames;
- display labels;
- selected frame/category;
- application commit or release;
- runtime profile;
- host, OS, browser, scaling, and zoom;
- capture date;
- deliberate exceptions.

Perform a full-resolution privacy review of every asset. Search for hidden disclosures in:

- inspector panels;
- filenames;
- terminal output;
- browser title bars;
- VSPreview scripts and window titles;
- report metadata;
- generated paths;
- overlay text.

Prefer recapture over blur. Redaction is allowed only when recapture cannot remove
non-product content and the redaction does not obscure evidence needed by the guide.

## Validation

### Static file validation

Confirm every referenced image exists and no unintended placeholder remains:

```powershell
git status --short
git diff --check
git grep -n "SCREENSHOT_SLOT" -- README.md docs/index.md docs/guides docs/windows-portable.md
```

The only acceptable result before HDR capture is the explicitly pending HDR slot. The
final accepted change must contain no `SCREENSHOT_SLOT` markers.

Verify image dimensions and decodability:

```powershell
@'
from pathlib import Path

from PIL import Image

for path in sorted(Path("docs/images").glob("*")):
    if path.suffix.lower() not in {".png", ".webp"}:
        continue
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        print(f"{path}: {image.width}x{image.height} {image.format}")
'@ | uv run --no-sync python -
```

### Documentation build

Install the locked documentation environment and run the strict build:

```powershell
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
```

Restore the contributor and documentation groups before focused tests:

```powershell
uv sync --group dev --group docs --locked
```

Run focused documentation and onboarding tests:

```powershell
uv run --no-sync pytest -q `
  tests/workflows/test_docs_workflow.py `
  tests/workflows/test_onboarding_docs.py `
  tests/windows_portable/test_windows_portable_docs.py
```

Do not modify tests merely to accommodate a broken link, inaccurate caption, or
misplaced asset.

### Rendered visual review

Serve the site:

```powershell
uv run --no-sync zensical serve
```

Inspect at minimum:

- desktop width around 1440 px;
- narrower desktop/tablet width around 1024 px;
- mobile width around 390 px;
- light palette;
- dark palette.

Review:

- README rendering on GitHub after push or in the PR;
- documentation home;
- first-comparison guide;
- reports-and-overlays guide;
- audio-alignment guide;
- HDR guide;
- Windows portable guide.

Confirm:

- text remains readable without opening the source asset;
- figures do not dominate the page;
- portrait terminal output has been eliminated;
- captions wrap cleanly;
- the same report assets look coherent across pages;
- no light/dark theme makes controls or captions unreadable;
- mobile layout does not create horizontal overflow.

## Acceptance criteria

The task is complete only when all of the following are true:

- The canonical report overview uses publication-safe natural footage.
- Slider, grid, and inspector use the same report and selected frame.
- Diff is either replaced with the natural report or explicitly retained with a recorded
  clarity rationale.
- VSPreview uses realistic, readable, full source labels.
- The completion image is a shallow final-summary crop.
- Doctor and Windows install captures have been reviewed at rendered width.
- The new HDR diagnostic asset is present and accurately captioned.
- No screenshot exposes private or original release identity.
- Rights and attribution are recorded.
- Existing image paths remain valid.
- Alt text and captions match the actual final assets.
- Strict Zensical build passes.
- Focused documentation tests pass.
- Desktop/mobile and light/dark review passes.
- `git diff --check` passes.
- The final diff contains no production-code, workflow, or unrelated documentation
  changes.
- The maintainer has reviewed the final images before the PR is merged.

## Stop conditions

Stop and ask the maintainer before proceeding when:

- the selected media rights or attribution posture is unclear;
- the report or inspector exposes raw source identity that supported labels cannot hide;
- the natural-image diff is misleading and retaining the controlled pattern would create
  an inconsistent or confusing set;
- the physical Windows HDR path fails or cannot prove the metadata intended for the
  overlay;
- alignment or frame mapping is incorrect;
- the only way to produce the desired screenshot would require product-code or report-UI
  changes;
- the strict documentation build reveals a pre-existing unrelated failure;
- the current branch contains unrelated uncommitted work.

Do not hide a stop condition with image editing, test changes, or undocumented
workarounds.

## Rollback

All implementation changes are documentation assets and adjacent captions.

To roll back:

1. restore the affected image files and Markdown from the parent commit;
2. remove the new HDR asset if it is part of the rejected pass;
3. rerun the strict documentation build;
4. retain the provenance record only when it still describes committed assets.

Do not delete user media, generated comparisons, or capture masters as part of repository
rollback.

## Closeout

After maintainer acceptance:

1. update `Status: Active` to `Status: Historical — completed`;
2. record the completion date and final commit in this plan;
3. replace the temporary V1 note in `docs/images/README.md` with the accepted capture
   baseline;
4. summarize replaced, retained, and newly added assets;
5. include exact validation commands and results in the PR description or handoff.

Do not start logo or accent-color work in the same commit. That is a separate design
decision and review surface.
