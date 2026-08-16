# Configuration recipes

These recipes show common outcomes without requiring a full read of the behavioral
contract. Treat them as focused starting points: merge only the relevant tables into
your existing `config.toml`, then run a dry run.

```bash
frame-compare run --dry-run
```

## Compare three named sources

**Goal:** choose an explicit reference and keep short, readable labels in the report.

```toml
[sources]
reference = "Reference.mkv"
analysis_source = "reference"
label_mode = "stem"

[sources.overrides."Reference.mkv"]
label = "Reference"

[sources.overrides."Encode-A.mkv"]
label = "Encode A"

[sources.overrides."Encode-B.mkv"]
label = "Encode B"
```

**What changes:** presentation labels and reference ownership.

**What does not change:** physical filenames, source fingerprints, alignment identity,
or source order after the chosen reference.

## Use exact frames only

**Goal:** reproduce a known comparison without metric analysis.

```toml
[analysis]
user_frames = [120, 1200, 2400]
random_frame_count = 0
dark_frame_count = 0
bright_frame_count = 0
motion_frame_count = 0
```

**What changes:** only the listed reference-domain frames are requested.

**What does not change:** alignment can still reduce the final shared frame domain.

## Mix broad coverage with visual extremes

**Goal:** combine reproducible random frames with dark, bright, and motion examples.

```toml
[analysis]
performance_mode = "quality"
random_seed = 42
random_frame_count = 8
dark_frame_count = 2
bright_frame_count = 2
motion_frame_count = 3
```

**Common failure:** short media plus large lead/trail exclusions may not have enough
eligible frames. Reduce the counts or exclusions rather than assuming a retry can always
satisfy the request.

## Iterate faster on a long source

**Goal:** reduce metric runtime while keeping deterministic approximate automatic
selection.

```toml
[analysis]
performance_mode = "performance"
random_frame_count = 8
dark_frame_count = 2
bright_frame_count = 2
motion_frame_count = 2
```

**Tradeoff:** brief events can fall between sampled bursts. Switch back to `quality` for
a final publication-bound run.

## Ignore an intro and credits

**Goal:** keep the media renderable but prevent automatic selection from concentrating
on opening or closing material.

```toml
[analysis]
ignore_lead_seconds = 60.0
ignore_trail_seconds = 90.0
```

**What changes:** the selectable analysis/frame-plan window.

**What does not change:** source files and configured source trims.

## Apply known source trims

**Goal:** remove source-specific leader or repeated tail frames from the comparison
domain.

```toml
[sources.overrides."Encode-A.mkv"]
trim_start_frames = 24
trim_end_frames = 48
```

**Common failure:** excessive trims can leave insufficient shared overlap after
automatic alignment.

## Correct mislabeled FPS metadata

**Goal:** interpret one source at the known reference rate without resampling.

```toml
[sources.overrides."Encode-A.mkv"]
effective_fps = "24000/1001"
```

Or apply the reference timing to every comparison without an explicit override:

```toml
[sources]
match_fps = "assume_reference"
```

**Warning:** this is AssumeFPS-style timing interpretation. It does not convert genuinely
different frame cadence or repair variable timing.

## Set an explicit active picture

**Goal:** override incorrect automatic crop evidence.

```toml
[sources.overrides."Encode-A.mkv"]
active_rect = { x = 0, y = 138, width = 1920, height = 804 }
```

**Common failure:** the rectangle must fit inside the probed source dimensions. Invalid
values fail rather than falling back.

## Keep generated data outside the Windows bundle

**Goal:** preserve reports, history, screenshots, and reusable caches across bundle
replacement.

```toml
[paths]
generated_dir = "D:/FrameCompareData"
```

Use a normal user-writable directory. The Windows updater and uninstaller leave an
external generated-data root outside their replacement boundary.

## Create a single-file report

**Goal:** produce one HTML file when a complete folder is inconvenient.

```toml
[report]
embed_images = true
```

**Tradeoff:** the HTML becomes much larger. The normal relative-image run folder is
usually easier to inspect, archive, and regenerate.

## Use diagnostic screenshot overlays

**Goal:** bake additional source, HDR, range, and selection evidence into screenshots.

```toml
[screenshots]
overlay_mode = "diagnostic"
```

**What changes:** rendered image pixels and file size.

**What does not change:** browser viewer labels and controls remain a separate
presentation layer.

## Keep a run local

**Goal:** guarantee no slow.pics upload for one invocation.

```bash
frame-compare run --no-upload
```

For the authored default:

```toml
[slowpics]
auto_upload = false
```

## Confirm upload only after reviewing the report

**Goal:** render locally, inspect the report, then decide interactively whether to
publish.

```toml
[slowpics]
auto_upload = true
confirm_upload_after_report = true
visibility = "unlisted"
```

This requires an interactive report-enabled run. JSON, quiet, and non-interactive
execution cannot prompt.

## Validation checklist

After every recipe:

1. Run `frame-compare doctor` when runtime-dependent behavior changed.
2. Run `frame-compare run --dry-run`.
3. Confirm reference and comparison order.
4. Confirm generated-data location and publishing state.
5. Review the final report before sharing it.

For exact field types, precedence, persistence, and error behavior, use the
[CLI Behavioral Contract](../current-cli-contract.md).
