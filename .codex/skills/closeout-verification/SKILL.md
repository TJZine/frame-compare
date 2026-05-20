---
name: closeout-verification
description: Use when Frame Compare work is about to be called done, fixed, ready, staged, committed, pushed, handed off, or closed after code, docs, workflow, or review changes.
---

# Closeout Verification

## Overview

Use this skill before making completion claims or taking branch/PR closeout actions.

The goal is evidence-backed closeout: verify the right surface, inspect the diff, preserve user changes, and report the actual state.

## Closeout Gate

Before saying work is complete, answer:

1. What changed?
2. What command or manual proof verifies the changed surface?
3. Did I run it fresh in this workspace?
4. Did I read the output and exit code?
5. Does the current diff contain only intended changes?
6. Are there unrelated dirty files I must leave alone?
7. Did authority docs, generated docs, plans, skills, or workflow files need updates?
8. Is an adversarial review required or requested?

If any answer is missing, do not claim completion. State the actual status and missing proof.

## Verification Routing

Use the runbook first:

- docs-only or small internal refactors: fast local sanity
- most code changes: focused tests plus `pyright`, `ruff`, and import-linter when imports changed
- CLI/config, hotspots, Docker/runtime, Windows/release, or workflow authority changes: full verification
- Docker/runtime changes: full verification plus `bash tools/verify_docker_integration.sh`
- Windows portable/release changes: run the Windows path on a compatible host or mark it documented-only

## Diff Audit

Run or inspect:

```bash
git status --short
git diff --stat
git diff -- <changed-files>
```

Classify changes:

- made by this task
- pre-existing user or workspace changes
- expected generated changes
- unexpected changes requiring investigation

Never revert unrelated user changes.

## Branch, Commit, Push, PR

Only perform branch/commit/push/PR actions when the user asked for them.

Before staging, verify or clearly state the missing verification, stage only intended files, and avoid `git add .`.

Before committing, inspect staged diff and use conventional commits.

## Final Response Checklist

Include:

- concise change summary
- verification run and result
- review result when applicable
- files of interest
- remaining risks or blockers

## Common Mistakes

- Claiming a release path is verified without the required platform
- Forgetting unrelated dirty files
- Running the wrong verification tier for public CLI/config behavior
- Calling work done before inspecting the final diff
