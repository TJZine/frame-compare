# Troubleshooting

Start with `frame-compare doctor` through the same Windows, Docker, uv, or pip route
that will run the comparison. Then use a dry run to check paths and intent before
trying the full pipeline again.

| Symptom | What to do |
| --- | --- |
| `frame-compare: command not found` after `uv sync` | Use `uv run --no-sync frame-compare ...`, activate `.venv`, or invoke `.venv/bin/frame-compare`. |
| `FC-1001` reports a missing configuration file | Run the wizard through the same workspace route that will run the pipeline. |
| No videos are discovered | Put at least two supported clips in the configured input directory, normally `comparison_videos/`, then rerun `run --dry-run`. |
| Doctor reports VapourSynth or L-SMASH-Works missing | Use Docker or Windows portable, or repair the native VapourSynth R78 and L-SMASH-Works 1296 installation. The default renderer requires VapourSynth. |
| Doctor reports an optional or network warning | Review it against the intended workflow. Disabled integrations need no setup; FFmpeg-dependent workflows still require FFmpeg. |
| Docker cannot write config or outputs | Export the host UID/GID variables and create `config`, `comparison_videos`, and `generated` as the host user, then rerun Compose. |
| A Docker report did not open | This is expected across the container boundary. Use the host helper and the exact report path printed by the run. |
| The Windows command is unavailable after installation | Open a new terminal so the updated user `PATH` loads. If needed, rerun `install.cmd` from the bundle's current location. |
| A code-only Windows update reports a media-runtime fingerprint mismatch | Install the complete portable ZIP for that release. Code-only updates do not replace VapourSynth, source plugins, vs-placebo, or FFmpeg, and the mismatch cannot be overridden. Preserve generated data by configuring it outside the bundle. |

Platform-specific help lives in [Advanced Docker Environments](../docker-environments.md)
and the [Windows Portable Guide](../windows-portable.md).

## Collect safe diagnostics

When asking for help, collect:

- the route and operating system you used;
- the exact command, whether it was a dry run, and the exit code;
- `frame-compare doctor` output (or `doctor --json` when structured output helps);
- sanitized run warnings and the names of the affected input files;
- `frame-compare run --diagnose-paths` output when path resolution is relevant.

Do not share `config.toml`, environment dumps, live webhook URLs, TMDB API keys,
cookies, or other credentials. Redact usernames and private filesystem locations if
they are not necessary to reproduce the issue. The
[CLI contract](../current-cli-contract.md) defines diagnostic streams and JSON behavior.
