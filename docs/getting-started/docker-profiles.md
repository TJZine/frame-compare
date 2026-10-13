---
description: The Docker Compose services, the NVIDIA and X11 profiles, and the host helper that opens reports.
---

# Docker profiles

The default Docker route is headless and uses software Vulkan. This page covers the
Compose services, the optional NVIDIA and X11 profiles, and the host helper. Start with
[Docker](docker.md) for basic use.

## Compose services

| Audience | Service | Purpose | Mount policy |
| --- | --- | --- | --- |
| User | `frame-compare-wizard` | One-time or intentional interactive configuration, isolated behind the `setup` profile and started explicitly by the quick-start command | `config/` and `generated/` writable; `comparison_videos/` read-only |
| User | `frame-compare-run` | Doctor, dry-run, normal runs, history, and other production-like CLI commands | `config/` and media read-only; `generated/` writable |
| Contributor | `frame-compare` | Interactive development shell | Runtime workspace mounts plus the generated-data mount, with a shell entrypoint |
| Contributor | `frame-compare-test` | Real-dependency integration verification | Repository and generated-data mounts |

Use the wizard and run services together so configuration and output paths match. Both
run as `FRAME_COMPARE_HOST_UID` and `FRAME_COMPARE_HOST_GID` so files they create belong
to you; the wizard is the only user service that can write configuration.

## Capability by host

| Environment | Supported | Not supported by default | Notes |
| --- | --- | --- | --- |
| macOS Docker Desktop | Backend rendering, HTML reports, software tonemap, `doctor`, non-GUI `run`, reproducible software Vulkan path | Native GPU acceleration, Docker-based VSView GUI launch, native Qt desktop forwarding | Supported for backend/software-Vulkan features only. macOS Docker does not support VSView GUI launch beyond the documented backend features; use a native desktop runtime for VSView GUI workflows. |
| Linux Docker, CPU/software Vulkan | Full default Docker path: backend rendering, HTML reports, software tonemap, CI parity, deterministic headless verification | Native GPU acceleration, GUI/VSView unless separately configured | This is the canonical default Docker mode. |
| Linux Docker with NVIDIA GPU | Optional `gpu-nvidia` override/profile and GPU proof script for host-dependent Vulkan acceleration | Guaranteed parity without host setup, default CI path, GUI/VSView by default | Documented-only/unverified in this repo unless you run the dedicated proof on a compatible Linux NVIDIA host. |
| Linux Docker with X11 GUI | Optional `gui-linux` override/profile and GUI proof script for VSView/plugin availability, generated-session loading, native panel construction, typed metadata/result integration, and offscreen rendering | CI coverage, Wayland, VNC/noVNC, automatic broad X server permissions | Linux/X11 only. The verifier contract covers VSView, exact Frame Compare panel entry-point loading, named `Reference`/`Comparison 1` outputs, frame-0 rendering, and sibling-sidecar validation. The Linux X11 host wrapper and visible launch remain unverified. |
| Native Windows portable | Full native app path including backend rendering, reports, VSView GUI, and Windows installer/update flow | Docker-specific container assumptions | See [Windows portable](windows-portable.md) for the native desktop and runtime distribution. |

Optional Docker GPU and GUI profiles require compatible host setup and separate
verification. Docker uses the deterministic headless software-Vulkan path by default,
even when a host could support more.

The NVIDIA profile is experimental until proved on the host. The X11 wrapper and a
visible desktop are unverified.

## NVIDIA GPU profile

Optional Linux NVIDIA hosts can try the separate GPU proof path:

```bash
bash tools/verify_docker_gpu.sh
```

The NVIDIA path keeps the default Docker services unchanged unless you opt into
`docker-compose.gpu-nvidia.yml` and the `gpu-nvidia` profile. The script requires a
compatible Linux NVIDIA host with NVIDIA Container Toolkit. It preflights Docker
Compose before using the Compose `gpus` attribute.

If your Compose plugin is older than 2.30.0, the script stops and prints a
`docker run --gpus all` fallback you can copy and paste. It does not switch to software
Vulkan. Run `bash tools/verify_docker_gpu.sh` successfully on a compatible Linux NVIDIA
machine to verify GPU support.

Use the official Docker documentation for host prerequisites and Compose behavior when
evaluating optional GPU or profile setup. Docker documents Engine GPU access, Desktop
GPU support, Compose profiles, and the Compose `gpus` service attribute at
[docs.docker.com/engine/containers/gpu](https://docs.docker.com/engine/containers/gpu/),
[docs.docker.com/desktop/features/gpu](https://docs.docker.com/desktop/features/gpu/),
[docs.docker.com/compose/how-tos/profiles](https://docs.docker.com/compose/how-tos/profiles/),
and
[docs.docker.com/reference/compose-file/services/#gpus](https://docs.docker.com/reference/compose-file/services/#gpus).

## Linux X11 GUI profile

The optional GUI profile is for Linux desktop users who want the native Frame Compare
VSView alignment panel inside the container for interactive alignment checks. The
panel is available only for Frame Compare-generated sessions. Use it for all human
alignment review. The profile keeps the default Docker image and CI path unchanged.

### X11 contract

- `DISPLAY` must be set to a live host X11 display.
- `/tmp/.X11-unix` must be mounted into the container.
- `XAUTHORITY` cookie sharing is optional, but many hosts require it. The compose
  override mounts `${FRAME_COMPARE_XAUTHORITY_PATH}` into the container when you set
  that env var, or falls back to a harmless placeholder when you do not.
- The GUI profile runs as the host UID/GID via `FRAME_COMPARE_HOST_UID` and
  `FRAME_COMPARE_HOST_GID` so local-user X11 permissions and mounted cookie files
  line up with the host session, while preserving the image's locked Python user
  base for VSView imports.

### Proof command

```bash
bash tools/verify_docker_gui.sh
```

The verifier covers the `frame-compare-alignment-review` entry point, offscreen panel
construction, generated output metadata, the atomic sidecar round trip, and
malformed-result rejection.

An offscreen pass does not prove visible desktop behavior. The X11 host wrapper and a
visible launch remain unverified until a compatible Linux/X11 host runs them. The host
wrapper needs Linux with X11 and does not run on macOS Docker Desktop.

If your X server denies access, use the narrow local-user form on the host instead
of `xhost +`:

```bash
xhost +si:localuser:$(id -un)
```

Cleanup:

```bash
xhost -si:localuser:$(id -un)
```

### Manual GUI launch

After the proof passes, launch an interactive container manually with this separate
command:

```bash
docker compose -f docker-compose.yml -f docker-compose.gui-linux.yml run --rm frame-compare-run \
  run --root /workspace --input /workspace/comparison_videos
```

Run `bash tools/verify_docker_gui.sh` successfully on a compatible Linux desktop host
to verify GUI support.

## Host open helper

Containerized runs cannot directly open the host browser for generated reports or
slow.pics links. For the default `docker compose` volume layout, use the
host-side helper instead:

```bash
python tools/open_docker_host_target.py "<report_path_from_run_output>"
python tools/open_docker_host_target.py https://slow.pics/c/example
```

To translate a container path without opening it:

```bash
python tools/open_docker_host_target.py --print-only "<report_path_from_run_output>"
```

The helper only translates the default compose output mounts used by
`docker-compose.yml`:

- `/workspace/generated` -> `./generated`

Use the exact `report_path` printed by the run. Screenshots and the report are
always grouped beneath `/workspace/generated/<run>/` and are retained through the
host `./generated` bind mount. A custom container output path is durable only when
you explicitly map it to a host-owned directory; the helper intentionally does not
translate arbitrary mounts.

The helper rejects `/workspace/config`, `/workspace/comparison_videos`,
`/workspace/screenshots`, non-canonical paths, symlink escapes, and
non-`https://slow.pics/...` URLs. It runs only on the host and leaves CLI and browser
actions inside the container unchanged. It translates only the default Compose mounts;
use your own path translation for arbitrary custom `docker run` bind mounts.
