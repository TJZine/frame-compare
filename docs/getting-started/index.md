# Choose an installation

Frame Compare has one CLI and three ways to supply its Python and media runtime. Choose
by operating system and by how much of the media runtime you want to manage.

<div class="fc-routes" markdown>

<div class="fc-route" markdown>

<p class="fc-route-tag">Windows 10/11 x64</p>

### [Windows portable](../windows-portable.md)

Complete runtime, VSView alignment panel, installer, and signed code-only updates.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">macOS · Linux</p>

### [Docker](docker.md)

Headless managed runtime with software-Vulkan HDR. Reports stay on the host.

</div>

<div class="fc-route" markdown>

<p class="fc-route-tag">Advanced</p>

### [Native source](native.md)

Bring your own FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo, and Vulkan.

</div>

</div>

## Which route fits

| Situation | Recommended route |
| --- | --- |
| Windows user who wants the broadest supported feature set | Windows portable |
| macOS user who wants a reproducible backend | Docker |
| Linux user who wants the canonical headless route | Docker |
| Linux user who needs NVIDIA acceleration or an X11 desktop | Docker, then the matching [Docker profile](docker-profiles.md) |
| Existing native VapourSynth environment | Native source with `uv` |
| Embedding Frame Compare in an existing Python environment | Native source with pip, with host runtime validation |
| Contributor changing application code | [Contributor environment](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md) |

## What each route includes

| Capability | Windows portable | Docker | Native source |
| --- | --- | --- | --- |
| Discovery, probing, frame selection, and alignment | Yes | Yes | Yes, with the required runtime |
| SDR screenshots and offline reports | Yes | Yes | Yes, with the required runtime |
| HDR tonemapping | Host Vulkan driver | Software Vulkan | Host Vulkan driver |
| VSView alignment panel | Included | Not included | Optional `vsview` extra |
| Opening the report and slow.pics URL automatically | Interactive desktop session | No; use the host helper | Interactive desktop session |
| Signed code-only updates and rollback | Yes | No | No |
| History and caches that persist | Yes | Yes, through the host `generated/` mount | Yes |

Browser and clipboard actions need an interactive desktop session; headless, SSH,
service, and non-TTY sessions should not rely on them.

## Who owns the runtime

| Route | Runtime owner | Setup effort | Support |
| --- | --- | --- | --- |
| Windows portable release | The bundle | Lowest | Recommended on Windows |
| Windows portable source build | Build scripts that assemble pinned inputs | Medium to high | Packaging fallback |
| Docker | The image | Low to medium | Recommended headless route on macOS and Linux |
| Native source with `uv` | Locked Python environment plus your media stack | High | Advanced |
| Native source with pip | Your Python and media stack | Highest | Advanced integration |

“Reproducible” does not mean identical pixels across unrelated operating systems or GPU
drivers. Use the same route and runtime when bit-for-bit output matters.

The [Supported media runtime](../supported-media-runtime.md) page is the home of
component versions.

## After installation

Use the same sequence on every route:

1. Put at least two supported video files in the selected input directory.
2. Run the wizard.
3. Run `doctor` through the same route.
4. Run a dry run to inspect source discovery and output intent.
5. Run the comparison and open the generated report.

Continue with [Your first comparison](../guides/first-comparison.md). Later
comparisons with an established configuration and runtime usually need only the dry
run and run; see [Repeat comparisons](../guides/first-comparison.md#repeat-comparisons).

!!! note "Publishing stays off"
    The first-use configuration keeps slow.pics automatic upload disabled. Local
    screenshot and report generation do not require any publishing account.
