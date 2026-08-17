<div class="fc-hero" markdown>

<p class="fc-kicker">Deterministic video comparison</p>

# Compare sources, not guesswork

Frame Compare selects representative frames, aligns source timing, renders HDR-aware
screenshots, and produces a static review report for local encodes, remasters, and
archival quality-control workflows.

<div class="fc-actions" markdown>

[Choose an installation](getting-started/index.md){ .md-button .md-button--primary }
[Run a first comparison](guides/first-comparison.md){ .md-button }
[Explore the report viewer](guides/reports-and-overlays.md){ .md-button }

</div>

</div>

<figure class="fc-doc-figure">
  <img src="images/report-viewer-overview.webp" alt="Frame Compare offline report displaying three synthetic video sources in slider mode with filmstrip, source labels, frame metadata, and primary controls visible.">
  <figcaption>The report viewer exposes the current frame, source pair, filmstrip, and primary review controls without requiring a server.</figcaption>
</figure>

## Start with the route that fits your system

<div class="fc-card-grid" markdown>

<div class="fc-card" markdown>

### Windows portable

The complete Windows 10/11 x64 distribution. It includes the supported Python and
media runtime, VSPreview, installer, updater, and rollback tooling.

[Install on Windows](windows-portable.md)

</div>

<div class="fc-card" markdown>

### Docker

The recommended reproducible, headless route for macOS and Linux. It isolates the
media toolchain and writes reports and cache data to explicit host mounts.

[Start with Docker](getting-started/docker.md)

</div>

<div class="fc-card" markdown>

### Native source

For advanced users who already manage FFmpeg, VapourSynth, source plugins, and a
compatible Vulkan implementation on the host.

[Install from source](getting-started/native.md)

</div>

</div>

[Compare route capabilities and support posture](getting-started/route-comparison.md)

## What a comparison includes

- Reproducible user, random, dark, bright, and motion frame selection.
- Shared-window and active-picture-aware analysis across the selected sources.
- Automatic audio alignment with optional prior-offset reuse and VSPreview review.
- HDR-to-SDR tonemapping when required, plus minimal, standard, or diagnostic overlays.
- A self-contained browsing experience with slider, overlay, diff, blink, grid,
  filmstrip, zoom, inspection, and review tools.
- Optional slow.pics publication and Discord-compatible webhook notification after a
  local result has been reviewed.

## Follow a workflow

<div class="fc-card-grid" markdown>

<div class="fc-card" markdown>

### Understand the pipeline

See where probing, frame selection, alignment, rendering, caches, and optional network
outputs fit together.

[How Frame Compare works](guides/how-it-works.md)

</div>

<div class="fc-card" markdown>

### Control the comparison

Choose the reference, label sources, handle trims or FPS metadata, and configure frame
selection without reading the full behavioral contract.

[Sources and labels](guides/sources-and-labels.md) ·
[Frame selection](guides/analysis-modes.md)

</div>

<div class="fc-card" markdown>

### Review the result

Learn the viewer modes, keyboard-oriented review workflow, metadata inspector, and
portable report layout.

[Reports and overlays](guides/reports-and-overlays.md)

</div>

</div>

## Find an answer

- Use [Configuration Recipes](guides/configuration-recipes.md) for common outcomes.
- Start with [Troubleshooting](guides/troubleshooting.md) when a run fails.
- Use [Commands and Configuration](reference/commands-and-configuration.md) for
  command discovery and reference links.
- Consult the [CLI Behavioral Contract](current-cli-contract.md) only when exact
  precedence, persistence, JSON, stream, or exit behavior matters.
- Contributors and maintainers should begin with
  [Contributing](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md)
  and the [Engineering Runbook](ENGINEERING_RUNBOOK.md).
