---
search:
  exclude: true
---

Status: Reference
Scope: Copy-paste implementation handoffs for the report viewer and CLI design refresh plan, one per review checkpoint.
Owner: Maintainer; implementation sessions run in Muse Code, reviews run in the planning (controller) session.

# Design refresh implementation handoffs

This file is an execution handoff, not a second plan. The authority is
[the design refresh plan](2026-09-23-report-and-cli-design-refresh.md). Each track
below is implemented in its own session, in order, on one branch, and stops for a
maintainer/controller review before the next track starts.

| Session | Units | Starts from | Ends at |
| --- | --- | --- | --- |
| 1. Track A | A1 → A2 → A3 → A4 | branch tip after the plan commit | Checkpoint A report |
| 2. Track B viewer | B1 → B2 → B3 | branch tip after Checkpoint A review and fixes | Checkpoint B-viewer report |
| 3. Track B terminal | B4 → B5 → B6 → B7 | branch tip after Checkpoint B-viewer review and fixes | Checkpoint B-terminal report |

Paste one prompt per session. Every prompt requires the session to read the
[Common rules](#common-rules) first.

## Common rules

These apply to every session. The prompts refer to them by name.

### Repository and branch

- Repository: `/Users/tristan/Software/frame-compare` (on Windows, the maintainer's
  equivalent checkout).
- Branch: `dev/v0.6.0-design-refresh`. Work directly on it. Do not create, switch,
  rebase, reset, or amend branches; do not push; do not open pull requests.
- Start by recording `git rev-parse HEAD`, `git status`, and `git log --oneline -5`.
  If the working tree has changes you did not make, stop and report them.
- Bootstrap with `uv sync --group dev --frozen` only if `.venv` is missing.

### Authority and reading order

1. The plan: `docs/plans/2026-09-23-report-and-cli-design-refresh.md`. Read it in
   full, including Locked decisions, Invariants, Shared specifications, your
   track's units, Sequencing, Verification, and Stop conditions.
2. The reference assets in `docs/plans/2026-09-23-design-refresh-assets/`
   (images, `viewer-mock.html`, `cli-*.svg`) for the units you implement. The plan
   text wins wherever an asset differs.
3. `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md` (Verification, Planning and Handoff,
   Review Policy), and the repo-local skills that match the changed surface in
   `.agents/skills/` (for example `report-output-patterns`,
   `cli-contract-boundaries`, `python-test-design`, `closeout-verification`).
4. The source files named as owners in each unit, read before editing.

### Follow the plan exactly

- Implement every bullet of every unit in your track, and nothing else. No extra
  features, refactors, renames, reformatting of untouched code, or "improvements".
- Use the exact strings, values, thresholds, file owners, and names in the plan.
- Do not make product, design, wording, or contract decisions. If the plan does
  not cover a situation, apply the nearest stated rule. If no rule applies, or two
  rules conflict, or a stop condition is reached: stop that unit, record the
  question, finish any independent units, and report.
- The only plan edit you may make is appending to its **Execution record**
  section. Do not change any other part of the plan or the assets.
- Preserve all invariants. In particular: no report payload key changes, no
  `phase_timings`/run-record/JSON output changes, burned-in screenshot text and
  slow.pics names keep the `|` separator, frozen audio strings verbatim, plain and
  log reporters unchanged.

### Subagents

Use subagents where they help. Keep one writer at a time: only the main session
edits files unless a subagent is given an explicit, disjoint file set and the
main session makes no competing edits while it runs.

Good uses:

- read-only exploration: locating callers, tests, fixtures, and every place a
  string or behaviour appears before changing it;
- running long verification (full pytest, browser smoke, docs build) and
  summarizing failures;
- rendering and inspecting output (browser screenshots at the plan's widths,
  terminal output at 60/80/120 columns);
- the adversarial reviews below (always read-only, fresh context).

### Adversarial review before every commit

After a unit's implementation and focused tests pass, and before committing it:

1. Stage the unit's changes (`git add` of the unit's files only).
2. Launch **independent, read-only reviewer subagents** with fresh context. Give
   each the plan path, the unit id, the full text of the unit's plan section plus
   the Invariants and Shared specifications it relies on, and the staged diff
   (`git diff --staged`). Do not give them your reasoning or conclusions.
   - **Plan-conformance reviewer** (every unit): "Assume this diff does not follow
     the plan. For every bullet and value in the unit's plan section, find the
     code and test that implement it, or report it missing or different. Report
     anything in the diff that the plan did not ask for. Report every invariant
     the diff could break."
   - **Regression and contract reviewer** (units A1, A4, B1, B4, B5, B6, B7, and any
     unit touching Python production code): "Find behaviour this diff breaks or
     changes outside the plan: public CLI/JSON/report/persistence contracts,
     callers of changed functions, saved browser state, accessibility (roles,
     names, focus), `NO_COLOR`, non-TTY output, Windows paths and encodings, and
     missing or weak tests."
3. Each reviewer returns findings as: plan clause or invariant, file:line,
   severity (blocker / major / minor), evidence, and a proposed correction; plus a
   list of plan bullets it verified as implemented.
4. Adjudicate every finding against the plan and the code: **fix** (then re-run
   focused tests and a fresh review of the changed parts), **reject with
   evidence** (quote the plan text or code that shows it is not a deviation), or
   **leave open** (record why). Never silently drop a finding.
5. Repeat until a review round has no unresolved blocker or major findings, to a
   maximum of three rounds. If blockers remain after three rounds, do not commit
   the unit; stop and report.
6. Commit the unit: one commit per unit, message
   `<type>(<scope>): <unit id> <summary>` (for example
   `feat(report): B2 proximity fade for the viewport palette`), body listing the
   plan bullets covered and any open findings.

After the last unit of the track, run one **track-level adversarial review** with
two fresh reviewers over `git diff <track start SHA>..HEAD`, given the whole
track's plan sections: one for plan conformance across units (including docs the
plan requires and cross-unit consistency), one for regressions. Fix or record
findings the same way; commit fixes as `fix(<scope>): <track> review corrections`.

### Verification

- Focused tests while editing; each unit's **Proof** list from the plan.
- Before the track report, run the full gate from the plan's Verification section
  and record every command with exit code, test counts, and every skip with its
  reason. A skipped browser suite is not browser proof.
- Keep screenshots and scratch output untracked (outside the repository or in an
  ignored path). Do not commit media.

### Final report (bring this back for review)

End the session with this report, in this order, and append a condensed version
to the plan's Execution record. Be complete and specific; the review stage relies
on it. Do not summarize problems away.

1. **Identity:** branch, start SHA, end SHA, commits (`sha` · unit · subject).
2. **Coverage matrix:** for every bullet of every unit in the track, one row:
   plan clause · implemented where (file:line) · proven by (test name or manual
   evidence) · status (done / partial / not done).
3. **Deviations:** every place the result differs from the plan text or the
   reference assets, however small, with the reason. If none, say "none found"
   and name who checked (which reviewer rounds).
4. **Judgment calls:** anything the plan did not specify exactly and what you
   chose (these should be rare; each is a review item).
5. **Stop conditions and open questions:** anything you stopped on, with the plan
   text and the facts that caused it.
6. **Adversarial review log:** each round per unit and the track-level review:
   findings, severity, and disposition (fixed in `sha` / rejected with evidence /
   open).
7. **Verification:** commands, exit codes, counts, skips with reasons, browser and
   terminal checks performed (viewport sizes, columns, modes), and anything not
   verified and why.
8. **Possible issues and risks:** suspected regressions, fragile code, weak tests,
   platform concerns (Windows, encodings, light terminal themes), performance.
9. **Files changed:** grouped by unit; flag any file outside the unit's owner list.
10. **Documentation:** which docs were updated for which unit, and the strict docs
    build result.

## Prompt 1 — Track A

```text
You are implementing Track A (units A1, A2, A3, A4) of the Frame Compare design
refresh plan.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules". Read that section and the whole plan before any edit, and
follow both exactly. The plan text is authoritative; do not make product or design
decisions. Stop and report instead.

Scope: A1 → A2 → A3 → A4, one commit per unit, each after passing adversarial
review as the Common rules describe. Then a track-level adversarial review, the
full verification gate, and the Final report. Stop after Track A; do not start
Track B.

Unit notes (in addition to the plan text, not instead of it):
- A1: implement the service table, the "Needs WEB next" rule, the lookup order, and
  the guessit name mappings exactly. ATVP/APTV/Apple TV+ → ATVP and HMAX/HBO Max →
  HMAX are intended changes; update only the tests that asserted the old codes and
  list each updated assertion in the report. Include every proof case the plan
  lists (including the "It" title and the no-WEB IT case).
- A2: use the exact FPS, size, runtime, timestamp, tonemap label, and
  active-picture rules. Source tonemap labels only from the plan's table.
- A3: add only the G shortcut and its title/Help text. Do not add a frame-position
  counter or shortcut letters to the toolbar (decision D9).
- A4: this includes decision D10 (plain-magnifier lens): remove the split
  comparison, its controls, state, and markup; add the Caption preference
  (default off) with the S1 caption text; keep the loading/unavailable notice and
  the accessible description. Also the Ring default, the Fixed text removal and
  note, distinct icons, SVG zoom glyphs, and the vertical palette order and icon
  buttons. Check that stored lens state containing comparisonEnabled or
  comparisonTarget loads without error.

Suggested subagent use: one read-only explorer to map every reference to the lens
comparison feature (JS, CSS, renderer, tests, docs) before A4 edits; one to map
every service-code assertion in tests before A1 edits; verification runners for the
browser smoke and full pytest.

Docs to update in the units that change them: docs/guides/sources-and-labels.md
(services), docs/guides/reports-and-overlays.md (lens, shortcuts, formatting), and
the architecture's viewer sections if they describe the lens comparison.
```

## Prompt 2 — Track B viewer

```text
You are implementing Track B viewer (units B1, B2, B3) of the Frame Compare design
refresh plan. Track A is complete and reviewed.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules". Read that section, the whole plan, and the plan's
Execution record for Track A before any edit, and follow both exactly. The plan
text is authoritative; do not make product or design decisions. Stop and report
instead.

Scope: B1 → B2 → B3, one commit per unit, each after passing adversarial review as
the Common rules describe. Then a track-level adversarial review, the full
verification gate, and the Final report. Stop after B3; do not start B4.

Unit notes (in addition to the plan text, not instead of it):
- B1: add the separator keyword with a " | " default to the three formatters and
  pass " · " only from report display building. Prove with one test that, for the
  same fixture, report display profiles use "·" while burned-in screenshot text
  and slow.pics image names still use "|". The viewer shows names only: no colour
  swatches, no #n, no LEFT/RIGHT (decisions D1 and D9). Toolbar: remove L:, vs,
  R:, Clip:; 20rem select cap with end ellipsis; Offset label/value typography.
  Stage labels: the HDR/SDR word rule exactly as written.
- B2: implement the proximity state machine with the exact thresholds (96 px /
  160 px hysteresis), 0.18 opacity, 150 ms transition, 3000 ms load override,
  drag override, popover override, focus-within, fine-pointer gating, and reduced
  motion. Cover each rule in the harness.
- B3: implement to viewer-inspector-frame.webp, viewer-inspector-clips.webp, and
  viewer-report-info.webp and the B3 text: tab style, Frame tab rows and Detail
  rule, the all-sources table, the shared clip card (full and compact variants),
  the shared line with omission rule, placement text, and the Report Information
  rows (Opens in / Default pair).

Visual verification: generate a report from the same fixtures the browser smoke
test uses (or an equivalent synthetic fixture with three sources and the three long
names from the plan), and compare it in a real browser against the reference images
at 1440, 1280, 768, and 375 px and at 200% zoom. Record differences in the
Deviations section. Keep screenshots untracked.

Suggested subagent use: read-only explorers to map every consumer of the display
profiles and of the stage-label and Inspector rendering before edits; a browser
verification subagent for the viewport matrix; verification runners.

Docs to update in the units that change them: docs/guides/reports-and-overlays.md
(names, palette fade, Inspector, Report Information) and the architecture's viewer
and Inspector sections.
```

## Prompt 3 — Track B terminal

```text
You are implementing Track B terminal (units B4, B5, B6, B7) of the Frame Compare
design refresh plan. Track A and Track B viewer are complete and reviewed.

Repository: /Users/tristan/Software/frame-compare
Branch: dev/v0.6.0-design-refresh (work directly on it; do not push)
Plan: docs/plans/2026-09-23-report-and-cli-design-refresh.md
Handoff rules: docs/plans/2026-09-23-report-and-cli-design-refresh-handoff.md,
section "Common rules". Read that section, the whole plan, and the plan's
Execution record for earlier tracks before any edit, and follow both exactly. The
plan text is authoritative; do not make product or design decisions. Stop and
report instead.

Scope: B4 → B5 → B6 → B7, one commit per unit, each after passing adversarial
review as the Common rules describe. Then a track-level adversarial review, the
full verification gate, and the Final report.

Unit notes (in addition to the plan text, not instead of it):
- Shared: create src/frame_compare/utils/terminal_theme.py with the S3 tokens,
  glyphs, ASCII fallback, and highlight=False console construction; keep
  lint-imports passing. Add short_source_names to services/release_identity.py
  per S1 (release group, fallback to compact name, explicit labels, collisions).
- B4: follow the Run plan row-mapping table row by row; the Sources, Execution,
  publish, and Summary rules; every publish state listed. Reproduce frozen audio
  strings verbatim (add exact-match tests). Only the Rich path changes: plain and
  log reporters keep uppercase labels and bracket tokens; --json and --quiet
  output unchanged. Fix the blank lines at their source. Update
  docs/current-cli-contract.md in this unit.
- B5: measure the VSView wait in _run_vsview_command; carry it in memory only
  (not phase_timings, run record, or JSON); implement the Align line and the
  summary time rows with the omission rules.
- B6: generated-script helpers only (no Rich or frame_compare imports in the
  generated script); colour tiers, glyph and arrow fallback, the ready block
  exactly as shown, short_names_by_stem parameter with a None default, and
  byte-identical output for identical inputs.
- B7: doctor layout and verdict line; glyphs and accent for wizard, history,
  preset, and errors without changing their text, streams, JSON, or history list's
  tab-separated rows.

Terminal verification: render each changed surface at 60, 80, and 120 columns, with
NO_COLOR, with an ASCII-only encoding, with --quiet, --verbose, --json, and non-TTY,
and compare the 104-column renders against the cli-*.svg references. Record
differences in the Deviations section. If a real media run is possible on this host,
run one and include its output; otherwise say so.

Suggested subagent use: read-only explorers to map every printer of the affected
panels and every test asserting their text before edits; a render subagent for the
column and mode matrix; verification runners.

Docs to update in the units that change them: docs/current-cli-contract.md (Run
plan rows, Rich phase labels, summary, doctor), the audio-alignment and publishing
guides where they quote terminal output, and docs/guides/sources-and-labels.md for
short names.
```
