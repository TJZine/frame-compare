# Test Plan — Paths Root Lock (Phase 2)

## Unit targets
- `frame_compare.py`: cover `_prepare_preflight` precedence (`tests/test_paths_preflight.py`):
  1. CLI `--root` override takes priority.
  2. `$FRAME_COMPARE_ROOT` env fallback.
  3. Sentinel discovery from CWD when no overrides.
- `frame_compare.py`: verify `_abort_if_site_packages` rejects site/dist-packages paths and reports offending labels.
- `frame_compare.py`: ensure `_collect_path_diagnostics` reports workspace/media/config paths, writability flags, and warnings without mutating the filesystem.
- `_resolve_workspace_subdir`: regression test that absolute paths or escapes raise `CLIAppError`.
- `src/config_template.copy_default_config`: confirm atomic write semantics (temp file + `os.replace`).
- CLI smoke tests (`CliRunner`): `--write-config` creates `ROOT/config/config.toml`; `--diagnose-paths` rejects site-packages roots.

## Writability probes
- Temporary directories marked read-only (`os.chmod`/`icacls` equivalent) to ensure preflight exits before heavy work.
- Mock failure path for `_atomic_write_json` to confirm seeding guard surfaces original `OSError`.

## Integration matrix
- Fixture scripts in `tests/integration/test_paths_root_lock.py`:
  1. Repo checkout run (`python frame_compare.py --diagnose-paths`) — ensure outputs remain under repo.
  2. Simulated site-packages install (temporary directory named `lib/python/site-packages/frame_compare`) — verify guard aborts before screenshotting.
  3. Read-only root (chmod 0555) — expect early failure with `code=2` and no partial writes.
  4. Custom root via env/flag — ensure diagnostics resolve to provided root and no writes occur outside.
- Smoke tests for `--diagnose-paths`: CLI returns zero exit code and prints single-line JSON.

## CI considerations
- Run integration matrix on Linux + Windows (GitHub Actions) with explicit cleanup of temp dirs.
- Use pytest markers (`@pytest.mark.skipif`) for permissions-sensitive tests when running on filesystems without chmod support (e.g., Windows FAT temp).
