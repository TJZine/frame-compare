# Frame Compare

> Reproducible video comparisons with deterministic frame selection, audio alignment,
> HDR-aware rendering, and offline review reports.

[![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-3776AB?logo=python&logoColor=white)](#installation)
[![License](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)
[![CI](https://github.com/TJZine/frame-compare/actions/workflows/ci.yml/badge.svg)](https://github.com/TJZine/frame-compare/actions/workflows/ci.yml)

**[Windows portable](docs/windows-portable.md)** ·
**[Docker](docs/getting-started/docker.md)** ·
**[Native source](docs/getting-started/native.md)** ·
**[Documentation](https://tjzine.github.io/frame-compare/)**

<figure class="fc-doc-figure">
  <a href="docs/guides/reports-and-overlays.md">
    <img src="docs/images/report-viewer-overview.webp" alt="Frame Compare offline report displaying three synthetic video sources in slider mode with filmstrip, source labels, frame metadata, and primary controls visible.">
  </a>
  <figcaption>The offline report keeps three source views, frame context, and review controls together for repeatable local inspection.</figcaption>
</figure>

Frame Compare turns two or more local video sources into a repeatable comparison:
it discovers and validates the clips, selects representative frames, aligns differing
edits when possible, renders labeled screenshots, and builds a static HTML report that
works without a server. Publishing to slow.pics and webhook notification are explicit
opt-ins.

## Why Frame Compare

- **Repeatable frame selection** — combine exact user frames with deterministic random,
  dark, bright, and motion selections.
- **Alignment-aware comparisons** — use automatic audio correlation, prior accepted
  offsets, and optional VSPreview verification.
- **HDR-aware rendering** — tonemap HDR sources through VapourSynth and vs-placebo when
  required, with configurable overlays and diagnostics.
- **A serious offline viewer** — inspect slider, overlay, diff, blink, and grid views;
  navigate by frame or category; zoom, pan, inspect metadata, and keep browser-local
  review notes.
- **Reproducible delivery** — use the complete Windows portable bundle or the managed
  Docker runtime instead of assembling the media stack by hand.

## Installation

| Route | Best for | Start here |
| --- | --- | --- |
| Windows portable | Windows 10/11 x64 users who want the complete supported runtime, VSPreview, installer, and updater | [Install the Windows portable bundle](docs/windows-portable.md) |
| Docker | Reproducible headless use on macOS or Linux | [Run with Docker](docs/getting-started/docker.md) |
| Native source | Advanced users who already manage FFmpeg, VapourSynth, source plugins, and Vulkan | [Install from source](docs/getting-started/native.md) |

Not sure which route fits? Use the
[installation chooser](docs/getting-started/index.md) or the
[detailed route comparison](docs/getting-started/route-comparison.md).

## First comparison

Every route follows the same safe sequence:

1. Put at least two supported clips in the selected input directory.
2. Run `frame-compare wizard` through that route.
3. Run `frame-compare doctor` and resolve relevant failures.
4. Preview the effective inputs and output intent with `run --dry-run`.
5. Run the comparison and open the generated `report.html`.

The exact commands and expected output are in
[Your First Comparison](docs/guides/first-comparison.md).

## Documentation map

- [How the pipeline works](docs/guides/how-it-works.md)
- [Sources, references, and labels](docs/guides/sources-and-labels.md)
- [Frame selection and analysis modes](docs/guides/analysis-modes.md)
- [Audio alignment and VSPreview](docs/guides/audio-alignment.md)
- [HDR and tonemapping](docs/guides/hdr-tonemapping.md)
- [Reports and overlays](docs/guides/reports-and-overlays.md)
- [Configuration recipes](docs/guides/configuration-recipes.md)
- [Troubleshooting](docs/guides/troubleshooting.md)
- [Commands and configuration reference](docs/reference/commands-and-configuration.md)

## Project status

Frame Compare is an alpha project. The CLI, documented configuration behavior, and
published release artifacts are the supported surfaces. Importable modules are
conveniences unless the project explicitly documents a compatibility promise.

The verification policy and current architecture are maintained in the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) and
[Current Architecture](docs/current-architecture.md).

## License

Frame Compare is licensed under the
[GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`).

```text
Copyright 2025-2026 Tristan <zine96@proton.me>
```
