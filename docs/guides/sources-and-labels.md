---
description: Choose the reference, the analysis source, labels, trims, timing, and the active picture for each source.
---

# Sources, references, and labels

Frame Compare identifies each source by its path. This guide covers which source is
the reference, how labels are built, and how to correct a source's trims, timing, and
picture area.

## Choose the reference

Frame Compare uses the reference's frame numbers for user frames. It also uses the
reference as the baseline for alignment and report presentation.

```toml
[sources]
reference = "Reference.mkv"
```

When `reference` is omitted or set to `"auto"`, the first deterministically discovered
source remains the reference. A selector can match an input-directory-relative path,
filename, or stem. Selectors are case-sensitive, and ambiguous matches fail before
runtime work begins.

## Choose the analysis source

You can choose a source other than the reference to compute luminance and motion metrics:

```toml
[sources]
analysis_source = "reference"
```

Supported patterns include:

- `"reference"`: analyze the selected reference;
- `"fastest"`: benchmark usable sources and analyze the fastest one;
- a source selector: analyze a specifically named source.

Changing the analysis source does not change reference order or display order. A
random/user-only plan that does not require metrics remains valid in a dry run with
`analysis_source = "fastest"` and `run --from-cache-only`; the `fastest` policy is
runtime-dependent and is incompatible with `run --from-cache-only` when metrics are
required.

## Make labels readable

Paths and fingerprints control discovery, caches, and alignment, while resolved labels
remain canonical for overlays, reports, and artifact mappings. Live render progress and
slow.pics columns use release descriptors when parsing is informative; explicit labels
remain exact.

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

Frame Compare rejects duplicate explicit labels. It qualifies derived collisions
deterministically so presentation remains unambiguous.

Frame Compare identifies streaming services from release filename tokens using the
TRaSH Guides *Streaming Services General* and *Streaming Services Anime* sets, with
guessit's streaming-service detection as a fallback. Apple TV+ displays as `ATVP`,
HBO Max displays as `HMAX`, and `MAX` alone stays `MAX`.

The filename tokens `CC`, `PLAY`, `HBO`, `HMAX`, `iT`, `MAX`, `SHO`, and `STAN` only match
directly when the next token is `WEB`, `WEBDL`, or `WEBRIP`. Without that token, the
service comes from guessit when it recognizes the name, so `iT` or `MAX` can still resolve,
while `IT` alone yields no service.

For live render progress, Frame Compare turns automatic labels into unique role-prefixed
compact release descriptors. For slow.pics, it turns them into unique full release
descriptors.

Terminal surfaces (the Sources length-difference lines and the Align summary) use
short source names: a source's release group when no other source shares it
(case-insensitive), otherwise its compact release descriptor, or its label when
neither is available. Explicit labels stay exact, and Frame Compare qualifies remaining
collisions deterministically.

The report derives collision-safe control and compact labels from the
prepared release identity while retaining the canonical label for keys and mappings.
The report **Clips** inspector keeps the exact filename available, and an explicit source
label remains the primary report presentation name.

None of these presentation choices changes baked overlays, local screenshot names,
report mappings, or the slow.pics collection title.

## Apply trims without modifying media

```toml
[sources.overrides."Reference.mkv"]
trim_start_frames = 24
trim_end_frames = 48
```

Frame Compare uses configured trims to define which frames it can render for that
source. It adds audio-alignment trims on top of them.

Use trims for known leader, repeated frames, or source-specific tails. Use analysis
leading/trailing exclusions when the frames should remain renderable but should not be
considered for automatic selection.

## Correct timing metadata

```toml
[sources.overrides."Encode-A.mkv"]
effective_fps = "24000/1001"
```

Frame Compare uses `effective_fps` to interpret timing without resampling, interpolating,
dropping, or duplicating frames. Use it only when the source timing metadata
is known to be wrong or when an AssumeFPS-style comparison is intentional.

For a consistent policy across sources:

```toml
[sources]
match_fps = "assume_reference"
```

Available policies are `disabled`, `assume_reference`, and `majority`. Explicit
per-source `effective_fps` values take precedence.

!!! warning "FPS matching is not conversion"
    These settings do not create new frames or make different timing
    structures equivalent. Inspect motion and cuts after applying them.

## Control the active picture

Let Frame Compare resolve the active picture to keep metric analysis and rendering
aligned with the visible image. Use an explicit rectangle only when the automatic
evidence is wrong or you know which image area to compare:

```toml
[sources.overrides."Encode-A.mkv"]
active_rect = { x = 0, y = 138, width = 1920, height = 804 }
```

The rectangle must fit inside the probed source dimensions. Frame Compare rejects
invalid explicit values without falling back.

The active-picture resolver uses this precedence:

1. explicit source configuration;
2. trusted static metadata;
3. dimension and aspect-ratio evidence;
4. optional content sampling when auto detection is enabled;
5. a full-frame fallback.

Frame Compare includes the resolved rectangle in analysis and cache identity because
changing the metric crop can change selected frames.

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
