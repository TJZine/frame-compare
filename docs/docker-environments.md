# Docker Environments

> Platform-specific Docker runtime details — capability matrix, GPU profiles,
> GUI profiles, and the host open helper.

For basic Docker usage (build, doctor, run), see the
[Quick Start](../README.md#quick-start) in the README.

---

## Docker Path Overview

The default Docker path is headless and deterministic: it uses software Vulkan and
matches the CI-safe backend proof path rather than a desktop GUI workflow.

The [README Docker Quick Start](../README.md#docker-recommended-for-macoslinux)
is the canonical user journey. It pre-creates host-owned bind directories, creates
configuration through the setup service, validates the intended run without side
effects, and then uses the production-like run service.

For reproducible "real deps" verification, prefer Docker:

```bash
bash tools/verify_docker_integration.sh
```

---

## Default Compose Services

| Service | Purpose | Mount policy |
| --- | --- | --- |
| `frame-compare-wizard` | One-time or intentional interactive configuration, isolated behind the `setup` profile and started explicitly by the quick-start command | `config/` writable; `comparison_videos/` read-only |
| `frame-compare-run` | Doctor, dry-run, normal runs, history, and other production-like CLI commands | `config/` and media read-only; `screenshots/` and `generated/` writable |
| `frame-compare` | Interactive development shell | Runtime workspace mounts with a shell entrypoint |
| `frame-compare-test` | Real-dependency integration verification | Repository mounted at the image source path |

Use the wizard and run services as a pair so configuration and output paths remain
consistent. The setup service is the only default user service that deliberately
grants configuration write access. The README route also maps both services to the
current host UID/GID so their writable bind-mount output remains host-owned.

---

## Docker Capability Matrix

| Environment | Current supported posture | Not first-class / not supported by default | Notes |
| ----------- | ------------------------- | ------------------------------------------ | ----- |
| macOS Docker Desktop | Backend rendering, HTML reports, software tonemap, `doctor`, non-GUI `run`, reproducible software Vulkan path | Native GPU acceleration, Docker-based VSPreview GUI launch, native Qt desktop forwarding | Supported for backend/software-Vulkan features only. macOS Docker does not support VSPreview GUI launch beyond the documented backend features; use a native desktop runtime for VSPreview GUI workflows. |
| Linux Docker, CPU/software Vulkan | Full default Docker path: backend rendering, HTML reports, software tonemap, CI parity, deterministic headless verification | Native GPU acceleration, GUI/VSPreview unless separately configured | This is the canonical default Docker mode. |
| Linux Docker with NVIDIA GPU | Optional `gpu-nvidia` override/profile and GPU proof script for host-dependent Vulkan acceleration | Guaranteed parity without host setup, default CI path, GUI/VSPreview by default | Documented-only/unverified in this repo unless you run the dedicated proof on a compatible Linux NVIDIA host. |
| Linux Docker with X11 GUI | Optional `gui-linux` override/profile and GUI proof script for VSPreview dependency availability on Linux desktop hosts | CI coverage, Wayland, VNC/noVNC, automatic broad X server permissions | Linux/X11 only. Documented-only/unverified until `bash tools/verify_docker_gui.sh` passes on a compatible Linux desktop host. Real UI launch remains manual and host-dependent even after the non-UI proof passes. |
| Native Windows portable | Full native app path including backend rendering, reports, VSPreview GUI, and Windows installer/update flow | Docker-specific container assumptions | This remains the first-class native desktop/runtime distribution. See [Windows Portable](windows-portable.md). |

Optional Docker GPU and GUI profiles require compatible host setup and separate
verification. The default Docker behavior remains the deterministic headless
software-Vulkan path even when a host could support more.

---

## NVIDIA GPU Profile

Optional Linux NVIDIA hosts can try the separate GPU proof path:

```bash
bash tools/verify_docker_gpu.sh
```

The NVIDIA path keeps the default Docker services unchanged unless you opt into
`docker-compose.gpu-nvidia.yml` and the `gpu-nvidia` profile. The script requires a
compatible Linux NVIDIA host with NVIDIA Container Toolkit. It preflights Docker
Compose before using the Compose `gpus` attribute. If your Compose plugin is older
than 2.30.0, the script stops and prints a copy/paste-friendly `docker run --gpus all`
fallback instead of silently dropping to software Vulkan.

GPU support here is still documented-only/unverified unless you run
`bash tools/verify_docker_gpu.sh` successfully on a compatible Linux NVIDIA machine.

If you are evaluating optional Docker GPU or profile wiring, use the official Docker
GPU/container and profile docs as the source of truth for host prerequisites and
compose semantics: Docker Engine GPU access, Docker Desktop GPU support notes,
Compose profiles, and the Compose `gpus` service attribute are documented at
[docs.docker.com/engine/containers/gpu](https://docs.docker.com/engine/containers/gpu/),
[docs.docker.com/desktop/features/gpu](https://docs.docker.com/desktop/features/gpu/),
[docs.docker.com/compose/how-tos/profiles](https://docs.docker.com/compose/how-tos/profiles/),
and
[docs.docker.com/reference/compose-file/services/#gpus](https://docs.docker.com/reference/compose-file/services/#gpus).

---

## Linux X11 GUI Profile

The optional GUI profile is for Linux desktop users who want VSPreview inside the
container for interactive alignment checks. It does not change the default Docker
image or the default CI-safe path.

### X11 Contract

- `DISPLAY` must be set to a live host X11 display.
- `/tmp/.X11-unix` must be mounted into the container.
- `XAUTHORITY` cookie sharing is optional, but many hosts require it. The compose
  override mounts `${FRAME_COMPARE_XAUTHORITY_PATH}` into the container when you set
  that env var, or falls back to a harmless placeholder when you do not.
- The GUI profile runs as the host UID/GID via `FRAME_COMPARE_HOST_UID` and
  `FRAME_COMPARE_HOST_GID` so local-user X11 permissions and mounted cookie files
  line up with the host session, while preserving the image's locked Python user
  base for VSPreview imports.

### Proof Command

```bash
bash tools/verify_docker_gui.sh
```

If your X server denies access, use the narrow local-user form on the host instead
of `xhost +`:

```bash
xhost +si:localuser:$(id -un)
```

Cleanup:

```bash
xhost -si:localuser:$(id -un)
```

### Manual GUI Launch

Manual GUI launch stays separate from proofing. After the proof passes, you can
launch an interactive container manually with:

```bash
docker compose -f docker-compose.yml -f docker-compose.gui-linux.yml run --rm frame-compare-run \
  run --root /workspace --input /workspace/comparison_videos
```

GUI support here remains documented-only/unverified until you run
`bash tools/verify_docker_gui.sh` successfully on a compatible Linux desktop host.

---

## Host Open Helper

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

- `/workspace/screenshots` -> `./screenshots`
- `/workspace/generated` -> `./generated`

Use the exact `report_path` printed by the run. With the default
`paths.use_run_folders = true`, screenshots and the report are grouped beneath
`/workspace/generated/<run>/`. When run folders are disabled,
`report.output_dir = null` places the report beneath `/workspace/screenshots`.

The helper rejects `/workspace/config`, `/workspace/comparison_videos`,
non-canonical paths, symlink escapes, and non-`https://slow.pics/...` URLs.
This helper is host-side only; it does not change the existing CLI/browser
ownership inside the container. It is not a general `docker run` path
translator for arbitrary custom bind mounts.
