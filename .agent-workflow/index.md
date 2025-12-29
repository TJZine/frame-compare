# Agent Workflow Run Index

> **Purpose:** Table of contents for all completed agent workflow runs.
> **Updated by:** Verification Agent (append) and Review Agent (finalize).

## Completed Runs

| RUN_ID | Target | Date | Verdict | Artifacts |
|--------|--------|------|---------|-----------|
| 2025-12-27__p0-1__repo-foundation | Phase 0 → Items 0.1-0.3 | 2025-12-28 | APPROVED | [plan](runs/2025-12-27__p0-1__repo-foundation/plan-v4.md) / [plan-review](runs/2025-12-27__p0-1__repo-foundation/plan-review-v4.md) / [impl](runs/2025-12-27__p0-1__repo-foundation/impl-v1.md) / [verify](runs/2025-12-27__p0-1__repo-foundation/verify-v1.md) / [review](runs/2025-12-27__p0-1__repo-foundation/review-v1.md) |
| 2025-12-27__p0-4__ci-pipeline | Phase 0 → Item 0.4 | 2025-12-28 | APPROVED | [plan](runs/2025-12-27__p0-4__ci-pipeline/plan-v4.md) / [plan-review](runs/2025-12-27__p0-4__ci-pipeline/plan-review-v4.md) / [impl](runs/2025-12-27__p0-4__ci-pipeline/impl-v1.md) / [verify](runs/2025-12-27__p0-4__ci-pipeline/verify-v1.md) / [review](runs/2025-12-27__p0-4__ci-pipeline/review-v1.md) |
| 2025-12-27__p0-5__container-setup | Phase 0 → Item 0.5 | 2025-12-28 | APPROVED | [plan](runs/2025-12-27__p0-5__container-setup/plan-v9.md) / [plan-review](runs/2025-12-27__p0-5__container-setup/plan-review-v9.md) / [impl](runs/2025-12-27__p0-5__container-setup/impl-v7.md) / [verify](runs/2025-12-27__p0-5__container-setup/verify-v6.md) / [review](runs/2025-12-27__p0-5__container-setup/review-v4.md) |
| 2025-12-28__p1-1__config-module | Phase 1 → Item 1.1 | 2025-12-29 | APPROVED | [plan](runs/2025-12-28__p1-1__config-module/plan-v7.md) / [plan-review](runs/2025-12-28__p1-1__config-module/plan-review-v7.md) / [impl](runs/2025-12-28__p1-1__config-module/impl-v1.md) / [verify](runs/2025-12-28__p1-1__config-module/verify-v1.md) / [review](runs/2025-12-28__p1-1__config-module/review-v1.md) |
<!-- Verification Agent: Append new entries here -->

## Legend

- **RUN_ID:** Unique identifier for the run (`YYYY-MM-DD__p<phase>-<item>__<short_slug>`; meta runs may use `YYYY-MM-DD__meta__<short_slug>`)
- **Target:** Phase → Checklist Item
- **Date:** Completion date
- **Verdict:**
  - `PENDING_REVIEW` after Verification is complete (Review not yet done)
  - Final review verdict after Review completes (`APPROVED` / `CHANGES_REQUIRED` / `DESIGN_ISSUE`)
- **Artifacts:** Links to the canonical stage artifacts in the run directory

## How to Update

### Step 1: Verification Agent (append)

After all verification gates pass, append a new row with `PENDING_REVIEW` and links to artifacts that exist at this stage (`plan`, `plan-review`, `impl`, `verify`).

### Step 2: Review Agent (finalize)

After writing `review-vN.md`, update the same row:

- Replace `PENDING_REVIEW` with the final verdict (`APPROVED` / `CHANGES_REQUIRED` / `DESIGN_ISSUE`)
- Add/update the `[review](...)` link

Example row (finalized):

```markdown
| 2025-12-25__p1-1-1__config-module | Phase 1 → Item 1.1 | 2025-12-25 | APPROVED | [plan](runs/2025-12-25__p1-1-1__config-module/plan-v1.md) / [plan-review](runs/2025-12-25__p1-1-1__config-module/plan-review-v1.md) / [impl](runs/2025-12-25__p1-1-1__config-module/impl-v1.md) / [verify](runs/2025-12-25__p1-1-1__config-module/verify-v1.md) / [review](runs/2025-12-25__p1-1-1__config-module/review-v1.md) |
```

> Replace `v1` with the exact artifact versions for the run you verified/reviewed (for example, `plan-v2.md`, `impl-v3.md`).

## See Also

- [Run Directory Convention](runs/README.md)
- [Agent Workflow Documentation](../docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md)
