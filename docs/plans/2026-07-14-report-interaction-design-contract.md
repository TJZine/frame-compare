Status: Unit 7 design contract / awaiting maintainer approval
Scope: Generated-report interaction decisions consumed by Product/UX Units 8–11
Owner: Frame Compare maintainer and the active Product/UX execution program

# Report interaction design contract

This supporting contract is governed by the sole active plan,
[`2026-07-13-product-ux-execution-program.md`](2026-07-13-product-ux-execution-program.md),
Package 7. It is not a second active execution plan. Maintainer approval of this
document permits Units 8–11 to implement only the seams frozen below; it does not
authorize production code, a framework, new CLI/config fields, a report rewrite, or
claims of implementation proof.

## Approval boundary and evidence

The decisions marked **Frozen** are the proposed design contract. Every item marked
**Implementation proof** remains a required test/browser/review obligation in its
own unit. Unit 8 must not start until this document is reviewed, approved, integrated,
and named by immutable reference in the active plan ledger.

The current generated viewer was inspected from its renderer, payload, CSS, JavaScript,
state harness, and an existing generated `.tmp/visual_audit_report.html`. The assigned
worker could not inspect it interactively: after the required Browser bootstrap and
troubleshooting, `agent.browsers.get("iab")` returned `Browser is not available: iab`
and `agent.browsers.list()` returned `[]`. No standalone Playwright or unrelated browser
surface was substituted. On 2026-07-14 the maintainer explicitly deferred that manual
in-app-browser proof until Units 8–11 are implemented so the complete report experience
can be validated in one pass and any resulting issues fixed then. This is an accepted
proof-timing deferral, not a pass: current-viewer continuity and the complete prototype/
implementation matrix remain mandatory final-program validation debt.

### Current strengths to preserve

- One static, offline HTML report owns a concentrated comparison workspace rather than
  generic application chrome.
- Slider, Single (internal overlay), diff, and pair-based blink modes; frame/category
  navigation; HUD; floating viewport palette; filmstrip; inspector tabs; fullscreen;
  pan/zoom/actual/width/height fit; reveal; and adjacent-frame preloading already form a
  coherent viewer.
- Report-id-scoped local viewer state preserves frame, mode, clip selection, viewport,
  alignment, HUD, filmstrip, inspector, and blink speed; blink pause is intentionally
  transient.
- Semantic controls, visible focus, polite status regions, modal focus handling, and
  reduced-motion blink entry-paused behavior provide a useful accessibility base.
- Cinema black, charcoal surfaces, cyan reference/action cues, monospace measurements,
  compact controls, subtle borders, and surface shifts suit technical image inspection.

### Current constraints to respect

- `frame_compare.services.report` and its plain viewer assets own markup, payload, and
  interactions; browser side effects and slow.pics policy remain elsewhere.
- The payload exposes report identity, clip presentation metadata/resolution, ordered
  frame metadata, and image sources, but no review schema or neutral blind identity.
- Existing alignment is a presentation transform in CSS pixels. It must not silently be
  described as source-pixel registration.
- The viewer asset is already a hotspot. New policy needs one central coordinate model
  and focused state owners, not conversions scattered through event handlers.
- Main images are DOM `<img>` layers. They remain DOM images; no main-stage canvas or
  unbounded raster copy is permitted.

## Design foundation

### Human, context, accomplishment, feel

The human is a video encoder, restoration reviewer, or release-quality checker who has
just generated frames from two or more clips. They open the report on a desktop during
an investigative pass, often revisit it later, and may use touch only as a constrained
fallback. They must locate a subtle difference, compare the same raster region honestly
across clips of equal or different dimensions, and leave a small transferable review
record. It should feel like a calibrated darkroom bench: dense, quiet, exact, and
trustworthy—not spacious, playful, decorative, or dashboard-like.

### Domain exploration

1. **Light table:** several renderings share one spatial reference.
2. **Loupe:** temporary enlargement supports judgment without replacing the whole view.
3. **Pixel lattice:** integer coordinates, pixel centers, and sampling limits matter.
4. **Registration marks:** a locked point links views while declaring imperfect mapping.
5. **Contact sheet:** frames and categories stay available as a compact filmstrip.
6. **Review slate:** bookmark, controlled tag, note, and preference record a decision.
7. **Darkroom bench:** controls recede while the image and evidence remain primary.

### Color world

- projector/cinema black `#050608` for the image surround;
- charcoal equipment `#0d0f13` and raised graphite `#1b1f25` for controls;
- cool paper-white `#f0f2f4` and steel text for readable hierarchy;
- restrained reference cyan `#51c7ea` for focus, active reference, and linking;
- annotation amber `#f3ad45` for ROI, notes, import conflicts, and non-destructive warning;
- desaturated error red near `#ef6a6a` only for missing/invalid/failure states.

Color communicates reference/action, annotation/attention, or failure. It does not
decorate surfaces or assign arbitrary hues to clips.

### Signature element

The signature is one coordinate-linked inspection point expressed in five places:
the stage crosshair, optional floating loupe, docked pixel inspector, mapped coordinate
rows for every visible clip, and the review record's frame context. The dock is the
source of truth; the loupe mirrors it and never owns independent state.

### Defaults explicitly rejected and replaced

1. Generic metric cards are replaced by aligned per-clip coordinate/sample rows.
2. Permanent sidebar navigation is replaced by the existing toolbar, filmstrip, and a
   task-scoped inspector drawer.
3. A canvas-based zoomable image application is replaced by existing DOM image layers
   plus a bounded one-pixel sampling scratch surface.
4. Freeform draggable dashboard tiles are replaced by deterministic 2/3/4/N grids.
5. Rainbow clip identities are replaced by neutral labels, one cyan reference cue, and
   one amber annotation cue.

### Mandatory component checkpoint

- **Intent:** foreground finding and recording visible differences; image area and the
  linked coordinate lead because those are the user's actual work.
- **Palette:** preserve cinema black/charcoal, restrained cyan, and amber; they arise
  from projection, reference monitoring, and annotation, and limit visual noise.
- **Depth:** borders plus whisper-small same-hue surface shifts only. The lens and modal
  may rise one level; no decorative shadows or glass effects are introduced.
- **Surfaces:** header/toolbar at charcoal, black image stage, deterministic comparison
  grid within the stage, raised inspector dock, amber-edged optional lens, and inset
  review fields. Existing filmstrip remains the bottom navigation surface.
- **Typography:** retain the current readable system UI stack; use the current monospace
  stack with tabular numerics for coordinates, dimensions, RGB, counts, and shortcuts.
- **Spacing:** 4 px base; 4/8 px control gaps, 12 px component padding, 16 px major
  separation. At constrained widths density reduces before information is removed.

## Frozen interaction contract

### Existing viewer preservation

**Frozen:** Slider/Single/diff/blink, current shortcut meanings, frame/category
navigation, HUD, palette, filmstrip, current inspector information, fullscreen,
pan/zoom/fit/reveal, preloading, report-scoped viewport persistence, and reduced-motion
blink behavior remain available. Grid is viewer-only and is not added to the public
`report.default_mode` enum in Unit 9. New work composes inside
`frame_compare.services.report` renderer/payload/assets; it adds no framework.

### Magnifier, sampling, and dock/lens relationship

**Frozen:** A visible `Inspect` control opens the existing inspector drawer on a new
Pixel tab and arms the inspection point. The drawer is closed on a first visit, honoring
the existing persisted inspector-open state thereafter. The dock is authoritative and
continues to show the locked point when the pointer leaves the stage. The floating lens
is optional, defaults off, mirrors the dock, stays inside the stage, never covers the
point or active label when another quadrant is available, and is suppressed for coarse
pointer/touch viewports. Its preference is report-scoped viewer state; the lock is not
persisted across page load.

The inspector tab order is exactly `Pixel`, `Frame`, `Clips`, `Align`, `Review`,
`Export`. Unit 8 adds Pixel without removing the current Frame/Clips/Align/Export
surfaces; Unit 10 adds Review before Export. When width cannot hold every label, the
tablist scrolls horizontally without truncating accessible names or changing DOM order.
Exactly one active tab has `tabindex="0"`; every other tab has `tabindex="-1"`.
Left/Right arrows wrap through tabs, Home/End choose the first/last tab, and each action
moves focus and activates the tab. These events stop before global frame shortcuts; Tab
then enters the active panel. `Inspect` and `M` open and focus Pixel. Existing `I` keeps
its inspector meaning; both `I` and the existing header information button open the last
persisted active inspector tab, defaulting to Frame. Only `Inspect` and `M` force Pixel.

Magnification choices are exactly **2×, 4×, 8×**, default **4×**. The lens magnifies the
decoded `<img>` bitmap with nearest-neighbor/pixelated presentation; the main stage is
never canvas-rendered. A pixel grid appears only at 8×. One reusable, offscreen 1×1
canvas is permitted solely to sample one decoded pixel. It must never resize above 1×1,
scan a region, copy a main image, or become visible.

Pixel text is `Decoded display sample · 8-bit sRGB` and may show `R G B A` integers only
after a successful same-origin/data/blob decode and read. It is not source bit depth,
linear-light data, encoded YUV, HDR code value, or proof of colorimetric equivalence.
Cross-origin taint, decode failure, browser restriction, or unavailable image yields
`Pixel value unavailable` while coordinates remain usable. Approximate data is never
shown with false precision.

### Coordinates and cross-dimension mapping

**Frozen:** coordinates are zero-based integer pixel indices in the selected image's
natural decoded raster, origin at the top-left. The central coordinate owner first
inverts stage pan/zoom, fit, the selected layer's alignment presentation transform, and
that layer's rendered image box exactly once to obtain the selected natural-raster
pixel. A point is the center of a pixel:

```text
u = (x + 0.5) / source_width
v = (y + 0.5) / source_height
target_x = clamp(floor(u * target_width), 0, target_width - 1)
target_y = clamp(floor(v * target_height), 0, target_height - 1)
```

Equal dimensions therefore map to the identical `(x, y)`. Different dimensions map by
normalized pixel center. That normalized source point is the only cross-clip mapping:
target-layer alignment is applied only in the forward render step that positions the
target crosshair/lens over its DOM image. It never changes the target natural-raster
coordinate. Every row shows its own `(x, y)` and `W×H`; the dock states `Normalized
cross-size mapping; not scene registration.` Manual alignment therefore changes selected
visual hit-testing and target crosshair presentation, but it is never folded into or
advertised as source registration. Aspect-ratio/crop differences are not inferred away.
A later geometry-aware mapping requires a separately approved payload fact; Unit 8 stops
rather than guessing.

The acquisition anchor is deterministic by mode:

| Mode | Natural-raster anchor |
| --- | --- |
| Slider | Left layer when the released point is on or left of the final clipped boundary; right layer otherwise |
| Single | The active clip |
| Diff | The left/base clip |
| Blink | The visible clip at pointer-down/keyboard acquisition, retained through blink phases until unlock |
| Grid | The cell receiving the pointer or focus |

The anchor is announced in the dock. Its own CSS alignment is included in inverse
hit-testing. Other clip rows are derived only through `(u, v)` and their alignment is
used only for forward crosshair/lens placement.

### ROI input, lock, pan/zoom, and resize

**Frozen:** unlocked mouse hover follows at most once per animation frame. A primary
press begins the current mode gesture and records its origin. If movement exceeds six
CSS pixels before release, existing Slider reveal or stage-pan behavior wins and no ROI
lock occurs. A release within six pixels applies the mode's final reveal position,
acquires the anchor from the table above, moves the ROI to that point, and locks it; a
tap while already locked relocates it and remains locked. Direct drag of the 44×44 px
ROI handle always captures the pointer, moves only the ROI, and remains locked on
release. This same arbitration applies to touch, with no hover assumption or
long-press-only action. Existing comparison gestures therefore remain available.

The stage exposes a focusable inspection-point control. When that control has focus,
Enter/Space toggles lock, arrows nudge one anchor-source pixel, Shift+arrows nudge ten,
and Escape unlocks. Those events stop before the existing global arrow/frame shortcuts.
Outside that focused control, current arrow behavior is unchanged.

While locked, ordinary pan/zoom/fit preserves `(u, v)` and the point; linked grid cells
preserve the same normalized viewport center and zoom intent. Resize/reflow recomputes
CSS placement from `(u, v)` without changing the locked source pixel. Clip/frame/mode
change unlocks by default and announces it, preventing a stale point from masquerading
as the same evidence. Grid page changes keep the normalized point but announce the newly
visible clip range. Missing target images retain the point and show an unavailable row.

### Deterministic grid and overflow

**Frozen:** cells have equal visual weight, never crop source content, retain each
image's aspect ratio in a black letterbox, and display a truncated visible label with the
full safe label in an accessible name/title.

- 2 clips: equal 2×1 above 768 px.
- 3 clips: equal 3×1 at 1200 px and wider; between 768–1199 px, equal 2-column cells
  with the third in the next row and no enlarged “winner.”
- 4 clips: equal 2×2 above 768 px.
- More than 4: deterministic payload-order pages of at most four, 2×2; previous/next
  set controls show `Clips a–b of N`. Only the current page's image nodes are mounted.
- Below 768 px or at equivalent browser-zoom reflow: one full-width cell at a time with
  explicit previous/next clip controls and `Clip n of N`; no focus-changing scroll snap.

Grid pan/zoom/ROI is linked by default across visible cells. A future unlink toggle is
out of scope. Portrait, 16:9, ultrawide, and very large images use available cell bounds;
no canvas or forced common crop is created.

### Focus, shortcuts, touch, motion, and announcements

**Frozen:** DOM/focus order is header, existing primary controls, Inspect/Grid additions,
stage inspection point, viewport palette, inspector tabs/content, filmstrip, footer.
`M` toggles Inspect only when focus is not in an editable/control element. Grid receives
no bare-letter shortcut; this avoids `S/O/D/B/H/F/I/X`, arrows, `1–9`, `+/-`, `R`, `?`,
Space, and blink `[/]`. Grid paging uses visible controls; `Alt+PageUp/PageDown` may be
implemented only if browser testing proves no platform conflict. Escape priority remains
modal/popover close, ROI unlock, inspector close, then fullscreen exit.

All pointer controls have at least a 44×44 CSS-pixel touch hit area on coarse pointers.
At 200% browser zoom there is no page-level horizontal overflow; only intended toolbar,
filmstrip, or grid-cell navigation may scroll. Reduced motion disables lens/dock movement
animation and shimmer; Blink retains its current enter-paused behavior. Unlocked pointer
motion is not announced. Lock/unlock, keyboard nudge after a 250 ms debounce, grid page,
missing image, storage failure, and import result use one polite live region with concise
messages. Errors use an assertive region only when the viewer cannot continue.

Accessible names include action and state: `Open pixel inspector`, `Inspection point,
locked at x … y … in …`, `Magnification 4×`, and `Clip n, <safe label>, mapped x … y …,
pixel value unavailable`. Text/background meets WCAG 2.2 AA 4.5:1 (3:1 for large text);
focus indicators and meaningful graphical boundaries meet 3:1. Cyan/amber are never the
only state indication.

### Loading, missing, error, and empty behavior

**Frozen:** image cells reserve geometry while loading and show static `Loading image…`
under reduced motion. One missing image becomes a labeled cell error with a `Retry`
action for non-embedded files; other clips and coordinates continue. The corresponding
sample row is unavailable. If all current images fail, the stage shows a recoverable
frame error while navigation remains. Malformed/incomplete payload keeps the current
viewer-level error behavior and disables inspection. Magnifier work begins only after
decode; no stale sample survives frame/clip changes.

### Performance and memory budgets

**Frozen:** the main stage remains DOM images. Unit 8 adds no more than one 1×1 sampling
canvas, one four-byte RGBA readback buffer, one lens image, and 2 MiB of measurable
feature-owned state/DOM overhead excluding browser-internal canvas/DOM bookkeeping and
the browser's existing decoded main image. Sampling is at most once per animation frame
and one pixel per active clip row; no histogram or region scan occurs. Resize work is
coalesced within 100 ms.

Unit 9 mounts at most four grid images for the current frame (one on mobile) and does not
preload other grid pages. Existing pair-mode adjacent-frame preloading stays unchanged.
Unit 10 rejects import bytes above 8 MiB before parsing and stores at most 1,000 review
records. All additions initialize lazily on first use. Browser QA must include 7680×4320
representative images and verify interaction latency rather than infer it from screenshots.

## Local review state contract

### Record model and storage

**Frozen:** one review record per report frame ordinal contains:

```text
frame_ordinal: integer 0..frames.length-1
bookmark: boolean
tag: null | "artifact" | "detail" | "motion" | "color" | "other"
note: plain text, 0..1000 Unicode scalar values, CRLF normalized to LF
preferred_clip_id: null | "clip:<zero-based payload ordinal>"
```

An all-default record is removed. Strings are assigned with `textContent`/form values,
never HTML. Report-local clip IDs deliberately use payload ordinal because `report_id`
already binds ordered clip identity; they reveal no new path. Review storage is separate
from viewport state at exactly
`frame-compare:report-review:v1:<report_id>`. The stored value is the same schema below
without `exported_at`; it contains no title, clip label, frame label/category, image URL,
or path. Reads validate fully and fail closed. Unsupported/corrupt data is ignored with a
warning and is not overwritten until the user changes review state.

If localStorage is unavailable, review remains in memory and a persistent message says
`Review changes will not persist in this browser; export to keep them.` Quota/write
failure preserves the prior stored bytes and current in-memory edits, marks them unsaved,
and keeps Export available. Review state never writes into HTML/run folders or uploads.

### Exact export JSON V1

**Frozen:** UTF-8, no BOM, two-space indentation, final LF, and fixed property order.
Reviews are deterministic by frame ordinal. Exported time is the only variable and is
UTC `YYYY-MM-DDTHH:mm:ss.sssZ` captured once.

```json
{
  "format": "frame-compare-review",
  "schema_version": 1,
  "report": {"id": "report_…", "payload_version": "1.0"},
  "reviews": [{"frame_ordinal": 0, "bookmark": true, "tag": "artifact", "note": "…", "preferred_clip_id": "clip:1"}],
  "exported_at": "2026-07-14T16:30:00.000Z"
}
```

Only the exact keys shown are accepted. `format`/version are constants; `report.id`
must match `^report_[0-9a-f]{32}$` and equal the current payload; payload version must
equal the current supported version; review ordinals are unique, in range, and sorted;
review tag/note/preference follow the record model and preferred clip ordinals must be in
range. Title, clip/frame labels, categories, resolutions, image data/URLs, absolute paths,
secrets, viewer preferences, blind mappings, and HTML are forbidden because `report_id`
already binds the ordered report identity. This removes unbounded payload-derived strings
from the portable schema.

Every V1 document successfully exported by Frame Compare must pass V1 byte, syntax, and
schema validation when imported into the same report. The 8,388,608-byte ceiling covers
the worst valid 1,000 records with 1,000 Unicode scalars per note even when every scalar
requires a six-byte JSON escape, plus fixed record overhead. Export serializes and checks
this same ceiling before offering the file; exceeding it is an implementation defect,
not a smaller undocumented export domain.

### Import, preview, conflicts, and rollback

**Frozen:** import accepts one local `.json` file no larger than 8,388,608 bytes. It
decodes strict UTF-8, parses once, rejects `__proto__`, `prototype`, and `constructor` at
every object depth, rejects all other unknown keys and non-finite values, then validates
the complete schema and current report identity before mutating memory or storage.
Unsupported version, report-ID mismatch, out-of-range review ordinal, or out-of-range
preferred clip hard-rejects; there is
no override, best-effort remap, label match, or partial import. Even identical-looking
content from a different `report_id` is rejected with `This review belongs to a different
report. No changes were made.`

A valid import opens a preview with add/change/remove/unchanged counts. The user chooses
**Merge** (default) or **Replace**. Merge inserts absent records and preserves local
records; when the same ordinal differs, a second explicit bulk choice defaults to `Keep
local`, with `Use imported` available. Replace makes the imported review set exact and
lists deletions. Cancel is always non-mutating. Apply builds one complete candidate,
serializes it, performs one `localStorage.setItem`, and swaps in-memory state only after
success. Where storage exists, any validation/quota/storage exception leaves both prior
memory and stored bytes unchanged. In the already-declared memory-only state, Apply
instead swaps one fully validated candidate into memory atomically, keeps it marked
unsaved, retains Export, and repeats the persistence warning; no storage write is
attempted. Imported strings render only as text.

## Blind A/B definition and Unit 11 stop

**Frozen:** the only claim available to Unit 11 is presentation blindness: before
explicit reveal, source identity cannot be inferred through ordinary visual UI,
accessibility APIs, focus/keyboard order, or state restored into those surfaces. This
includes labels/order, filenames/paths, alt text, titles/tooltips, accessible names,
baked image overlays, report metadata, inspector/review/export UI, slow.pics links,
reference styling, and deterministic label assignment. Vote and reveal are distinct
state, and neutral A/B assignment must be unbiased and held for the session.

The current static document embeds identity-bearing clip names/labels, image sources, and
metadata. Browser developer tools, View Source, network/file names, raw localStorage, and
exported file bytes are explicitly outside that claim because viewer JavaScript cannot
hide them. Therefore Unit 11 must not claim adversarial, secure, or storage-level
blindness. It may proceed only if its feasibility audit proves a
clearly labeled **presentation-blind session** against all ordinary UI/accessibility
surfaces without misleading copy. If baked overlays or embedded payload/file names leak
identity—or honest behavior requires neutral render artifacts, a new report format, or a
public config/payload decision—Unit 11 stops and produces a separate decision package.

For a feasible presentation-blind session, anonymous labels use a per-session
Fisher–Yates permutation driven by `crypto.getRandomValues`. The mapping is held only in
memory, applies equally to visual order, focus order, accessible names, restored viewport
selection, stored preferred-clip facts, votes, and reveal, and is never derived from
payload order or `report_id`. Before reveal, slow.pics, identity-bearing clip metadata,
preferred-clip labels, and review Export/Import are hidden or disabled with an
explanation. Exact V1 export remains available only after explicit reveal because its
report ID and preferred-clip ordinals can correlate the anonymous presentation with the
embedded payload. Reveal is not persisted and cannot be undone within that session;
starting a new session creates a new neutral mapping. Raw payload/DOM/devtools/storage
limitations remain disclosed as above.

## Implementation seams, proof, rollback, and stops

- **Unit 8:** add a central coordinate/ROI model and minimal Pixel markup/style/event
  composition in viewer assets. Reuse natural dimensions and current transforms. Stop if
  accurate inverse mapping or decoded sampling cannot be proved without a payload change,
  main-stage canvas, or scattered conversion logic.
- **Unit 9:** add viewer-only Grid markup/state/styles and at-most-four image mounting.
  Do not alter the public default-mode enum. Stop if it requires a layout framework,
  unbounded decoded images, or duplicate viewport state.
- **Unit 10:** add a focused review-state/import/export owner under report assets and
  compose it into the static bundle; do not create a generic persistence layer. Stop if
  stable report-local identity cannot validate exact imports.
- **Unit 11:** run the leak audit first and obey the blind stop above.

Each unit requires semantic renderer assertions, focused JavaScript state-harness tests,
CSS contract checks, and in-app-browser proof over 2/3/4/6 clips; 16:9, ultrawide,
portrait, and 8K representatives; long labels; categories/slow.pics present and absent;
pointer, keyboard-only, coarse/touch viewport, reduced motion, 200% zoom; loading,
missing, error, storage failure, malformed import, identity mismatch, and import conflict.
Screenshots support layout review only; they do not prove focus order, announcements,
contrast, touch target size, coordinate accuracy, sampling honesty, memory, or rollback.

Rollback is additive and unit-scoped: remove the new UI/readers and ignore namespaced
local data. Earlier reports remain readable; no migration or deletion is required.

### Decision/proof ledger

| Surface | Approved-design decision in this contract | Still required before shipping |
| --- | --- | --- |
| Magnifier | Dock authoritative; optional lens; 2×/4×/8×; bounded 1×1 sampling | Transform math, taint/color labels, DPI/resize, latency and mode-regression proof |
| Grid | Exact 2/3/4/N and mobile policy; linked normalized viewport/ROI | Browser geometry, image failure, long-label, memory and focus proof |
| Review | Exact bounded model, storage key/failures, JSON V1 and import transaction | Malicious/oversize/schema/quota/round-trip and accessible-state proof |
| Blind | Exhaustive leak definition and honest stop | Unit 11 feasibility audit; no implementation presumption |
| Accessibility | Focus order, input model, names, live behavior, contrast/zoom targets | Automated semantic checks plus keyboard/touch/reduced-motion/manual audits |
| Performance | DOM main images, bounded scratch/grid/import budgets, lazy work | Measured browser evidence on representative very large images |

## Disposable prototype matrix

The disposable prototype lives outside the repository at
`/Users/tristan/.codex/visualizations/2026/07/14/019f5e84-2e71-7083-9ca9-3289abfe416f/unit7-report-design/`.
Its scenario controls cover 2/3/4/6 clips, four aspect/size classes, long labels,
categories and slow.pics on/off, ready/loading/error/missing/import-conflict states,
ROI pointer/click/keyboard behavior, grid paging, lens/dock relationship, reduced-motion
styling, responsive single-cell mobile layout, and bounded review fields. It is plain
HTML/CSS/JS, contains no production asset, dependency, or canvas, and is supporting
evidence only. Controller-side in-app-browser viewport screenshots and interaction notes
must be captured during final-program manual validation because the worker browser backend
was absent and the maintainer explicitly deferred this proof on 2026-07-14. Until that
pass is recorded, no closeout may claim responsive, keyboard, touch, zoom, reduced-motion,
or visual-continuity proof from this prototype.
