# Paths Audit — Frame Compare (Phase 2)

## Config discovery & write locations
- Resolution order: `--config` flag → `$FRAME_COMPARE_CONFIG` → `ROOT/config/config.toml` (seeded if missing) → legacy `ROOT/config.toml` (loaded with warning and migration note).
- Seeding uses `copy_default_config`, which now writes through a temp file and `os.replace` to guarantee atomic creation even when interrupted (`src/config_template.py`).
- `ROOT` itself resolves before config lookup and is refused if it lives under any `site-packages`/`dist-packages` segment.
- Legacy configs outside the workspace are no longer seeded automatically; the CLI emits an error instead of writing to home or package directories.

## Workspace resolution & IO targets
- `_prepare_preflight` computes the workspace root with priority `--root` → `$FRAME_COMPARE_ROOT` → nearest ancestor containing `pyproject.toml`/`.git`/`comparison_videos` → CWD (`frame_compare.py`).
- Input workspace defaults to `ROOT/comparison_videos` (configurable via `[paths].input_dir`, still constrained to stay within ROOT).
- Screenshots live in `ROOT/comparison_videos/<directory_name>`; caches (`generated.compframes`, audio offsets) also reside beneath the input workspace.
- Preflight ensures `ROOT`, the media workspace, and the config directory are writable before any ffmpeg/VapourSynth work begins; failures raise `CLIAppError` immediately.
- `_abort_if_site_packages` guards config, workspace root, screenshot output, and caches against landing inside site/dist-packages.

## Diagnostic behaviour
- `--diagnose-paths` (and `FRAME_COMPARE_ROOT`/`--root`) now report:
  ```json
  {"workspace_root": "…", "media_root": "…", "config_path": "…", "config_exists": true|false,
   "legacy_config": true|false, "under_site_packages": true|false,
   "writable": {"workspace_root": bool, "media_root": bool, "config_dir": bool, "screens_dir": bool},
   "warnings": ["…"]}
  ```
- Diagnostic mode never seeds or creates directories; it falls back to in-memory defaults when `config.toml` is absent so operators can inspect expected paths without side effects.
- `--write-config` ensures `ROOT/config/config.toml` exists (creating `ROOT/config/` as needed) and exits after printing the resolved path.

## Reproduction notes (post-fix)
- **Site-packages invocation** (Windows or POSIX): running the CLI from an installed package directory now aborts immediately with a site-packages guard error referencing the offending path. No directories are created and the process exits with code 2.
- **Read-only target root**: pointing `--root` at a non-writable directory yields `Workspace root is not writable` before analysis starts.
- **Missing config**: when `ROOT/config/config.toml` is absent, the CLI seeds it atomically inside ROOT (not in home) provided the directory is writable.

## Scenario matrix (current behaviour)
| Scenario | Config path | Workspace root → media root | Screenshots dir | Result |
| --- | --- | --- | --- | --- |
| Repo checkout (`python frame_compare.py`) | `REPO/config/config.toml` (seeded automatically) | `REPO` → `REPO/comparison_videos` | `REPO/comparison_videos/screens` | ✅ Works; paths stay inside repo tree. |
| Editable install (`pip install -e .`, run from repo) | `REPO/config/config.toml` | `REPO` → `REPO/comparison_videos` | `REPO/comparison_videos/screens` | ✅ Works; identical to checkout. |
| CLI from `$HOME/projects/foo`, no flags | `foo/config/config.toml` | `foo` → `foo/comparison_videos` | `foo/comparison_videos/screens` | ✅ Works once root is writable (directories auto-created). |
| Global install run from home | `ROOT/config/config.toml` (ROOT defaults to `$HOME`) | `$HOME` → `$HOME/comparison_videos` | `$HOME/comparison_videos/screens` | ✅ Works; home becomes workspace root unless overridden. |
| Run from `site-packages/frame_compare` | — | Guard rejects root (`…/site-packages/frame_compare`) | — | ⛔ Fails fast with site-packages error (no freeze). |
| `--root /readonly` | — | `/readonly` → `/readonly/comparison_videos` | `/readonly/comparison_videos/screens` | ⛔ Immediate writability error; user must choose another root. |

## Current guardrails
- Atomic config seeding and preflight writability probes stop permission issues before rendering.
- Site-packages detection spans workspace root and all derived paths, preventing accidental writes alongside installed packages.
- `PathsConfig.input_dir` default is now relative (`"comparison_videos"`), reinforcing the requirement that media and screenshots stay inside the workspace root.
- Analysis cache (`analysis.frame_data_filename`) and audio offsets (`audio_alignment.offsets_filename`) now pass through `_resolve_workspace_subdir`, so any attempt to escape the media root (absolute paths or `..`) raises a `CLIAppError`; regression tests cover these guards.
- slow.pics cleanup only deletes screenshot directories created during the current run, preventing accidental removal of pre-existing folders.
