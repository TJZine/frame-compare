---
search:
  exclude: true
---

Status: Active
Scope: Implement the accepted CLI, onboarding, report-navigation, copy, and visual-usability improvements from the September 22 UX review; coordinate existing temporal-alignment UX work without duplicating it.
Owner: Maintainer-directed implementation session; one controller owns integration and acceptance evidence.

# CLI and report UX implementation plan

Implementation dispatch uses the [simplified controller handoff](2026-09-22-cli-and-report-ux-handoff.md),
including the user's per-run Luna/xhigh and Sol/medium settings. Implementation
workers run in separate Codex tasks and message completion back to the controller,
which ends its turn after dispatch instead of polling or waiting. This document
remains the product scope and acceptance authority; the handoff is not a second
active plan.

## Objective and approved direction

Make the existing experience easier to discover, understand, and recover from while
preserving its specialist workflow, neutral charcoal surfaces, brass selection
accent, image-first hierarchy, native controls, and offline report model.

The user requested this plan, not implementation in the planning session. Product
work starts in a subsequent implementation session. No commit, push, release, or
publication is authorized by this document.

**Confirmed floating-control decision: remove Fit width (↔), not the orientation
switch. Keep the orientation switch and every other floating control.** Do not move
the remaining controls into a new menu, hide them to reduce density, or remove their
existing mode-dependent behavior. Keep zoom out/range/in/reset, zoom readout, actual
size, fit height, image-offset settings/reset, fullscreen, label visibility, Lens
and its controls, and Blink pause/speed. Existing popovers remain popovers.

Preserve the CLI command names, flag names, accepted values, precedence, persistence,
exit codes, error codes, stdout/stderr routing, and JSON envelope/detail structure.
Human message and hint strings may change as specified below; document those changes.
Preserve report payload v1.2, report identity, screenshot contents, review JSON format,
and browser-local review storage. This is not a new design system, blind comparison
mode, alignment algorithm, installer, or guided-tour project.

## Baseline, evidence, and related work

- Planning baseline: inspected HEAD `2cb61501`; recheck HEAD and the worktree before
  implementation rather than treating this SHA as a permanent starting branch.
- The worktree already contains audio-alignment changes and edits to
  `docs/current-architecture.md`, `docs/current-cli-contract.md`, and
  `docs/guides/audio-alignment.md`, plus related service/integration tests. Preserve
  them. Shared authority documents require targeted integration, not replacement.
- The review reproduced unhelpful `--overlay banana` output: `Invalid configuration:
  overlay_mode` / `Check field types and constraints`. Choice details already exist
  in the typed error; the fix belongs at the CLI presentation/parse boundary.
- Historical documentation images predate the current viewer. The conversation
  preview used current viewer code with synthetic red/green geometry fixtures and
  passed syntax checking only. It is not browser, responsive, natural-footage, or
  native VSView acceptance evidence.
- The existing [audio remediation and UX plan](2026-09-22-audio-alignment-post-activation-remediation-and-ux.md)
  owns terminal temporal-alignment copy (U1), native VSView presentation (U2), and
  physical-Windows acceptance (W1). Reuse its frozen state/copy matrix. This plan
  owns report spatial-offset naming and integration checks, not a competing rewrite
  of those temporal surfaces.
- The existing [documentation screenshot plan](2026-08-17-documentation-v2-screenshot-remediation.md)
  owns publication-safe image recapture and provenance. Coordinate final captures
  after these UI changes; do not restore historical images as current evidence or
  alter that plan's status without its own acceptance.

Use [AGENTS.md](../../AGENTS.md), the [runbook](../ENGINEERING_RUNBOOK.md),
[CLI contract](../current-cli-contract.md), and the report sections of the
[architecture](../current-architecture.md) as authority. Apply Ponytail full mode
with repository overrides. Default to one implementation agent and cohesive units;
no automatic planner/reviewer or parallel-write pipeline is required.

## Coverage and implementation sequence

| Accepted suggestion | Implementation unit | Completion evidence |
| --- | --- | --- |
| Actionable CLI validation errors | P1 | Flag-specific remedies; preserved typed/JSON contracts |
| Self-sufficient run help | P1 | Choices, metavariables, persistence explanation, examples |
| Correct Inspector Export organization | P3 | Four useful tabs; report metadata retained in Report Information |
| Explicit note-storage location | P3 | Accurate browser/session-only states and transfer actions |
| Spatial versus temporal alignment terminology | P4 + P5 | Image-offset labels; accepted temporal wording from U1/U2 |
| Better setup handoff and repeat-use guidance | P2 | Correct next commands and route-specific documentation |
| Floating controls, label wording, mode explanations, visual QA | P4 + P6 | Only Fit width removed; all other controls retained and verified |
| Native-panel density assessment and current documentation imagery | P5 + P6 | Scoped native evidence and coordinated image recapture |

Implement P1 → P2 → P3 → P4, integrate P5 when its upstream work is available, then
complete P6 against the integrated candidate. P1/P2 can proceed while alignment work
continues. Refresh relevant source and shared-document context at each unit boundary.

## P1 — Actionable CLI errors and useful help

Owners: `src/frame_compare/cli/run_command.py` (choice and frame/count coercion),
`cli/entry.py` (help), and `cli/errors.py` only if the presentation adapter needs it.
Reuse `config/schema_enums.py` and existing validation facts; keep configuration
validation policy inside its current owner. Do not introduce a second option registry.

1. Give enum failures their public flag name and allowed values without requiring
   `--verbose`. Pass explicit flag context through the existing choice-coercion seam.
   Target form: `Invalid value for --overlay: banana` followed by
   `Choose one of: minimal, standard, diagnostic, none.` Obtain choices from the enum,
   not duplicated hand-maintained lists. Apply this to tonemap preset and curve too.
2. Check existing frame/count errors before changing them. Retain already-actionable
   messages; fill gaps with the exact option, violated grammar/range, and a valid
   example. Preserve run frame parsing rather than imposing the wizard's separate
   frame-list grammar. Leave expected failures inside the typed FC error path.
3. Preserve redaction: do not expose raw file/environment configuration inputs or
   secrets to make messages friendlier. Bound and safely escape echoed CLI values.
   CLI-specific flag language must not mislabel TOML validation failures as flags.
4. Keep raw string option parsing where it deliberately supports structured JSON
   errors. Improve displayed metavariables without converting these flags to Typer
   enums/integers that intercept failures before the JSON adapter.
5. Use `COUNT`, `FRAME[,FRAME…]`, `NITS`, and appropriate choice metavariables. List
   valid overlay, preset, and curve values in help using the existing enums while
   preserving lazy runtime imports and the current task-based help panels.
6. Replace repeated/ambiguous persistence clauses with one prominent explanation:
   eligible overrides apply to this invocation; `--write-config` saves the effective
   configuration and exits without running. Retain option-specific constraints and
   clearly distinguish run-only flags. Keep `--write-config`'s own description explicit.
7. Add three concise examples: preview the configured comparison, override exact
   frames/overlay for a local run, and save an override without executing. Do not
   imply `--frames` disables other configured selection categories. Show zero metric
   and random counts if an example promises an exact-frame-only run.

Acceptance: normal errors reveal choices/remedies; FC-1003, exit 2, normalized
validation details, JSON-only stdout, and existing stream behavior remain intact.
Help remains readable at 80 and 120 columns, with a 60-column wrapping check; choices
do not drift from enums. Command completion and dependency-light help imports work.

Proof: extend meaningful cases in `tests/cli/test_help_and_import.py`,
`test_run_command.py`, `test_run_json_errors.py`, and `test_exit_codes.py`; use config
override tests where touched. Assert semantic fragments and stream separation,
not whole-terminal snapshots. Update the CLI contract and command reference in this unit.

## P2 — Wizard next steps and repeat-use documentation

Owners: `cli/wizard_command.py`, existing command/path helpers where appropriate,
`docs/guides/first-comparison.md`, `docs/reference/commands-and-configuration.md`,
and the relevant README/getting-started sections.

1. After a successful write, append a compact next-steps block on stderr: diagnose
   the runtime, preview the selected configuration, then execute it. Also offer next
   steps after a valid no-op, retaining the existing no-change message. Do not print
   run guidance after cancellation, write failure, or invalid configuration.
2. Print `frame-compare doctor` with its actual supported options: it currently has
   no `--root` or `--config`. Include the resolved workspace and selected config on
   both suggested `run` commands so they cannot silently target another workspace.
   Preserve the installed-portable config fallback and paths containing spaces.
3. Commands are suggestions, never executed by the wizard. Identify their context:
   use the same installation/launcher and environment. Use POSIX quoting for POSIX
   shells and explicitly label Windows examples as PowerShell with correct literal
   quoting; do not claim one string is safe in every shell.
4. Keep route-specific host commands in the existing Windows/Docker/uv/pip docs.
   Container paths are container paths; do not fabricate host paths or an inferred
   Compose invocation. Provide the matching Docker host sequence in the guide.
5. Separate first-time setup from subsequent comparisons. Setup retains wizard →
   doctor → dry-run → run. Repeat use can begin with preview/run when configuration
   and runtime are already established; explain when setup or diagnostics should
   be revisited. State that dry-run does not probe media or prove runtime readiness.
6. Correct stale wizard descriptions that still imply it configures rendering or
   publishing: its present scope is paths, reference, and frame-selection goals.

Acceptance: each suggested command is supported, targets the correct context, and
introduces no new probes, browser launches, config writes, or prompts. Cancellation
and no-op preservation remain unchanged. A reader can identify the normal repeat-run
path without rereading installation instructions.

Proof: extend `tests/cli/test_wizard_command.py` for successful save, no-op, cancel,
failure, alternate config/root, spaces and shell metacharacters. Test generated
argument meaning without launching a comparison. Reuse onboarding/docs tests and
update the wizard CLI contract in the same unit.

## P3 — Inspector organization and honest note persistence

Owners: `services/report/renderer.py`, `assets/inspector.js`,
`assets/review_state.js`, `assets/viewer.js`, and related styling only as necessary.

1. Remove the misleading Export tab and panel. The final tabs are Frame, Clips,
   Image offset, and Review (the third tab is renamed in P4). Preserve all useful
   metadata in the existing Report Information modal: title, report ID, timestamp,
   frame/clip counts, and safe slow.pics link. Most are already present; deduplicate
   rather than introducing another metadata panel or export interface.
2. Retain Export review JSON and Import review JSON beside the Review fields. Remove
   obsolete Export DOM lookups/rendering and update roving tab/focus behavior.
   A persisted `inspectorTab: export` uses the existing invalid-tab fallback to Frame;
   no migration or report-ID/version bump is needed. Existing generated reports remain
   self-contained. Do not discard notes or other valid viewer preferences.
3. Persistent status: `{n} review records saved in this browser.` Pair it with a
   short static note: `Notes are not stored in the report file. Export review JSON
   to keep or transfer them.` Explain report identity/version scoping in the guide.
4. Preserve the more urgent unsaved/storage-failure messages. When storage is
   unavailable, state `Changes are kept only for this session. Export review JSON
   to keep them.` Do not claim browser persistence after a failed write or memory-only
   fallback. Keep existing atomic import behavior and all schema/identity checks.
5. Do not announce the static storage explanation on every keystroke. Retain the
   existing polite live-region transition policy and normal editing focus.

Acceptance: users find metadata under Report Information and transfer actions under
Review; there is no dead tab or focus target. Saved, unsaved, and session-only states
are truthful. Existing review records and import/export semantics are unchanged.

Proof: renderer, Inspector, viewer-state, and review-controller harnesses plus browser
focus/initialization proof. Cover old saved Export selection, empty and nonempty notes,
blocked storage, failed writes, and successful/failed import. Update the report guide
and architecture's Inspector and browser-local state descriptions.

## P4 — Viewer language and the approved control removal

Owners: report renderer, viewer/Inspector/format/viewport assets as relevant, and
`viewer.css` for focused layout repairs only.

1. Remove only `button[data-fit="width"]` from the floating palette. Keep
   `#btn-palette-orientation` and its horizontal/vertical behavior. Remove the help
   legend entry advertising the absent Fit width button. Do not add a replacement
   menu, shortcut, or hidden button.
2. Retain existing width-fit calculations and restoration of a saved `fitMode: width`:
   this request removes a visible control, not viewport math or existing state.
   Retain zoom/reset/pan/resize behavior and ensure actual-size/fit-height controls
   remain keyboard reachable when restored state matches neither visible button.
   Do not add a compatibility subsystem or erase stored viewer settings.
3. Rename visible Inspector Align to **Image offset**. Use the same term in the
   settings button's accessible name/tooltip, preset/input labels, reset actions,
   status tooltip, and report help. Keep the compact `Offset: none` status and
   existing numeric semantics; explain `Spatial adjustment only; does not change
   source-frame timing.` beside the settings. Retain internal keys if renaming them
   offers no user benefit. Never infer temporal trust from spatial offset values.
4. Rename HUD to **Source labels**, including visibility action names and shortcut
   help. Preserve shortcut H and its existing behavior, including any associated
   frame HUD; explain that baked screenshot text is unaffected. Do not suggest that
   hiding labels makes the report blind or anonymous.
5. Add concise purpose text to mode tooltips and a compact section in the existing
   help modal: Slider—reveal spatial differences; Single—inspect one source;
   Diff—locate changed pixels; Blink—alternate the selected pair;
   Grid—scan sources together. Keep shortcuts, mode order, and switching behavior.
   Descriptions must also be available without hover through Help.
6. Accommodate the longer labels through local wrapping/spacing changes within the
   established responsive design. Preserve all remaining floating controls, including
   their current conditional visibility; no overflow menu or global font-size change.

Acceptance: the control inventory differs only by the absent Fit width button and
approved wording. Horizontal/vertical orientation, zoom, fit height, reset, fullscreen,
offset popover, label visibility, Lens, and Blink remain usable. No orphan separators,
stale help instructions, misleading temporal claims, or broken radio-group navigation.

Proof: renderer/viewport/viewer/Inspector harnesses and relevant CSS contracts, then
browser interaction and visual checks in P6. Update report guide and architecture;
preserve payload, source identity, mapped source frames, and review-state contracts.

## P5 — Integrate temporal-alignment and native-panel UX

The active audio plan's U1/U2/W1 packages own implementation and acceptance here.
Record their actual status and candidate/evidence identity during integration; an
unchecked dependency is not completed work. If they remain outstanding, report that
precisely and continue independent units rather than creating a competing implementation.

Confirm the accepted terminology distinguishes accepted/applied, manually confirmed,
provisional/not applied, and unavailable evidence; zero remains different from missing.
Confirm native-panel hierarchy is outcome → action → collapsed evidence, with captured
positions distinguished from currently viewed frames, actionable manual entry, and
clear post-save continuation guidance. Use the frozen matrix in that plan verbatim
where it governs. Do not add temporal-trust fields or a new alignment panel to report
payload v1.2; that would be a separate product/schema decision.

Inspect real Qt rendering at normal/narrow widths and enlarged text through the
existing native acceptance route. Any confirmed readability defect goes to the
existing U2 owner with evidence. Do not claim natural desktop usability from source,
offscreen assertions, the inline preview, or default headless Docker checks.

## P6 — Integrated usability, documentation, and acceptance

Perform one integrated review after the units are merged. Use generated reports from
the candidate code with representative, rights-cleared natural images for visual
judgment and deterministic fixtures for edge cases. Keep media/captures untracked
unless the existing screenshot plan authorizes the exact publication-safe assets.

| Surface | Required scenarios |
| --- | --- |
| Desktop layout | 1440×900 and 1280×800; Inspector open/closed; both palette orientations |
| Narrow layout | 768px and 375px widths; long filenames/source names; all retained controls reachable |
| Enlarged UI | Desktop at 200% browser zoom; readable text, wrapping, no clipped actions or document overflow |
| Viewer modes | Slider, Single, Diff, Blink, Grid; two and multiple sources; Lens and label toggle |
| Viewport behavior | Zoom/reset, actual size, fit height, pan, image offsets, resize, fullscreen; saved width-fit state |
| Keyboard | Tab/Shift-Tab, radio groups, Inspector tabs, mode shortcuts, H, help/modal Escape and focus restoration |
| Feedback | Image-loading failure/retry where supported, storage failure, import rejection, empty/nonempty notes |
| Motion/touch | Reduced-motion Blink starts paused; coarse-pointer retained controls have usable separate targets |
| Terminal | 60/80/120 columns, no-color, quiet, verbose, JSON; actionable error and setup handoff |
| Native VSView | Matching U2/W1 evidence for normal/narrow/enlarged text and manual/keyboard review states |

Record inspected viewport, browser/platform, candidate identity, states exercised,
and findings. Repair demonstrated issues inside the approved layout. A material new
direction, a second removed/moved control, or a wire-schema change requires returning
to the maintainer; routine copy, wrapping, and focus repairs do not.

Synchronize README/first-use and command-reference prose, report guide, and relevant
authority sections with the implemented behavior. Remove stale Export/HUD/Align/
Fit-width-button references in current-facing guidance. Do not rewrite historical
changelogs or unrelated past plans. Reuse the screenshot plan for final current
viewer imagery and provenance, then verify the rendered documentation page.

## Verification gates

P1–P5 change public behavior or report hotspots, so implementation uses Full
Verification under the runbook. Run focused tests while editing, then one current
integrated full gate; reuse valid evidence rather than repeating unchanged suites.

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
```

Viewer/browser proof:

```bash
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py
```

Reuse this test's full-suite result if it actually ran. Inspect skips; green pytest
with no browser is not browser proof. Use existing locked Node harnesses via pytest,
not an arbitrary global Node. Real-browser appearance/focus checks remain required
where smoke does not cover the changed behavior. Use an approved inspection route;
if a tool denies access, do not bypass it. Record the missing evidence and obtain a
compatible-host/manual acceptance run. The visualize skill can communicate designs,
but adapted inline previews do not prove standalone file-report behavior.

For user-facing docs, install the locked docs toolchain only if missing and preserve
the development environment, then run the documented strict build/drift checks:

```bash
uv sync --group dev --group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
```

Run contract/onboarding docs tests for changed authority and guidance. Regenerate API
docs with the existing generator if CLI documentation changes produce legitimate
drift. No new general-purpose checker or test framework is needed.

Report-only changes do not require native media integration. Apply distribution
verification if package inclusion/entry points change; native-panel, Docker, runtime,
and physical-Windows proof remain governed by the affected surface and existing audio
plan. Do not label platform proof complete on an incompatible host.

## Rollback, stop conditions, and handoff

Keep the implementation units separately reviewable. Revert only task-owned changes
in reverse dependency order if a unit fails acceptance. No persisted-data migration
is planned; never clear browser notes, rewrite old reports, or delete config/cache
data as rollback. Coordinate shared-doc reversions with the existing alignment work.

Return to planning only for a consequential unresolved choice outside this scope:
another removed/moved control, new temporal data in reports, changed parsing or
storage contracts, conflicts with the frozen audio UX matrix, or a material visual
redesign. Missing platform proof blocks that acceptance claim, not unrelated work.

Completion requires all P1–P6 acceptance criteria, or an explicit account of which
upstream/platform dependencies remain incomplete; do not mark the whole plan complete
while required evidence is pending. Record changed owners, verified commands and
observed results/skips, browser/native evidence, integrated upstream status, and
remaining limitations below. Inspect the task-owned diff and preserve unrelated work.
Mark this plan Historical only after its complete scope is accepted.

## Execution record

- Planning only: created September 22, 2026. No product implementation performed.
- User clarification: remove **Fit width (↔)**; retain the **orientation switch** and
  every other floating control. This supersedes the review's proposed control hiding.
- P1–P6: not started under this plan; upstream audio/screenshot work has independent
  execution records and must be checked at implementation time.
