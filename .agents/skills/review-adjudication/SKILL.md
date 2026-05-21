---
name: review-adjudication
description: Use when Frame Compare receives code review comments, PR suggestions, reviewer findings, or external feedback that must be accepted, modified, rejected, deferred, or validated.
---

# Review Adjudication

## Overview

Use this skill to decide what to do with review feedback.

Verify the claim, calibrate severity to Frame Compare, choose an action, and avoid both blind acceptance and reflexive rejection.

## Use This Skill For

- PR review suggestions
- AI reviewer findings
- Human review feedback
- Conflicting reviewer comments
- Feedback that may be valid but too broad for the current task

## Evidence Standard

Classify each important claim:

- `Observed`: direct code, diff, test, config, docs, or command output
- `Inferred`: reasonable conclusion from observed evidence
- `Unknown`: not established

Evidence hierarchy:

1. current code and diff behavior
2. fresh test or reproduction output
3. tracked Frame Compare docs, verifier rules, and config
4. official framework/vendor docs for external behavior
5. established best practices
6. style preference

## Verdicts

Use exactly one:

- `Accept`
- `Accept with modification`
- `Reject`
- `Defer`
- `Needs validation`

Use `Needs validation` narrowly and name the exact evidence needed.

## Priority

- `8-10`: security, data loss, severe correctness, breaking public contract, release-path breakage
- `6-7`: serious bug risk, missing safeguard, high-risk boundary drift
- `4-5`: maintainability, moderate reliability, typing/error-handling weakness
- `1-3`: style, naming, minor docs, local cleanup

Adjust upward for CLI/config contracts, release paths, runtime integrations, filesystem persistence, import layers, and current hotspots.

## Sequence

1. Normalize and cluster comments by underlying concern.
2. Identify affected files and owner boundary.
3. Load matching boundary skills when implicated.
4. Verify the claim against current source and tests.
5. Separate concern from proposed implementation.
6. Assign verdict, priority, category, and confidence.
7. Choose action and verification with `verification-strategy`.

## Output Shape

```text
REVIEW_ADJUDICATION
ITEM:
VERDICT:
PRIORITY:
EVIDENCE:
REASONING:
ACTION:
VERIFICATION:
RESIDUAL_RISK:
```

## Common Mistakes

- Treating every reviewer comment as blocking
- Rejecting feedback without stronger counter-evidence
- Letting a reviewer redefine public contract scope without updating docs and plans
- Skipping verification because the change came from review
