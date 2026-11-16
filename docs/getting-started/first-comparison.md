---
description: Run the wizard, check the runtime, preview with a dry run, and run your first comparison.
---

# Your first comparison

Run your first comparison in four stages: configure, diagnose, preview, then execute.
Use the same installation route and workspace for every stage so Frame Compare reads
the same configuration and resolves paths consistently.

## Before you begin

Create or select a workspace with at least two supported files in its input directory.
For a two-source example, use files such as:

```text
comparison_videos/
├── pq10-reference.ts
└── hlg10-comparison.ts
```

The terminal samples below use three releases of the same Black Sails episode.

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

The wizard asks you to set the input directory, the generated-data location, the
reference, and the frame-selection goal. Configure rendering and publishing through
configuration, environment variables, or presets; the wizard has no upload toggle.
It writes configuration only after confirmation, and the first-use configuration
keeps `slowpics.auto_upload = false`.

After a successful save, or a no-op with nothing to change, the wizard prints suggested
`doctor`, `run --dry-run`, and `run` commands for your resolved workspace and config file.
It never runs them.

### 2. Doctor

`doctor` checks the runtime used by the selected route. Resolve critical failures for
the features you intend to use. Optional integrations can remain disabled, but an
FFmpeg, VapourSynth, source-plugin, or Vulkan failure can block the corresponding
rendering or alignment path.

### 3. Dry run

A dry run reads your configuration and the file names in the input directory.
It shows the sources it found, the reference, the frames you asked for, and what a run
would create. It does not open the videos, so run `doctor` to check the media runtime.

Check:

- the Reference line names the source you expect;
- every intended comparison is present once;
- the input directory is correct;
- frame counts and analysis mode match your intent;
- publishing remains disabled unless deliberately enabled.

Check the sources, the Reference line, and the frame counts in this output.

``` { .text .fc-output title="Output · frame-compare run --dry-run" }
No side effects: this dry run validates configuration and input filenames only; it does not write, render, upload, or
open anything.

Will use
  Workspace: /workspace
  Input directory: comparison_videos
  Sources (3): Black.Sails.S01E08.1080p.Bluray.DD5.1.x264-EbP.mkv,
Black.Sails.S01E08.VIII.1080p.AMZN.WEB-DL.DDP.5.1.H.264-GNOME.mkv,
Black.Sails.S01E08.VIII.1080p.BluRay.REMUX.AVC.DTS-HD.MA.5.1-NOGRP.mkv
  Reference: Black.Sails.S01E08.1080p.Bluray.DD5.1.x264-EbP.mkv -> Black.Sails.S01E08.1080p.Bluray.DD5.1.x264-EbP.mkv
  Frame selection: specific frames, random frames, dark frames, bright frames, motion frames
  Specific frames: 0, 120
  Frame counts: specific=2, random=4, dark=2, bright=2, motion=2
  Analysis: quality mode; metrics required; random seed 42

Would create in a real run
  Screenshots: yes
  Run folder: yes
  Offline report: yes
  Open report after success: not configured

Publishing after success
  slow.pics upload: disabled; visibility public
  Copy URL to clipboard: not applicable
  Open the published URL: not applicable
  Create a URL shortcut: not applicable
  Send a webhook notification: not applicable

Unknown until execution
  Run folder name: not available yet (resolved during run-folder reservation)
  Final selected frames: not available before media probing and runtime frame selection
  Clip metadata: not available before media probing
  Output dimensions: not available before media probing and render planning

Not performed by dry-run
  - runtime readiness checks
  - FFmpeg and ffprobe checks
  - media probing
  - frame analysis
  - audio alignment
  - cache reads and writes
  - run-folder reservation and metadata writes
  - screenshot rendering and report generation
  - network metadata lookup and publishing
  - browser, clipboard, and VSView actions
```

### 4. Run

The normal run reserves a fresh run folder, probes the sources, builds the frame plan,
performs analysis and alignment when required, renders screenshots, records metadata,
and writes the report. Network publication occurs only when the effective configuration
or command explicitly enables it.

Use the report and screenshot paths in the completed-run summary.

``` { .text .fc-output title="Output · frame-compare run" }
╭─ ! Comparison complete · 1 warning
│ report          generated/Black Sails/report.html
│ screenshots     generated/Black Sails/screenshots  30 files
│ alignment       GNOME +147f · NOGRP +0f · audio
│ diagnostics     generated/Black Sails/alignment_diagnostics
│
│ run             10 of 12 frames · 3 sources · analysis computed
│ time            11m 12s total
│   machine       setup 48.5 s · analyze 7m 16s · align 2m 51s · render 16.6 s
╰─

╭─ ! Warnings
│ ! 2 requested frames fall outside the shared range and were skipped: 0, 120
╰─
```

## Repeat comparisons

Once configuration and the runtime are established, most later comparisons only need
the preview and execute stages.

=== "Windows portable"

    ```powershell
    frame-compare run --dry-run
    frame-compare run
    ```

=== "Docker"

    ```bash
    docker compose run --rm frame-compare-run run --root /workspace --dry-run
    docker compose run --rm frame-compare-run run --root /workspace
    ```

=== "Native with uv"

    ```bash
    uv run --no-sync frame-compare run --root . --dry-run
    uv run --no-sync frame-compare run --root .
    ```

=== "Native with pip"

    ```bash
    frame-compare run --root . --dry-run
    frame-compare run --root .
    ```

Revisit `wizard` when the input directory, generated-data location, reference, or
frame-selection goal changes. After a successful save, or a no-op, it prints suggested
`doctor`/`run --dry-run`/`run` commands for your resolved workspace and config file.
Run them through the same route that ran the wizard. In Docker, the printed paths are
container paths such as `/workspace`; use the Docker commands above from the host.

Revisit `doctor` after any change to the runtime: an application upgrade, a new
machine, a different Docker image, a graphics-driver or Vulkan update, or a
VSView/plugin change.

## Find the result

Frame Compare reserves a run folder beneath `paths.generated_dir` for each executed run:

```text
generated/
├── cache/
├── clip_probe.toml
└── <run-name>/
    ├── report.html
    ├── screenshots/
    ├── alignment_diagnostics/
    ├── generated/
    ├── run_info.toml
    └── run_result.toml
```

See [Output layout](../reference/output-layout.md) for what each item holds.
`alignment_diagnostics/` exists only when audio alignment ran.

Open `report.html` while keeping the run folder together. Relative screenshot links
continue to work when the entire folder is moved or archived. Docker users should use
the host-open helper or translate `/workspace/generated/` to the host `generated/`
directory.

## Check the result before you share it

Before sharing a result:

1. Review several frames in **Slider** and **Diff** views.
2. Check source labels, resolution, HDR/SDR identity, and frame numbers.
3. Verify alignment around dialogue, cuts, and motion.
4. Look for crop, aspect-ratio, or tonemapping differences that could make the
   comparison misleading.
5. Keep the result local until it looks correct.

## Next steps

<div class="fc-cards" markdown>

- [Reports and overlays](../guides/reports-and-overlays.md)

    Use the report views to check the result.

- [Audio alignment](../guides/audio-alignment.md)

    Read what the alignment result means.

- [Troubleshooting](../guides/troubleshooting.md)

    Problems listed by stage.

</div>
