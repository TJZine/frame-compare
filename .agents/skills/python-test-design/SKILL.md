---
name: python-test-design
description: Use when changing Frame Compare pytest coverage, fixtures, CLI tests, mocks, property tests, subprocess tests, or runtime-boundary verification.
---

# Python Test Design

Protect stable behavior through the nearest public seam:

- establish a defect through a failing regression test or the best available
  observational proof; the test may itself be the reproduction. For refactors,
  prove the invariant without mirroring implementation branches;
- assert exported behavior, typed results, filesystem effects, CLI contracts, or
  integration-boundary requests rather than private fields and call order;
- keep fixtures local and typed; use `tmp_path`, `monkeypatch`, and isolated
  environments so tests cannot share persisted or process state;
- in isolated tests, mock HTTP, subprocess, clock, browser, and heavy runtime
  boundaries, not the owned collaborator whose behavior is under test. Real
  integration proof must exercise the changed external boundary;
- cover malformed/partial external data, timeout/cancellation, cleanup, and expected
  error translation when those paths change;
- give every direct `subprocess.run` or console-entrypoint invocation an explicit
  timeout; bound every `Popen` `communicate()`/`wait()` path and terminate or kill the
  child during failure cleanup;
- make HTTP tests reject unexpected requests and verify expected routes were used;
  use strict RESPX configuration or an exhaustive `MockTransport` handler;
- for CLI behavior assert exit code and separate stdout/stderr, and parse JSON rather
  than matching serialized text; assert stable semantic help/output fragments rather
  than full help or output snapshots;
- restore patches/resources deterministically and never run `CliRunner` concurrently;
- use property tests only for genuine input domains with stable invariants;
- avoid giant snapshots, private probes, test-only production hooks, and tests that
  simply restate implementation structure.

Check what actually ran: `tests/conftest.py` supplies a VS mock when the runtime is
absent, and native/browser/platform tests may skip. A passing Python suite does not
establish those capabilities. Use the runbook's matching runtime, report-browser,
distribution, or Windows proof and report relevant skips. Report state tests reuse
the locked Node runtime through `tests/services/node_harness.py`.

Use the runbook's applicable static and suite gates without repeating still-current
checks. If the apparent test seam is private, investigate the nearest observable
behavior and existing tests. Choose meaningful proof within the current owner;
do not add a production abstraction solely for test access. Escalate only a
consequential unresolved contract or scope decision.
