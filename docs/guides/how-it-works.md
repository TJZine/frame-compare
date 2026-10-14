---
description: The six stages of a Frame Compare run and what each stage decides.
---

# How Frame Compare works

Frame Compare runs a comparison in six stages. Each stage makes one decision,
such as which frames to render or how far apart two sources are, and passes the
result to the next stage.

<div class="fc-pipeline" markdown>

1. [Discovery and validation](#1-discovery-and-validation)
2. [Probing and selectable-window preparation](#2-probing-and-selectable-window-preparation)
3. [Frame planning and analysis](#3-frame-planning-and-analysis)
4. [Alignment](#4-alignment)
5. [Rendering and tonemapping](#5-rendering-and-tonemapping)
6. [Report and optional publication](#6-report-and-optional-publication)

</div>

The sections below use the same numbers.

## 1. Discovery and validation

The CLI resolves the workspace and selected configuration, then discovers supported
media. It chooses the reference and comparison order and applies source overrides.
It checks where it can write before expensive runtime work begins.

Use a dry run to inspect the sources and settings before probing and rendering the
full comparison.

## 2. Probing and selectable-window preparation

Frame Compare loads source properties through the configured media runtime and creates
the initial selectable window from source lengths, explicit trims, effective FPS policy,
and leading or trailing exclusions. Frame Compare later maps that plan into the aligned
overlap and may reduce the frames every source can represent.

Frame Compare resolves the active picture before metric analysis. It checks explicit
rectangles first, then trusted static evidence and dimension/aspect-ratio evidence.
Optional content sampling and a full-frame fallback follow according to configuration.

## 3. Frame planning and analysis

Frame Compare chooses exact user frames and deterministic random frames without dense
luminance or motion metrics. It uses those metrics for dark, bright, and motion requests.

- `quality` analyzes every eligible frame in the prepared metric window.
- `performance` analyzes a deterministic sampled subset and may choose different
  automatic frames.

Frame Compare keys metric caches by the source and runtime facts that can change the
metric arrays. It applies selection counts and quantile choices after metrics are
available.

## 4. Alignment

Frame Compare maps the frame plan into the aligned comparison domain. It uses audio
correlation to propose an offset.

Frame Compare applies a fresh automatic offset to the trims only when decoded video
confirms it and every other authority check passes. It requires a passed audio authority
recount, resolved competing runs and credible chunk disagreements, and no confirmed
alternative offset.
A candidate remains `NOT APPLIED` if any authority check fails, even when video
confirms it; the current alignment stays.

Frame Compare reuses an offset accepted in an earlier run while the sources and settings
still match. With VSView review enabled, the panel opens after alignment unless a
complete set of previously confirmed offsets was reused. The panel works only from the
same environment as Frame Compare.

Silence, replaced music, substantially different edits, or unrelated audio streams can
produce weak or misleading matches. Review motion, cuts, and dialogue in the final report.

For details, see [Audio alignment](audio-alignment.md) and
[VSView alignment review](vsview-review.md).

## 5. Rendering and tonemapping

Frame Compare maps each aligned frame back to the corresponding source frame. It
renders SDR sources without HDR tonemapping. For HDR sources that need SDR output, it
uses the configured VapourSynth and vs-placebo tonemapping path before encoding
screenshots and composing overlays.

The report viewer adds interactive labels and controls in the browser. Baked screenshot
overlays are part of the image itself and remain visible outside the report.

## 6. Report and optional publication

Frame Compare writes the canonical result as a static `report.html` in the reserved run
folder beside its screenshots and run records. It works without a server and can be
moved as a complete folder.

You can turn on slow.pics upload and webhook notification as separate actions after
rendering. Both are optional for a local comparison.

## Owned persistent artifacts

| Artifact | Purpose |
| --- | --- |
| Analysis cache | Reuse luminance and motion metrics when the relevant source, window, active picture, algorithm, and runtime identity still match |
| Probe cache | Reuse validated source properties for compatible sources and runtime identity |
| Alignment reuse cache | Reuse accepted computed or confirmed offsets while sources and settings match |
| `alignment_diagnostics/` | Record each comparison's alignment evidence for review; never changes trims |
| Frame Compare-owned `.lwi` index | Isolate L-SMASH-Works indexes by selected runtime lineage instead of trusting ambiguous legacy sidecars |
| `run_info.toml` | Record the reserved run identity and runtime provenance |
| `run_result.toml` | Record the completed or failed lifecycle result used by history commands |
| `report.html` and `screenshots/` | Preserve the reviewable comparison |
| Native alignment result sidecar | Store the saved panel decision beside the generated VSView session; see [VSView alignment review](vsview-review.md) |

For implementation ownership and exact phase boundaries, see
[Current architecture](../current-architecture.md). For exact command, configuration,
and persistence behavior, see the [CLI behavioral contract](../current-cli-contract.md).
