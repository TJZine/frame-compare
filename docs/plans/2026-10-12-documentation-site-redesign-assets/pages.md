---
search:
  exclude: true
---

# Documentation site redesign: page specifications

Part of the `[documentation site redesign plan](../2026-10-12-documentation-site-redesign.md)`.
Read the [style guide](style-guide.md) first. This file says what changes on each page;
the style guide says how the result reads. Where this file shows a Markdown link inside
a code span, write it in the page as an ordinary link, without the backticks.

## How to edit an existing page

Every existing user page gets a **voice pass** plus the structural changes its section
lists. A voice pass:

1. Keeps every fact, number, literal, command, key, option, link target, figure, and
   guard string on the page, unless the page section says to delete or move it.
2. Rewrites sentences and paragraphs that break the style guide's voice rules or use a
   pattern from its "not allowed" table. Splits paragraphs over 70 words at sentence
   boundaries, keeping sentence order. Turns any procedure written as prose into a
   numbered list or a steps block.
3. Adds no fact that the page or its cited source does not already state. If a rewrite
   seems to need a new fact, report `blocked`.
4. Does not reorder or rename headings unless the page section says so, because other
   pages link to their anchors.
5. Adds the front matter `description:` given in [Descriptions](#descriptions).

Kept text that already meets the style guide stays byte-identical. The reviewer checks
fact preservation by reading the diff, so keep edits local: change the sentence, not the
paragraph around it.

## Guard strings

Tests match these literals. They must survive the voice pass verbatim, on one physical
line, in the file named. Where a rewrite would remove one, keep the sentence that holds
it and rewrite around it.

| File | Literal strings | Test |
| --- | --- | --- |
| `docs/getting-started/windows-portable.md` | `$tag = "<tag>"`; `git/ref/tags/$tag`; `$tagSha.Count -ne 1`; `^[0-9a-f]{40}$`; `--repo TJZine/frame-compare`; `--signer-workflow TJZine/frame-compare/.github/workflows/windows-portable-build.yml`; `--source-digest $tagSha`; `Could not resolve release tag`; `Release provenance verification failed`; `## VSView alignment review`; `frame-compare-alignment-review`; `self-contained Python`; `PATH-only VSView executable`; `](../guides/vsview-review.md)`; `` bundle_info.schema_version` 3 ``; `pre-native-panel schema-2 bundles`; `PowerShell 7 or newer`; `Windows PowerShell 5.1 remains supported`; `fresh, empty folder`; `Overlaying a full ZIP onto an existing bundle root is unsupported`; `AppData fallback configuration and external user data are preserved`; `Identity-less legacy backups cannot be restored or migrated` | `tests/windows_portable/test_windows_portable_docs.py` |
| `docs/getting-started/windows-portable.md` | Must not contain: `--source-ref`, `screenshots_dir`, `use_run_folders`, `output_dir`, `Keep current offset` | same |
| `docs/guides/vsview-review.md` | `typed, atomic sibling sidecar`; `Missing, malformed,`; `stale, mixed-session, duplicate, incomplete`; `ordinary VSView session`; `Confirm these aligned positions`; `Keep current alignment` | same |
| `docs/getting-started/native.md` | ``The `vsview` extra pins VSView 0.12.1``; `package to R81`; `` `vapoursynth-lsmas 1310.0.0.0` ``; `` `vs-placebo 2.0.4` `` | `tests/workflows/test_onboarding_docs.py` |
| `docs/reference/configuration.md` | One key block per config key (see U3) | `tests/test_cli_contract_docs.py` |

`docs/current-cli-contract.md`, `docs/current-architecture.md`,
`docs/supported-media-runtime.md`, `docs/media-runtime-windows-validation.md`, and
`docs/analysis-performance-validation.md` are also read by tests. Unit U8 removes only
the contract's manual Contents list; unit U3 removes only the API-generator references
named in the repository changes. Nothing else in them changes.

## Descriptions

Each page gets exactly this `description:` in its front matter. Pages that already have
front matter add the key; others get a new front matter block.

| Page | `description:` |
| --- | --- |
| `docs/index.md` | Frame Compare picks frames from two or more videos, aligns them by audio when needed, renders matching screenshots, and writes an offline report. |
| `docs/getting-started/index.md` | Choose between the Windows portable bundle, Docker, and a native source install. |
| `docs/getting-started/windows-portable.md` | Download, verify, and install the Windows portable bundle, then update, back up, or remove it. |
| `docs/getting-started/docker.md` | Run Frame Compare in Docker on macOS or Linux and find the results on the host. |
| `docs/getting-started/docker-profiles.md` | The Docker Compose services, the NVIDIA and X11 profiles, and the host helper that opens reports. |
| `docs/getting-started/native.md` | Install Frame Compare from source with uv or pip on a system where you manage the media libraries. |
| `docs/getting-started/first-comparison.md` | Run the wizard, check the runtime, preview with a dry run, and run your first comparison. |
| `docs/guides/index.md` | Guides for sources, frame selection, audio alignment, HDR, reports, presets, publishing, and troubleshooting. |
| `docs/guides/how-it-works.md` | The six stages of a Frame Compare run and what each stage decides. |
| `docs/guides/sources-and-labels.md` | Choose the reference, the analysis source, labels, trims, timing, and the active picture for each source. |
| `docs/guides/analysis-modes.md` | Choose frames by number, at random, or by brightness and motion, and make the selection repeatable. |
| `docs/guides/audio-alignment.md` | How Frame Compare measures the offset between sources from their audio, and what APPLIED and NOT APPLIED mean. |
| `docs/guides/vsview-review.md` | Confirm or enter alignment by eye in the VSView alignment panel. |
| `docs/guides/hdr-tonemapping.md` | How HDR sources become SDR screenshots, which settings change the result, and what the overlay reports. |
| `docs/guides/reports-and-overlays.md` | Open the report, switch views, inspect frames, keep review notes, and choose screenshot overlays. |
| `docs/guides/presets-history-generated-data.md` | Where Frame Compare keeps run folders and caches, how to reopen past runs, and how to save presets. |
| `docs/guides/publishing-and-webhooks.md` | Upload a reviewed comparison to slow.pics and send a webhook notification. |
| `docs/guides/troubleshooting.md` | Problems and fixes, listed by pipeline stage, and how to collect diagnostics safely. |
| `docs/reference/index.md` | Commands, configuration keys, exit codes, output layout, requirements, and terms. |
| `docs/reference/commands.md` | Every Frame Compare command and option, and the exit codes it returns. |
| `docs/reference/configuration.md` | Every configuration key with its values, its default, and what it changes. |
| `docs/reference/output-layout.md` | What a run writes to the generated-data root and which files you can move or delete. |
| `docs/reference/requirements.md` | What each installation route needs on your system. |
| `docs/reference/glossary.md` | Definitions of the terms used in this documentation. |
| `docs/internals/index.md` | Contracts, architecture, runbooks, and validation records for people who maintain Frame Compare. |

## Unit U4: new and replaced pages

U4 writes these files exactly. They are complete files.

### `docs/index.md` (replace)

````markdown
---
template: home.html
title: Documentation
description: Frame Compare picks frames from two or more videos, aligns them by audio when needed, renders matching screenshots, and writes an offline report.
hide:
  - navigation
  - toc
  - path
---

<div class="fc-home" markdown>

## Report views

Each run writes one `report.html` with every rendered frame for every source. You
switch views inside the report.

=== "Slider"

    <figure class="fc-figure">
      <img src="images/report-overview.webp" alt="Report in Slider view comparing the PQ10 reference with the HLG10 comparison at frame 1000." width="1600" height="1000" loading="lazy">
      <figcaption>Use Slider for crop, scaling, haloing, texture, grain, and tone. Footage © EBU, CC BY 4.0.</figcaption>
    </figure>

=== "Grid"

    <figure class="fc-figure">
      <img src="images/report-grid.webp" alt="Report in Grid view showing both sources side by side at frame 1000." width="1600" height="1000" loading="lazy">
      <figcaption>Use Grid to find the source that differs, then compare it in Slider. Footage © EBU, CC BY 4.0.</figcaption>
    </figure>

=== "Inspector"

    <figure class="fc-figure">
      <img src="images/report-inspector.webp" alt="Report with the Inspector open on the Clips tab, listing each source's picture size, length, file size, presentation, and signal." width="1600" height="1000" loading="lazy">
      <figcaption>The Clips tab lists each source's size, length, and HDR signal. Footage © EBU, CC BY 4.0.</figcaption>
    </figure>

=== "Lens"

    <figure class="fc-figure">
      <img src="images/report-lens.webp" alt="Report in Slider view with the lens magnifying the area under the pointer." width="1600" height="1000" loading="lazy">
      <figcaption>Drag the lens grip to move the window. Footage © EBU, CC BY 4.0.</figcaption>
    </figure>

## How a comparison runs

<div class="fc-features" markdown>

<div class="fc-feature" markdown>

<div class="fc-feature__visual">
  <ol class="fc-strip" aria-label="Frames selected in the example run">
    <li><img src="images/home-strip-45.webp" alt="" width="480" height="270">45 · Bright</li>
    <li><img src="images/home-strip-83.webp" alt="" width="480" height="270">83 · Random</li>
    <li><img src="images/home-strip-948.webp" alt="" width="480" height="270">948 · Random</li>
    <li class="fc-strip__user"><img src="images/home-strip-1000.webp" alt="" width="480" height="270">1000 · User</li>
    <li><img src="images/home-strip-1050.webp" alt="" width="480" height="270">1050 · Dark</li>
    <li><img src="images/home-strip-1080.webp" alt="" width="480" height="270">1080 · Random</li>
  </ol>
</div>

### Frame selection

Name frames by number, or let Frame Compare add random, dark, bright, and motion
frames. The same seed selects the same frames.

[Frame selection and analysis](guides/analysis-modes.md)

</div>

<div class="fc-feature" markdown>

<div class="fc-feature__visual">
  <img src="images/diagram-audio-offset.svg" alt="The reference and comparison audio tracks show the same pattern shifted in time; the shift is the offset." width="640" height="190">
</div>

### Audio alignment

Frame Compare estimates each comparison's offset from its audio. The offset is
applied only when the video confirms it and every other check passes; otherwise the
run reports `NOT APPLIED` and you review it.

[Audio alignment](guides/audio-alignment.md)

</div>

<div class="fc-feature" markdown>

<div class="fc-feature__visual">
  <img src="images/hdr-diagnostic-overlay.webp" alt="Diagnostic overlay on the HLG10 comparison listing the source, the HLG BT.2020 signal, and the BT.2390 tonemap at 100 nits." width="1920" height="1080" loading="lazy">
</div>

### HDR tonemapping

PQ and HLG sources are tonemapped with vs-placebo. The diagnostic overlay prints the
detected signal and the applied tonemap on each screenshot.

[HDR and tonemapping](guides/hdr-tonemapping.md)

</div>

<div class="fc-feature" markdown>

<div class="fc-feature__visual" markdown>

```text
pq10-reference + hlg10-comparison/
├── report.html
├── screenshots/
├── generated/
├── run_info.toml
└── run_result.toml
```

</div>

### Offline report

Each run writes its own folder. The report links to its screenshots by relative
path, so you can move or archive the folder as a whole.

[Output layout](reference/output-layout.md)

</div>

</div>

## Install

Every route follows the same four steps. The routes differ in who provides Python and
the media libraries.

<div class="fc-cards" markdown>

- [Windows portable](getting-started/windows-portable.md)

    Complete runtime, VSView alignment panel, installer, and signed code-only
    updates. Use this on Windows 10 or 11.

- [Docker](getting-started/docker.md)

    Headless runtime with software Vulkan for HDR. Reports stay on the host. Use
    this on macOS and Linux.

- [Native source](getting-started/native.md)

    Bring your own FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo, and Vulkan. Use
    this if you already run VapourSynth.

</div>

## Your first comparison

Run these commands in order. The dry run shows the sources, the reference, and the
frames you asked for, without opening the videos.

=== "Windows portable"

    ```powershell
    frame-compare wizard           # set the input folder, reference, and frames
    frame-compare doctor           # check the media runtime
    frame-compare run --dry-run    # list what a run would do
    frame-compare run              # run the comparison
    ```

=== "Docker"

    ```bash
    export FRAME_COMPARE_HOST_UID="$(id -u)"
    export FRAME_COMPARE_HOST_GID="$(id -g)"
    mkdir -p config comparison_videos generated
    docker compose build frame-compare-run
    docker compose run --rm frame-compare-wizard
    docker compose run --rm frame-compare-run doctor
    docker compose run --rm frame-compare-run run --root /workspace --dry-run
    docker compose run --rm frame-compare-run run --root /workspace
    ```

=== "Native with uv"

    ```bash
    uv run --no-sync frame-compare wizard
    uv run --no-sync frame-compare doctor
    uv run --no-sync frame-compare run --root . --dry-run
    uv run --no-sync frame-compare run --root .
    ```

[Your first comparison](getting-started/first-comparison.md) covers each stage and
the Docker setup.

## Reference

<div class="fc-cards" markdown>

- [Configuration](reference/configuration.md)

    Each key with its values and default.

- [Commands](reference/commands.md)

    Every command and option.

- [Exit codes](reference/commands.md#exit-codes)

    Codes returned to scripts.

- [Troubleshooting](guides/troubleshooting.md)

    Problems listed by stage.

</div>

</div>
````

The three overview pages set `title:` so browser tabs read "Guides", "Reference", and
"Internals"; their H1 and navigation label stay "Overview".

The home page's hero (H1, lead, buttons, slider, and footage credit) is in
`overrides/home.html` (theme specification); the H1 text there is "Frame Compare".

### `docs/guides/index.md` (new)

````markdown
---
title: Guides
description: Guides for sources, frame selection, audio alignment, HDR, reports, presets, publishing, and troubleshooting.
---

# Overview

Each guide covers one part of a comparison. Start with how the stages fit together.

<div class="fc-cards" markdown>

- [How Frame Compare works](how-it-works.md)

    The six stages of a run and what each stage decides.

- [Sources, references, and labels](sources-and-labels.md)

    Choose the reference, labels, trims, and the active picture.

- [Frame selection and analysis](analysis-modes.md)

    Choose which frames to render and make the choice repeatable.

- [Audio alignment](audio-alignment.md)

    Line up sources by their audio and read the result.

- [VSView alignment review](vsview-review.md)

    Confirm or enter alignment by eye.

- [HDR and tonemapping](hdr-tonemapping.md)

    Turn HDR sources into comparable SDR screenshots.

- [Reports and overlays](reports-and-overlays.md)

    Use the report views and choose screenshot overlays.

- [Presets, history, and generated data](presets-history-generated-data.md)

    Keep results, reopen past runs, and reuse settings.

- [Publishing and webhooks](publishing-and-webhooks.md)

    Upload to slow.pics and send a notification.

- [Troubleshooting](troubleshooting.md)

    Problems listed by stage.

</div>
````

### `docs/reference/index.md` (new)

````markdown
---
title: Reference
description: Commands, configuration keys, exit codes, output layout, requirements, and terms.
---

# Overview

Look up an exact command, key, or path. The guides explain when to use them.

<div class="fc-cards" markdown>

- [Commands](commands.md)

    Every command and option, and the exit codes.

- [Configuration](configuration.md)

    Each key with its values and default.

- [Output layout](output-layout.md)

    What a run writes and what you can move or delete.

- [Requirements](requirements.md)

    What each installation route needs on your system.

- [Glossary](glossary.md)

    The terms this documentation uses.

</div>
````

### `docs/internals/index.md` (new)

````markdown
---
title: Internals
description: Contracts, architecture, runbooks, and validation records for people who maintain Frame Compare.
---

# Overview

These pages are for people who change Frame Compare. They state the exact behavior the
code must keep, how the project is built and released, and the evidence behind past
decisions. To use Frame Compare, start with
[Choose an installation](../getting-started/index.md).

<div class="fc-cards" markdown>

- [CLI behavioral contract](../current-cli-contract.md)

    Streams, JSON documents, persistence, and exit codes, stated exactly.

- [Current architecture](../current-architecture.md)

    Modules, ownership, and data flow.

- [Supported media runtime](../supported-media-runtime.md)

    Every component version and the reason it was selected.

- [Engineering runbook](../ENGINEERING_RUNBOOK.md)

    Commands, checks, and procedures for development and release.

- [Physical Windows runtime validation](../media-runtime-windows-validation.md)

    The acceptance checklist for the Windows bundle on real hardware.

- [Analysis performance validation](../analysis-performance-validation.md)

    How analysis performance is measured.

- [Analysis benchmark history](../analysis-benchmark-history.md)

    Recorded benchmark results.

- [Historical decisions](../DECISIONS.md)

    Why past design choices were made.

</div>

Contributing guidelines are in
[`CONTRIBUTING.md`](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md).
````

### `docs/reference/requirements.md` (new)

````markdown
---
description: What each installation route needs on your system.
---

# Requirements

Frame Compare needs a Python runtime and a media stack: FFmpeg, VapourSynth,
L-SMASH-Works, and, for HDR sources, vs-placebo with Vulkan. Each installation route
provides that stack differently.

| Route | Operating system | You install | The route provides |
| --- | --- | --- | --- |
| [Windows portable](../getting-started/windows-portable.md) | Windows 10 or 11, x64 | Nothing else to run Frame Compare; verifying the download uses the GitHub CLI | Python, the media stack, VSView with the alignment panel, the installer, and the updater |
| [Docker](../getting-started/docker.md) | macOS or Linux | Docker with Docker Compose, and a clone of the repository | Python and the media stack, with software Vulkan for HDR |
| [Native source](../getting-started/native.md) | Any system the media stack supports | Python, FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo with Vulkan, and uv or pip | Frame Compare and its Python dependencies |

## Supported video files

Frame Compare discovers files with the extensions `.mkv`, `.mp4`, `.avi`, `.m2ts`, and
`.ts`, matched case-insensitively.

## HDR tonemapping

HDR sources need vs-placebo and a working Vulkan implementation. The Windows bundle
uses the host's Vulkan driver. Docker uses software Vulkan, which needs no GPU. A native
install uses the host's Vulkan driver.

## Alignment review

The VSView alignment panel ships with the Windows bundle. A native install adds it with
the `vsview` extra. The default Docker services do not include it, and Docker on macOS
does not run VSView. [Docker profiles](../getting-started/docker-profiles.md) describes
an optional Linux X11 profile for the panel; that profile is not yet verified on a
visible desktop.

## Exact versions

The native install page lists the versions you install yourself. Every component
version, with the reason it was chosen, is in the
[Supported media runtime](../supported-media-runtime.md) record.
````

The alignment-review facts come from the "Capability by host" table in
`docs/getting-started/docker-profiles.md` (rows for macOS Docker Desktop and Linux Docker
with X11 GUI).

### `docs/reference/glossary.md` (new)

Write this file exactly. The definitions follow the style guide's terminology table,
rewritten for readers.

````markdown
---
description: Definitions of the terms used in this documentation.
---

# Glossary

These are the terms this documentation uses, with their exact meaning.

source
:   One input video that takes part in a comparison.

reference
:   The source whose frame numbers define the comparison. It appears first.

comparison
:   Any source other than the reference. The report names them Comparison 1,
    Comparison 2, and so on.

input directory
:   The folder Frame Compare searches for sources, set by `paths.input_dir` or
    `run --input`.

generated-data root
:   The folder that holds run folders and shared caches, set by `paths.generated_dir`.

run folder
:   The folder Frame Compare creates for one run inside the generated-data root.

report
:   The file `report.html` that a run writes. The report viewer is its interactive
    interface.

offset
:   The signed difference between a reference frame number and the matching comparison
    frame number.

trim
:   Frames excluded from the start or end of a source.

active picture
:   The image area without letterbox or pillarbox bars. Set it explicitly with
    `active_rect`.

alignment
:   Finding and applying offsets between sources.

applied, not applied
:   Whether an offset changes the trims. The terminal prints `APPLIED` or
    `NOT APPLIED`.

audio candidate
:   An offset found from the audio that has not been confirmed yet.

VSView alignment panel
:   The **Frame Compare Alignment Review** panel inside VSView, where you confirm or
    enter alignment by eye.

user frames
:   Frames you list in `analysis.user_frames` or `run --frames`.

frame selection
:   Choosing which frames to render.

tonemapping
:   Converting HDR video to an SDR presentation.

dry run
:   What `frame-compare run --dry-run` prints: the sources, the frames you asked for,
    and what a run would create, without opening the videos.

workspace root
:   The folder set by `--root`, which defaults to the current folder.

Windows portable bundle
:   The complete Windows distribution of Frame Compare. Its download is the complete
    portable ZIP.

Single view
:   The report view that shows one source at a time. Its configuration value is
    `overlay` (`report.default_mode`).

baked overlay
:   Text rendered into the screenshot pixels, set by `screenshots.overlay_mode`.

source labels
:   The source names the report viewer shows on the image, toggled by
    **Source labels**.

slow.pics
:   The image-comparison website Frame Compare can publish to. Its settings are in the
    `[slowpics]` table.
````

## Unit U5: Get started pages and repository front door

### `docs/getting-started/index.md`

- Voice pass.
- Replace the sentence "The `[Supported media runtime](../supported-media-runtime.md)`
  page is the home of component versions." with "`[Requirements](../reference/requirements.md)`
  lists what each route needs."
- Replace the three H3 route cards at the top (the `fc-route` markup or H3 links) with
  the cards block from the home page's **Install** section, with link targets made
  relative to this page (`windows-portable.md`, `docker.md`, `native.md`).
- Keep "Which route fits", "What each route includes", "Who owns the runtime", and
  "After installation". In "After installation", replace the five-step list with a steps
  block of the same five steps.

### `docs/getting-started/windows-portable.md`

Restructure in this order. Keep every guard string.

1. Lead: replace the two opening paragraphs with:

    > The Windows portable bundle is the complete Frame Compare distribution for Windows
    > 10 and 11 (x64). It includes Python, the media runtime, VSView with the alignment
    > panel, an installer, and signed code-only updates.

    Move the second opening paragraph (the `vsview` package, extras, BestSource,
    vspackrgb, and L-SMASH-Works sentences) unchanged into a new final H2,
    "Bundle contents", directly before "Troubleshooting".
2. "Install from a published release" becomes "Install", with this structure:
   - The button `[Download the latest release](https://github.com/TJZine/frame-compare/releases/latest){ .md-button .md-button--primary }`.
   - A steps block with five steps: **Download both files from the same release.**;
     **Verify the download.**; **Extract the ZIP into a fresh, empty folder.**;
     **Run the installer from the extracted folder.**; **Open a new terminal.**
   - Step 1 holds the existing `text` block that lists the two file names. Delete the
     sentence "Download both files for the same release tag:"; the step title replaces
     it.
   - Delete the sentence "Extract the ZIP into a fresh, empty folder, open the extracted
     bundle folder, and run:"; steps 3 and 4 replace it.
   - Step 2 holds, in order:
     1. The sentence: "On an internet-connected machine with the GitHub CLI installed,
        confirm that this repository's Windows build workflow produced the ZIP, then
        compare its SHA-256 checksum." It replaces the paragraph beginning
        "Authenticate the ZIP's release provenance".
     2. A `??? fc-disclosure "Show the verification commands"` block containing the
        existing provenance code block (title `PowerShell · release provenance`), the
        existing sentence "Then verify the ZIP checksum before extracting it:", and the
        existing checksum code block (title `PowerShell · SHA-256 checksum`). Code
        blocks are byte-for-byte except for the added titles.
     3. `!!! warning "The hashes must match exactly"` whose body is exactly: "Delete and
        download both files again if verification fails; do not bypass the mismatch."
        It replaces the paragraph beginning "The expected and actual hashes".
   - Step 4 holds the existing `.\install.cmd` block with title `PowerShell`.
   - Step 5 holds the existing "Open a new terminal …" sentence and the sentence "Check
     the runtime with `frame-compare doctor`."
   - Keep the install figure after the steps block, with `src` relative to the new
     location (`../images/windows-portable-install.png`).
   The prototype on 2026-10-12 built this structure and kept every guard string.
3. Move "Build the portable bundle from a clone" to directly before "Bundle contents".
4. "Update behavior": keep the update-type table and the `frame-compare-update apply`
   block. Move the paragraph beginning "The updater bounds the archive" into a
   `??? fc-disclosure "Why an update can be refused"` block directly after the command
   block, as two paragraphs: the first ends "…are bounded before extraction."; the
   second begins "It accepts only a native-panel-capable full bundle". Change no words,
   and keep the physical lines that hold `` bundle_info.schema_version` 3 `` and
   `pre-native-panel schema-2 bundles` as they are.
5. Voice pass on the rest. "Workspace and generated data", "First comparison", "VSView
   alignment review", "Inspect previous runs", "Backup and rollback", "Uninstall",
   "Bundle provenance and licenses", and "Troubleshooting" keep their headings.

### `docs/getting-started/docker.md`

- Voice pass.
- In "Run your first comparison", split the single command block into two titled
  blocks: `title="Set up the workspace"` (the two `export` lines and `mkdir`) and
  `title="Build the image and run the four stages"` (the five `docker compose` lines).
  Keep the existing paragraph about the UID and GID variables before the first block.
  Put the sentence "Then build the image and run the four stages:" before the second.
- Turn the paragraph after the commands (beginning "The wizard creates or reviews") into
  at most two short paragraphs; keep every fact.
- Replace the "Next steps" text with a cards block: `[Your first comparison](first-comparison.md)`,
  card sentence "What each stage checks, with the Docker commands."; and
  `[Docker profiles](docker-profiles.md)`, card sentence "NVIDIA and X11 profiles and the
  full service list.".

### `docs/getting-started/docker-profiles.md`

- Voice pass. Keep headings and the services table.
- Split the paragraph beginning "The NVIDIA path keeps the default Docker services
  unchanged" and the paragraph beginning "The verifier covers the
  `frame-compare-alignment-review` entry point" at sentence boundaries, to at most 70
  words each.

### `docs/getting-started/native.md`

- Voice pass. Keep the prerequisites list and every guard string.
- Split the 152-word `vsview` extra paragraph into four paragraphs without changing
  words: (1) the sentence ending "package to R81."; (2) from "It uses VSView's base
  dependency graph" to "is unsupported."; (3) from "On Windows it also installs" to
  "vs-placebo installations."; (4) from "If you do not need native panel review" to the
  end. Keep the physical lines that hold the guard strings.
- Replace the link to the Supported media runtime page with links to
  `[Requirements](../reference/requirements.md)` for the summary and the Supported media
  runtime record for exact versions.

### `docs/getting-started/first-comparison.md`

- Voice pass, including the rewrites shown as examples in the style guide (the dry-run
  paragraph is one of them).
- Replace the two terminal figures with output blocks. Source text: strip ANSI escape
  codes from `.tmp/docs-refresh-2026-10-08/capture/dry-run.ansi` (the whole output) and
  from `.tmp/docs-refresh-2026-10-08/capture/run.ansi` (the `Comparison complete` panel,
  from the line starting `╭─ ✓ Comparison complete` to its closing `╯` line). Titles:
  `Output · frame-compare run --dry-run` and `Output · frame-compare run`. Use this
  stripping code:

    ```python
    import re
    def plain(path):
        text = open(path, encoding="utf-8").read()
        text = re.sub(r"\x1b\]8;[^\x1b\x07]*(?:\x1b\\|\x07)", "", text)
        return re.sub(r"\x1b\[[0-9;]*m", "", text)
    ```

  Then remove trailing whitespace from every line (`"\n".join(line.rstrip() for line
  in text.splitlines())`). If either file is missing, report `blocked`.
- "Repeat comparisons": delete only the last sentence of the paragraph beginning
  "Revisit `wizard`" ("A dry run only validates configuration and intent; it does not
  probe media or prove the runtime is ready to render."), which repeats "3. Dry run".
  Keep the rest of that paragraph.
- In "3. Dry run", two checklist items describe output the dry run does not print.
  Replace "the expected reference is first;" with "the Reference line names the source
  you expect;" (the dry run lists sources by name and prints the reference on its own
  line), and replace "the generated-data root is correct;" with "the input directory is
  correct;".
- Rename the H2 "Confirm the comparison is trustworthy" to "Check the result before you
  share it". No page links to its anchor; the style test rejects "trustworthy".
- Replace the "Continue with:" list at the end with a **Next steps** H2 and a cards
  block of `[Reports and overlays](../guides/reports-and-overlays.md)`,
  `[Audio alignment](../guides/audio-alignment.md)`, and
  `[Troubleshooting](../guides/troubleshooting.md)`. Card sentences: "Use the report views
  to check the result.", "Read what the alignment result means.", "Problems listed by
  stage."

### `README.md`

- Update links: `docs/windows-portable.md` → `docs/getting-started/windows-portable.md`;
  `docs/guides/first-comparison.md` → `docs/getting-started/first-comparison.md`
  (both occurrences, keeping the `#repeat-comparisons` anchor).
- Delete the blockquote tagline; the paragraph after the links already describes the
  tool.
- Rename "Why Frame Compare" to "What it does". Rewrite its five bullets without bold
  lead-ins or em dashes, one sentence each, keeping their facts.
- Voice pass on the remaining README prose. Keep the badges, the image, the credit
  line, and the tables.

### `INSTALL-WINDOWS.md`

- Update the link to `docs/getting-started/windows-portable.md` and the link text to
  "Windows portable guide".
- Change the H1 "Windows Installation" to "Windows installation". The rest of the page
  already meets the style guide.

## Unit U6: guides, part one

### `docs/guides/how-it-works.md`

- Lead: replace with the style guide's "After" example for this page.
- Replace the Mermaid block with this pipeline strip, followed by the sentence "The
  sections below use the same numbers.":

    ```markdown
    <div class="fc-pipeline" markdown>

    1. [Discovery and validation](#1-discovery-and-validation)
    2. [Probing and selectable-window preparation](#2-probing-and-selectable-window-preparation)
    3. [Frame planning and analysis](#3-frame-planning-and-analysis)
    4. [Alignment](#4-alignment)
    5. [Rendering and tonemapping](#5-rendering-and-tonemapping)
    6. [Report and optional publication](#6-report-and-optional-publication)

    </div>
    ```

- The Mermaid diagram showed that only a confirmed automatic offset changes the trims.
  Section 4 must state that rule in prose; if it does not after the voice pass, keep the
  existing sentence that does.
- Voice pass on sections 1 to 6 and "Owned persistent artifacts".

### `docs/guides/sources-and-labels.md`

- Lead: replace with "Frame Compare identifies each source by its path. This guide
  covers which source is the reference, how labels are built, and how to correct a
  source's trims, timing, and picture area." Move the rest of the old lead (from "Paths
  and fingerprints control" to "explicit labels remain exact.") to be the first
  paragraph of "Make labels readable", before its existing first paragraph.
- Split the two long paragraphs in "Make labels readable" (92 and 128 words).
- Voice pass on the rest. Keep the example section.

### `docs/guides/analysis-modes.md`

- Voice pass. Split the 95-word paragraph in "Selection types" and the 61-word
  paragraph in "Excluding intros and credits" if it exceeds 70 words after edits.
- "Choosing between modes": voice pass only; keep both lists and the example.

### `docs/guides/audio-alignment.md`

- Add the offset diagram after the lead:

    ```html
    <figure class="fc-figure">
      <img src="../images/diagram-audio-offset.svg" alt="The reference and comparison audio tracks show the same pattern shifted in time; the shift is the offset." width="640" height="190" loading="lazy">
      <figcaption>The offset is the shift between the two tracks. The waveform is illustrative.</figcaption>
    </figure>
    ```

- Split the 94-word paragraph in "What the results mean" and the 65-word paragraph in
  "Choose the audio streams" if over 70 words after edits.
- Voice pass.

### `docs/guides/vsview-review.md`

- Voice pass only. Keep every guard string.

## Unit U7: guides, part two

### `docs/guides/hdr-tonemapping.md`

- Lead: "Frame Compare turns HDR sources into SDR screenshots so you can compare them
  in one browser report. It tonemaps a source with vs-placebo when the source's
  properties show that it is HDR." Keep the remaining facts of the old lead in "What
  the pipeline does".
- Voice pass.

### `docs/guides/reports-and-overlays.md`

- Replace the five view H3s ("Slider", "Single", "Diff", "Blink", "Grid") and their
  one-to-three-sentence bodies with a table under "Views": columns "View" and "Use it
  for", one row per view in the existing order, each cell built from the existing
  sentences. Keep the sentence about `report.default_mode` before the table. Keep the
  Slider figure where it is, near the top of the page, and put the Grid figure directly
  after the table. The Blink row keeps the existing caveat that browser timing is not
  frame-accurate playback.
- Split the two long paragraphs (94 words in "Navigate and inspect", 101 words in
  "Review notes").
- Voice pass.

### `docs/guides/presets-history-generated-data.md`

- Lead: "Frame Compare keeps your configuration separate from what runs produce. This
  guide covers where run folders and caches go, how to reopen a past run, and how to
  save settings as a preset."
- Voice pass.

### `docs/guides/publishing-and-webhooks.md`

- Add a lead after the H1, before the first H2: "Frame Compare keeps every comparison on
  your computer until you turn on publishing. This guide covers uploading to slow.pics
  and sending a webhook notification."
- Move the sentence "Frame Compare is offline-first." out; the lead replaces it. Keep
  the rest of that paragraph's facts in "Turn on publishing".
- Turn the paragraph beginning "Do not commit a live webhook URL." into
  `!!! danger "Keep webhook URLs out of config files"` whose body is that paragraph,
  unchanged, in the same place.
- Split the paragraph beginning "The webhook payload is the Discord-compatible" at
  sentence boundaries, to at most 70 words each.

### `docs/guides/troubleshooting.md`

- Run `convert_troubleshooting.py` first (see [scripts](scripts.md#convert_troubleshootingpy)).
- Lead: "Start with the same installation route that runs the comparison. Run these two
  commands through it:" followed by the existing command block, then the existing
  sentence about wrappers.
- After "Common problems", add an H2 "Error codes" with one sentence: "Error codes start
  with `FC-` and a digit that names the family; the `[exit codes](../reference/commands.md#exit-codes)`
  table maps each family to an exit code." Place it before "Diagnose by pipeline stage".
- Voice pass on the converted entries: each entry's paragraph is one or two sentences;
  keep the H3 text unchanged so its anchor stays stable.
- The entry "An alignment line says `NOT APPLIED`" currently says the candidate "was not
  confirmed by the video". A candidate can stay `NOT APPLIED` even when the video
  confirms it (`docs/guides/audio-alignment.md`, "What the results mean"). Its paragraph
  becomes exactly: "Frame Compare did not apply an offset, because the audio candidate
  did not pass every check or no usable candidate was found; see
  `[what the results mean](audio-alignment.md#what-the-results-mean)`."

## Unit U8: Reference pages and the contract's contents list

### `docs/reference/commands.md`

- Lead: "Every command and option, with what it changes and whether `--write-config`
  saves it. For exact output streams and JSON fields, see the
  `[CLI behavioral contract](../current-cli-contract.md)`."
- Replace the body of "Exit codes" (currently one link) with, in order: the sentence
  "Commands exit with these codes:"; the contract's eight-row table from "Exit Codes And
  Error Families", copied byte-for-byte; and the paragraph "The first digit of an `FC-`
  code selects its family and exit code. Human output prints the code and message on
  stderr; `--json` prints a typed error document, described in the
  `[CLI behavioral contract](../current-cli-contract.md#output-modes)`." Keep the H2
  text "Exit codes" so the anchor `#exit-codes` stays stable.
- After U3's conversion, the two paragraphs that followed the Run options table sit at
  the end of `### Output modes`. Move the paragraph beginning "Runs and dry runs reject"
  to directly after the Run section's first paragraph, before
  `### Workspace and configuration`. Replace the paragraph beginning
  "`frame-compare run --help` lists the same options" with the sentence
  "`frame-compare run --help` groups the options under the same six headings as this
  section." and place it directly after the moved paragraph.
- Add the test `test_commands_reference_exit_codes_match_contract` from the
  [repository changes](repository-changes.md#exit-code-sync-test-unit-u8).
- Voice pass on the remaining prose.

### `docs/reference/configuration.md`

- Lead (new first paragraph after the H1): "Every key Frame Compare reads from
  `config/config.toml`, with its values, its default, and what it changes."
- "How settings combine": replace the first sentence with an ordered list of the four
  sources, highest first: run options, environment variables, the TOML file, built-in
  defaults. Keep the remaining sentences.
- "Environment variables and secrets": add `title="Shell"` to the export block.
- Voice pass on section introductions. Do not edit key blocks except to fix a
  style-guide violation inside an effect sentence.

### `docs/reference/output-layout.md`

- Voice pass. Keep the tree and the tables.

### `docs/current-cli-contract.md`

- Delete the H2 "Contents" and its list. Change nothing else.
