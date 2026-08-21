---
search:
  exclude: true
---

# TODO

> Non-authoritative backlog. These items are candidates, not approved plans or
> current product contracts. Update or remove an item when its work is completed,
> rejected, or promoted into an active plan.

- Consider adding a dedicated packaging/release workflow skill if Python packaging, Docker, Windows portable, or updater/signing work becomes frequent.

## Release Identity Presentation Follow-Ups

- Consider dedicated release-identity display fields for the HTML report/HUD, baked
  screenshot overlays, wizard/dry-run exact-file presentation, and warnings where
  useful. Exclude run-folder/history names, the slow.pics collection title, and all
  internal identities.

---

## CLI Output Follow-Ups

### Plain Non-TTY Human Renderer

**Context**: Interactive TTY output now has a decision-first information hierarchy
and Rich progress presentation. Redirected and CI human output still uses the
existing log-oriented progress path; JSON remains the automation contract.

**What**: For non-JSON, non-quiet redirected or CI human runs, replace the existing
user-facing log-progress milestones with automatic chronological text output without
live redraws or spinners. Keep the current run-plan, source, and result renderers and
their stream ownership; do not emit both log-progress milestones and chronological
phase lines.

**Acceptance criteria**:

- Emit each run-plan, source, phase, warning, and result fact at most once.
- Keep `run --json` output, schema, stderr behavior, and reporter selection unchanged.
- Preserve `--quiet`, exit codes, prompt eligibility, and interactive TTY behavior.
- Do not add a default `--plain` flag.
- Update the authoritative CLI contract in the implementation pass that changes the
  current non-TTY human behavior.

**Risk**: Touches orchestration progress selection and user-visible CLI streams.
Preserve JSON/stdout purity, quiet behavior, exit codes, and TTY prompt handling;
use a focused plan and full verification.
