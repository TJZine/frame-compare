---
name: verification-strategy
description: Use when a Frame Compare task needs an explicit proof surface or when the correct verification depth is unclear.
---

# Verification Strategy

Read the runbook and matching boundary skills, apply any stronger required gate, and
choose the smallest proof that covers the risk:

- regression/contract test for a stable behavior defect or public contract;
- existing focused tests plus static checks for invariant refactors;
- integration/manual proof for runtime, Docker, Windows, or visual behavior;
- workflow/documentation verification for control-plane-only edits.

Record:

```text
VERIFICATION_RECORD
RISK: low | medium | high
PRIMARY_MODE: regression | contract | invariant | integration | manual | workflow
RATIONALE:
TEST_DECISION: add | update | existing coverage sufficient | not applicable
COMMANDS_AND_EXPECTED_OUTCOMES:
UNAVAILABLE_OR_DOCUMENTED_ONLY_PROOF:
```

Avoid snapshots and tests that merely restate implementation details. Full-suite
verification does not replace targeted proof.
