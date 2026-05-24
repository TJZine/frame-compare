---
name: python-test-design
description: Use when adding or changing Python tests, pytest fixtures, markers, CliRunner tests, tmp_path or monkeypatch usage, HTTPX/RESPX mocks, Hypothesis tests, subprocess tests, or runtime-boundary verification in Frame Compare.
---

# Python Test Design

## Overview

Use this skill to keep Frame Compare tests behavior-focused, isolated, deterministic, and useful as production evidence.

Tests should protect public seams and owner boundaries, not freeze incidental implementation shape.

## Research Basis

This skill is based on official pytest, HTTPX, RESPX, Hypothesis, subprocess, Typer, and Click documentation plus Frame Compare's current pytest config, fixtures, markers, and contract tests.

## Use This Skill For

- New or changed tests under `tests/**`
- Fixture, marker, monkeypatch, tmp-path, or capture changes
- CLI tests using `CliRunner`
- HTTPX/RESPX or no-network test boundaries
- Hypothesis/property-based tests
- Subprocess, FFmpeg, VapourSynth, Docker, or Windows portable test paths
- Snapshot-like output assertions

## Required Reading

1. [`pyproject.toml`](../../../pyproject.toml) for pytest options, markers, warnings, and type-checking differences between `src` and `tests`
2. [`tests/conftest.py`](../../../tests/conftest.py)
3. [`tests/integration/conftest.py`](../../../tests/integration/conftest.py) when integration/runtime fixtures are involved
4. Relevant existing tests near the changed owner
5. `docs/current-cli-contract.md` when CLI behavior is involved

## Core Rules

- Prefer behavior-focused tests over implementation-shaped tests.
- Assert observable outcomes: exit code, stdout/stderr, parsed JSON, persisted files, HTTP request shape, generated paths, state transitions, or typed errors.
- Use `tmp_path` for filesystem writes. Do not write into repo paths, user home, shared `/tmp`, or global fixture directories unless explicitly testing those paths.
- Use `monkeypatch` for env vars, cwd, globals, and boundary replacement; keep patches local to a test or fixture.
- Do not introduce undeclared markers. Add new markers to `pyproject.toml` only when they describe a real routing category.
- Default unit tests must not require network, VapourSynth, FFmpeg, PowerShell, or Docker.
- Pair runtime-dependent tests with existing markers/skips such as `integration`, `vs_required`, `slow`, or `network`.
- Each test must own its filesystem, env, network mocks, subprocesses, threads, and clocks.

## CLI Tests

- Use `typer.testing.CliRunner`.
- Assert `result.exit_code`, `result.stdout`, and `result.stderr` directly when stream placement matters.
- Parse JSON with `json.loads(result.stdout)` instead of string matching.
- Prefer semantic help assertions over full Rich-rendered snapshots unless the exact layout is the contract.
- Use isolated filesystem or `tmp_path` for CLI paths and generated files.

## HTTP Tests

- Do not hit real network in default tests.
- Inject `httpx.Client`, `httpx.AsyncClient`, or transports where possible.
- Use `httpx.MockTransport` for simple response mapping.
- Use RESPX when route matching, call assertions, side effects, or richer HTTPX mocking matter.
- Keep `assert_all_mocked` and `assert_all_called` strict when the route is part of the contract; loosen only with a local reason.

## Hypothesis Tests

- Use Hypothesis for invariants, parsers, normalizers, serializers, option merging, idempotence, and boundary-heavy pure functions.
- Avoid Hypothesis for tests that depend on wall clock, random global state, live network, subprocess timing, or unordered output unless those values are controlled and normalized.
- Tune expensive tests with explicit settings or profiles instead of scattering arbitrary low example counts.

## Subprocess And Runtime Tests

- Use subprocess tests only when process behavior is the contract: console entrypoints, packaging/module invocation, env isolation, cwd handling, stream encoding, timeout behavior, or exit status.
- Prefer `sys.executable`, argument lists, explicit `cwd`, explicit `env`, `capture_output=True`, `text=True`, `timeout=...`, and `check=False` so tests can assert failure output.
- Every direct `subprocess.run()`, `Popen`, PowerShell, FFmpeg, Docker, or
  console-entrypoint invocation in tests must have an explicit timeout or call a
  repo helper that applies one. Let `TimeoutExpired` fail clearly unless the test
  is specifically exercising timeout translation.
- For FFmpeg/VapourSynth/PowerShell/Docker paths, use the runbook's verification routing and mark or skip tests honestly when the local runtime is unavailable.

## Anti-Brittleness Rules

- Do not compare entire help output, tracebacks, timestamps, random IDs, temp paths, unordered collections, or styled Rich output unless that exact output is the public contract.
- Normalize dynamic values and assert stable structure or semantic fragments.
- Prefer semantic command assertions over exact YAML/PowerShell line fragments
  unless the literal text is itself the contract.
- Avoid parsing code or scripts with regexes that depend on indentation,
  one-line bodies, or brace columns. Use a small brace-depth/token helper or
  semantic regex around the exact command being protected.
- Avoid exact log event/call-shape assertions unless structured log fields are a
  documented diagnostic contract. Prefer behavior assertions plus a warning/error
  fired check for generic invalid-entry paths.
- Avoid private probes. If a test needs internals, consider a public seam, a real collaborator, or a narrower owner extraction.
- Private or underscore owner-seam patches are acceptable when they are the
  repo's deliberate test seam and the public path cannot deterministically reach
  the branch under test; record that reason in the test name or surrounding
  context.
- Do not hide cleanup in broad autouse fixtures unless the fixture's isolation contract is obvious and tested by use.
- Scan changed tests for duplicate helper definitions, stale file-level Pyright
  pragmas, undeclared markers, broad autouse fixtures, hidden network/runtime
  dependencies, and skips that silently remove coverage.

## Review Checklist For Test-Heavy Diffs

When reviewing a test-heavy PR or cleanup, explicitly check:

- Does each new assertion protect public behavior or an intentional owner seam?
- Could harmless formatting, log wording, temp path spelling, ordering, or
  capitalization break the test?
- Are malformed/negative cases covered for the code paths changed by the PR?
- Are runtime-dependent tests skipped honestly, and is the remaining unit
  coverage still meaningful without the runtime?
- Are all subprocess and shell invocations bounded by timeouts?
- Did test cleanup remove a check that was documenting deterministic behavior?

## Verification

- Run the touched test selection first.
- Then run the runbook-required gate for the changed surface.
- For test-only changes that alter fixtures, markers, or runtime assumptions, run enough of the affected suite to prove the fixture contract, not just the new test.

## Common Mistakes

- Testing implementation order instead of public behavior
- Using repo-global files instead of `tmp_path`
- Allowing real network in default tests
- Adding a marker without registering it
- Snapshotting Rich output when a parsed or semantic assertion would be stronger
- Treating skipped runtime tests as proof that the runtime path works
