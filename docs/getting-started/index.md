# Choose your installation

Pick one route. Each route runs the same Frame Compare CLI, but the included runtime
and host integration differ.

| Situation | Recommended route | Host requirements | Important differences |
| --- | --- | --- | --- |
| Windows 10/11 x64 | [Windows portable](../windows-portable.md) | PowerShell; Git and network access only when building from a clone | Most complete distribution. The full bundle includes Python, FFmpeg, VapourSynth R76, plugins, VSPreview, and PyQt6, plus the native installer and updater. |
| macOS | [Docker](docker.md) | Docker Desktop with Compose | Reproducible headless backend, software Vulkan, HTML reports. No native GPU acceleration or Docker-based VSPreview GUI workflow. |
| Linux, reproducible headless use | [Docker](docker.md) | Docker Engine or Docker Desktop with Compose | Default deterministic software-Vulkan path. Optional NVIDIA GPU and X11 profiles require separate host setup and proof. |
| Linux or macOS with an existing media toolchain | [Native source](native.md) | Python 3.13+, FFmpeg, VapourSynth R76, L-SMASH-Works, and `uv` or pip | Advanced route. You own native dependency installation; VSPreview is optional. |
| Development and contribution | Native contributor environment | Requirements in the contributor guide | Use the repository's locked development workflow; see [Contributing](https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md). |

VapourSynth is required by the default renderer. An FFmpeg-only configuration can
set `screenshots.use_ffmpeg = true`, but HDR frames that need tonemapping still use
the VapourSynth path. VSPreview is separate and optional unless you need interactive
manual alignment.

After installation, continue with [Your First Comparison](../guides/first-comparison.md).
