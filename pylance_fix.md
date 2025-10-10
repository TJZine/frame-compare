# Codex Cloud Task — Pyright/Pylance Autofix (Iterative)

_Last updated: 2025-10-10 08:03._

## Purpose
Iteratively **detect, batch-fix, and verify** Pyright/Pylance diagnostics per the repo’s **`pyrightconfig.json`** (or `[tool.pyright]`), with safety gates and minimal intervention.

## Modes
- **Analysis-Only**: Report findings + minimal diffs; no edits.
- **Auto-Patch (Safe)**: Apply only Tier-A fixes in small batches, then re-check types and tests.
- **Auto-Patch (Aggressive)**: Includes Tier-B fixes; still gated by tests and type re-checks.

> Set the mode and limits in the **Parameters** section below.

---

## Parameters (edit at top of task before running)
```yaml
mode: "auto-safe"         # "analysis-only" | "auto-safe" | "auto-aggressive"
max_iterations: 6         # stop after this many fix → check cycles
batch_size: 25            # max files per patch batch
warning_budget: 10        # gate: 0 errors and ≤ warning_budget warnings
test_command: "pytest -q" # set to "" to skip tests (not recommended)
paths: ["src", "tests"]   # folders to analyze/fix
rules_allowlist: []       # e.g., ["reportOptionalMemberAccess","reportMissingTypeArgument"]
rules_blocklist: []       # e.g., ["reportGeneralTypeIssues"]
git_branch: "codex/pylance-autofix"  # new branch (if VCS allowed)
```

**Tier A (safe) fixes**
- Add explicit **Optional guards** for `reportOptionalMemberAccess`/`reportOptionalCall`.
- Add **type annotations** inferred from usage/signatures; avoid introducing `Any`.
- Replace `dict`-shapes with **TypedDict** where shape is stable and local.
- Introduce **Protocol** for narrow, duck-typed dependencies at boundaries.
- Narrow **unions** via `isinstance` or `match`; avoid unchecked member access.
- Minimal import path corrections (relative ↔ absolute) when unambiguous.

**Tier B (aggressive) fixes**
- Broader signature changes (param/return types) where call sites agree.
- Converting dynamic attributes to dataclasses/attrs when clear and local.
- Auto-generating stubs for 3rd-party libs (local `typings/.../*.pyi`).

---

## Task Steps (what Codex Cloud should do)

1) **Detect configuration**
   - Locate `pyrightconfig.json` or `[tool.pyright]` in `pyproject.toml`. Abort with instructions if missing.

2) **Baseline analysis**
   - Run: `npx pyright --warnings --outputjson {"paths": <paths>}`
   - Parse JSON: count **errors/warnings**, group by **rule ID**, **file**, and **line**.
   - If **errors == 0** and **warnings ≤ warning_budget** → **PASS** and stop.

3) **Prioritize**
   - Create **buckets by rule ID**. Order: imports/env issues → Optional/union issues → Unknown/Any leaks → signature/contract issues → stubs.
   - Apply **rules_blocklist / rules_allowlist** if provided.

4) **Propose batch plan (diff plan)**
   - Build a batch of up to **batch_size files** across the top buckets.
   - For each file, prepare **minimal diffs** with rationale and expected impact.
   - Present the plan; if `mode == "analysis-only"`, stop after presenting.

5) **Apply patches (if auto modes)**
   - Create/checkout `{git_branch}` (if VCS allowed).
   - Apply the batch diffs.

6) **Verify**
   - Re-run: `npx pyright --warnings --outputjson` and summarize delta (↓errors/↓warnings).
   - If `test_command` is set, run tests; if tests fail, **revert this batch** and mark those files as **deferred**.
   - If metrics improved and gates not yet met, **iterate** from step 3 (up to `max_iterations`).

7) **Finish**
   - If gates met: prepare a summary and (optionally) a PR description with changes and remaining warnings.
   - If gates not met: output a **Fix Plan JSON** with remaining buckets and suggested next batches.

---

## Output Requirements

- **Summary table**: before/after counts (errors, warnings), iterations, files touched.
- **Findings list**: `file:line` with **rule IDs** and one-liners.
- **Patches**: unified diffs per file in code fences.
- **If stubs created**: list paths under `typings/` and link to the files.
- **If any `# type: ignore[...]` used**: include one-line justification and TODO ticket stub.

---

## Guardrails & Policies

- Follow repo policy in `CODEX.md`/`AGENTS.md`: **diff-plan → approval → patch** when required.
- Do **not** change public APIs unless called out in the batch plan.
- Avoid introducing `Any`—prefer strengthening types.
- Prefer early-return/guard patterns for Optionals.
- Respect **tests** as the primary runtime gate.

---

## Notes

- Pyright is the CLI used by Pylance; using the CLI ensures Cloud results match CI and local policy.
- For huge diffs, set smaller `batch_size` and higher `max_iterations` to converge safely.
- If Node is unavailable, install pyright once: `npm i -g pyright` then run `pyright --warnings --outputjson`.
