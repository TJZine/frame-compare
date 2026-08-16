# Your first comparison

A safe first run has four stages: configure, diagnose, preview, then execute. Use the
same installation route and workspace for every stage so configuration and path
resolution remain consistent.

## Before you begin

Create or select a workspace with at least two supported files in its input directory.
For a publication-safe example, use names such as:

```text
comparison_videos/
├── Reference.mkv
├── Encode-A.mkv
└── Encode-B.mkv
```

Supported extensions are `.mkv`, `.mp4`, `.avi`, `.m2ts`, and `.ts`, matched
case-insensitively.

## Run the four stages

=== "Windows portable"

    ```powershell
    frame-compare wizard
    frame-compare doctor
    frame-compare run --dry-run
    frame-compare run
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

=== "Native with pip"

    ```bash
    frame-compare wizard
    frame-compare doctor
    frame-compare run --root . --dry-run
    frame-compare run --root .
    ```

## What each stage protects

### 1. Wizard

The wizard reviews workspace paths, source behavior, frame selection, rendering, and
publishing choices. It writes configuration only after confirmation. The first-use
configuration explicitly keeps `slowpics.auto_upload = false`.

### 2. Doctor

`doctor` checks the runtime used by the selected route. Resolve critical failures for
the features you intend to use. Optional integrations can remain disabled, but an
FFmpeg, VapourSynth, source-plugin, or Vulkan failure can block the corresponding
rendering or alignment path.

<!-- SCREENSHOT_SLOT: first-run-doctor
Target file: ../images/first-run-doctor.png
Place a terminal capture after this paragraph. Show a successful human-readable doctor
summary from the Windows portable route. Include the runtime profile, FFmpeg,
VapourSynth, source plugin, and tonemapping checks. Redact usernames and absolute paths.
Suggested alt text: "Successful Frame Compare doctor output for the Windows portable
runtime."
-->

### 3. Dry run

A dry run validates configuration, source discovery, reference and comparison order,
selection intent, and output intent without entering the rendering pipeline. Check:

- the expected reference is first;
- every intended comparison is present once;
- the generated-data root is correct;
- frame counts and analysis mode match your intent;
- publishing remains disabled unless deliberately enabled.

<!-- SCREENSHOT_SLOT: first-run-dry-run
Target file: ../images/first-run-dry-run.png
Place a cropped terminal capture here. Show the at-a-glance section of a three-source
dry run with generic labels and no private paths. Annotate the reference, comparisons,
selected analysis mode, output root, and upload state.
Suggested alt text: "Frame Compare dry-run summary identifying the reference, comparison
sources, frame plan, and local output destination."
-->

### 4. Run

The normal run reserves a fresh run folder, probes the clips, builds the frame plan,
performs analysis and alignment when required, renders screenshots, records metadata,
and writes the report. Network publication occurs only when the effective configuration
or command explicitly enables it.

<!-- SCREENSHOT_SLOT: first-run-complete
Target file: ../images/first-run-complete.png
Place a final terminal capture here. Show the completed run summary, report path, frame
count, warnings area, and elapsed time. Use generic source labels and redact absolute
paths after the generated-data root is recognizable.
Suggested alt text: "Completed Frame Compare run showing the generated report path and
summary."
-->

## Find the result

Each executed run gets a reserved directory beneath `paths.generated_dir`:

```text
generated/
├── cache/
└── <run-name>/
    ├── report.html
    ├── screenshots/
    ├── generated/
    ├── run_info.toml
    └── run_result.toml
```

Open `report.html` while keeping the run folder together. Relative screenshot links
continue to work when the entire folder is moved or archived. Docker users should use
the host-open helper or translate `/workspace/generated/` to the host `generated/`
directory.

## Confirm the comparison is trustworthy

Before sharing a result:

1. Review several frames in slider and diff modes.
2. Check source labels, resolution, HDR/SDR identity, and frame numbers.
3. Verify alignment around dialogue, cuts, and motion.
4. Look for crop, aspect-ratio, or tone-mapping differences that could make the
   comparison misleading.
5. Keep the result local until it looks correct.

Continue with:

- [Reports and Overlays](reports-and-overlays.md)
- [Sources, References, and Labels](sources-and-labels.md)
- [Frame Selection and Analysis](analysis-modes.md)
- [Audio Alignment and VSPreview](audio-alignment.md)
- [HDR and Tonemapping](hdr-tonemapping.md)
- [Troubleshooting](troubleshooting.md)
