# Docker

Docker is the recommended reproducible, headless route for macOS and Linux. On macOS
Docker Desktop, HDR tonemapping uses the CPU-backed software-Vulkan path and needs no
GPU passthrough. Supported extensions are `.mkv`, `.mp4`, `.avi`, `.m2ts`, and `.ts`
(case-insensitive).

## Run your first comparison

Run the following commands from a cloned repository. Copy at least two supported video
files into `comparison_videos/` before the wizard.

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

## Where results go

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

Output and wizard suggestions show container paths such as `/workspace`; run the
commands above from the host instead.

## The index warning

Every comparison run (not a dry run) prints, once per source each time sources load:

`Loading /workspace/comparison_videos/<file> without an L-SMASH index cache after index construction failed`

This behavior is implemented at `src/frame_compare/vs/source.py:210` and was observed
in the 2026-10-08 Docker run. The run service mounts media read-only, and Frame Compare
keeps its L-SMASH-Works index beside the media as described in [Output layout](../reference/output-layout.md).
Each run therefore rebuilds the index in memory, which costs indexing time on every run.
Frame selection, alignment, and rendering are unaffected. The message is expected on
this route and needs no action.

## Next steps

See [Docker profiles](docker-profiles.md) for NVIDIA and X11 profiles and the full
service list. Continue with [Your first comparison](../guides/first-comparison.md)
for what each safety step checks.
