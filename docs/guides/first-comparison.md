# Your first comparison

A safe first run follows the same four stages on every route: configure, diagnose,
preview the intent, then run. Put at least two `.mkv`, `.mp4`, `.avi`, `.m2ts`, or
`.ts` files in the route's `comparison_videos/` directory first.

| Stage | Windows portable or pip | Native uv | Docker |
| --- | --- | --- | --- |
| Configure | `frame-compare wizard` | `uv run --no-sync frame-compare wizard` | `docker compose run --rm frame-compare-wizard` |
| Diagnose | `frame-compare doctor` | `uv run --no-sync frame-compare doctor` | `docker compose run --rm frame-compare-run doctor` |
| Dry run | `frame-compare run --dry-run` | `uv run --no-sync frame-compare run --root . --dry-run` | `docker compose run --rm frame-compare-run run --root /workspace --dry-run` |
| Run | `frame-compare run` | `uv run --no-sync frame-compare run --root .` | `docker compose run --rm frame-compare-run run --root /workspace` |

## What the stages protect

1. **Wizard** reviews input, reference, and frame-selection choices and writes only
   after confirmation. Use the same workspace route for the wizard and the run.
2. **Doctor** checks required runtime dependencies and reports optional or network
   warnings separately. Review warnings against the features you intend to use.
3. **Dry run** validates configuration, discovered filenames, selection intent, and
   output intent without running the pipeline.
4. **Run** renders the comparison and writes its outputs.

Publishing is off by default: first-use wizard output explicitly sets
`slowpics.auto_upload = false`. Keep the first run local, inspect its report, and
enable publishing later only if you want it.

Every run reserves a fresh folder beneath the configured `paths.generated_dir` root.
With the default value, screenshots, run metadata, and the canonical
`generated/<run>/report.html` are grouped together with sibling `screenshots/` and
`generated/` directories. An authored absolute `paths.generated_dir` uses the same
layout outside the workspace; route-specific Docker and Windows persistence details
remain in their dedicated guides. The [reports guide](reports-and-overlays.md)
covers the offline report and relative screenshot layout.

If a stage fails, go to [Troubleshooting](troubleshooting.md). For exact command and
configuration semantics, use the [CLI and configuration contract](../current-cli-contract.md).
