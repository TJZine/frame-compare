# ADR 0001 — Workspace Root Lock & Path Policy

Status: Accepted  
Date: 2025-10-24  
Owner: Tooling / Release

## Context
- Default config seeding may currently target `site-packages`, leading to permission issues and freezes during screenshot generation (`PATHS-AUDIT.md`).
- Workspace discovery relies on relative paths that drift with the working directory, so installers running inside package directories inherit read-only roots.
- We must provide a low-risk, multi-platform plan that locks configuration and IO under a predictable project root without breaking existing repo workflows.

## Decision

### Root resolution policy
1. CLI `--root` flag (highest priority).
2. `FRAME_COMPARE_ROOT` environment variable.
3. Nearest ancestor of the working directory containing any sentinel: `pyproject.toml`, `.git`, or `comparison_videos`.
4. Fallback to current working directory.

Resolved root becomes the canonical workspace for config, metrics, screenshots, and caches.

### Path policy
- **Config search order**: `ROOT/config/config.toml` (primary). If missing, atomically seed from template. Legacy support for `ROOT/config.toml` remains but emits a deprecation warning instructing relocation.
- **Input directory default**: `ROOT/comparison_videos`.
- **Screenshot output**: `ROOT/comparison_videos/screens`.
- Additional generated artifacts (frame metrics, audio offsets, selection metadata) live under `ROOT`.

### Ban & guard
- Reject any root that equals or sits under `site-packages`/`dist-packages`. Abort with actionable guidance to pass `--root`/`FRAME_COMPARE_ROOT`.
- Never create or delete artefacts alongside installed package files; all writes route through `ROOT`.

### Atomic seeding & writability probes
- Seed templates via temp-file + `os.replace` (`tempfile.NamedTemporaryFile`, `os.replace`) to maintain atomicity.
- Before running analysis:
  - Probe writability for `ROOT/config/`, `ROOT/comparison_videos/`, and `ROOT/comparison_videos/screens/` (touchless checks: ensure parent exists, `os.access(..., W_OK)`).
  - Fail fast with explicit errors when any directory is missing or read-only.

### Migration / warnings
- Detect legacy configs at `ROOT/config.toml` and emit a migration warning pointing to `ROOT/config/config.toml` and `--diagnose-paths` for confirmation.
- Document manual relocation steps; a convenience helper remains a potential follow-up.

### Risk analysis & mitigations
- **Windows ACL quirks**: Use `os.access` + informative error; document requirement to run from writable root.
- **Temp file collisions**: Place temp files inside target directory to guarantee same filesystem; ensure clean-up on failure.
- **Editable installs**: Root detection via sentinel ensures running from repo/venv picks the project checkout instead of site-packages.
- **Non-interactive automation**: Support `--root` for CI scripts; document environment variable for headless contexts.

## Consequences
- Users set an explicit root when working outside the repo tree; `--diagnose-paths` surfaces the resolved paths and writability checks.
- Installed/package runs fail fast instead of freezing on permission errors; all generated artefacts stay under the selected workspace root.
- CLI helper `--write-config` ensures config seeding; additional migration automation remains optional.
- Tests must cover new root detection branches and writability failures (see `docs/tests_plan_paths_root_lock.md`).
