# Frame Compare agent entrypoint

Read [`.agents/project.md`](.agents/project.md) for repository contracts, source routes,
and verification selection. Load only the sections and referenced sources relevant
to the task; inspect the affected callers and runtime path before changing behavior.

Use `develop-code` for implementation; load `design-code`, `review-code`, or
`verify-code` when that responsibility is needed. These skills own the common
workflow, not mandatory stages. Use `maintain-workflow` only for explicitly
requested maintenance. This repository owns its product contracts and commands.
Use the requested mode: a review or design request does not by itself authorize
implementation, publication, or release.

Working rules:

- Use the task revision or active checkout; resolve actual PR base/head for reviews.
  Query the default branch only when a base is needed and no task context identifies
  one. Never infer the active branch from an old profile.
- Treat existing owners and patterns as evidence. Improve or replace them when the
  scoped outcome justifies it; preserve product obligations, not accidental structure.
- Preserve runtime-free CLI help/version, typed errors, machine-clean JSON stdout,
  deterministic artifacts, owned resource cleanup, and explicit persistence boundaries.
- Fresh computed alignment needs the documented audio/video authority before it can
  affect trims or computed-cache authority. Keep a valid zero offset distinct
  from unavailable evidence.
- Honor explicit test constraints for the current task. Choose meaningful proof for
  changed behavior; neither test count nor E2E-only coverage is a quality target.
- Keep incidental generated outputs, caches, credentials, and unrelated work out of
  the change. Keep one canonical copy of instructions and skill bodies.
- State what actually ran and what remains unverified. A skip or an absent CI job is
  not a runtime/platform pass.

Specialist procedures remain in [`docs/ENGINEERING_RUNBOOK.md`](docs/ENGINEERING_RUNBOOK.md).
Current ownership and CLI contracts remain in [`docs/current-architecture.md`](docs/current-architecture.md)
and [`docs/current-cli-contract.md`](docs/current-cli-contract.md). Keep those sources
current when the corresponding contract changes.

Run independent investigation, checks, and implementation in parallel when ownership,
contracts, and working state permit it. A plan is not a mandatory sequential
pipeline. Serialize only actual dependencies or conflicting shared resources.
