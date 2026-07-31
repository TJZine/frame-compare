---
name: closeout-verification
description: Use when Frame Compare work is about to be called done, staged, committed, pushed, handed off, or closed.
---

# Closeout Verification

Use the runbook's risk-matched gate, then inspect `git status --short`, the diff
stat, and the task-owned diff. Preserve unrelated changes.

Before claiming completion, confirm:

- the requested outcome is present;
- fresh verification passed and its output was read;
- authority docs changed when their contract changed;
- no required runtime/platform proof is being overstated;
- remaining risks or blockers are named.

Only stage, commit, push, or open a PR when requested. Stage intended files only.
