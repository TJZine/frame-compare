---
name: python-test-design
description: Use when changing Frame Compare pytest coverage, fixtures, CLI tests, mocks, property tests, subprocess tests, or runtime-boundary verification.
---

# Python Test Design

Protect stable behavior at the highest observable seam. List the failure modes before
writing the test.

## E2E first

- Put credible feature proofs in `tests/e2e/`: run the installed `frame-compare`
  executable as a child process against generated media, use an isolated `--root`,
  and leave the S3 artifact (`command.txt`, streams, run output, `summary.json`).
- E2E tests read only exit codes, stdout, stderr, and produced files. They do not
  import `frame_compare`, mock or monkeypatch it, reach the network, or use snapshots.
- The CLI tier needs no media runtime. The media tier is marked `e2e` and
  `vs_required`, and runs only when `FRAME_COMPARE_E2E_REQUIRE_MEDIA=1`; use
  `FRAME_COMPARE_E2E_ARTIFACTS` for its artifact root. Only the Docker gate enables it.
- Give every direct `subprocess.run` or console-entrypoint invocation an explicit
  timeout; bound every `Popen` `communicate()`/`wait()` path and terminate or kill the
  child during failure cleanup.
- For CLI behavior assert exit code and separate stdout/stderr, parse JSON rather than
  matching serialized text, and assert semantic help/output fragments rather than full
  help snapshots.

## Retained real-runtime integration

Keep `tests/integration/`, `tests/vs/`, and other real-runtime proofs that exercise the
changed FFmpeg/VapourSynth boundary. A passing native suite with the `tests/conftest.py`
VapourSynth mock does not establish runtime capability; use and report the runbook's
matching Docker, browser, distribution, or Windows proof.

## Isolated tests: keep categories only

Before writing one, answer: what behavior does it protect; what credible regression
fails it; why do E2E and integration not already catch it; and does it need a production
seam that no production caller needs? If the last answer is yes, do not write it.

Use only these S6 categories: `failure-mode` (timeouts, malformed data, partial or
atomic writes, cancellation, cleanup); `network` (strict HTTP boundary tests);
`security`; `numeric`; `contract`; and `platform`. In isolated tests, mock HTTP,
subprocess, clock, browser, and heavy-runtime boundaries, not the owned collaborator.
Make HTTP tests reject unexpected requests and verify expected routes with strict RESPX
configuration or an exhaustive `MockTransport` handler. Keep fixtures local and typed;
use `tmp_path`, `monkeypatch`, and isolated environments. Restore resources
deterministically and never run `CliRunner` concurrently. Use property tests only for
genuine input domains with stable invariants.

Delete or reject tests that are junk: no assertion or an assertion that cannot fail;
self-comparison or an expected value computed by the code under test; copied inventory,
manifest, export list, or constant without an independent source; source/import/string
grep that guards no user-facing key, byte, or path; private call shape or order where
order is unobservable; a mock implementing the behavior asserted; a duplicate contract
invocation; or a test that only keeps a test-only export, wrapper, or hook alive.
