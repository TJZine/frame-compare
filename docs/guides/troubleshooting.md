# Troubleshooting

Start with the same installation route that will run the comparison:

```bash
frame-compare doctor
frame-compare run --dry-run
```

For `uv`, Docker, or another wrapper, keep the same prefix used for the normal run.
This avoids diagnosing a different Python or media runtime than the one that failed.

## Common problems

| Symptom | What to do |
| --- | --- |
| `frame-compare: command not found` after `uv sync` | Use `uv run --no-sync frame-compare ...`, activate `.venv`, or invoke the environment’s entry point directly |
| `FC-1001` reports a missing configuration file | Run the wizard through the same root/config route that will execute the pipeline |
| No videos are discovered | Confirm the configured input directory and supported extensions, then rerun the dry run |
| The wrong source is the reference | Set `sources.reference` to an unambiguous relative path, filename, or stem and verify the dry run |
| Duplicate or confusing source labels | Use explicit per-source labels; duplicate explicit labels are rejected |
| Doctor reports VapourSynth or L-SMASH-Works missing | Use Docker or Windows portable, or repair the native supported runtime; the default renderer requires VapourSynth |
| Doctor reports vs-placebo or Vulkan unavailable | Repair the selected plugin/driver path or use the supported Docker software-Vulkan route for headless work |
| Automatic alignment is weak or incorrect | Confirm corresponding audio streams, inspect for different edits or silence, and verify with the native Frame Compare VSView panel when available |
| Doctor reports the Frame Compare alignment panel is missing | Install `frame-compare[vsview]` in the same Python environment that runs Frame Compare; PATH-only VSView discovery is unsupported |
| The native alignment panel is inactive | Open a Frame Compare-generated session; ordinary VSView sessions and malformed/mixed output metadata intentionally remain inert |
| The panel closed before saving | No typed result sidecar was written; reopen the generated session, visit every source, and choose **Use these aligned positions** or **Keep audio-derived alignment** |
| Native review result was rejected | The sidecar is missing, malformed, stale, mixed-session, duplicated, incomplete, or outside raw source bounds; generate a fresh session and review again |
| Requested frames cannot survive alignment | Reduce trims or frame counts and inspect the final shared overlap; user frames are not silently replaced |
| Docker cannot write config or generated data | Export host UID/GID values and pre-create `config`, `comparison_videos`, and `generated` as the host user |
| Docker report did not open | Expected across the container boundary; use the host helper and exact path printed by the run |
| Windows command is unavailable after install | Open a new terminal; if needed, rerun `install.cmd` from the bundle’s current location |
| Windows shim says the bundle moved | Rerun `install.cmd` from the new bundle location to update installed state |
| Code-only update reports a runtime fingerprint mismatch | Install the complete portable ZIP for that release; code-only updates cannot replace native media components |
| Report opens without images | Keep `report.html` beside its `screenshots/` directory or rerun the comparison with `report.embed_images = true` |
| A cache hit appears stale after replacing media | Ensure path, size, or modification time changed, or remove the smallest relevant cache entry |

## Diagnose by pipeline stage

### Configuration or discovery

Use:

```bash
frame-compare run --diagnose-paths
frame-compare run --dry-run
```

Check the resolved config file, input directory, generated-data root, discovered files,
reference, comparison order, and output intent. Do not share unredacted path diagnostics
when private usernames or directories are unnecessary.

### Runtime and probing

Use:

```bash
frame-compare doctor
frame-compare doctor --json
```

Human output is better for interactive diagnosis. JSON is useful for automation or a
sanitized bug report. Managed routes can treat selected FFmpeg, VapourSynth, source
plugin, and runtime-policy failures as critical; optional network integrations remain
separate.

### Frame selection

Review:

- requested user/random/dark/bright/motion counts;
- quality versus performance mode;
- source trims;
- leading and trailing exclusions;
- the resolved active picture;
- the shared window after alignment.

Interactive full-window recovery is available only for eligible exclusion-constrained
selection failures. It is not a general “continue anyway” option.

### Alignment

Check that the selected audio streams contain corresponding material. A stable constant
offset cannot fix drift, different edits, or mismatched cadence. Review early, middle,
and late evidence. When native VSView review is available, open **Frame Compare
Alignment Review**, unlink playheads, and visit the Reference and every Comparison tab.
Leave each source on the same visible moment; the source lineup reports which outputs
are ready and previews the signed trim. Save the complete lineup once with **Use these
aligned positions**. If you already know the values, expand **Enter alignment
manually...** and choose either source frames or signed offsets. **Keep audio-derived
alignment** is the secondary whole-set action when you want to retain Frame Compare's
current alignment.

### Rendering and HDR

Confirm source loading, range/transfer/primaries evidence, vs-placebo availability, and
Vulkan initialization. Avoid enabling an FFmpeg-only path as a workaround when HDR
frames still require VapourSynth tonemapping.

### Report or browser behavior

Open the canonical `report.html` from the run folder. Keep the relative image layout
intact, try another current browser, and distinguish baked screenshot overlays from
viewer labels or browser-local state.

## Collect safe diagnostics

Include:

- operating system and installation route;
- exact Frame Compare version;
- exact command and exit code;
- whether the command was interactive, quiet, or JSON;
- sanitized `doctor` output;
- sanitized run warnings and error code;
- affected source extensions and relevant media properties;
- `run --diagnose-paths` output when path resolution matters;
- whether the issue reproduces with a small publication-safe fixture.

Do **not** include:

- live webhook URLs, API keys, cookies, or tokens;
- an unredacted `config.toml` containing secrets;
- full environment dumps;
- private media or screenshots without permission;
- usernames and filesystem paths that are irrelevant to reproduction.

## When to clear state

Clear only the owner related to the problem:

| State | Remove it when |
| --- | --- |
| Analysis cache entry | Metric identity or source freshness is known to be stale outside normal detection |
| Probe cache entry | Source properties were cached under an unmanaged runtime that changed |
| Alignment reuse entry | A previously accepted offset is no longer valid for the source relationship |
| Frame Compare-owned `.lwi` | The unmanaged decoder/plugin ABI changed or the owned index is known to be unusable |
| Browser-local report state | Viewer preferences or notes are corrupt; the run folder itself is still valid |

Do not delete the complete generated-data root as a first response.

Platform-specific help:

- [Windows Portable](../windows-portable.md)
- [Docker](../getting-started/docker.md)
- [Advanced Docker Environments](../docker-environments.md)
- [Native Source](../getting-started/native.md)

For exact error streams, JSON shape, and exit behavior, see the
[CLI Behavioral Contract](../current-cli-contract.md).
