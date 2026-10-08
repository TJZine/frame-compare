---
search:
  exclude: true
---

# Codex prompt: review remediation orchestrator

Paste everything below the line into a fresh Codex chat on the `frame-compare`
project (local environment, this checkout). Use a capable orchestrator model at
high reasoning.

---

You are the orchestrator for implementing the accepted findings of the
2026-10-08 comprehensive review. The governing plan is
`docs/plans/2026-10-08-review-remediation.md`. Read it in full, then `AGENTS.md`,
`.agents/project.md`, and the findings in
`docs/reviews/comprehensive-review-2026-10-08/REPORT.md` that each unit owns.
The plan is the specification; if anything conflicts with it, stop and tell me.

I authorize, for this plan only:

- separate Codex implementation and review chats through the
  `orchestrate-implementation-chats` skill, with model and reasoning effort passed
  explicitly from the `.codex/agents/*.toml` preset named for each unit, and one
  terminal callback from each child to this chat. Children cite this message as
  their authorization before calling back;
- local commits on `agent/e2e-test-strategy` made by you, one per unit plus the
  initial docs commit, staged by explicit path;
- the maintainer decisions D-01, D-02, D-03, and W-1 recorded in the plan.

I do not authorize pushes, PRs, branch switches, worktrees, rebases, resets,
stashes, dependency or lockfile changes, releases, signing, or requests to live
services. Children never commit.

Follow the plan's orchestrator procedure:

1. Baseline and docs commit.
2. Wave A dispatch, with the U1 design checkpoint handled by you.
3. Per-unit integration, cheap gates, and commit.
4. A `reviewer` chat per wave, including the deviations register,
   over-engineering hunt, and test map.
5. Wave B (U10, with its design checkpoint), then wave C (U11).
6. Heavy gates once at the end, serially.
7. CHANGELOG, then the execution record and the acceptance handoff.

When nothing useful remains while children run, end your turn and let their
callbacks resume you; do not poll.

Then stop. Your final message lists:

- commits (SHA and subject);
- each unit's preset and actual model and effort;
- gate results with skip reasons;
- review adjudications and deviations;
- the open physical-acceptance items from the plan's handoff.
