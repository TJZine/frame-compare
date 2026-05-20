---
name: parallel-sidecars
description: Use when a Frame Compare task has optional read-only sidecars, blocking documentation research, adversarial review, or long waits that can be delegated without handing off implementation ownership.
---

# Parallel Sidecars

## Overview

Use this skill to delegate bounded read-only sidecars, documentation research, review passes, or wait states.

Default to no delegation. Delegate only when the sidecar is real, scoped, and materially improves reliability, throughput, context hygiene, or source quality.

## Use This Skill For

- Focused repo-doc or code discovery that does not take over implementation
- Adversarial review of a plan, diff, skill, workflow artifact, or release-path change
- Official docs research through `docs_researcher`
- Long waits, polling, or command observation through `monitor`

## Do Not Use This Skill For

- Immediate blocking work that belongs in the main thread
- Tasks with overlapping write scopes
- Unresolved planning, routing, or ownership decisions
- Any edit that should instead use `bounded-worker-execution`

## Decision Gate

Delegate only when:

1. the main session knows the exact sub-question or output needed
2. the sidecar can finish without changing the next local write scope
3. one tracked role can handle it
4. delegation materially improves reliability, throughput, context hygiene, or source quality
5. either local non-overlapping work remains, or the sidecar is substantial enough to isolate

## Role Routing

- `explorer`: focused repo discovery
- `reviewer`: adversarial review
- `docs_researcher`: official API/tool/platform documentation research
- `monitor`: waits, polling, or background verification

Do not route edits through read-only roles.

## Research Packet

Small docs lookups should return:

```text
DOCS_RESEARCH_PACKET
QUESTION:
SOURCES_CHECKED:
FINDINGS:
VERSION_OR_DATE_NOTES:
FRAME_COMPARE_IMPLICATION:
CONFLICTS_OR_UNCERTAINTY:
LOCAL_VERIFICATION_REQUIRED:
```

## Common Mistakes

- Delegating because multiple agents are available rather than useful
- Giving a sidecar a fuzzy brief
- Treating a research packet as final proof for security, dependency, packaging, or runtime decisions
- Trusting sidecar conclusions without checking cited evidence for high-risk work
