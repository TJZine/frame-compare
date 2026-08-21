# Sources, references, and labels

Frame Compare keeps source identity separate from presentation. Paths and fingerprints
control discovery, caches, and alignment, while resolved labels remain canonical for
overlays, reports, and artifact mappings. Live render progress and slow.pics columns
use release descriptors when parsing is informative; explicit labels remain exact.

## Choose the reference

The reference defines the frame-number domain used by user selections and the baseline
relationship used by alignment and report presentation.

```toml
[sources]
reference = "Reference.mkv"
```

When `reference` is omitted or set to `"auto"`, the first deterministically discovered
source remains the reference. A selector can match an input-directory-relative path,
filename, or stem. Selectors are case-sensitive, and ambiguous matches fail before
runtime work begins.

## Choose the analysis source

The clip used to compute luminance and motion metrics does not need to be the reference:

```toml
[sources]
analysis_source = "reference"
```

Supported patterns include:

- `"reference"` — analyze the selected reference;
- `"fastest"` — benchmark usable sources and analyze the fastest one;
- a source selector — analyze a specifically named source.

Changing the analysis source does not change reference order or display order. The
`fastest` policy is runtime-dependent and is therefore incompatible with
`run --from-cache-only`.

## Make labels readable

```toml
[sources]
label_mode = "parsed"
label_parser = "auto"
```

Label modes:

| Mode | Result |
| --- | --- |
| `stem` | Filename without extension |
| `filename` | Full filename including extension |
| `parsed` | Best-effort release-aware label assembled from parsed metadata |

Use an explicit per-source label when automatic parsing is not appropriate:

```toml
[sources.overrides."Encode-A.mkv"]
label = "Encode A — AV1"
```

Duplicate explicit labels fail. Derived collisions are qualified deterministically so
presentation remains unambiguous.

For live render progress, automatic labels become unique role-prefixed compact release
descriptors. For slow.pics, automatic labels become unique full release descriptors.
Neither presentation changes baked overlays, local screenshot names, report mappings,
or the slow.pics collection title.

## Apply trims without modifying media

```toml
[sources.overrides."Reference.mkv"]
trim_start_frames = 24
trim_end_frames = 48
```

Configured trims define the base renderable domain for that source. Audio-alignment
trims compose on top of them rather than replacing them.

Use trims for known leader, repeated frames, or source-specific tails. Use analysis
leading/trailing exclusions when the frames should remain renderable but should not be
considered for automatic selection.

## Correct timing metadata

```toml
[sources.overrides."Encode-A.mkv"]
effective_fps = "24000/1001"
```

`effective_fps` changes timing interpretation without resampling, interpolating,
dropping, or duplicating frames. It is appropriate only when the source timing metadata
is known to be wrong or when an AssumeFPS-style comparison is intentional.

For a consistent policy across sources:

```toml
[sources]
match_fps = "assume_reference"
```

Available policies are `disabled`, `assume_reference`, and `majority`. Explicit
per-source `effective_fps` values take precedence.

!!! warning "FPS matching is not conversion"
    These settings do not create new frames or make genuinely different timing
    structures equivalent. Inspect motion and cuts after applying them.

## Control the active picture

Automatic active-picture resolution is normally preferable because it keeps metric
analysis and rendering aligned with the visible image. Use an explicit rectangle only
when the automatic evidence is wrong or the desired comparison domain is known:

```toml
[sources.overrides."Encode-A.mkv"]
active_rect = { x = 0, y = 138, width = 1920, height = 804 }
```

The rectangle must fit inside the probed source dimensions. Invalid explicit values fail
instead of silently falling back.

The active-picture resolver uses this precedence:

1. explicit source configuration;
2. trusted static metadata;
3. dimension and aspect-ratio evidence;
4. optional content sampling when auto detection is enabled;
5. a full-frame fallback.

The resolved rectangle is included in analysis and cache identity because changing the
metric crop can change selected frames.

## Example: three sources with readable labels

```toml
[sources]
reference = "Reference.mkv"
analysis_source = "reference"
label_mode = "stem"
match_fps = "disabled"

[sources.overrides."Reference.mkv"]
label = "Reference"

[sources.overrides."Encode-A.mkv"]
label = "Encode A"

[sources.overrides."Encode-B.mkv"]
label = "Encode B"
```

Validate the result before rendering:

```bash
frame-compare run --dry-run
```

For exact selector precedence, path rules, collision behavior, and config-only fields,
see the [sources contract](../current-cli-contract.md#config-only-sources-surface).
