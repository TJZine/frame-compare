---
name: review-request
description: Use when Frame Compare needs an adversarial review of a plan, implementation diff, workflow artifact, skill, launcher, release path, or completed work before closeout or handoff.
---

# Review Request

## Overview

Use this skill to request the right review with bounded context.

The goal is to give a reviewer enough evidence to find real defects without handing them unbounded history or letting them change task ownership.

## Use This Skill For

- Plan review before implementation
- Implementation review before closeout
- Workflow/control-plane, launcher, skill, or runbook review
- CLI/config contract, Docker/runtime, Windows/release, or hotspot review
- Risky local changes before staging, committing, or handoff

## Review Routing

- Use tracked `reviewer` for adversarial review.
- Use `frame-compare-cleanup-review` for cleanup/refactor plans and implementations.
- Use `frame-compare-feature-review` for feature plans and implementations.
- Use `frame-compare-workflow-harness-review` for workflow/control-plane, skill topology, and review-loop audits.
- Use a narrow reviewer sidecar when the target is smaller than a launcher session.

Keep reviewers read-only.

## Context Packet

Pass a bounded packet:

```text
REVIEW_REQUEST
TASK:
TASK_FAMILY:
RISK_TIER:
REVIEW_TARGET:
PLAN_OR_ARTIFACT:
FILES_IN_SCOPE:
FILES_OUT_OF_SCOPE:
KEY_INVARIANTS:
VERIFICATION_RUN:
KNOWN_RISKS:
WHAT_TO_PRIORITIZE:
OUTPUT_EXPECTATION:
```

For diffs, include `git diff --stat`, exact changed files, commands run, and observed results.

For workflow/skills, include triggering examples, non-triggering examples, affected authority docs, and expected verification.

For high-risk Frame Compare surfaces, add explicit review prompts instead of
generic risk wording:

- CLI/config: invalid inputs, Pydantic validation failures, exit code mapping,
  stdout/stderr separation, JSON cleanliness, and traceback leakage.
- VapourSynth/runtime/media metadata: malformed, missing, unknown, and explicitly
  unspecified values; deterministic fallback behavior; lazy runtime imports.
- Windows portable/release/workflows: explicit subprocess timeouts, semantic
  PowerShell/YAML assertions, CI/local command parity, and documented-only
  verification gaps.
- Orchestration/hotspots: state transitions, partial failures, cleanup, and
  typed result/union seams that were broadened to `object`, `Any`, or ad hoc
  dicts.
- Test-suite changes: brittle exact strings, call-order/log-shape assertions,
  private seam justification, duplicate helpers, stale pragmas, broad fixtures,
  undeclared markers, skipped runtime tests, and hidden external dependencies.

## Reviewer Prompt Rules

Ask the reviewer to lead with findings ordered by severity, cite files and lines, separate blockers from optional improvements, identify missing tests or weak verification, check scope creep and owner-boundary violations, and say explicitly when no blocking findings are found.

## Defect Checklist

Review for correctness, public contract drift, security/privacy, filesystem/data-loss risk, architecture boundary drift, maintainability, performance/resource leaks, insufficient verification, docs drift, and unrelated changes.

When the target is a crucial PR/commit review or release-path change, ask the
reviewer to explicitly close out each applicable high-risk prompt as either a
finding, no material issue, verification gap, or out of scope with reason.

## After Review

Use `review-adjudication` before implementing findings.

## Common Mistakes

- Asking for "thoughts" instead of a concrete review contract
- Letting a reviewer use write access
- Failing to pass verification evidence
- Treating reviewer output as automatically correct
