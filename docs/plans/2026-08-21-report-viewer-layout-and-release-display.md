---
search:
  exclude: true
---

Status: Active
Scope: Local report clip presentation, stable toolbar composition, and responsive Inspector layout
Owner: Primary implementation controller

Progress:

- 2026-08-21 — Session A implemented report v1.2 clip display metadata, explicit
  identity exclusion, release-aware human-surface adoption, canonical review/key
  preservation, focused Python/Node coverage, and current authority-doc updates.
  Verification and commit evidence are recorded in the Session A handoff; this plan
  intentionally remains active and is not SHA-locked.
- 2026-08-21 — Session B implemented the presentational context wrapper, CSS-only
  wide/medium/narrow toolbar zones, one responsive Inspector width shared with stage
  reservation, stable release-aware clip-card hierarchy, local wrapping/overflow
  constraints, and real-Chrome geometry/overflow/accessibility probes at the required
  viewport widths. The plan remains Active for Session C integration, visual evidence,
  documentation closeout, and review.
- 2026-08-21 — Session C integration passed the focused report/Node/browser suite,
  the full repository gate, strict documentation build, and an additional real-Chrome
  2560×1440 geometry probe. Adversarial review found and remediation closed the v1.2
  Review initialization defect, impossible cross-version transfer guidance, duplicated
  release presentation, stale current-facing screenshots, and legacy display fallbacks.
  The final read-only reviewer cleared all blockers and the Ponytail verdict was “Lean
  already. Ship.” Physical-Windows v1.2 recapture and extension-backed interactive
  Chrome zoom remain unavailable on this host, so this plan stays Active until that
  manual evidence is recorded.

# Frame Compare Local Report Presentation and Layout Refinement
## Execution-Ready Plan

**Repository:** `TJZine/frame-compare`
**Working branch:** `dev/v0.2.0`
**Branch policy:** work directly on the existing `dev/v0.2.0`; do not create or switch to a feature branch
**Dispatch:** use the current repository `worker` role. When the host supports a per-session override, the maintainer intends GPT-5.6 Sol light; otherwise preserve the role TOML as authoritative
**Review:** one fresh adversarial read-only review plus Ponytail minimality review
**Suggested tracked path:** `docs/plans/2026-08-21-report-viewer-layout-and-release-display.md`
**Suggested commit sequence:**

1. `feat(report): add release-aware clip presentation`
2. `feat(report): stabilize toolbar and inspector layout`
3. `docs(report): update viewer guidance and visual evidence`

> This plan is deliberately not SHA-locked. Every session must fetch and re-read the
> latest `dev/v0.2.0` before editing. Capture an execution-time baseline commit for
> review and rollback, but do not write that SHA into this durable plan. Current
> branch source, tests, contracts, and unrelated maintainer work outrank anticipated
> paths or signatures below.

---

# 1. Executive implementation decision

Implement this work as **three sequential bounded worker sessions suitable for GPT-5.6 Sol light** on the existing
`dev/v0.2.0`, followed by one fresh adversarial review.

The work is one product package but too broad for a single reliable light-reasoning
session because it combines:

- an additive generated-report payload contract;
- reuse of the newly implemented release-identity system;
- an audit of every human-facing clip-name consumer in multiple report JS assets;
- responsive toolbar composition;
- a larger, overflow-safe Inspector;
- real-browser geometry and accessibility proof;
- user-facing documentation and screenshots.

The sessions must run sequentially. They share `payload.py`, `renderer.py`,
`viewer.js`, the browser fixture, report contract documentation, and the generated
artifact version. Parallel writes are not justified.

## Session sequence

| Session | Outcome | Primary risk |
| --- | --- | --- |
| A | Report v1.2 clip-display contract and release-aware names across viewer surfaces | Display metadata leaking into identity/state |
| B | Stable three-zone toolbar and responsive overflow-safe Inspector | CSS geometry, responsive behavior, accessibility |
| C | Browser/manual acceptance, docs, full verification, closeout | Integration and evidence completeness |
| Review | Fresh adversarial and Ponytail review | Hidden contract drift or over-engineering |

Do not add another planning/reviewer loop unless the fresh review finds a material
issue.

---

# 2. Verified current problems

## 2.1 Toolbar controls move when mode changes

Current markup places frame navigation, mode buttons, a mode-specific context group,
and alignment status as flex siblings. Current CSS uses:

- `display: flex`;
- `flex-wrap: wrap`;
- a growing `.rv-frame-controls`;
- hidden pair/active/grid context groups with materially different widths.

As the visible context group changes between Slider, Single, Diff, Blink, and Grid,
the frame group absorbs a different amount of remaining width and the mode group moves
horizontally.

This is a layout-model problem, not a transition/animation problem.

## 2.2 The report still renders canonical long labels in human controls

Current report markup and JS use `clip["label"]` or `clip.label` directly in:

- top-bar clip selects;
- stage source labels;
- grid and lens identities;
- Inspector source/clip/pair text;
- info-modal pair and clip headings;
- review-facing clip choices and accessible labels.

The newly implemented release-identity system already provides structured:

- full compact identity;
- release descriptor;
- micro descriptor;
- deterministic presentation-name collision handling.

The report must consume those facts rather than parsing or naively truncating
filenames in JavaScript.

## 2.3 Inspector is too narrow and permits unusable overflow

Current desktop Inspector width is fixed at `min(360px, calc(100vw - 2rem))`, and the
viewer stage reserves the same 360px. Clip headings intentionally ellipsize. The
panel scrolls vertically but does not establish a complete horizontal-overflow policy.

At desktop widths this makes long source, signal, and presentation data difficult to
read, and may produce clipped content or a document/panel horizontal scrollbar.

The primary fix is **not** to add horizontal scrolling. It is to:

- allocate a useful responsive width;
- present release-aware names;
- wrap exact filenames and technical values;
- constrain every internal grid/flex item with `min-width: 0`;
- eliminate horizontal overflow.

The Inspector tab strip may continue to scroll horizontally on narrow screens.

---

# 3. Repository workflow

## 3.1 Work directly on `dev/v0.2.0`

Do not create another branch.

At the start of every session:

```bash
git status --short
git branch --show-current
git fetch origin
```

Required branch:

```text
dev/v0.2.0
```

Then:

1. Inspect whether `origin/dev/v0.2.0` advanced.
2. Incorporate it only through the maintainer's normal non-force workflow.
3. Confirm prior session commits are present.
4. Preserve unrelated tracked and untracked work.
5. Stop on conflicts rather than guessing.
6. Re-read affected files after any update.

Before every commit or push:

```bash
git status --short
git diff --check
git diff --stat
git diff
git fetch origin
```

Never force-push `dev/v0.2.0`.

## 3.2 Required reads and skills

Each session must read the current versions of:

- `AGENTS.md`
- relevant `docs/ENGINEERING_RUNBOOK.md`
- `docs/current-cli-contract.md`
- `docs/current-architecture.md`
- `docs/guides/reports-and-overlays.md`
- `docs/guides/sources-and-labels.md`
- this active plan
- complete affected owners and focused tests

Load the smallest matching skill set:

- `.agents/skills/model-selection/SKILL.md`
- `.agents/skills/report-output-patterns/SKILL.md`
- `.agents/skills/architecture-boundaries/SKILL.md`
- `.agents/skills/python-quality-boundaries/SKILL.md`
- `.agents/skills/python-test-design/SKILL.md`
- `.agents/skills/closeout-verification/SKILL.md`
- `.agents/skills/bounded-worker-execution/SKILL.md`

The final reviewer should use the current repository reviewer role and production or
suggestion-review skill.

## 3.3 Active-plan lifecycle

This is a cross-session public generated-artifact change, so a tracked active plan is
justified.

If committed under `docs/plans/`:

- preserve the Zensical search-exclusion front matter;
- keep `Status: Active` during implementation;
- keep only one active plan for this workstream;
- mark `Status: Historical` only after accepted review findings are closed and all
  required verification passes.

---

# 4. Frozen contracts and invariants

Do not change:

- CLI commands, options, JSON, streams, or exit codes;
- source discovery, probing, selection, alignment, rendering, or publishing;
- canonical `ClipState.label`;
- cache keys, fingerprints, alignment keys, screenshot lookup keys, or source IDs;
- physical screenshot filenames or run-folder names;
- slow.pics collection/column behavior in this package;
- baked screenshot overlay text;
- report image membership, frame mapping, geometry mapping, or source identity;
- browser review JSON schema and canonical clip keys;
- viewer keyboard shortcuts;
- default mode or selected clips;
- report auto-open behavior.

The new report display metadata is presentation-only.

---

# 5. Report artifact version and compatibility decision

## 5.1 Bump generated report version to `1.2`

The report clip payload gains a new nested display object and the viewer uses it in
multiple surfaces. This is a real generated-artifact contract revision.

Set:

```python
REPORT_VERSION = "1.2"
```

Update the report footer, documentation, tests, and expected payload version.

## 5.2 Existing reports

Existing v1.1 HTML reports are self-contained and remain unchanged/viewable.

No in-place report migration is needed.

## 5.3 Browser-local state

The report ID currently incorporates the report version. Newly generated v1.2 reports
may therefore receive a new report ID and a fresh browser-local viewer/review state.

Do not add state migration in this package. Review export/import is scoped to copies of
the exact same report ID and payload version; it cannot transfer v1.1 review data into a
regenerated v1.2 report.

## 5.4 Display metadata must not affect semantic report identity

Although the version bump changes IDs once, future wording or formatting changes inside
v1.2 must not change `report_id`.

`build_report_identity_clips()` must explicitly exclude the new display object.

Add a regression test proving that changing only:

- primary display name;
- control label;
- micro label;
- exact filename display text;

does not change `report_id`.

Canonical label, source identity, frame facts, rendering facts, and other existing
identity inputs remain unchanged.

---

# 6. Additive report clip display contract

## 6.1 Payload shape

Add:

```python
class ReportClipDisplayPayload(TypedDict):
    primary: str
    release: str
    control: str
    micro: str
    filename: str
```

Add the required nested field to new v1.2 clip payloads:

```python
class ReportClipPayload(TypedDict):
    ...
    display: ReportClipDisplayPayload
```

Add the corresponding frozen input dataclass:

```python
@dataclass(frozen=True, slots=True)
class ReportClipDisplayInfo:
    primary: str
    release: str
    control: str
    micro: str
    filename: str
```

Add:

```python
display: ReportClipDisplayInfo
```

to `ClipInfo` as required v1.2 input. Update direct test construction to supply the
complete display profile; do not retain a v1.1 compatibility fallback.

## 6.2 Field semantics

### `primary`

- explicit source label when configured;
- otherwise full compact release identity;
- canonical label fallback when parsing is unavailable.

Example:

```text
Avatar Aang The Last Airbender (2026) | 2160p | ATV WEB-DL | DV HDR10+ | REPACK | Kitsune
```

### `release`

- parsed release descriptor even when an explicit label exists;
- empty string when no informative release descriptor exists.

Example:

```text
2160p | ATV WEB-DL | DV HDR10+ | REPACK | Kitsune
```

### `control`

- explicit source label when configured;
- otherwise unique release descriptor;
- full primary/canonical fallback when release descriptor is unavailable.

Use for selects and ordinary source controls.

### `micro`

- explicit source label when configured;
- otherwise unique micro descriptor;
- control fallback.

Use for lens/grid and other constrained visual labels.

### `filename`

Exact `clip.path.name`, never truncated in the payload.

## 6.3 Build once at report assembly

In the current report phase, build all display profiles once for the complete clip
set using the existing:

- `format_compact_identity`;
- `format_release_descriptor`;
- `format_micro_descriptor`;
- `unique_presentation_names`.

Use source roles:

```text
Reference
Comparison 1
Comparison 2
...
```

to resolve collisions deterministically.

Do not parse filenames in report JavaScript.

Do not parse repeatedly during frame/render loops.

## 6.4 Fallback

When release metadata is absent:

```text
primary = canonical label
release = ""
control = canonical label
micro = canonical label
filename = exact filename
```

---

# 7. Report display-name adoption matrix

Audit every current human-facing `clip.label` / `clip["label"]` read in:

- `renderer.py`
- `viewer.js`
- `grid_view.js`
- `lens.js`
- review-controller/state UI code

Classify each use as:

- canonical identity/key — unchanged;
- human presentation — migrate to the appropriate display profile.

| Surface | Display profile | Exact filename availability |
| --- | --- | --- |
| Header report title | Existing report title | No change |
| Top-bar pair/single selects | `control` | `title`/accessible text uses `primary` + `filename` |
| Stage left/right labels | `control` | Inspector/info modal |
| Grid cell headings | `control` or `micro` by current density | Inspector/info modal |
| Lens identities and source choices | `micro` | Inspector/info modal |
| Inspector source-frame list | `control` | Inspector Clips tab |
| Inspector clip cards | stable role + `primary`/`release` | Full `filename` row |
| Inspector alignment pair | `control` | Clips tab |
| Review preferred-clip options | `control` text; canonical value/key | Clips tab |
| Info modal default pair | `control` | Clip details |
| Info modal clip headings | `primary` | Full `filename` row |
| Image alt/ARIA source identity | `primary` | Include filename when helpful |
| Review/export stored data | Canonical label | Unchanged |
| Frame filmstrip labels | Frame labels | No source-name change |
| Baked screenshot overlay | Canonical existing overlay label | Explicitly deferred |

## 7.1 JavaScript helper

Add a small viewer-owned pure display helper, for example:

```javascript
clipDisplay(clip, profile = 'control')
clipFilename(clip)
clipAccessibleName(clip)
```

It must:

- use the payload display object;
- fall back to `clip.label` / `clip.name`;
- perform no filename parsing;
- contain no DOM state.

`grid_view.js` and `lens.js` should call the viewer helper through their existing
viewer reference. Do not add a new asset/module unless current code proves that direct
reuse would otherwise duplicate logic.

## 7.2 Native select behavior

Render option text with `control`.

Preserve numeric option values/index semantics.

Add a full `title` to each option where useful and update the selected `<select>`
element's `title` after mode/clip changes to:

```text
<primary> — <filename>
```

Do not replace native selects with custom dropdown components.

---

# 8. Stable top-toolbar composition

## 8.1 Markup

Keep one toolbar and current keyboard/focus order.

Add a wrapper around mode-specific context controls and alignment status:

```html
<div class="rv-context-zone">
    <div data-control-scope="grid" ...></div>
    <div data-control-scope="pair" ...></div>
    <div data-control-scope="active" ...></div>
    <div id="alignment-status" ...></div>
</div>
```

Keep frame controls and mode controls as existing siblings.

The wrapper is presentational only and has no new ARIA role.

## 8.2 Wide-screen layout

Replace the primary flex layout with a three-zone CSS grid:

```css
.rv-primary-controls {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    grid-template-areas: "frame mode context";
    align-items: center;
}
```

Assignments:

```text
frame controls   -> left flexible zone
mode controls    -> stable centered zone
context/status   -> right flexible zone
```

The center of the mode radiogroup must remain stable when switching between:

- Slider;
- Single;
- Diff;
- Blink;
- Grid.

Do not use absolute positioning or JavaScript width measurement.

## 8.3 Context zone

The right zone must retain stable geometry regardless of which context group is
visible.

Requirements:

- the visible pair/active/grid group fills or aligns within the same zone;
- pair selects share available width;
- Single's active select may expand to the available zone;
- alignment status remains a non-growing trailing item;
- hidden controls do not affect layout;
- all flex/grid children use `min-width: 0`;
- select text may ellipsize only after release-aware labels are applied.

## 8.4 Responsive layout

Use CSS-only responsive layouts.

Target behavior:

### Wide desktop

```text
[frame navigation]       [view modes]       [context controls + alignment]
```

### Medium

Two rows:

```text
[frame navigation]                         [view modes]
[context controls + alignment across the available width]
```

### Narrow/mobile

Stack:

```text
frame navigation
view modes
context controls
alignment status
```

Start with a breakpoint near `70rem` and tune only from browser evidence. Preserve the
existing mobile breakpoint semantics.

Do not create per-mode CSS widths.

## 8.5 Browser geometry contract

At wide width, mode controls must keep the same horizontal center (within one device
pixel) across every mode.

Also prove:

- frame controls remain anchored left;
- context zone remains anchored right;
- groups do not overlap;
- document width does not exceed viewport width;
- the toolbar does not jump vertically at a fixed responsive state.

---

# 9. Responsive Inspector redesign

## 9.1 Width

Introduce one CSS custom property:

```css
--rv-inspector-width: clamp(28rem, 30vw, 42rem);
```

Desktop:

```css
.rv-inspector {
    width: min(var(--rv-inspector-width), calc(100vw - 2rem));
}

body.rv-inspector-open .rv-viewer-stage {
    margin-right: min(var(--rv-inspector-width), calc(100vw - 2rem));
}
```

These values are an initial product target. Adjust only if the real-browser matrix
shows a concrete readability or stage-space failure.

At widths where the Inspector already overlays instead of shrinking the stage:

- preserve zero stage margin;
- use up to `92vw`;
- retain a sensible maximum on tablet;
- allow near-full-width presentation on phones.

Do not add a resizable drawer in this package.

## 9.2 Horizontal overflow policy

The Inspector must not require horizontal scrolling for normal report data.

Apply:

- `overflow-x: hidden` to the drawer and panels;
- `min-width: 0` to panel, cards, grids, flex children, and values;
- `overflow-wrap: anywhere` to filenames and long technical values;
- ordinary word wrapping to release names;
- no `white-space: nowrap` on primary source identities;
- no ellipsis as the only representation of an Inspector source name.

The tab row may remain horizontally scrollable on narrow screens.

## 9.3 Clip card information hierarchy

Replace the current long-label heading with:

```text
Reference                                      HDR
Avatar Aang The Last Airbender (2026)
2160p | PMTP WEB-DL | DV HDR10+ | Kitsune

View role     Left
File          Avatar.Aang.The.Last.Airbender....mkv
Resolution    3840x2160
FPS           23.976...
File size     4.16 GiB
Signal        HDR · BT.2020 / PQ / BT.2020nc · Limited · DV RPU
Presentation  Tonemapped · BT.2390 -> 100 nits
Active picture ...
```

For comparisons:

```text
Comparison 1                                   HDR
...
```

Rules:

- stable source role is derived from clip index;
- dynamic viewer role remains a metadata row;
- `primary` and `release` are both shown only when they differ and are useful;
- exact filename is fully present and wraps;
- signal/presentation wrap;
- badge remains compact;
- no source title is hidden behind ellipsis.

## 9.4 Inspector metadata grid

Use a bounded label column and flexible value column:

```css
grid-template-columns: minmax(5.5rem, max-content) minmax(0, 1fr);
```

Do not allow long values to expand the drawer.

## 9.5 No body-level overflow masking

Do not solve the problem by globally hiding all document horizontal overflow without
fixing the responsible children.

The browser test must prove:

```text
document.documentElement.scrollWidth <= document.documentElement.clientWidth
inspector.scrollWidth <= inspector.clientWidth
active inspector panel scrollWidth <= clientWidth
```

---

# 10. Session A — Report clip-display contract and viewer adoption

## Objective

Add report v1.2 clip-display metadata, preserve report identity semantics, and migrate
all human source-name surfaces to the correct release-aware display profile.

## Primary write boundary

Likely files:

- `src/frame_compare/services/report/payload.py`
- `src/frame_compare/services/report/display.py` only if current report-owned shaping
  belongs there
- `src/frame_compare/orchestration/phase_post_render.py`
- `src/frame_compare/services/report/renderer.py`
- `src/frame_compare/services/report/assets/viewer.js`
- `src/frame_compare/services/report/assets/grid_view.js`
- `src/frame_compare/services/report/assets/lens.js`
- review UI asset only where display text changes
- `src/frame_compare/services/report/viewer.py` only if asset loading changes
- focused report/payload/renderer/JS tests
- `docs/current-cli-contract.md`
- `docs/current-architecture.md`
- active plan progress notes

Do not change toolbar geometry or Inspector CSS in Session A except minimal markup
needed for display fields.

## Required implementation

1. Bump report version to 1.2.
2. Add `ReportClipDisplayInfo` and nested payload.
3. Build set-level names once in `phase_post_render`.
4. Exclude display from report identity.
5. Add JS helpers that consume the required v1.2 display profile.
6. Audit every human-facing clip-label consumer.
7. Preserve canonical keys and persisted review data.
8. Add full accessible/title strings.
9. Update report contract documentation.

## Acceptance criteria

- New report payload has display metadata.
- Direct `ClipInfo` tests provide the required v1.2 display profile.
- Changing only display metadata does not change report ID.
- Canonical label and source identity still do change report identity as before.
- All relevant viewer surfaces show release-aware names.
- Exact filename remains available in Inspector/info modal.
- Explicit labels remain authoritative.
- No JS filename parser exists.
- No report image, geometry, review-state, or clip-key semantics change.
- Old v1.1 reports remain self-contained.
- New v1.2 reports and test payloads always provide the complete display profile.

## Focused proof

At minimum:

```bash
uv run --no-sync pytest -q \
  tests/services/test_report.py \
  tests/services/test_report_entry.py \
  tests/services/test_report_renderer_markup.py \
  tests/orchestration/test_phase_post_render_outputs.py
```

Run current Node harness tests covering viewer, grid, lens, and review state.

Then run the full repository gate.

## Suggested commit

```text
feat(report): add release-aware clip presentation
```

---

# 11. Session B — Toolbar anchoring and Inspector layout

## Objective

Replace mode-dependent flex drift with stable CSS grid zones and make the Inspector
wide, wrapping, and horizontally overflow-free.

## Primary write boundary

Likely files:

- `src/frame_compare/services/report/renderer.py`
- `src/frame_compare/services/report/assets/viewer.css`
- `src/frame_compare/services/report/assets/viewer.js`
- focused renderer/layout/JS tests
- `tests/browser/test_report_browser_smoke.py`
- browser fixture/helpers
- current contract/architecture docs

## Required implementation

1. Add `rv-context-zone` markup.
2. Implement wide three-zone grid.
3. Implement medium two-row and narrow stacked layouts.
4. Keep mode center stable across all modes.
5. Expand current context select to stable zone.
6. Add responsive Inspector width variable.
7. Recompose Inspector clip cards.
8. Eliminate horizontal overflow.
9. Extend real-browser geometry probes.

## Browser assertions

At minimum prove:

- mode-control center is stable across Slider/Single/Diff/Blink/Grid;
- frame and context zones retain their anchors;
- no control overlap;
- no document horizontal overflow;
- Inspector width follows desktop and overlay policies;
- Inspector/panel `scrollWidth <= clientWidth`;
- full filename text is present;
- release descriptor contains expected resolution/service/type/HDR/group facts;
- opening Inspector still anchors viewport palette correctly;
- keyboard/focus/ARIA behavior remains;
- 3440x1440, 1920x1080, 1366x768, 1024x768, and one phone-width state behave as
  designed.

Use the existing real-Chrome browser harness. Do not add Playwright, Selenium, or a
new browser dependency.

## Suggested commit

```text
feat(report): stabilize toolbar and inspector layout
```

---

# 12. Session C — Integration, manual acceptance, docs, and closeout

## Objective

Integrate the report contract and layout work, regenerate visual evidence, run all
proof, perform the Ponytail pass, and prepare the adversarial review packet.

## Required actions

1. Fetch latest `dev/v0.2.0`.
2. Inspect complete task-owned diff.
3. Resolve only task-related regressions.
4. Run all focused report/JS/browser tests.
5. Run full repository verification.
6. Run strict docs build.
7. Generate a real report using long realistic release names.
8. Capture the full manual visual matrix.
9. Update report/sources guides and sanitized screenshots.
10. Perform explicit Ponytail pass.
11. Prepare fresh review packet.
12. Mark plan Historical only after review closure.

## Manual visual matrix

### Modes

- Slider
- Single
- Diff
- Blink
- Grid

Confirm mode buttons do not move within the same responsive layout.

### Viewport sizes

- 3440x1440
- 2560x1440
- 1920x1080
- 1366x768
- approximately 1024x768
- narrow/mobile width

### Inspector

- Frame tab
- Clips tab
- Align tab
- Review tab
- Export tab
- two clips
- more than two clips
- long filename
- explicit label
- incomplete release parsing fallback
- long signal/presentation values
- browser zoom 100%, 125%, and 150%

### Source display

Verify key differentiators remain:

- resolution;
- service;
- source/type;
- SDR/HDR claim;
- release group;
- REPACK/PROPER when present.

### Accessibility

- keyboard navigation;
- visible focus;
- select/title accessible names;
- no clipped essential text;
- no horizontal page/Inspector scroll;
- text remains understandable at zoom.

## Documentation

Update as applicable:

- `docs/current-cli-contract.md`
- `docs/current-architecture.md`
- `docs/guides/reports-and-overlays.md`
- `docs/guides/sources-and-labels.md`
- directly stale screenshots under `docs/images/`

Explain:

- report v1.2;
- release-aware report source names;
- exact filename availability in Inspector;
- stable toolbar zones;
- responsive Inspector;
- existing v1.1 reports remain self-contained.

## Suggested documentation commit

```text
docs(report): update viewer guidance and visual evidence
```

A separate docs commit is optional; one cohesive code commit plus docs commit is
acceptable.

---

# 13. Verification

Bootstrap when needed:

```bash
uv sync --group dev --frozen
```

Focused proof should include all current tests covering:

- report payload and report ID;
- report entry/generation;
- renderer markup;
- viewer state;
- grid view;
- lens;
- review state/controller;
- phase post-render mapping;
- real-browser smoke.

Explicit browser run:

```bash
uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py
```

Full gate for every implementation session:

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
git diff --check
```

When docs/images change:

```bash
uv sync --only-group docs --locked
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
uv sync --group dev --group docs --locked
```

No Docker or Windows-portable gate is required unless the implementation unexpectedly
touches render/runtime or packaging owners.

---

# 14. Architecture attention

The following are current large/hot owners and require complete-file inspection and
a recorded disposition:

| Owner | Existing responsibility | New behavior | Expected disposition |
| --- | --- | --- | --- |
| `services/report/renderer.py` | Static report markup composition | Context wrapper and display metadata markup | Cohesive growth |
| `services/report/assets/viewer.js` | Main viewer interaction/composition | Display helper and Inspector semantics | Cohesive growth; no unrelated refactor |
| `services/report/assets/viewer.css` | Viewer visual system and responsive layout | Grid toolbar and drawer sizing | Cohesive growth |
| `orchestration/phase_post_render.py` | Report/slow.pics phase DTO assembly | Attach preformatted report clip display | Cohesive growth |
| `services/report/payload.py` | Report wire schema and stable identity | Add display payload, exclude it from ID | Cohesive growth |

Do not split these owners solely because of line count.

A small focused extraction is permitted only when:

- it represents a distinct present-day responsibility;
- it has at least two current consumers;
- it improves import/layer boundaries;
- it does not become a generic UI framework.

---

# 15. Ponytail / YAGNI pass

Use the repository's current `@ponytail-review` or equivalent after implementation.

Required closeout report:

```text
PONYTAIL: PASS
REUSED
REJECTED ABSTRACTIONS
CODE REMOVED/SIMPLIFIED
REMAINING ONE-CALLER HELPERS
```

Apply the ladder:

1. Is the behavior necessary?
2. Does existing release identity already provide it?
3. Can CSS Grid/native wrapping solve it?
4. Can the existing browser harness prove it?
5. Only then add the minimum code.

Explicitly reject:

- a second release parser in JavaScript;
- a custom select/dropdown component;
- JavaScript width measurement for toolbar layout;
- absolute-positioned center controls;
- per-mode hard-coded widths;
- ResizeObserver-driven toolbar composition;
- a resizable Inspector;
- horizontal scrolling as the primary Inspector solution;
- a generic report component framework;
- a new front-end dependency;
- a report migration framework;
- display metadata in report ID;
- changing canonical labels/keys;
- changing baked overlays;
- global overflow hiding that masks broken children;
- giant HTML/CSS/browser snapshots.

Minimality must not remove:

- exact filename access;
- collision handling;
- responsive behavior;
- zoom/accessibility proof;
- report identity tests;
- no-overflow browser tests;
- escaped/unsafe-text protection.

---

# 16. Stop conditions

Stop and return evidence if implementation appears to require:

- a CLI/config change;
- a new frontend dependency;
- canonical label or source identity changes;
- report geometry/image/frame semantic changes;
- review JSON schema changes;
- baked overlay changes;
- JavaScript filename parsing;
- report display metadata entering report ID;
- custom select replacement;
- JavaScript layout measurement;
- a resizable drawer;
- unrelated render/runtime modifications;
- force-pushing `dev/v0.2.0`;
- overwriting unrelated work;
- guessing through target-branch conflicts;
- claiming browser proof when Chrome did not actually run.

---

# 17. Rollback

No persistence migration is introduced.

Rollback options:

1. Revert all report v1.2/layout commits.
2. Revert toolbar/Inspector commit while retaining display payload work.
3. Revert report display consumers while retaining payload fields.
4. Revert the affected display-surface change if a browser-specific issue is isolated;
   do not add a legacy payload fallback.
5. Existing v1.1 reports remain unaffected.

Do not add a legacy-viewer compatibility switch as rollback machinery.

---

# 18. Fresh adversarial review

Use a fresh read-only reviewer with no implementation transcript.

Provide:

- this plan;
- execution-time baseline and final commit range;
- complete task-owned diff;
- payload/version/identity tests;
- Node and real-browser results;
- manual screenshots at required widths/modes;
- docs proof;
- known environment gaps;
- Ponytail report.

Review priorities:

## Contract

- report v1.2 shape;
- report ID exclusion of display metadata;
- old-report compatibility statement;
- canonical labels/keys;
- review-state keys;
- geometry/image/frame identity;
- HTML escaping.

## Display correctness

- required release differentiators remain visible;
- explicit label precedence;
- exact filename availability;
- required display-profile behavior;
- all human-facing clip-name consumers audited;
- no display/canonical confusion.

## Layout

- mode controls anchored;
- context zone stable;
- responsive breakpoints;
- no control overlap;
- no document/Inspector horizontal overflow;
- Inspector width and stage margin use one source of truth;
- no clipped essential information;
- browser zoom behavior.

## Accessibility

- focus order;
- roles/ARIA;
- title/accessible names;
- keyboard mode/clip selection;
- high zoom;
- no information only available through hover.

## Architecture/Ponytail

- no JS parser;
- no generic framework;
- no layout-measurement code;
- no unnecessary DTO fields;
- no repeated formatter logic;
- no brittle snapshots;
- no stale docs.

Finding format:

```text
SEVERITY
CONFIDENCE
FILE / EVIDENCE
RISK MECHANISM
RECOMMENDED FIX
MERGE BLOCKER: YES/NO
```

End with:

```text
VERDICT
PONYTAIL VERDICT
RESIDUAL RISKS
VERIFICATION GAPS
```

Do not manufacture findings.

---

# 19. Definition of done

This work is complete only when:

- all implementation commits are present on current `dev/v0.2.0`;
- report version is 1.2;
- display metadata is excluded from report ID;
- all approved report source-name surfaces use release-aware display;
- exact filenames remain available;
- mode controls do not shift across modes at desktop width;
- Inspector has no horizontal overflow and is meaningfully wider;
- real-browser geometry tests pass;
- full verification passes;
- strict docs build passes;
- manual Windows/Chrome visual matrix is recorded;
- Ponytail review is complete;
- fresh adversarial review has no unresolved merge blocker;
- plan status is Historical;
- no force push occurred.
