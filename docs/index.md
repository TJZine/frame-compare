---
hide:
  - toc
---

<div class="fc-home" markdown>

<section class="fc-stage" markdown>

<div class="fc-stage-copy" markdown>

<p class="fc-kicker">Deterministic video comparison</p>

<h1 id="compare-sources-not-guesswork">Compare sources,<br><span class="fc-split">not guesswork</span></h1>

Select useful frames, align source timing, render HDR-aware screenshots, and review
every difference in a report that opens without a server.

<div class="fc-actions" markdown>

[Choose an installation](getting-started/index.md){ .md-button .md-button--primary }
[Run your first comparison](guides/first-comparison.md){ .fc-text-link }

</div>

</div>

<figure class="fc-stage-shot">
  <img src="images/report-overview.webp" alt="Frame Compare report in Slider mode comparing the EBU DVB PQ10 reference with the HLG10 comparison at frame 1000." width="1600" height="1000" loading="eager">
  <figcaption><span class="fc-chip">Slider</span> EBU DVB PQ10 reference and HLG10 comparison, frame 1000.</figcaption>
</figure>

</section>

<ol class="fc-strip" aria-label="Report viewer views">
  <li><img src="images/report-overview.webp" alt="" width="1600" height="1000" loading="lazy"><span>Slider</span></li>
  <li><img src="images/report-grid.webp" alt="" width="1600" height="1000" loading="lazy"><span>Grid</span></li>
  <li><img src="images/report-inspector.webp" alt="" width="1600" height="1000" loading="lazy"><span>Inspector</span></li>
  <li><img src="images/report-lens.webp" alt="" width="1600" height="1000" loading="lazy"><span>Lens</span></li>
</ol>

<p class="fc-credit">Footage: EBU/DVB HEVC test content © EBU, shot by Frans de Jong (EBU), PQ10 conversion by Andrew Cotton (BBC), licensed under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Source: <a href="https://dvb.org/specifications/verification-validation/hevc-test-content/">DVB HEVC test content</a>.</p>

## Pick the route that owns your runtime

<div class="fc-routes" markdown>

<div class="fc-route" markdown>

<p class="fc-route-tag">Windows 10/11 x64</p>

### [Windows portable](windows-portable.md)

Complete runtime, VSView alignment panel, installer, and signed code-only updates.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">macOS · Linux</p>

### [Docker](getting-started/docker.md)

Headless managed runtime with software-Vulkan HDR. Reports stay on the host.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">Advanced</p>

### [Native source](getting-started/native.md)

Bring your own FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo, and Vulkan.

</div>

</div>

## From sources to a report in four commands

<div class="fc-flow" markdown>

<div markdown>

<span class="fc-step">01</span>

### Configure

`frame-compare wizard` sets the input folder, reference, and frame goal.

</div>

<div markdown>

<span class="fc-step">02</span>

### Diagnose

`frame-compare doctor` checks the media runtime you will render with.

</div>

<div markdown>

<span class="fc-step">03</span>

### Preview

`frame-compare run --dry-run` shows sources, frames, and outputs without side effects.

</div>

<div markdown>

<span class="fc-step">04</span>

### Compare

`frame-compare run` aligns, renders, and writes `report.html`.

</div>

</div>

Docker and `uv` add a command prefix; [Your first comparison](guides/first-comparison.md)
shows every route.

## Find an answer

<div class="fc-answer-links" markdown>

- [Configuration](reference/configuration.md) — every key, type, and default.
- [Troubleshooting](guides/troubleshooting.md) — symptoms by pipeline stage.
- [Audio alignment](guides/audio-alignment.md) — what `APPLIED` and `NOT APPLIED` mean.
- [CLI behavioral contract](current-cli-contract.md) — exact streams, JSON, and exit codes.

</div>

</div>
