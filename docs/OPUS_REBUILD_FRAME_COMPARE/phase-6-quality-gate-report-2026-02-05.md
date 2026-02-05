# Phase 6 Quality Gate Report (2026-02-05)

## Environment
- Host: /Users/tristan/Software/frame-compare
- Python: 3.13 (repo .venv)
- Date: 2026-02-05

## Summary
- PASS: 7 items
- FAIL: 1 item
- WARN: 2 items

## Gate Results

1. `frame-compare run` executes full pipeline
- Status: FAIL (not executed)
- Reason: Requires real video inputs + config; no sample videos are present in the repo.
- Notes: This gate should be run manually with real inputs once available.

2. `frame-compare wizard` configures interactively
- Status: PASS (Docker)
- Command: `docker run --rm -i --entrypoint /bin/bash frame-compare:dev -lc "mkdir -p comparison_videos && printf 'comparison_videos\nn\npublic\nn\n\n' | frame-compare wizard"`
- Result: Exit 0
- Notes: Non-TTY warning from `getpass` (expected in non-interactive stdin). Config was written inside container.

3. `frame-compare doctor` checks dependencies
- Status: PASS (Docker)
- Command: `docker run --rm frame-compare:dev doctor --json`
- Result: JSON payload with `success=true`. Optional checks (`dovi_tool`, `TMDB API key`) reported as fail but not critical.

4. All CLI options work per api-design.md
- Status: PASS (tests)
- Command: `.venv/bin/pytest -q tests/cli/test_cli_commands.py`
- Result: `28 passed`

5. Exit codes match `ExitCode` enum
- Status: PASS
- Command: `.venv/bin/pytest -q tests/cli/test_exit_codes.py`
- Result: `1 passed`

6. FramePlan determinism verified (subprocess test passes)
- Status: WARN (closest available determinism test)
- Command: `.venv/bin/pytest -q tests/orchestration/test_preflight.py::TestDiscoverInputs::test_discover_inputs_sorted_case_insensitive`
- Result: `1 passed`
- Notes: No explicit “subprocess determinism” test found in repo; this is the determinism check in current test suite.

7. Tonemap wiring integration tests pass
- Status: PASS
- Command: `.venv/bin/pytest -q tests/render/test_tonemap_wiring.py`
- Result: `7 passed`

8. VSPreview unit tests pass (or skipped if deferred)
- Status: PASS
- Command: `.venv/bin/pytest -q tests/vspreview/test_overrides.py`
- Result: `13 passed`

9. Docker verification passes (real deps, zero skips)
- Status: PASS
- Command: `bash tools/verify_docker_integration.sh`
- Result: Docker build + tests completed, `80 passed`, zero skips.
- Warning: docker-compose `version` attribute is obsolete (warning emitted by docker).

10. E2E tests pass
- Status: PASS
- Command: `.venv/bin/pytest -q tests/e2e`
- Result: `2 passed`

## Open Issues / Blockers
- `frame-compare run` full pipeline not executed due to lack of real input videos/config in repo.

## Recommendations
- When sample inputs are available, run `frame-compare run` against a real comparison set to close item #1.
