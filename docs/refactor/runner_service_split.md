# Runner Service Split (completed)

> Source of truth for how the runner was decomposed into injectable services. Tracks are complete; this file now summarizes the final shape and where to find evidence.

## Current state

- `runner.run` orchestrates typed services only; side effects flow through adapters injected via `RunDependencies`.
- Services: `MetadataResolver`, `AlignmentWorkflow`, `ReportPublisher`, and `SlowpicsPublisher` live under `src/frame_compare/services/` with DTOs and factories in `interfaces/` + `services/factory.py`.
- Dependency injection is the only supported path. The legacy `_run_legacy_publishers` path was retired on 2025-11-19; requests for it emit warnings only.
- Public flags: `--service-mode` drives the service publishers; `--legacy-runner` is retained for compatibility warnings only. See README flag table and `docs/DECISIONS.md` entries on 2025-11-19.

## Key outcomes

- ✅ Service-mode publishing is the default; HTML/slow.pics outputs route through adapters so tests can stub I/O and network usage.
- ✅ CLI shims delegate to `runner.run` after preflight; `default_run_dependencies()` is constructed inside the runner with runtime context (cfg, reporter, cache roots).
- ✅ Layout/logging parity is preserved: CLI output and JSON tails match the pre-split behavior while surfacing service-mode warnings and availability flags.
- ✅ Tests cover sequencing and adapters: `tests/runner/test_runner_services.py`, `tests/services/test_publishers.py`, `tests/services/test_metadata.py`, `tests/services/test_alignment.py`.

## References

- Decisions: docs/DECISIONS.md (2025-11-19 entries for service-mode defaults and CLI flag retirement; 2025-11-15–11-18 entries for alignment/metadata DTOs).
- Changelog: CHANGELOG.md entries on/after 2025-11-19 record the rollout and flag notes.
- Related docs: README flag table, docs/README_REFERENCE.md publishing section.

## Residual follow-ups

- None tracked here; any future adapter reshuffling should land in `docs/refactor/refactor_cleanup.md` with new decision log entries.
