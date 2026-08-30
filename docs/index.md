---
hide:
  - toc
---

<div class="fc-home" markdown>

<section class="fc-hero" markdown>

<div class="fc-hero-copy" markdown>

<p class="fc-kicker">Deterministic video comparison</p>

<h1 id="compare-sources-not-guesswork">
  <span>Compare</span>
  <span>sources, not</span>
  <span>guesswork</span>
</h1>

Select useful frames, align source timing, render HDR-aware screenshots, and review
every difference in a portable report.

<div class="fc-actions" markdown>

[Choose an installation](getting-started/index.md){ .md-button .md-button--primary }
[View the report](guides/reports-and-overlays.md){ .fc-text-link }

</div>

</div>

<figure class="fc-hero-visual">
  <img
    src="images/report-viewer-overview.webp"
    alt="Frame Compare report viewer showing a side-by-side slider comparison"
    width="1683"
    height="1080"
    loading="eager"
  >
  <figcaption>One frame. Two sources. Every difference visible.</figcaption>
</figure>

</section>

## Start with the route that fits your system

<p class="fc-section-intro">Choose the supported package for your platform or bring your own media toolchain.</p>

<div class="fc-card-grid fc-route-grid" markdown>

<div class="fc-card" markdown>

<p class="fc-card-label">Windows 10/11 · Complete package</p>

### Windows portable

The supported Python and media runtime, VSPreview, installer, updater, and rollback
tooling in one distribution.

[Install on Windows](windows-portable.md)

</div>

<div class="fc-card" markdown>

<p class="fc-card-label">macOS + Linux · Reproducible</p>

### Docker

The recommended headless route, with an isolated media toolchain and explicit host
mounts for reports and cache data.

[Start with Docker](getting-started/docker.md)

</div>

<div class="fc-card" markdown>

<p class="fc-card-label">Advanced · Bring your own runtime</p>

### Native source

For users who already manage FFmpeg, VapourSynth, source plugins, and a compatible
Vulkan implementation.

[Install from source](getting-started/native.md)

</div>

</div>

[Compare route capabilities and support posture](getting-started/route-comparison.md){ .fc-inline-cta }

## What a comparison gives you

<div class="fc-capability-grid" markdown>

<div markdown>

### Frames worth inspecting

Reproducible user, random, dark, bright, and motion selection focused on shared
picture content.

</div>

<div markdown>

### Sources that line up

Shared-window analysis, automatic audio alignment, trim handling, and optional
VSPreview review.

</div>

<div markdown>

### Evidence you can share

HDR-aware screenshots and a portable offline report with slider, diff, blink, grid,
filmstrip, zoom, and inspection tools.

</div>

</div>

## Follow the workflow

<ol class="fc-steps">
  <li>
    <span class="fc-step-number">01</span>
    <h3>Understand the pipeline</h3>
    <p>See how probing, selection, alignment, rendering, caches, and optional network outputs fit together.</p>
    <a href="guides/how-it-works/">How Frame Compare works</a>
  </li>
  <li>
    <span class="fc-step-number">02</span>
    <h3>Control the comparison</h3>
    <p>Choose the reference, label sources, handle trims or FPS metadata, and configure frame selection.</p>
    <a href="guides/sources-and-labels/">Sources and labels</a>
    <span aria-hidden="true"> · </span>
    <a href="guides/analysis-modes/">Frame selection</a>
  </li>
  <li>
    <span class="fc-step-number">03</span>
    <h3>Review the result</h3>
    <p>Learn the viewer modes, keyboard-oriented workflow, metadata inspector, and portable report layout.</p>
    <a href="guides/reports-and-overlays/">Reports and overlays</a>
  </li>
</ol>

## Find an answer

<div class="fc-answer-links" markdown>

- [Configuration Recipes](guides/configuration-recipes.md) for common outcomes.
- [Troubleshooting](guides/troubleshooting.md) when a run fails.
- [Commands and Configuration](reference/commands-and-configuration.md) for command discovery.
- [CLI Behavioral Contract](current-cli-contract.md) for exact precedence, persistence, JSON, stream, and exit behavior.
- [Contributing](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md) and the [Engineering Runbook](ENGINEERING_RUNBOOK.md) for project work.

</div>

</div>
