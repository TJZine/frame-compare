---
search:
  exclude: true
---

# TODO

> Non-authoritative backlog. These items are candidates, not approved plans or
> current product contracts. Update or remove an item when its work is completed,
> rejected, or promoted into an active plan.

- Consider adding a dedicated packaging/release workflow skill if Python packaging, Docker, Windows portable, or updater/signing work becomes frequent.

---

## CLI Output Follow-Ups

### Plain Non-TTY Human Renderer

**Context**: Interactive TTY output now has a decision-first information hierarchy
and Rich progress presentation. Redirected and CI human output still uses the
existing log-oriented progress path; JSON remains the automation contract.

**What**: Add automatic chronological text output for redirected or CI human runs,
without live redraws or spinners. Reuse the current run-plan, source, phase, and
result information hierarchy. Do not add a `--plain` flag by default and do not
change JSON output.

**Risk**: Touches orchestration progress selection and user-visible CLI streams.
Preserve JSON/stdout purity, quiet behavior, exit codes, and TTY prompt handling;
use a focused plan and full verification.
