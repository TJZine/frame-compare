---
name: python-test-design
description: Use when changing Frame Compare pytest coverage, fixtures, CLI tests, mocks, property tests, subprocess tests, or runtime-boundary verification.
---

# Python Test Design

Protect stable behavior at the highest observable seam. List failure modes before
writing tests. A bug regression must fail on pre-fix code once at the highest
reproducing seam. Ask: could a user-visible bug ship if this test were deleted?

## E2E first

- Put feature proofs in `tests/e2e/`: run the installed `frame-compare` executable
  as a child process on generated media, with an isolated `--root`, and leave
  `command.txt`, stdout, stderr, run output and a checked `summary.json` artifact.
- Read only exit codes, stdout, stderr and produced files. Never import
  `frame_compare`, mock or monkeypatch it, reach the network or use snapshots.
- The CLI tier needs no media runtime. The media tier is marked `e2e` and
  `vs_required`, and runs only when `FRAME_COMPARE_E2E_REQUIRE_MEDIA=1`; use
  `FRAME_COMPARE_E2E_ARTIFACTS` for its artifact root. Only Docker enables it.
- Bound every `subprocess.run` or console-entrypoint invocation with a timeout;
  bound every `Popen` `communicate()`/`wait()` path and terminate or kill children
  during failure cleanup.
- Assert CLI exit codes and separate stdout/stderr. Parse JSON; use semantic
  help/output fragments rather than serialized-text matches or full snapshots.
- Retain real-runtime integration and viewer proofs. A native suite using the
  `tests/conftest.py` VapourSynth mock does not establish runtime capability;
  report the matching Docker, browser, distribution or Windows proof.

## Parallel and cached verification

- Full native command: `uv run --no-sync pytest -q -n4 --dist loadgroup`.
  Focused selections may stay serial; do not add parallelism to `addopts`.
  Native CI uses `-n auto --dist loadgroup`; Windows portable CI stays serial.
- New tests must be parallel-safe: use `tmp_path` and `monkeypatch`, avoid fixed
  paths or ports, and use `xdist_group` only with a stated concrete reason.
  Existing `browser` grouping protects a shared Chrome profile; `alignment-u4`
  grouping generates its session media on one worker.
- The full `bash tools/verify_docker_integration.sh` gate uses ten workers with
  `--dist loadgroup` for E2E, integration and VS tests, plus runtime and
  production-image proofs. Follow the runbook's runtime/dependency/media triggers.
  `--pytest-path tests/e2e` is focused development/scenario proof, not a substitute
  for a required full gate. Rebuild after `docker-test` dependency or `uv.lock`
  changes before using the new plugin; the default builds, while `--no-build`
  requires known-current images.
- `FRAME_COMPARE_TEST_MEDIA_CACHE` enables only u4 media caching. The verifier
  exports `/workspace/generated/test-media-cache` (host `generated/test-media-cache`),
  using `<cache>/<generator>/<key>/`. SHA-256 includes exact generator source and
  complete FFmpeg version output obtained with an explicit timeout. Publish on the
  same filesystem and prune only that generator's old keys. Consume temporary
  symlinks so indexes stay outside the cache; unset the variable for temporary
  generation. Run verifiers one at a time per checkout because pruning cannot
  overlap. E2E media is uncached; no CI cache was added, Docker CI retains
  `--no-cache`, and cold regeneration has no warm-cache speedup.

## One owner per observable behavior

Group by behavior, not function. Keep the strongest owner; prove duplicates are
covered by a mutation that fails that owner's assertion. Distinct cases reach a
unique production branch or boundary, or a mutation fails one but not another;
consolidate shared setup into parameter rows without losing cases or assertions.
User-visible outputs include exit codes, documented streams, written files and
persisted formats, external requests, hangs/leaks/lost files, VSView, Windows
install/update behavior, documented API results/errors, default warnings/errors,
and cache identity/reuse decisions.

**Flow rule:** follow production callers. A value is internal only if it never
changes a user-visible output's content; debug-log appearance does not count.
Reaching output makes it a case of that output, not an automatic keep. Keep an
edge only with a cited production branch/boundary no retained output test reaches.
Internal assertions (call counts/order, intermediate fields, private values,
undocumented logs/progress) are never a reason to keep a test.

Keep isolated tests only in these categories:
- `owner`: strongest proof of an observable behavior E2E/integration cannot observe.
- `edge`: a distinct boundary input and its user-visible consequence, including
  negative offsets, retiming, VFR and `match_fps`; cite the production branch.
- `failure`: otherwise untriggered hangs, leaked children, partial/lost files,
  wrong exit/error codes or corrupted persisted state.
- `contract`: documented CLI/API behavior, persisted formats, frozen strings or
  release/Docker/Windows workflow contracts; cite the document/writer and field,
  byte or key. Each element has one owner.
- `network`: slow.pics/TMDB through strict RESPX or exhaustive `MockTransport`.
- `security`: path escape, secret redaction and signature verification.
- `platform`: platform-specific behavior, including distinct POSIX/Windows cases.

## Retention rules

**R1: test-only production code.** Functions, classes, methods, modules, parameters
or branches with no tracked caller outside tests in `src/`, `tools/`, `.github/`
or project entry points, and no documented CLI/API contract, are test-only.
Check references with `git grep`; do not add production seams solely for tests.
Remove tests whose only subject is such a symbol. If retained tests use it as an
oracle, inline independently expected values or use the real API, then remove the
symbol when no retained caller needs it, within authorized production scope.

**R2: program-written data.** For each validator/parser/constructor entry point
reading data the program writes itself (evidence, caches, run records, reports,
VSView sessions or internal carriers), keep one test per distinct failure outcome:
a warning/refusal, documented error, cache miss or unavailable fallback. Different
malformed-data branches reaching that same outcome are redundant. This does not
apply to user-authored config/flags/env/filenames/presets/edited files, external
FFmpeg/ffprobe/HTTP/plugin data, security checks or cache identity/reuse decisions;
retain their distinct branch cases.

## Test boundaries and junk

Mock HTTP, subprocess, clock, browser and heavy-runtime boundaries, not owned
collaborators. Reject unexpected HTTP requests and verify expected routes. Keep
fixtures local and typed; use `tmp_path`, `monkeypatch` and isolated environments.
Restore resources deterministically; never run `CliRunner` concurrently. Use
property tests only for genuine input domains with stable invariants.
Reject no-op assertions, self-comparisons, expected values computed by the subject,
copied inventories/constants without an independent source, source/import/string
greps guarding no user-facing key/byte/path, private unobservable call shape/order,
mocks implementing the asserted behavior and test-only hooks. Tests checking only
internal outcomes do not justify retention. Do not weaken retained assertions.
