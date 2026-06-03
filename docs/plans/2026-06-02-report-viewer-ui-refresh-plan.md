Status: Historical
Scope: Report viewer UI/UX production refresh for hierarchy, canvas maximization, HUD/Single terminology, collapsible filmstrip, floating viewport tools, smart labels, inspector drawer, blink controls, focus mode, tests, docs, and adversarial review loop
Owner: Next AI cleanup-loop orchestrator session

# Report Viewer UI/UX Production Refresh Plan

## 1. Purpose

Upgrade the Frame Compare static HTML report viewer from a dense but functional engineering viewer into a production-quality QC workstation while preserving the repo's CLI-first/offline report architecture.

This plan is execution-grade for AI agents with direct codebase access. It freezes product decisions, owner seams, invariants, verification, stop conditions, and subagent workflow so implementation does not invent policy mid-run.

## 2. Controller workflow

Use `frame-compare-cleanup-loop` as the orchestrator workflow.

Required orchestration sequence:

1. Read, in order:
   1. `AGENTS.md`
   2. `docs/ENGINEERING_RUNBOOK.md`
   3. this active plan
   4. `docs/current-architecture.md`
   5. `docs/current-cli-contract.md`
   6. `importlinter.ini`
   7. relevant repo-local skills:
      - `frame-compare-cleanup-plan`
      - `frame-compare-cleanup-review`
      - `frame-compare-cleanup-implement`
      - `review-adjudication`
      - `verification-strategy`
      - `closeout-verification`
2. Keep `update_plan` as the authoritative live execution state.
3. Request an adversarial plan review before code changes.
4. Adjudicate the plan review using `review-adjudication`.
5. Implement approved units in reviewed checkpoints. The maintainer approved
   grouping small adjacent units on 2026-06-02; grouped checkpoints must still
   preserve bounded scope and receive adversarial review before the next
   checkpoint.
6. Run that unit's targeted verification.
7. Request adversarial implementation review for that unit.
8. Adjudicate findings.
9. Repeat until all units close.
10. Run final verification and `closeout-verification`.
11. Mark this plan `Status: Historical` only after merged/accepted closeout or maintainer approval.

The orchestrator must not batch multiple implementation units into one unreviewed
diff unless the maintainer explicitly approves. Maintainer approval was given on
2026-06-02 for adjacent small report-viewer units to be grouped when that reduces
subagent overhead without mixing unrelated owner surfaces.

## 3. Task family and risk tier

Task family: high-risk generated-report UI/UX feature/refactor.

Risk tier: High.

Reasons:

- The work changes `src/frame_compare/services/report/**`, a user-visible generated output surface.
- The architecture document currently describes the report viewer's feature surface and must stay current.
- The viewer persists browser-local state; changes can regress state restoration, N-source pair behavior, or accessibility.
- The viewer is static/offline and must continue working under local `file://` report usage.
- Generated report HTML/JS/CSS behavior is not a CLI flag surface, but it is part of a public release artifact.

Verification tier: Full verification, plus manual browser-runtime proof. Docker verification is not required unless implementation touches `render/**`, `vs/**`, Docker files, or real FFmpeg/VapourSynth integration tests.

## 4. Current authority and evidence to preserve

Current report ownership:

- `frame_compare.services.report` owns the static offline report payload and viewer assets.
- The generated viewer currently exposes slider, overlay, diff, blink, frame/category navigation, info modal, current-frame stage overlay, local view state, pan, zoom, fit controls, viewport alignment, and adjacent-frame preloading.
- Browser opening and slow.pics policy are CLI-owned and out of scope.

Current viewer implementation facts:

- `viewer.css` defines the app shell, toolbar, stage, overlay/diff/blink modes, stage labels, alignment popover, category filters, filmstrip, modals, footer, and responsive behavior.
- `viewer.js` owns viewer state, mode switching, frame navigation, clip selection, viewport pan/zoom/fit, alignment persistence, category filtering, keyboard shortcuts, image updates, and preloading.
- `renderer.py` owns generated HTML markup for controls, stage, help modal, info modal, category filters, filmstrip, footer, embedded JSON, CSS, and JS.
- `payload.py` owns report payload shaping and should not be expanded unless required by this plan.
- Existing tests in `tests/services/test_report_renderer.py` and `tests/services/test_report_viewer_state.py` protect renderer contracts and viewer-state behavior.

## 5. Product decisions frozen by this plan

### 5.1 Final UX target

Implement one cohesive default report viewer, not three separate mock modes.

The final target combines:

- Conservative refresh: clearer hierarchy and terminology.
- QC workstation: primary toolbar, floating viewport tool palette, collapsible timeline/filmstrip, right inspector drawer.
- Zen review: focus mode for minimal chrome and maximum canvas.

### 5.2 Terminology

User-facing terminology must change as follows:

| Current user-facing text | New user-facing text | Internal compatibility rule |
| --- | --- | --- |
| `Overlay` mode | `Single` | Keep internal `mode === "overlay"` and payload/config value `"overlay"` unless maintainer explicitly approves config enum migration. |
| `Overlays` button | `HUD` | The button hides/shows viewer labels/HUD. Internal state may keep `overlaysHidden` to avoid localStorage churn. |
| `Hide overlays` / `Show overlays` | `Hide HUD` / `Show HUD` | Update ARIA labels, titles, help modal, and tests. |

Do not change the public config value or enum for `report.default_mode`. If a report payload has `default_mode = "overlay"`, the viewer still enters Single mode.
Metadata and inspector/export display surfaces must map internal/default mode
`overlay` to user-facing `Single`; the embedded payload value remains `overlay`.

### 5.3 Layout hierarchy

Default desktop layout:

1. Header:
   - title
   - generated timestamp
   - frame/clip counts
   - slow.pics link if present
   - Info and Help buttons
2. Primary toolbar:
   - frame previous/select/next
   - mode segmented control: Slider / Single / Diff / Blink
   - pair controls or single active clip control
   - pair/alignment status pill
3. Viewer stage:
   - image canvas
   - floating secondary viewport palette anchored inside the stage
   - smart labels
4. Right inspector drawer:
   - collapsible
   - tabs: Frame, Clips, Align, Export
5. Bottom panel:
   - category filters
   - filmstrip/timeline
   - collapse handle
6. Footer:
   - concise shortcut hint only; do not duplicate long help modal content.

Responsive layout:

- At narrow widths, inspector is closed by default and becomes a drawer overlay.
- Primary toolbar can wrap, but secondary viewport controls must not consume top vertical space.
- Collapsed bottom panel must reclaim most of the bottom vertical space.

### 5.4 Floating viewport palette

Move these controls out of the top toolbar and into a floating palette inside `.rv-viewer-stage`:

- zoom out
- zoom range/value or compact zoom indicator
- zoom in
- reset/actual size
- fit width
- fit height
- fill
- alignment popover trigger
- HUD toggle
- fullscreen
- focus mode toggle if not placed elsewhere

The palette must be keyboard reachable and visible on focus. It may be semi-transparent, but text and focus outlines must remain readable.

### 5.5 Collapsible filmstrip and bottom panel

Add a bottom panel shell around category filters and filmstrip.

Required behavior:

- Button and keyboard shortcut `F` toggle collapsed/expanded state.
- Collapsed state hides category filter chips and thumbnails, leaving only a slim handle/status row.
- Expanded state restores filter chips and thumbnails.
- Persist collapsed state in the existing report-local `localStorage` payload.
- `report.include_filmstrip = false` still means no thumbnail buttons are rendered; do not reintroduce thumbnails when the config disabled them.
- When `include_filmstrip = false`, the bottom handle may show `Filmstrip disabled` but must not imply it can reveal thumbnails.

Filmstrip size modes:

- Add `compact`, `normal`, and `large`.
- Default: `normal`.
- Persist selected size in localStorage.
- Controls may be implemented as a compact dropdown or three-button segmented group.
- Do not implement arbitrary drag resizing in this iteration.

### 5.6 Smart stage labels

In Slider mode:

- Attach left/right clip labels near the slider divider instead of permanently pinning them to bottom corners.
- Labels must move with the divider.
- Labels must remain clamped within the visible image/canvas bounds.
- Labels must not block pointer dragging of the divider.
- HUD toggle hides these labels.
- Stage frame metadata remains available but should be less intrusive than current bottom-center pill.

In Single mode:

- Show only the active clip label.
- Use a low-obstruction placement, preferably top-left inside the image area.
- HUD toggle hides it.

In Diff mode:

- Continue hiding stage labels by default unless a low-obstruction diff label is explicitly implemented.
- Do not obscure difference pixels with large labels.

In Blink mode:

- Show the currently visible clip label and frame metadata in a low-obstruction HUD.
- HUD toggle hides them.

### 5.7 Inspector drawer

Add a collapsible right-side inspector.

Tabs and required content:

1. Frame
   - frame label
   - frame number
   - category
   - detail field
   - visible position among filtered frames, e.g. `3 of 10 shown`
2. Clips
   - all clip labels
   - current left/right or active designation
   - resolution
   - FPS
   - HDR/SDR
   - source name
3. Align
   - current pair key or pair labels
   - current preset
   - X/Y offset
   - reset current pair
   - reset all pair alignments
   - note that offsets are pair-scoped
4. Export
   - report title
   - report ID
   - generated timestamp
   - slow.pics status/link if present
   - copyable summary text may be added only if implemented without clipboard permission surprises; otherwise show text only.

Required behavior:

- Toggle with Info button or `I`.
- Preserve existing info modal only if needed for small screens; otherwise Info opens the drawer. Help remains a modal.
- If both drawer and modal remain, avoid duplicate keyboard traps.
- Persist drawer open/closed state and active tab in localStorage.
- On narrow screens, drawer overlays the stage and can be closed with Escape.
- Do not require new payload fields for the first implementation. Use existing `ReportPayload` fields.

### 5.8 Alignment UX

Keep pair-scoped alignment semantics.

Add visible alignment status:

- `Aligned: none`
- `Aligned: +1x 0y`
- `Aligned: custom +5x -2y`
- `Aligned: preset left 1px`

Alignment popover/drawer requirements:

- Existing preset and X/Y controls must continue working.
- Add `Reset current pair`.
- Add `Reset all pairs`.
- Do not invent automatic reverse-pair propagation unless current viewer state already supports it. If reverse-pair behavior exists, preserve it; otherwise stop and ask before adding.

### 5.9 Blink controls

Add blink control UI:

- speed options: `0.3s`, `0.7s`, `1.2s`
- default remains `0.7s`
- pause/resume button
- keyboard shortcut:
  - Space toggles pause only when mode is Blink and focus is not inside input/select/button.
  - `[` slows blink one step.
  - `]` speeds blink one step.
- Persist speed in localStorage.
- Do not persist paused state.

Reduced motion:

- Respect `prefers-reduced-motion: reduce`.
- If reduced motion is active, entering Blink mode starts paused or uses the slowest speed. Choose one and document in tests/help.
- Preferred decision: entering Blink mode starts paused and shows a visible `Blink paused` status in the floating palette.

### 5.10 Focus / Zen mode

Add focus mode as a standard browser-window state, separate from Fullscreen API.

Required behavior:

- Toggle with `Z`.
- Hide or minimize header, primary toolbar, inspector, bottom panel, and footer.
- Keep a minimal floating HUD: frame, mode, pair, and instructions to exit.
- Keep floating viewport palette accessible.
- Escape exits focus mode before exiting browser fullscreen.
- Persist focus mode? No. Do not persist focus mode; reports should reopen in the normal workstation layout.
- Fullscreen button continues to use Fullscreen API and can coexist with focus mode.

### 5.11 N-source behavior

The viewer remains pair-based for comparison modes.

For 3+ clips:

- Pair selection must remain deterministic and reachable.
- Number keys `1` through `9` keep current semantics unless this unit explicitly updates help text.
- Left/reference lock is allowed only if implemented as a clear UI state; otherwise defer.
- Inspector Clips tab must show all clips and identify active/pair roles.
- Pair-scoped alignment persistence must keep existing behavior and tests.

Do not implement an all-clips grid or compositor mode in this plan.

### 5.12 Combobox/input replacement

Do not replace native `<select>` with a custom combobox in this plan.

Reason:

- Native selects are accessible and already covered by renderer tests.
- The larger UX problem is hierarchy and canvas space.
- A custom combobox requires additional keyboard/a11y/test scope.

Allowed low-risk improvement:

- Add an adjacent numeric jump input only if it does not replace the select and has tests.
- Otherwise defer.

### 5.13 Dependencies

Do not add runtime dependencies.

Do not add browser automation/dev dependencies without maintainer approval.

Use existing Python, pytest, and pyright/nodejs-wheel patterns. If browser proof is needed, perform documented manual browser QA rather than adding Playwright/Cypress.

## 6. Files in scope

Primary implementation:

- `src/frame_compare/services/report/renderer.py`
- `src/frame_compare/services/report/assets/viewer.css`
- `src/frame_compare/services/report/assets/viewer.js`

Likely tests:

- `tests/services/test_report_renderer.py`
- `tests/services/test_report_viewer_state.py`
- `tests/services/viewer_state_harness.js`
- `tests/services/test_report.py` only if report-generation behavior changes.

Docs:

- `docs/current-architecture.md`
- this plan file under `docs/plans/`
- `docs/current-cli-contract.md` only if implementation changes CLI/config/report config semantics. The intended implementation should not require this.

Out of scope:

- `src/frame_compare/cli/**`
- `src/frame_compare/config/**`
- `src/frame_compare/render/**`
- `src/frame_compare/vs/**`
- slow.pics publisher/upload code
- Windows portable tooling
- Docker files
- public config enum changes
- new JS framework
- generated mock PNGs committed into the repo

## 7. Public contracts and invariants

Preserve:

- CLI command/flag behavior.
- JSON stdout schema.
- `report.default_mode` accepted config values.
- `ReportPayload.default_mode` values.
- Offline static report behavior.
- Safe JSON embedding in `<script type="application/json" id="report-data">`.
- No inline `style` attributes from `renderer.py`.
- HTTP/HTTPS-only slow.pics href behavior.
- Existing image `src` behavior, including embedded image support.
- Existing frame/category filtering semantics unless explicitly extended.
- Existing pair-scoped alignment persistence semantics.
- Existing image preloading and atomic diff swap behavior.
- Existing `include_filmstrip = false` semantics.
- Import-layer boundaries.

LocalStorage:

- Keep current storage key shape.
- Preserve current fields unless a unit explicitly changes them.
- New fields allowed:
  - `filmstripCollapsed: boolean`
  - `filmstripSize: "compact" | "normal" | "large"`
  - `inspectorOpen: boolean`
  - `inspectorTab: "frame" | "clips" | "align" | "export"`
  - `blinkIntervalMs: 300 | 700 | 1200`
- Do not persist `focusMode`.
- Do not persist `blinkPaused`.

## 8. Implementation units

### Unit 0 — Preflight and plan review

Owner: Orchestrator.

Actions:

1. Confirm branch is `stage1` or the intended implementation branch.
2. Confirm this plan is the only active report-viewer plan.
3. Run or inspect:
   - `git status --short`
   - `git diff --stat`
4. Bootstrap only if needed:
   - `uv sync --group dev --frozen`
5. Request adversarial plan review.

Plan review packet:

```text
REVIEW_REQUEST
TASK: Report viewer UI/UX production refresh
TASK_FAMILY: high-risk generated-report UI/UX feature/refactor
RISK_TIER: High
REVIEW_TARGET: active tracked plan
PLAN_OR_ARTIFACT: docs/plans/2026-06-02-report-viewer-ui-refresh-plan.md
PRIMARY_QUESTIONS:
- Does the plan preserve CLI/config/report payload contracts?
- Are owner files and out-of-scope files correct?
- Are terminology decisions safe, especially Single vs internal overlay?
- Is localStorage handling explicit enough?
- Is verification sufficient without adding browser automation dependencies?
- Are stop-and-replan triggers complete?
```

Exit criteria:

- Blocking plan review findings adjudicated.
- Approved implementation units are unchanged or updated in this plan.
- `update_plan` reflects Unit 1 as next.

### Unit 1 — Terminology refresh and help text

Owner: Renderer/JS/CSS implementer.

Goal:

Resolve user-facing Overlay/Overlays confusion with minimal behavior change.

Changes:

- In `renderer.py`:
  - Mode button text: `Overlay` -> `Single`.
  - Mode ARIA/title: `Single clip view (O)`.
  - HUD button text: `Overlays` -> `HUD`.
  - HUD ARIA/title: `Hide HUD (H)` / `Show HUD (H)` as runtime changes.
  - Help modal mode row: `Modes (Slider/Single/Diff/Blink)`.
  - Help modal HUD row: `Toggle HUD`.
- In `viewer.js`:
  - Keep internal mode value `overlay`.
  - Update HUD runtime labels/titles/ARIA.
  - Ensure `O` still selects Single/internal overlay mode.
  - Ensure `H` still toggles HUD.
- In `viewer.css`:
  - No major layout changes yet; only class names if necessary.
- Tests:
  - Update renderer tests that assert mode/help/HUD labels.
  - Add/assert that `data-mode="overlay"` remains in generated markup while visible text is `Single`.

Acceptance criteria:

- User never sees a top-level control labeled `Overlay` or `Overlays`.
- Config/payload/default mode value `"overlay"` remains accepted.
- Existing viewer mode behavior unchanged.
- Tests pass:
  - `pytest tests/services/test_report_renderer.py -q`
  - `pytest tests/services/test_report_viewer_state.py -q`

Review focus:

- No public config enum drift.
- No accidental break to default mode handling.
- No stale help/footer text.

### Unit 2 — Layout shell and primary/secondary toolbar split

Owner: Renderer/CSS implementer.

Goal:

Create clear hierarchy without yet implementing the floating palette.

Changes:

- In `renderer.py`:
  - Split current `.rv-controls` into:
    - `.rv-primary-controls`
    - `.rv-secondary-controls` or a stage-hosted placeholder shell.
  - Primary controls contain:
    - frame prev/select/next
    - mode buttons
    - pair/active clip selectors
    - alignment status pill placeholder
  - Secondary controls contain viewport controls initially, if not yet moved.
- In `viewer.js`:
  - Update `cacheDOM()` selectors only as needed.
  - Preserve all existing control IDs where possible.
  - Add `updateAlignmentStatus()` and call it after alignment state changes and render.
- In `viewer.css`:
  - Style primary controls with stronger grouping.
  - Demote secondary controls visually.
  - Keep responsive behavior sane at <= 768px.

Acceptance criteria:

- Existing controls still work.
- Toolbar visual hierarchy is clear.
- Alignment status pill shows current pair state.
- No vertical space regression beyond current toolbar height before Unit 3.
- Tests updated for new toolbar classes and alignment status hook.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
```

### Unit 3 — Floating viewport palette

Owner: CSS/JS implementer.

Goal:

Move viewport and tool controls into a floating stage palette.

Changes:

- In `renderer.py`:
  - Render `.rv-viewport-palette` inside `.rv-viewer-stage`.
  - Move or duplicate the following controls into the palette, but do not leave duplicate active controls:
    - zoom out
    - zoom range/value or compact zoom control
    - zoom in
    - reset viewport
    - fit actual/width/height/fill
    - alignment trigger
    - HUD toggle
    - fullscreen
    - focus mode toggle if Unit 8 is done now; otherwise leave placeholder out.
- In `viewer.js`:
  - Update DOM cache references.
  - Preserve behavior for zoom, fit, alignment popover, HUD, and fullscreen.
  - Ensure palette controls are disabled in empty/error states.
- In `viewer.css`:
  - Place palette at bottom-right inside stage.
  - Ensure readable contrast.
  - Ensure no image pointer conflicts for slider dragging except when interacting with the palette itself.
  - Ensure focus-visible styles are clear.

Acceptance criteria:

- Primary toolbar no longer contains viewport controls.
- Palette is keyboard reachable.
- Palette does not block main stage interactions outside its own bounds.
- Fullscreen mode still updates button text/ARIA.
- Empty report state disables palette controls except Help/Info as appropriate.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
```

Manual smoke:

- Open a generated report in a browser.
- Use mouse wheel zoom.
- Use palette zoom buttons.
- Use fit height/width/fill.
- Toggle HUD.
- Toggle fullscreen.

### Unit 4 — Collapsible bottom panel and filmstrip size modes

Owner: Renderer/JS/CSS implementer.

Goal:

Maximize canvas space without requiring browser fullscreen.

Changes:

- In `renderer.py`:
  - Wrap category filters and filmstrip in `.rv-bottom-panel`.
  - Add collapse handle/button:
    - ID: `btn-filmstrip-toggle`
    - text expanded: `Hide filmstrip`
    - text collapsed: `Show filmstrip`
  - Add size control:
    - ID: `filmstrip-size-select` or segmented buttons.
    - Values: `compact`, `normal`, `large`.
- In `viewer.js`:
  - Add state:
    - `filmstripCollapsed`
    - `filmstripSize`
  - Restore/persist both through existing localStorage payload.
  - Add `setFilmstripCollapsed()`, `toggleFilmstrip()`, `setFilmstripSize()`.
  - Add keyboard shortcut `F`.
  - Update help modal.
  - If filmstrip is disabled by config/no items, toggle must not imply hidden thumbnails can be shown.
- In `viewer.css`:
  - Implement `.rv-bottom-panel--collapsed`.
  - Implement size classes:
    - `.rv-filmstrip--compact`
    - `.rv-filmstrip--normal`
    - `.rv-filmstrip--large`
  - Adjust stage flex sizing so collapse actually gives space back to canvas.

Acceptance criteria:

- `F` toggles bottom panel.
- Toggle state persists per report.
- Size state persists per report.
- `include_filmstrip=False` still renders no thumbnail items.
- Category filters hide with collapsed panel and restore when expanded.
- Frame keyboard navigation works while collapsed.
- Active frame scrolls into view after expansion.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
node tests/services/viewer_state_harness.js
```

### Unit 5 — Smart stage labels

Owner: CSS/JS implementer.

Goal:

Reduce image obstruction while improving side identification.

Changes:

- In `renderer.py`:
  - Replace or augment existing `.rv-stage-labels` markup with elements that can serve:
    - slider-attached left label
    - slider-attached right label
    - single active label
    - blink active label
  - Keep IDs stable or update tests accordingly.
- In `viewer.js`:
  - Compute label placement from current reveal/divider position.
  - Use CSS variables when possible:
    - `--reveal-percent`
    - `--label-left-x`
    - `--label-right-x`
  - Update labels on:
    - `render()`
    - `updateSlider()`
    - mode changes
    - clip changes
    - HUD toggle
  - Ensure labels do not intercept pointer events.
- In `viewer.css`:
  - Slider label placement near divider.
  - Clamped placement within canvas/image region where practical.
  - Low-obstruction label placement for Single/Blink.
  - Keep Diff labels hidden unless deliberately minimal.

Acceptance criteria:

- Slider labels move with divider.
- Labels do not block slider dragging.
- HUD toggle hides all stage labels/metadata.
- Diff mode remains low-obstruction.
- Tests assert markup/hooks and key CSS selectors, not brittle pixel positions.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
```

Manual smoke:

- Drag slider from 0% to 100%.
- Confirm labels remain readable and do not block the divider.
- Toggle HUD.
- Switch Single/Diff/Blink.

### Unit 6 — Inspector drawer

Owner: Renderer/JS/CSS implementer.

Goal:

Make report/frame/clip metadata available without interrupting QC.

Changes:

- In `renderer.py`:
  - Add `.rv-inspector` drawer.
  - Add tab controls:
    - `Frame`
    - `Clips`
    - `Align`
    - `Export`
  - Populate initial static metadata where possible from payload.
  - Add dynamic placeholders for current-frame/pair state.
- In `viewer.js`:
  - Add state:
    - `inspectorOpen`
    - `inspectorTab`
  - Restore/persist both.
  - Toggle with `I` and Info button.
  - Update inspector data on render/frame/clip/mode/alignment changes.
  - Add Escape close behavior when inspector overlays the stage on narrow screens.
  - Ensure Help modal and inspector do not conflict.
- In `viewer.css`:
  - Desktop: right side drawer that reduces available stage width.
  - Narrow screen: overlay drawer.
  - Accessible focus styles and scroll behavior.
- Tests:
  - Renderer tests assert drawer markup and tab labels.
  - Viewer harness tests state persistence for `inspectorOpen` and `inspectorTab`.

Acceptance criteria:

- Info button opens/toggles inspector, not a blocking modal, unless narrow-screen design keeps modal as a fallback.
- Frame tab updates when frame changes.
- Clips tab handles 2, 4, and 10 clips without clipping labels unusably.
- Align tab shows current pair offset and reset controls work.
- Export tab shows report ID/generated/slow.pics status.
- Inspector closed state persists.
- Inspector tab persists.
- No new required payload fields.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
node tests/services/viewer_state_harness.js
```

### Unit 7 — Blink speed, pause, and reduced motion

Owner: JS/CSS/renderer implementer.

Goal:

Make Blink usable and accessible.

Changes:

- In `renderer.py`:
  - Add blink controls to floating palette or mode-adjacent mini control:
    - speed select/options: `0.3s`, `0.7s`, `1.2s`
    - pause/resume button
  - Controls may be visible only in Blink mode.
- In `viewer.js`:
  - Add state:
    - `blinkIntervalMs`
    - `blinkPaused`
  - Persist `blinkIntervalMs` only.
  - Do not persist `blinkPaused`.
  - Replace hard-coded `700` interval with state-driven interval.
  - Restart interval when speed changes.
  - Add keyboard shortcuts:
    - Space pause/resume in Blink mode
    - `[` slower
    - `]` faster
  - Check `window.matchMedia("(prefers-reduced-motion: reduce)")`.
  - If reduced motion matches, entering Blink mode starts paused.
- In `viewer.css`:
  - Hide blink controls outside Blink mode or visually disable them.
  - Ensure paused state visible.

Acceptance criteria:

- Default speed remains 700ms.
- Speed persists per report.
- Pause state does not persist.
- Reduced-motion users do not get immediate auto-blink.
- Existing blink pair behavior and active clip toggling remain correct.
- Help modal documents shortcuts.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
node tests/services/viewer_state_harness.js
```

### Unit 8 — Focus / Zen mode

Owner: JS/CSS/renderer implementer.

Goal:

Offer standard-window canvas maximization.

Changes:

- In `renderer.py`:
  - Add focus mode button to palette:
    - ID: `btn-focus-mode`
    - label: `Focus`
    - ARIA: `Enter focus mode`
- In `viewer.js`:
  - Add transient state:
    - `focusMode`
  - Do not persist.
  - Toggle with `Z`.
  - Escape exits focus mode before closing fullscreen.
  - When entering focus mode:
    - close inspector
    - collapse visual chrome
    - keep minimal HUD and floating palette
  - Exiting focus restores normal layout; do not overwrite persisted filmstrip/inspector preferences except inspector may remain closed if user closed it.
- In `viewer.css`:
  - `.rv-focus-mode` or body-level class hides/minimizes:
    - header
    - primary toolbar
    - inspector
    - bottom panel
    - footer
  - Keep stage filling viewport.
  - Keep focus exit hint visible.
  - Ensure fullscreen and focus mode work together.

Acceptance criteria:

- `Z` enters/exits focus mode.
- Escape exits focus mode first.
- Focus mode does not persist after reload.
- Fullscreen still works.
- Keyboard frame navigation still works.
- HUD toggle still works.

Targeted verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
```

Manual smoke:

- Enter focus mode.
- Navigate frames.
- Toggle HUD.
- Toggle browser fullscreen while focus mode is active.
- Escape exits in correct order.

### Unit 9 — Responsive and accessibility hardening

Owner: Accessibility/UI reviewer-implementer pair.

Goal:

Make the final layout usable on common desktop/laptop widths and keyboard-only navigation.

Changes:

- Review CSS breakpoints:
  - >= 1600px
  - 1366px
  - <= 992px
  - <= 768px
- Increase hit targets for header icon buttons and floating palette buttons where needed.
- Ensure all interactive controls have labels/titles/ARIA state.
- Ensure no hidden disabled controls stay tabbable.
- Ensure modals/drawers trap or manage focus appropriately.
- Ensure `Escape` order:
  1. help modal
  2. inspector overlay
  3. alignment popover
  4. focus mode
  5. fullscreen
- Ensure text contrast is readable in dark theme.
- Add `prefers-reduced-motion` CSS/JS behavior for blink and transitions.

Acceptance criteria:

- Keyboard-only user can access:
  - frame navigation
  - modes
  - clip selectors
  - viewport palette
  - filmstrip toggle/size
  - inspector tabs
  - alignment reset
  - help
- No major control unreachable at 1366x768.
- Header/toolbar no longer consume excessive vertical space when filmstrip is collapsed.
- Help modal matches actual shortcuts.

Verification:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
```

Manual browser QA required; see Section 11.

### Unit 10 — Docs and final tests

Owner: Docs/test implementer.

Docs:

- Update `docs/current-architecture.md` report viewer feature summary to mention:
  - Single label for internal overlay mode
  - HUD toggle
  - collapsible/size-adjustable filmstrip
  - inspector drawer
  - floating viewport palette
  - focus mode
  - blink speed/pause/reduced-motion handling
- Do not update `docs/current-cli-contract.md` unless implementation changes CLI/config behavior.
- Keep this plan active until closeout; mark historical after accepted.

Tests:

- Ensure renderer tests cover:
  - new labels
  - no stale `Overlay`/`Overlays` user-facing text
  - floating palette markup
  - bottom panel controls
  - inspector drawer/tabs
  - focus mode button
  - blink controls
  - no inline style attributes
  - include_filmstrip false behavior
- Ensure viewer-state harness covers:
  - localStorage new fields
  - invalid persisted values for new fields fall back safely
  - old core fields still restored
  - filmstrip collapsed/size persistence
  - inspector open/tab persistence
  - blink speed persistence
  - focus mode not persisted
  - pair alignment behavior unchanged
- Avoid giant HTML snapshots.

Final verification commands:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Manual browser proof is also required.

## 9. Subagent implementation routing

The orchestrator should use narrow implementation subagents.

### 9.1 Renderer markup subagent

Scope:

- `renderer.py`
- renderer-related tests only

Do not edit:

- `viewer.js` except for IDs coordinated in the unit
- unrelated report generation code
- payload schema unless the unit explicitly says so

Prompt template:

```text
IMPLEMENTATION_REQUEST
ROLE: renderer markup subagent
UNIT: <unit number and name>
APPROVED_PLAN: docs/plans/2026-06-02-report-viewer-ui-refresh-plan.md
FILES_ALLOWED:
- src/frame_compare/services/report/renderer.py
- tests/services/test_report_renderer.py
OBJECTIVE:
<unit objective>
CONSTRAINTS:
- Preserve ReportPayload values and CLI/config behavior.
- No inline style attributes.
- No new dependencies.
- No broad snapshots.
STOP_IF:
- You need a payload schema change not named in the plan.
- You need to change config enums or CLI behavior.
OUTPUT:
Changed files, targeted tests run, residual risks.
```

### 9.2 Viewer JS state subagent

Scope:

- `viewer.js`
- `viewer_state_harness.js`
- `test_report_viewer_state.py`

Prompt template:

```text
IMPLEMENTATION_REQUEST
ROLE: viewer JS state subagent
UNIT: <unit number and name>
APPROVED_PLAN: docs/plans/2026-06-02-report-viewer-ui-refresh-plan.md
FILES_ALLOWED:
- src/frame_compare/services/report/assets/viewer.js
- tests/services/viewer_state_harness.js
- tests/services/test_report_viewer_state.py
OBJECTIVE:
<unit objective>
CONSTRAINTS:
- Preserve existing pair-scoped alignment behavior.
- Preserve existing mode values, especially internal "overlay".
- Preserve existing storage key shape.
- Do not persist focus mode or blink paused state.
- Do not add browser dependencies.
STOP_IF:
- Current state behavior contradicts the plan.
- A shortcut conflicts with browser/input behavior.
OUTPUT:
Changed files, targeted tests run, residual risks.
```

### 9.3 CSS/layout subagent

Scope:

- `viewer.css`
- renderer tests only when hooks/classes are asserted

Prompt template:

```text
IMPLEMENTATION_REQUEST
ROLE: CSS/layout subagent
UNIT: <unit number and name>
APPROVED_PLAN: docs/plans/2026-06-02-report-viewer-ui-refresh-plan.md
FILES_ALLOWED:
- src/frame_compare/services/report/assets/viewer.css
- tests/services/test_report_renderer.py only if class/hook assertions need updates
OBJECTIVE:
<unit objective>
CONSTRAINTS:
- Preserve dark theme.
- Preserve stage as primary visual focus.
- Keep controls keyboard/focus visible.
- Do not use external fonts/assets.
- Do not hide controls in a way that leaves them tabbable.
STOP_IF:
- Layout requires renderer markup not in the unit.
- Responsive behavior cannot be made usable at 1366x768.
OUTPUT:
Changed files, targeted tests run, manual visual risks.
```

### 9.4 Test/docs subagent

Scope:

- targeted tests
- architecture docs
- plan status at closeout

Prompt template:

```text
IMPLEMENTATION_REQUEST
ROLE: test/docs subagent
UNIT: <unit number and name>
APPROVED_PLAN: docs/plans/2026-06-02-report-viewer-ui-refresh-plan.md
OBJECTIVE:
Add/adjust tests and docs required by the unit.
CONSTRAINTS:
- Test public seams and generated output hooks.
- Avoid brittle full HTML/CSS snapshots.
- Do not update current-cli-contract unless CLI/config behavior changed.
- Do not mark the plan Historical until orchestrator closeout.
STOP_IF:
- Implementation behavior is unclear or contradicts tests.
OUTPUT:
Changed files, tests run, doc authority notes.
```

## 10. Adversarial review routing

Every implementation unit needs review before the next unit starts.

Review subagents:

1. Repo contract reviewer
   - CLI/config/report payload drift
   - docs authority drift
   - import-layer violations
2. UI behavior reviewer
   - stale labels
   - confusing states
   - canvas space regression
   - mode semantics
3. JS state reviewer
   - localStorage drift
   - pair alignment regression
   - keyboard shortcut conflicts
   - empty/error state failures
4. Accessibility reviewer
   - ARIA/focus/Escape order
   - reduced motion
   - keyboard reachability
5. Test sufficiency reviewer
   - brittle assertions
   - missing coverage
   - verification mismatch

Implementation review packet:

```text
REVIEW_REQUEST
TASK: Report viewer UI/UX production refresh
UNIT: <unit number and name>
RISK_TIER: High
REVIEW_TARGET: current diff for this unit
APPROVED_PLAN: docs/plans/2026-06-02-report-viewer-ui-refresh-plan.md
FILES_CHANGED:
<paste git diff --stat and changed files>
PRIMARY_QUESTIONS:
- Does the diff implement only the approved unit?
- Did it preserve CLI/config/report payload contracts?
- Did it preserve pair-scoped alignment and existing viewer state?
- Are labels, help text, ARIA, and shortcuts consistent?
- Are tests sufficient and non-brittle?
- Is the named verification enough for the changed surface?
OUTPUT:
Findings ordered by severity with file/line evidence. Say explicitly if no blocking findings.
```

Adjudication:

- Use `review-adjudication` for every finding.
- Accepted findings must either be fixed before continuing or explicitly deferred with maintainer-acceptable rationale.
- Blocking findings cannot be deferred by an implementer subagent.

## 11. Verification strategy

Primary verification modes:

- `contract-first`: generated report HTML/JS/CSS and localStorage state.
- `manual-runtime`: visual/browser interaction proof.
- `refactor-invariance`: preserve viewer behavior while restructuring layout.

Automated verification per unit:

```bash
.venv/bin/pytest tests/services/test_report_renderer.py tests/services/test_report_viewer_state.py -q
node tests/services/viewer_state_harness.js
```

Use the Node harness command only after units that touch state logic. If Node is accessed through the pyright nodejs wheel in pytest, the direct `node` command may be unavailable; in that case run the pytest wrapper test and record the direct Node command as not applicable.

Final verification:

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Docker verification:

- Not required unless files under `render/**`, `vs/**`, Docker files, or runtime integration scripts are changed.
- If accidentally touched, stop and re-plan before proceeding.

Windows portable verification:

- Not required unless Windows portable files, release asset docs, or packaging workflow files are changed.
- If accidentally touched, stop and re-plan before proceeding.

Manual browser QA required:

Browsers:

- Chromium-based browser
- Firefox if available

Report cases:

1. Normal 2-clip report.
2. 4-clip or more report, generated synthetically if local sample data is absent.
3. Empty payload/unit-test generated report if easy to produce.
4. `include_filmstrip = false` report, generated synthetically if local sample data is absent.

Viewport sizes:

- 3440x1440 or ultrawide if available.
- 1920x1080.
- 1366x768.
- <= 768px responsive emulation.

Manual checklist:

- Report opens from local filesystem.
- Header title/counts visible.
- Primary toolbar usable.
- Slider, Single, Diff, Blink modes work.
- `O` selects Single/internal overlay mode.
- `H` toggles HUD.
- `F` collapses/expands bottom panel.
- Filmstrip size changes and persists.
- Frame/category filters work.
- Active filmstrip item scrolls into view.
- Floating palette zoom/fit/HUD/fullscreen controls work.
- Alignment popover/drawer controls work.
- Pair alignment persists per pair.
- Inspector opens/closes with Info/`I`.
- Inspector tabs update on frame/clip changes.
- Blink speed/pause controls work.
- Reduced-motion simulation starts Blink paused.
- `Z` focus mode works and does not persist.
- Escape ordering is correct.
- Keyboard shortcuts do not fire inside input/select/button controls.
- Missing image path shows a safe error/status, not a broken infinite loop.
- No major labels obstruct critical image content in default layout.

Record manual proof in closeout:

```text
MANUAL_BROWSER_PROOF
BROWSER:
REPORT:
VIEWPORTS:
CHECKS_PASSED:
CHECKS_FAILED:
NOT_VERIFIED:
```

## 12. Stop-and-replan triggers

Stop and ask the maintainer before continuing if any of these occur:

1. A public config enum/value change appears necessary.
2. CLI behavior, JSON stdout, report auto-open, or slow.pics behavior appears affected.
3. New runtime or dev dependencies appear necessary.
4. Browser automation dependency is desired.
5. Payload schema requires new required fields.
6. Upstream orchestration/render/VS changes appear necessary.
7. Existing pair-scoped alignment behavior conflicts with the planned UX.
8. LocalStorage migration becomes more complex than adding optional fields.
9. A second active plan exists for the same workstream.
10. `docs/current-architecture.md` or `docs/current-cli-contract.md` contradicts observed code in a way not safely fixable here.
11. Responsive layout cannot remain usable at 1366x768 without reducing scope.
12. Tests become broad snapshots instead of behavior/contract assertions.
13. Manual browser proof reveals a severe UX regression that automated tests miss.
14. Any subagent wants to touch out-of-scope files.

## 13. Rollback surface

The implementation must be easy to revert by units.

Preferred commit/checkpoint boundaries:

1. Terminology and help.
2. Toolbar/layout shell.
3. Floating palette.
4. Bottom panel/filmstrip.
5. Smart labels.
6. Inspector.
7. Blink controls.
8. Focus mode.
9. Docs/tests.

Rollback should not require changing config, payload generation, render pipeline, or CLI code.

If a late unit fails, keep earlier approved units if they remain coherent and reviewed.

## 14. Final closeout

Before claiming completion:

1. Run `git status --short`.
2. Run `git diff --stat`.
3. Inspect diffs for all changed files.
4. Confirm no unrelated dirty files were modified.
5. Run final verification commands.
6. Complete manual browser proof.
7. Run final adversarial review.
8. Adjudicate final review.
9. Update `docs/current-architecture.md`.
10. Mark this plan `Status: Historical` only after maintainer acceptance or merge readiness.
11. Report:
    - changed files
    - verification commands and results
    - manual proof status
    - review status
    - residual risks
    - deferred items

## 15. Deferred follow-ups

These are intentionally not part of this plan:

- Custom combobox replacing native `<select>`.
- All-clips grid/compositor comparison mode.
- Pixel black-bar detection.
- New payload metrics/timecode fields requiring upstream analysis changes.
- Playwright/Cypress browser automation dependency.
- Public config rename from `overlay` to `single`.
- Slow.pics UI integration changes beyond displaying existing status/link.
