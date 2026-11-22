---
description: What each installation route needs on your system.
---

# Requirements

Frame Compare needs a Python runtime and a media stack: FFmpeg, VapourSynth,
L-SMASH-Works, and, for HDR sources, vs-placebo with Vulkan. Each installation route
provides that stack differently.

| Route | Operating system | You install | The route provides |
| --- | --- | --- | --- |
| [Windows portable](../getting-started/windows-portable.md) | Windows 10 or 11, x64 | Nothing else to run Frame Compare | Python, the media stack, VSView with the alignment panel, and the installer |
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

The VSView alignment panel ships with the Windows bundle. For visual review on Linux,
follow the [native installation instructions](../getting-started/native.md#install-with-uv)
with `--extra vsview`. Docker runs headless.

## Exact versions

The native install page lists the versions you install yourself. Every component
version, with the reason it was chosen, is in the
[Supported media runtime](../supported-media-runtime.md) record.
