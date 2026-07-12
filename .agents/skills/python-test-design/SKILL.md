---
name: python-test-design
description: Use when changing Frame Compare pytest coverage, fixtures, CLI tests, mocks, property tests, subprocess tests, or runtime-boundary verification.
---

# Python Test Design

Protect stable behavior through the nearest public seam:

- reproduce a real defect before adding a regression test; for refactors, prove the
  invariant without mirroring implementation branches;
- assert exported behavior, typed results, filesystem effects, CLI contracts, or
  integration-boundary requests rather than private fields and call order;
- keep fixtures local and typed; use `tmp_path`, `monkeypatch`, and isolated
  environments so tests cannot share persisted or process state;
- mock HTTP, subprocess, clock, browser, and heavy runtime boundaries—not the owned
  collaborator whose behavior the test is meant to prove;
- cover malformed/partial external data, timeout/cancellation, cleanup, and expected
  error translation when those paths change;
- for CLI behavior assert exit code and separate stdout/stderr, and parse JSON rather
  than matching serialized text;
- restore patches/resources deterministically and never run `CliRunner` concurrently;
- use property tests only for genuine input domains with stable invariants;
- avoid giant snapshots, private probes, test-only production hooks, and tests that
  simply restate implementation structure.

Run the focused test first, then the runbook-required static and suite gates. Stop
when the only testable seam is private; resolve the production owner instead of
adding test-only access.
