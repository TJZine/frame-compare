# Docker

Docker is the recommended reproducible, headless route for macOS and Linux. Run the
following commands from a cloned repository. Copy at least two supported video files
into `comparison_videos/` before the wizard; supported extensions are `.mkv`, `.mp4`,
`.avi`, `.m2ts`, and `.ts` (case-insensitive).

The UID and GID variables make container-created bind-mount files belong to the
current host user. Pre-creating the directories keeps ownership predictable.

```bash
export FRAME_COMPARE_HOST_UID="$(id -u)"
export FRAME_COMPARE_HOST_GID="$(id -g)"
mkdir -p config comparison_videos generated

docker compose build frame-compare-run
docker compose run --rm frame-compare-wizard
docker compose run --rm frame-compare-run doctor
docker compose run --rm frame-compare-run run --root /workspace --dry-run
docker compose run --rm frame-compare-run run --root /workspace
```

The wizard creates or reviews `config/config.toml`; it writes only after confirmation.
The wizard and run service mount the generated-data root at
`/workspace/generated`; this single host directory retains reports, screenshots,
run records, run-local state, and shared caches after container removal. The run
service mounts configuration and media read-only. The first-use wizard keeps
`slowpics.auto_upload = false`, so the normal run is local unless you later opt in.

With the default run-folder policy, screenshots and the report are grouped beneath
`generated/`. Containerized Frame Compare cannot open the host browser. Use the exact
report path printed at the end of the run:

```bash
python tools/open_docker_host_target.py "<report_path_from_run_output>"
```

If host Python is unavailable, translate `/workspace/generated/` to `./generated/`
and open `report.html` normally. A custom container output path is durable only
when you explicitly bind-mount it to a host-owned directory; paths without a host
mount disappear with the container.

For service details, capability limits, the host-open helper, and optional Linux
NVIDIA/X11 profiles, see [Advanced Docker Environments](../docker-environments.md).
Continue with [Your First Comparison](../guides/first-comparison.md) for what each
safety step checks.
