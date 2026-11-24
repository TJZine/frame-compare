---
description: Run Frame Compare in Docker on macOS or Linux and find the results on the host.
---

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

```bash title="Set up the workspace"
export FRAME_COMPARE_HOST_UID="$(id -u)"
export FRAME_COMPARE_HOST_GID="$(id -g)"
mkdir -p config comparison_videos generated
```

Then build the image and run the four stages:

```bash title="Build the image and run the four stages"
docker compose build frame-compare-run
docker compose run --rm frame-compare-wizard
docker compose run --rm frame-compare-run doctor
docker compose run --rm frame-compare-run run --root /workspace --dry-run
docker compose run --rm frame-compare-run run --root /workspace
```

The wizard creates or reviews `config/config.toml`; it writes only after confirmation.
The wizard and run service mount the generated-data root at
`/workspace/generated`; this single host directory retains reports, screenshots,
run records, run-local state, and shared caches after container removal.

The run service mounts configuration and media read-only. The first-use wizard keeps
`slowpics.auto_upload = false`, so the normal run is local unless you later opt in.

## Compose services

| Audience | Service | Purpose | Mount policy |
| --- | --- | --- | --- |
| User | `frame-compare-wizard` | Interactive configuration in the `setup` profile, started explicitly | Configuration and generated output writable, media read-only |
| User | `frame-compare-run` | Doctor, dry runs, comparisons, and history | Configuration and media read-only, generated output writable |
| Contributor | `frame-compare` | Interactive development shell | Configuration and media read-only, generated output writable |
| Contributor | `frame-compare-test` | Real-dependency integration tests in the `test-runtime` image | Repository and generated output writable |

The wizard and run services use `FRAME_COMPARE_HOST_UID` and
`FRAME_COMPARE_HOST_GID` so files they create belong to you. The wizard is the
only user service with write access to configuration.

## Open results on the host

Screenshots and the report are grouped beneath `/workspace/generated/<run>/`.
Use the exact report path printed by the run or pass an HTTPS slow.pics comparison
URL to the host helper. Run these commands from the repository on the host.

```bash
python tools/open_docker_host_target.py "<report_path_from_run_output>"
python tools/open_docker_host_target.py https://slow.pics/c/example
```

To print the translated path or the accepted URL without opening it, add
`--print-only`.

```bash
python tools/open_docker_host_target.py --print-only "<report_path_from_run_output>"
```

For file paths, the helper maps only the default Compose output mount,
`/workspace/generated` to `./generated`. It rejects paths under
`/workspace/config`, `/workspace/comparison_videos`, and `/workspace/screenshots`,
as well as non-canonical paths and symlink escapes. The helper accepts comparison
URLs of the form `https://slow.pics/c/<id>` and passes them to the host browser.

If host Python is unavailable, use the same mapping to locate the report and open
it directly. For custom output paths, bind-mount the output to a host directory
and translate the path using that mount.

## The index warning

A comparison run logs this warning when an index cache was supplied, source
admission produced a reusable geometry probe token, and the managed load returned
no clip:

`Loading <path> without the managed L-SMASH index cache; indexing in memory for this run`

Sources without a reusable geometry probe token do not produce this warning.

The run service mounts media read-only and persists indexes under
`/workspace/generated/cache/source-indexes/` by default. The generated mount
must be writable by the container's effective user for the first build and later
reuse. Existing adjacent media indexes are left untouched. If the managed cache is
unusable, Frame Compare retries without a disk cache and indexes in memory for that
run. See [Output layout](../reference/output-layout.md).

## Next steps

<div class="fc-cards" markdown>

- [Your first comparison](first-comparison.md)

    What each stage checks, with the Docker commands.

- [Native Linux installation for visual alignment review](native.md#install-with-uv)

    Install with `--extra vsview` to use the [alignment panel](../guides/vsview-review.md).

</div>
