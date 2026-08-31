# Choose an installation

Frame Compare has one CLI and three primary ways to provide its Python and media
runtime. Choose based on operating system and how much native dependency management
you want to own.

<div class="fc-card-grid" markdown>

<div class="fc-card" markdown>

## Windows portable

**Recommended for Windows 10/11 x64.**

The published bundle includes Python, FFmpeg, VapourSynth, the supported source and
tonemapping plugins, VSView with its PySide6 backend, installer, updater, and rollback
tooling.

[Install the Windows portable bundle](../windows-portable.md){ .md-button .md-button--primary }

</div>

<div class="fc-card" markdown>

## Docker

**Recommended for reproducible macOS and Linux headless use.**

The image provides the managed runtime and uses explicit host mounts for configuration,
media, reports, run records, and caches. The default route uses software Vulkan and
does not include interactive VSView.

[Start with Docker](docker.md){ .md-button .md-button--primary }

</div>

<div class="fc-card" markdown>

## Native source

**For advanced host-managed installations.**

Use this when direct host integration matters and you already manage compatible
FFmpeg, VapourSynth, source plugins, vs-placebo, and Vulkan components.

[Install from source](native.md){ .md-button .md-button--primary }

</div>

</div>

## Recommendation by situation

| Situation | Recommended route |
| --- | --- |
| Windows user who wants the broadest supported feature set | Windows portable |
| macOS user who wants a reproducible backend | Docker |
| Linux user who wants the canonical headless route | Docker |
| Linux user who specifically needs NVIDIA or X11 integration | Docker, then follow the separately verified advanced profile |
| Existing native VapourSynth environment | Native source with `uv` |
| Embedding Frame Compare in an existing Python environment | Native source with pip, with host runtime validation |
| Contributor changing application code | Contributor environment from `CONTRIBUTING.md` |

For dependency ownership, feature availability, and support boundaries, see the
[full route comparison](route-comparison.md).

## After installation

Use the same sequence on every route:

1. Put at least two supported clips in the selected input directory.
2. Run the wizard.
3. Run `doctor` through the same route.
4. Run a dry run to inspect source discovery and output intent.
5. Run the comparison and open the generated report.

Continue with [Your First Comparison](../guides/first-comparison.md).

!!! note "Publishing remains off by default"
    The first-use configuration keeps slow.pics automatic upload disabled. Local
    screenshot and report generation do not require any publishing account.
