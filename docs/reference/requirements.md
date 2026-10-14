---
description: What each installation route needs on your system.
---

# Requirements

Frame Compare needs a Python runtime and a media stack: FFmpeg, VapourSynth,
L-SMASH-Works, and, for HDR sources, vs-placebo with Vulkan. Each installation route
provides that stack differently.

| Route | Operating system | You install | The route provides |
| --- | --- | --- | --- |
| [Windows portable](../getting-started/windows-portable.md) | Windows 10 or 11, x64 | Nothing else to run Frame Compare; verifying the download uses the GitHub CLI | Python, the media stack, VSView with the alignment panel, the installer, and the updater |
| [Docker](../getting-started/docker.md) | macOS or Linux | Docker with Docker Compose, and a clone of the repository | Python and the media stack, with software Vulkan for HDR |
| [Native source](../getting-started/native.md) | Any system the media stack supports | Python, FFmpeg, VapourSynth, L-SMASH-Works, vs-placebo with Vulkan, and uv or pip | Frame Compare and its Python dependencies |

## Supported video files

Frame Compare discovers files with the extensions `.mkv`, `.mp4`, `.avi`, `.m2ts`, and
`.ts`, matched case-insensitively.

## HDR tonemapping

HDR sources need vs-placebo and a working Vulkan implementation. The Windows bundle
uses the host's Vulkan driver. Docker uses software Vulkan, which needs no GPU. A native
install uses the host's Vulkan driver.

## Alignment review

The VSView alignment panel ships with the Windows bundle. A native install adds it with
the `vsview` extra. The default Docker services do not include it, and Docker on macOS
does not run VSView. [Docker profiles](../getting-started/docker-profiles.md) describes
an optional Linux X11 profile for the panel; that profile is not yet verified on a
visible desktop.

## Exact versions

The native install page lists the versions you install yourself. Every component
version, with the reason it was chosen, is in the
[Supported media runtime](../supported-media-runtime.md) record.
