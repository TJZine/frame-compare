# Frame selection and analysis modes

Frame Compare can combine exact user-selected frames with deterministic random and
metric-selected dark, bright, or motion frames. The right configuration depends on
whether you want reproducible coverage, specific moments, or the strongest automatic
search for visually distinct frames.

## Selection types

| Selection | Requires metric analysis | Best use |
| --- | --- | --- |
| User frames | No | Exact moments already known to matter |
| Random frames | No | Broad, reproducible coverage without metric cost |
| Dark frames | Yes | Shadow detail, black levels, and low-light compression behavior |
| Bright frames | Yes | Highlights, clipping, grain, and tone-mapping behavior |
| Motion frames | Yes | High frame-to-frame change such as action, camera movement, flashes, or cuts; useful for locating potentially stressful scenes |

Frame numbers are interpreted in the selected reference source domain before alignment.
The final render plan is normalized to the overlap every aligned source can represent.
A configured user frame that cannot survive trims or alignment is reported rather than
silently replaced.

Automatic selections divide the eligible timeline into deterministic temporal regions.
Random selection chooses a seeded candidate from each region, while dark, bright, and
motion selection chooses that region's strongest available metric candidate before
globally backfilling any missing choices. Frame Compare prefers five-frame separation
from all earlier evidence, but relaxes that spacing deterministically when a short clip
still has enough distinct frames to satisfy the request. User frames remain exact and
take precedence over every automatic category.

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

Both modes use full-resolution luma PlaneStats on the prepared active picture, respect
source trims and the shared leading/trailing exclusion window, and leave user and random
frames eligible across the full selectable window.

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

The exact defaults and accepted ranges are documented in the
[analysis configuration contract](../current-cli-contract.md#config-only-analysis-surface).

## Excluding intros and credits

Leading and trailing exclusions reduce the metric and selection window without changing
the source files:

```toml
[analysis]
ignore_lead_seconds = 60.0
ignore_trail_seconds = 90.0
```

Use conservative values. Large exclusions on short clips can leave too few frames for
the requested plan.

In an interactive run, Frame Compare can offer a one-time full-window retry when the
configured exclusions are the reason the frame request cannot be satisfied. Accepting
the retry changes only the effective in-memory run configuration, recomputes
window-dependent active-picture and cache-domain evidence, emits a warning, and never
rewrites the authored TOML. JSON, quiet, cache-only, and skipped-analysis paths fail
closed instead of prompting.

## Exact user frames

```toml
[analysis]
user_frames = [120, 1200, 2400]
random_frame_count = 0
dark_frame_count = 0
bright_frame_count = 0
motion_frame_count = 0
```

A user-only plan skips metric analysis entirely. This is useful for reproducing a known
comparison or investigating a specific scene without creating or loading an analysis
metrics cache.

## Reproducibility boundaries

The same inputs and effective configuration produce the same deterministic selection,
but the following changes can legitimately change the result:

- source path, byte size, modification time, trims, or effective FPS;
- selected reference or analysis source;
- active-picture evidence or selection window;
- performance mode or metric algorithm identity;
- relevant managed media-runtime components;
- alignment results that reduce the shared renderable overlap.

Automatic frame choices may also differ from releases that predate temporal
stratification, even when the same inputs and configuration are reused.

Frame Compare does not hash complete media contents for cache freshness. If media is
replaced while preserving its path, byte size, and modification time, advance the
modification time or remove the smallest relevant cache entry before reuse.

A cache hit means the cached metric request still matches; it does not freeze later
selection or alignment decisions.

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

For measured hardware-dependent evidence, see
[Analysis Performance Validation](../analysis-performance-validation.md) and
[Benchmark History](../analysis-benchmark-history.md).
