---
description: Choose frames by number, at random, or by brightness and motion, and make the selection repeatable.
---

# Frame selection and analysis

Frame Compare can combine exact user frames with deterministic random and
metric-selected dark, bright, or motion frames. The right configuration depends on
whether you want reproducible coverage, specific moments, or the strongest automatic
search for visually distinct frames.

## Selection types

| Selection | Requires metric analysis | Best use |
| --- | --- | --- |
| User frames | No | Exact moments already known to matter |
| Random frames | No | Broad, reproducible coverage without metric cost |
| Dark frames | Yes | Shadow detail, black levels, and low-light compression behavior |
| Bright frames | Yes | Highlights, clipping, grain, and tonemapping behavior |
| Motion frames | Yes | High frame-to-frame change such as action, camera movement, flashes, or cuts; useful for locating potentially stressful scenes |

Frame Compare interprets frame numbers in the selected reference source before
alignment. It limits the final render plan to the overlap every aligned source can
represent. It reports a configured user frame that cannot survive trims or alignment
and leaves it unreplaced.

Frame Compare divides the eligible timeline into deterministic temporal regions.
For random selection, it chooses a seeded candidate from each region. For dark, bright,
and motion selection, it chooses that region's strongest available metric candidate,
then backfills any missing choices across the timeline.

Frame Compare prefers a half-second separation from all earlier evidence, rounded up to
`ceil(selection-domain effective FPS / 2)` frames using the effective reference FPS.
If the preferred gap cannot satisfy a category, the selector relaxes it by one frame
at a time down to one-frame uniqueness.

User frames remain exact and take precedence over every automatic category.

## Quality versus performance analysis

Choose the metric strategy in `config.toml`:

```toml
[analysis]
performance_mode = "quality"
```

| Mode | Metric coverage | Use it when |
| --- | --- | --- |
| `quality` (default) | Every eligible frame | You want the highest-confidence automatic dark, bright, and motion selection |
| `performance` | A deterministic sample of `ceil(window_length / 4)` frames, distributed across as many as eight contiguous bursts | Faster analysis matters and approximate automatic selections are acceptable |

Frame Compare uses full-resolution luma PlaneStats on the prepared active picture in
both modes. It respects source trims and the shared leading/trailing exclusion window.
User and random frames remain eligible across the full selectable window.

!!! warning "Performance mode is approximate"
    It samples about 25% of the window; when the window length is not a multiple of
    four, rounding up can exceed exactly 25%. It can miss brief events between sampled
    bursts and is not expected to match `quality` frame-for-frame. It remains
    deterministic for the same inputs, runtime, configuration, and selectable window.

## A practical starting point

Use a mixed frame plan so the report contains both broad coverage and targeted extremes:

```toml
[analysis]
performance_mode = "quality"
random_frame_count = 8
dark_frame_count = 2
bright_frame_count = 2
motion_frame_count = 3
random_seed = 42
```

Short media with large lead or trail exclusions may not have enough eligible frames;
reduce the counts or the exclusions.

The exact defaults and accepted ranges are documented in the
[analysis configuration contract](../current-cli-contract.md#config-only-analysis-surface).

## Excluding intros and credits

Set leading and trailing exclusions to reduce the metric and selection window without
changing the source files:

```toml
[analysis]
ignore_lead_seconds = 60.0
ignore_trail_seconds = 90.0
```

Use conservative values. Large exclusions on short sources can leave too few frames for
the requested plan.

In an interactive run, Frame Compare can offer a one-time full-window retry when the
configured exclusions are the reason the frame request cannot be satisfied. Accepting
the retry changes only the effective in-memory run configuration.

Frame Compare recomputes window-dependent active-picture and cache-domain evidence and
emits a warning. It leaves the config file unchanged.
JSON, quiet, cache-only, and skipped-analysis paths fail closed instead of prompting.

## Exact user frames

```toml
[analysis]
user_frames = [120, 1200, 2400]
random_frame_count = 0
dark_frame_count = 0
bright_frame_count = 0
motion_frame_count = 0
```

Frame Compare skips metric analysis entirely for a user-only plan. This is useful for
reproducing a known comparison or investigating a specific scene without creating or
loading an analysis metrics cache.

## Reproducibility boundaries

Frame Compare repeats the same deterministic selection for the same inputs and effective
configuration. The following changes can change the result:

- source path, byte size, modification time, trims, or effective FPS;
- selected reference or analysis source;
- active-picture evidence or selection window;
- performance mode or metric algorithm identity;
- relevant managed media-runtime components;
- alignment results that reduce the shared renderable overlap.

Frame Compare does not hash complete media contents for cache freshness. If media is
replaced while preserving its path, byte size, and modification time, advance the
modification time or remove the smallest relevant cache entry before reuse.

A cache hit means the cached metric request still matches. Frame Compare still makes
selection and alignment decisions afterward.

## Choosing between modes

Use `quality` when:

- the comparison is final or publication-bound;
- short flashes, cuts, or motion peaks matter;
- runtime is acceptable or metrics can be reused;
- you want the strongest automatic selection evidence.

Use `performance` when:

- you are iterating on configuration;
- the source is very long;
- random and user frames already provide broad coverage;
- approximate dark, bright, and motion examples are sufficient.

A faster iteration setup for a long source:

```toml
[analysis]
performance_mode = "performance"
random_frame_count = 8
dark_frame_count = 2
bright_frame_count = 2
motion_frame_count = 2
```

Brief events can fall between sampled bursts. Switch back to `quality` for a final
publication-bound run.

For measured hardware-dependent evidence, see
[Analysis performance validation](../analysis-performance-validation.md) and
[Analysis benchmark history](../analysis-benchmark-history.md).
