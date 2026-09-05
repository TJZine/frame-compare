---
name: debugging-remediation
description: Use when Frame Compare has a bug, regression, failing test, unexplained runtime behavior, or user-reported symptom where the cause is unknown or easy to misdiagnose.
---

# Debugging Remediation

## Overview

Use this skill to debug before fixing.

Turn an unclear symptom into a source-backed explanation, a bounded owner seam, and a verification path.

## Use This Skill For

- User-reported bugs where the cause is unknown
- Failing or flaky tests, type-check failures, lint failures, import-layer failures, or runtime errors
- CLI/config contract regressions
- FFmpeg, VapourSynth, Docker, Windows portable, TMDB, slow.pics, or browser-open behavior
- Review findings that require reproduction or source audit before accepting the proposed fix

## Debugging Contract

Before proposing a fix, establish:

- exact symptom and expected behavior
- smallest reliable reproduction or best available observational proof
- failing layer and nearest owner boundary
- evidence distinguishing credible alternative causes when any remain
- verification mode and command/manual proof that will prove the fix

If reliable reproduction is impossible, say so and gather enough diagnostic evidence to make the next probe meaningful.

## Investigation Sequence

1. Frame the symptom: command, inputs, environment, expected behavior, observed behavior, frequency, and first known bad change when available.
2. Reproduce or observe through the cheapest real boundary: targeted pytest, CLI invocation, static check, Docker/runtime verification, Windows host proof, log/stack inspection, or source audit.
3. Isolate the layer using the relevant boundary skill:
   - CLI options, config precedence, streams, or exit behavior: `cli-contract-boundaries`
   - generated reports, overlays, or presentation: `report-output-patterns`
   - runtime integrations: `runtime-integration-boundaries`
   - filesystem persistence: `persistence-boundaries`
   - ownership/import layer: `architecture-boundaries`
4. When causality remains ambiguous, compare falsifiable hypotheses. A directly
   reproduced, source-confirmed cause does not require an invented alternative:

```text
HYPOTHESIS:
EVIDENCE_FOR:
EVIDENCE_AGAINST:
NEXT_PROBE:
STATUS: open | rejected | likely | confirmed
```

5. Choose the remediation seam: owner file/module, files in scope, files out of scope, and stop-and-replan triggers.
6. Use the relevant runbook verification gate; consult `verification-strategy` only
   when the proof surface remains unclear.

## Output Shape

For intermittent or multi-layer failures, use this record when it helps retain the
investigation. For a direct failure, the cause, fix, and proof can be a short note:

```text
DEBUGGING_RECORD
SYMPTOM:
REPRODUCTION_OR_OBSERVATION:
ROOT_CAUSE:
REJECTED_CAUSES:
OWNER_SEAM:
FIX_SUMMARY:
VERIFICATION:
RESIDUAL_RISK:
```

## Common Mistakes

- Fixing the stack-trace line when the bad value originates upstream
- Widening a CLI/config contract without updating docs and tests
- Treating Docker, Windows, or VS behavior as verified from source reads alone
- Letting a symptom file absorb policy that belongs to a service, runtime, or config owner
