---
name: review-request
description: Use when Frame Compare needs an independent review or when reviewer findings must be adjudicated.
---

# Review Lifecycle

Follow the runbook's Review policy: use independent review when requested or a
concrete consequential risk merits a second assessment. State the reason; file
size, location, or a high-risk label alone does not require a reviewer. Review a
plan separately only when its seam or public contract remains costly to get wrong.

Send the reviewer the task, files, invariants, non-goals, verification evidence,
known risks, and requested output. Reviewers stay read-only and lead with concrete
findings ordered by severity.

For every finding, inspect the cited source and record its identifier, priority,
evidence, disposition, rationale, required action, verification, and owner/trigger
when deferred:

- accept when current source confirms the risk; implement or block on the action;
- modify when the concern is real but scope, owner, severity, or remedy changes;
- reject only with stronger counter-evidence, never preference alone;
- defer only with a non-blocking rationale, owner, and concrete trigger;
- validate by naming the exact missing proof; do not treat it as closed.

Re-review only when a material review surface changed or accepted findings need
closure; do not require duplicate clean gates.
