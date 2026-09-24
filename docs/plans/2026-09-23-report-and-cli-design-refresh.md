---
search:
  exclude: true
---

Status: Active
Scope: Implement the September 23 UI/UX audit decisions for the report viewer, terminal output of `run` and the other human commands, the VSView session-script output, and streaming-service parsing.
Owner: Maintainer-directed implementation session; one controller owns integration and acceptance evidence.

# Report viewer and CLI design refresh

## Objective

Raise the report viewer and terminal output to an elegant, functional, consistent
standard while keeping the image-first viewer, neutral charcoal surfaces, brass
selection accent, and offline report model. The maintainer reviewed screenshots of
the current surfaces, a ranked audit, and rendered before/after mockups on
September 23, 2026, and approved the direction recorded here.

This plan authorizes implementation in later sessions. It does not authorize a
commit to `main`, push, release, or publication.

## How to use this plan

This plan is written to be implemented without product or design decisions. If a
situation is not covered, apply the nearest stated rule; if no rule applies, stop
and record the question (see [Stop conditions](#stop-conditions)) rather than
choosing.

- **Plan text is authoritative.** The mockups in
  `docs/plans/2026-09-23-design-refresh-assets/` show layout,
  hierarchy, spacing, and tone. Where a mockup and this text differ, the text wins.
  Mockup images use a synthetic picture and illustrative timings.
- **Branch and sessions:** implement on `dev/v0.6.0-design-refresh`, one session per
  review checkpoint, using the prompts and common rules in the
  [implementation handoff](2026-09-23-report-and-cli-design-refresh-handoff.md).
- **One unit per commit** on that branch, in the order under
  [Sequencing](#sequencing-and-review-checkpoints). Each commit message names the
  unit (for example `feat(report): B2 proximity fade for the viewport palette`).
- **Stop at each review checkpoint** and hand the branch to the controller for
  review before starting the next track.
- **Record** each unit's result in the [Execution record](#execution-record):
  commit, changed owners, commands run with outcomes, skipped checks and why.
- Do not refactor, rename, or reorganize code beyond what a unit requires. Keep
  existing public function names; add parameters with defaults instead of changing
  signatures.

### Reference assets

| File | Shows |
| --- | --- |
| `viewer-viewer.webp` | B1 toolbar and stage labels (name only: no swatches, numbers, or side words); B2 palette ghost state; A4 icons |
| `viewer-lens.webp` | A4 plain lens (caption off by default) and Ring marker; B2 palette shown state |
| `viewer-inspector-frame.webp` | B3 Frame tab |
| `viewer-inspector-clips.webp` | B3 Clips tab (full clip card) |
| `viewer-report-info.webp` | B3 and A2 Report Information (compact clip card) |
| `viewer-popovers.webp` | A4 lens settings (Caption option), a lens with the caption on, and the vertical palette (icon buttons) |
| `viewer-mock.html` | Source of the viewer images; open in a browser (append `#viewer`, `#lens`, … to show one frame) |
| `cli-run-plan.svg`, `cli-sources.svg`, `cli-execution.svg`, `cli-summary-declined.svg`, `cli-upload-success.svg`, `cli-upload-partial-failure.svg` | B4 terminal targets at 104 columns (Rich-rendered) |
| `cli-doctor.svg` | B7 `doctor` target |

## Relationship to other plans

- [CLI and report UX plan](2026-09-22-cli-and-report-ux-improvements.md) (Active,
  pending external W1 and imagery evidence): its accepted outcomes are the baseline
  and must be preserved: Fit width removed, orientation switch retained, **Source
  labels** and **Image offset** naming, four Inspector tabs, truthful note-storage
  copy, actionable CLI errors, wizard next steps. This plan does not change that
  plan's status.
- [Audio alignment remediation plan](2026-09-22-audio-alignment-post-activation-remediation-and-ux.md):
  its frozen terminal state/copy matrix is reproduced **verbatim** (status lines,
  detail lines, review lines). This plan changes layout, colour, and grouping
  around those strings only. The VSView bootstrap text in
  `vsview/session_script.py` is not part of that matrix.
- [Documentation screenshot plan](2026-08-17-documentation-v2-screenshot-remediation.md):
  owns documentation image recapture. After Track B lands, note in its execution
  record that the viewer changed; do not add documentation images here.

## Locked decisions

- **D1 Source naming.** Report-wide content identity (title, year, episode) is not
  repeated per source. Resolution, service with source type, HDR format, and release
  group are always kept. The viewer identifies a source by its name alone: no
  colour swatches, source numbers, or left/right words. The terminal introduces
  each source once by its standard name and then refers back to it by its release
  group (the *short name*). Specification in [S1](#s1-source-names).
- **D2 Palette** stays floating and gains a proximity fade ([B2](#b2-proximity-fade-for-the-viewport-palette)).
  Source-label pills and the frame chip do not fade.
- **D3 Terminal direction** as mocked: brass accent, one value grammar, phase
  timeline, panels only for the plan, sources, decision points, and the summary.
  Specification in [S3](#s3-terminal-style-tokens) and [B4](#b4-run-terminal-output).
- **D4** L-SMASH `Creating lwi index file` output is left unchanged.
- **D5** VSView review wait is measured and shown separately from machine time.
- **D6** VSView session-script output gets the same treatment ([B6](#b6-vsview-session-script-output)).
- **D7** `doctor`, `wizard`, `history`, `preset`, and error presentation adopt the
  shared terminal tokens ([B7](#b7-other-commands)).
- **D8** Streaming-service parsing covers the TRaSH Guides *General* and *Anime*
  streaming services in addition to today's services ([A1](#a1-streaming-service-parsing)).
- **D9 Viewer restraint.** The maintainer rejected added viewer chrome as clutter:
  no frame-position counter in the toolbar, no shortcut letters in the mode
  control, no colour swatches, `#n` numbers, or `LEFT`/`RIGHT` markers in the viewer. Shortcuts stay
  in tooltips and Help.
- **D10 Lens is a plain magnifier.** Remove the split "Compare inside lens" view,
  its comparison-source select, and the "Current source" header in lens settings.
  The lens caption becomes an opt-in setting (default off) for people who hide the
  source labels. This reverses the Sept 22 retention of those lens-settings
  controls by maintainer decision; palette controls are unaffected.
- **Rejected during planning:** digit shortcuts for view modes (digits `1`–`9`
  already select sources, `viewer.js`), and `<optgroup>` grouping of the frame
  select. The frame select keeps today's order by frame number and today's option
  text; the filmstrip category filter covers finding by category.

## Invariants (all units)

- Report payload stays version `1.2` with the same keys. The string values of the
  existing `display` profiles change for newly generated reports; no key is added,
  removed, or renamed.
- **Separator changes** (`·` instead of `|`) apply only to report display profiles
  and terminal output. slow.pics image names (`_slowpics_upload_clips`) keep the
  `|` separator. Burned-in screenshot text uses the clip label (the filename, via
  `batch.label`), never a release descriptor, and is unaffected by this plan.
  (Corrected at the Checkpoint B-viewer review: an earlier version wrongly named
  `format_micro_descriptor` in `phase_render.py` as burned-in text; it only builds
  the terminal render-progress label, which is terminal output; see B4.)
- **Parser fixes** (A1) intentionally change the descriptor wherever it appears,
  including terminal output and slow.pics names, because the service is now
  identified correctly.
- User-supplied explicit clip labels (`label_is_explicit`) are shown as given (in
  the terminal, the label is also the short name).
- CLI command names, flags, exit codes, error codes, stdout/stderr routing, JSON
  output, `--quiet` output, and the plain (non-TTY) and log reporters keep their
  current content, including uppercase phase labels and bracket status tokens.
  Terminal redesign targets the interactive Rich path only.
- The persisted run record and `phase_timings` keys are unchanged.
- `NO_COLOR` / `--no-color` output stays fully informative: a glyph or word always
  carries meaning, never colour alone.
- Browser-local review storage and review JSON format are unchanged. A changed
  default (lens marker) applies only when no saved preference exists.
- Every Sept 22 retained palette control stays present and keyboard reachable;
  A4 removes only the static `Fixed` text.

## Shared specifications

### S1 Source names

Three lengths, all from existing display profiles:

| Length | Profile | Content | Example |
| --- | --- | --- | --- |
| Full | `primary` + filename | content + release facts; filename | `The End of Oak Street (2026) · 2160p · AMZN WEB-DL · HDR · SCOPE` |
| Standard | `control` (and `release`) | resolution · service + source type · dynamic range · revision/variant tags · group | `2160p · iT WEB-DL · DV HDR · ThisBlockHasProblems` |
| Compact | `micro` | service + source type · dynamic range · revision tags · group | `iT WEB-DL · DV HDR · ThisBlockHasProblems` |

- Separator `" · "` (space, U+00B7, space) in report display profiles and terminal
  output. Implement by adding a keyword `separator: str = " | "` to
  `format_release_descriptor`, `format_micro_descriptor`, and
  `format_compact_identity` in `services/release_identity.py`, and passing `" · "`
  from report display building (`run_report_phase`) and terminal printers. Leave
  `unique_presentation_names`' `"{role} | {name}"` collision format unchanged.
- Terminal short name: add `short_source_names(...)` to
  `services/release_identity.py` returning one name per source in clip order. A
  source uses its release group when it has one and no other source has the same
  group (case-insensitive); otherwise it uses its compact name. Explicit labels use
  the label. Resolve any remaining collision with `unique_presentation_names`.
  Example: `SCOPE`, `ThisBlockHasProblems`, `TheEndOfTheFuckingWorld`. The viewer
  never uses short names or numbers.
- Lens caption text: the compact name with any segment made only of
  dynamic-range words (`HDR`, `HDR10`, `HDR10+`, `DV`, `HLG`, `SDR`) removed:
  `iT WEB-DL · ThisBlockHasProblems`. Computed in the viewer from the `micro`
  profile by splitting on `" · "`; explicit labels are used as given. The caption
  wraps instead of truncating (no ellipsis); see B1.
- Truncation: names end-truncate with an ellipsis where width is constrained. The
  group is last, so it is cut first. Full name is always available in a tooltip
  (`title`) or accessible name.

### S2 Viewer typography

- Monospace (`--font-mono`) only for numbers and data values: frame numbers,
  counts, dimensions, sizes, zoom and lens magnification, offsets, filenames.
- UI face (`--font-sans`) for labels and prefixes, including the offset status
  label, filmstrip category text, and source names.

### S3 Terminal style tokens

Create one module, `src/frame_compare/utils/terminal_theme.py`, importable by every
layer under `importlinter.ini`. It holds:

| Token | Value |
| --- | --- |
| `ACCENT` | `#d2ac6b` (section names, plan/sources panel titles, "waiting on you") |
| `KEY` | `dim` (row keys) |
| `VALUE` | terminal default foreground (no style) |
| `MUTED` | `dim` (filenames, secondary facts, durations) |
| `OK` / `WARN` / `FAIL` | `green` / `yellow` / `red` |
| `BORDER` | `dim` for neutral panels; `yellow` for pending decisions and warned summaries; `green` for a successful summary; `red` for a failed summary |

Status glyphs (Unicode → ASCII fallback): ok `✓`→`+`, warning `!`→`!`,
skipped `–`→`-`, failed `✗`→`x`, waiting on you `›`→`>`, running `…`→`~`.
Use ASCII when the console encoding (Rich `Console.encoding`) does not start with
`utf`. Terminal consoles created for human output set `highlight=False` (removes
Rich's automatic number colouring). Remove every use of `magenta`.

Value grammar: prose values, lower case after the first word of a section value,
lists separated by `" · "`, durations `4m 00s` style (existing `_format_duration`),
no `key=value`, no `(true)`/`(false)`, no `Enabled;` fragments.

Density rule: a `·` list only for items of the same kind; different kinds of fact
get their own keyed row. Lists of whole items that may wrap (summary timings,
after-upload results) render with Rich `Columns` so they wrap between items,
never inside one.

## Track A — correctness and consistency

### A1 Streaming-service parsing

Owner: `services/metadata_parsing.py` (`_SERVICE_ALIASES`, `_SERVICE_TOKEN_ALIASES`,
`_service`). Tests: the existing metadata-parsing tests.

Scope: today's services plus TRaSH Guides *Streaming Services General* and
*Streaming Services Anime* (checked September 23, 2026). No other regional sets.

Display codes and token aliases. Tokens are the upper-cased release-suffix tokens
already produced by `_release_tokens` (split on `[^A-Za-z0-9+]`; the suffix starts
at the resolution or source type, so the title is never matched; the terminal
release group is already removed). A tuple is a consecutive token sequence.

| Code (display) | Token aliases | Needs `WEB` next |
| --- | --- | --- |
| `AMZN` | AMZN · AMAZON · AMAZONHD · (AMAZON, PRIME) | no |
| `ATV` | ATV · APPLETV · (APPLE, TV) | no |
| `ATVP` | ATVP · APTV · (APPLE, TV+) | no |
| `CC` | CC | yes |
| `DCU` | DCU · (DC, UNIVERSE) | no |
| `DSNP` | DSNP · DSNY · DISNEY · DISNEY+ | no |
| `PLAY` | PLAY | yes |
| `HBO` | HBO (not followed by MAX) | yes |
| `HMAX` | HMAX · HBOM · HBOMAX · (HBO, MAX) | yes |
| `HULU` | HULU | no |
| `iT` | IT · ITUNES | yes |
| `MAX` | MAX (not preceded by HBO) | yes |
| `MA` | MA · (MOVIES, ANYWHERE) | no (existing, unchanged) |
| `NF` | NF · NETFLIX · NETFLIXHD · NETFLIXUHD | no |
| `PMTP` | PMTP · PARAMOUNT · PARAMOUNT+ | no |
| `PCOK` | PCOK · PEACOCK · (PEACOCK, TV) | no |
| `ROKU` | ROKU | no |
| `SHO` | SHO · SHOWTIME | yes |
| `STAN` | STAN | yes |
| `SYFY` | SYFY | no |
| `ABEMA` | ABEMA · ABEMATV · (ABEMA, TV) | no |
| `ADN` | ADN | no |
| `B-Global` | BGLOBAL · (B, GLOBAL) | no |
| `Bilibili` | BILI · BILIBILI | no |
| `CR` | CR · CRUNCHYROLL · (CRUNCHY, ROLL) | no |
| `FUNI` | FUNI · FUNIMATION | no |
| `HIDIVE` | HIDI · HIDIVE | no |
| `VRV` | VRV | no |
| `WKN` | WKN · WAKA · WAKANIM | no |

"Needs `WEB` next" (from TRaSH's own patterns): the token immediately after the
alias must be `WEB`, `WEBDL`, or `WEBRIP`.

Resolution order in `_service`:

1. Token aliases, checking multi-token and longer aliases before shorter ones (so
   `HMAX`/(HBO, MAX) win over `HBO` and `MAX`, and `ATVP` over `ATV`).
2. Otherwise map guessit's `streaming_service` name (case-folded) through
   `_SERVICE_ALIASES`. Keep existing entries except the two changes below and add:
   `itunes`→`iT`, `appletv`→`ATVP`, `apple tv+`→`ATVP`, `comedy central`→`CC`,
   `dc universe`→`DCU`, `disney`→`DSNP`, `hbo go`→`HBO`, `hbo max`→`HMAX`,
   `the roku channel`→`ROKU`, `showtime`→`SHO`, `stan`→`STAN`, `syfy`→`SYFY`,
   `crunchy roll`→`CR`, `anime digital network`→`ADN`, `peacock`→`PCOK`.
3. Otherwise no service.

Intended behaviour changes: `ATVP`/`APTV`/`Apple TV+` now display `ATVP` (was
`ATV`); `HMAX`/`HBO Max` now display `HMAX` (was `MAX`). `MAX` alone stays `MAX`.
Update tests that asserted the old collapsed codes.

Acceptance and proof (parametrized tests): each code from a realistic filename
(`Show.S01E01.1080p.<CODE>.WEB-DL.DDP5.1.H.264-GRP.mkv`); `It.2017.2160p.iT.WEB-DL…`
gives title `It` and service `iT`; `…1080p.IT.DDP5.1.H.264-GRP` (no WEB next) gives
no service; `…HBO.MAX.WEB-DL…` gives `HMAX`; `…HBO.WEB-DL…` gives `HBO`; the
screenshots' `…2160p.iT.WEB-DL…` file gives `2160p | iT WEB-DL | DV HDR |
ThisBlockHasProblems` from `format_release_descriptor`; all existing parser tests
pass or were updated only for the two intended changes.

### A2 One formatting policy

Owners: `assets/viewer_format.js`, `assets/inspector.js`, `renderer.py`, and the
terminal formatter in `orchestration/fps_report.py`.

- **FPS:** round to 3 decimals and drop trailing zeros (`23.976`, `25`, `29.97`),
  suffix ` fps`. Fix `ViewerFormat.formatFps`, which prints the raw float. Where a
  rational is known and shown today, keep it in parentheses: `23.976 fps
  (24000/1001)`.
- **File size:** two decimals in viewer and terminal (`10.83 GiB`); change the
  terminal formatter in `fps_report.py` to match `ViewerFormat.formatFileSize`.
- **Runtime:** `H:MM:SS` from `frame_count / fps`, floored to whole seconds.
- **Generated timestamp:** `Intl.DateTimeFormat(undefined, { dateStyle: 'medium',
  timeStyle: 'short' })` in the header meta and Report Information, with the raw ISO
  string in the element's `title` and a `<time datetime>` element.
- **Advanced tonemap labels** (Report Information), from the vs-placebo `Tonemap`
  documentation: gamut mapping `0 Clip, 1 Perceptual, 2 Soft clip, 3 Relative,
  4 Saturation, 5 Absolute, 6 Desaturate, 7 Darken, 8 Highlight, 9 Linear`;
  metadata `0 Automatic selection, 1 None, 2 HDR10 (static), 3 HDR10+ (MaxRGB),
  4 Luminance (CIE Y)`. Unknown integers display as the number. `Source peak Auto`
  displays `Automatic`. Smoothing period displays `{n} frames`. Scene thresholds
  combine to one row: `{low} low · {high} high`. Other rows unchanged.
- **Active picture:** `{w}×{h} · full frame` when `active_picture` is null;
  otherwise `{w}×{h} · active {aw}×{ah}, {top} px top` and, only when the left
  offset is non-zero, `, {left} px left`; then ` · DV L5` when the active picture's
  provenance is `dolby_vision_l5` (restored in B3 after the Checkpoint A review).

Proof: `viewer_format` harness cases for each rule (including `23.976023976023978`,
`25`, unknown enum, zero and non-zero left offsets); tonemap label mapping; terminal
size formatting test.

### A3 Grid shortcut

Owners: `viewer.js`, `renderer.py` (Grid button title, Help modal markup).

- Add `G` / `g` for Grid in the keyboard handler. Keep `S`, `O`, `D`, `B`, and the
  digit source-selection behaviour. Update the Grid button title to
  `Grid (G) — scan sources together` and the Help shortcut list.
- Do not show shortcut letters in the mode control, and do not add a frame-position
  counter to the toolbar (D9). The frame select keeps today's order and text.

Proof: viewer-state harness for `G` and `g`. Title and Help wording: review.

### A4 Lens and palette details

Owners: `renderer.py`, `lens.js`, `viewer.css`, viewport/palette markup.
Reference: `viewer-lens.webp`, `viewer-popovers.webp`.

- Default sample marker becomes **Ring** when no saved lens preference exists.
- Remove the `<span class="rv-lens-fixed-status">Fixed</span>` element and its CSS
  rules (static text, no behaviour). Add to lens settings, below the reset button:
  `The lens window stays where you put it; drag its grip to move it. Settings are
  saved in this browser.` (replaces the current persistence sentence where it says
  the same thing; keep any storage-failure message).
- Plain magnifier (D10): remove the "Compare inside lens" checkbox
  (`#lens-comparison-enabled`), the comparison-source select
  (`#lens-comparison-target`), the `[data-lens-comparison-settings]` block, the
  comparison pane and its image slot, the split-lens layout, the `COMPARE` caption,
  and the "Current source" output (`[data-lens-current-source]`). Remove the
  `comparisonEnabled`/`comparisonTarget` state; stored values for those keys are
  ignored by the existing validation and dropped on the next write (no migration).
- Lens settings contain, in order: Size, Sample marker, **Caption** (Off/On
  radiogroup styled like the others, default Off, saved with the other lens
  preferences), the reset button, and the note above.
- Caption (when On): one row under the magnified image with the S1 lens caption
  text for the magnified source, end-truncated. In Diff mode:
  `{left caption} ↔ {right caption}`. In Grid: the source of the cell under the
  pointer. Remove the `ACTIVE`/`DIFF` role badges.
- Always, regardless of the caption setting: keep the loading/unavailable status
  notice when a lens image cannot be shown, and keep the lens's accessible
  description of the magnified source (full name) for assistive technology.
- Keep the drag grip.
- Distinct icons: the image-offset settings button uses a four-way move icon; the
  lens settings button uses a gear. Replace Unicode `−`/`+` zoom glyphs with SVG
  icons of the same stroke weight as the other palette icons.
- Vertical palette: zoom-in above the range and zoom-out below it (range direction
  matches: up = larger). In the vertical orientation only, the Source labels and
  Lens buttons show icons instead of text (a label/tag icon and a magnifier icon)
  so the column is as narrow as the other controls; their `aria-label`,
  `aria-pressed`, and `title` (with shortcut) are unchanged. The horizontal
  orientation keeps the text buttons.

Proof: lens-state harness (Ring default without saved prefs; saved `off` kept;
Caption default off and persisted; caption text rule including a DV name and an
explicit label, Diff pair text; stored `comparisonEnabled` ignored); renderer test
that the removed controls are absent (`Fixed`, comparison controls,
`data-lens-current-source`) and that the new radiogroups default to Ring and Caption
Off. Icons, vertical order, palette width, and caption appearance per mode: review.

## Track B — agreed design

### B1 Source identity across the viewer

Owners: `services/release_identity.py` (separator parameter only),
`orchestration/phase_post_render.py` (`run_report_phase` passes `" · "`),
`renderer.py`, `viewer.js`, `viewer_format.js`, `lens.js`, `grid_view.js`,
`inspector.js`, `review_state.js`, `viewer.css`. Reference: `viewer-viewer.webp`.

- Report display profiles use `" · "` per S1.
- Sources are identified by name only: no colour swatches, no `#n`, no side words
  anywhere in the viewer (D9). Toolbar option text stays the `control` name.
- Toolbar: remove the `L:`, `vs`, `R:`, and `Clip:` text; keep the swap button
  between the two selects and the existing ids and aria-labels. Source selects get
  `max-width: 20rem` with end ellipsis; `title` holds the full name. Offset status
  renders `Offset` in the UI face and the value in mono.
- Stage labels: remove the `LEFT:` / `RIGHT:` (and any other side or role) prefix
  in every mode. Content: the `control` name, then muted
  `· {resolution} · {size}`. Include the `HDR`/`SDR` word only when the displayed
  name contains none of the whole words `HDR`, `HDR10`, `HDR10+`, `DV`, `HLG`,
  `SDR`. File size stays (documented contract). The bottom-left frame chip is
  unchanged.
- Apply S2 typography to the toolbar, stage labels, filmstrip captions, the lens
  caption (UI face, not mono), and palette readouts.
- Accessible names and descriptions contain no `#n` either: the lens's accessible
  description (`fullSourceIdentity` in `lens.js`) uses the full name without a
  number prefix.
- Lens caption (Checkpoint A review decision): the caption wraps instead of
  truncating. Remove the caption's end-truncation and character-capacity logic.
  Single, Slider, and Grid: one caption text that wraps within the lens width. Diff:
  two lines, the left source's caption text, then `↔ ` and the right source's
  caption text; each line wraps if needed. The lens window grows to fit the
  caption. Harness proof: caption text lines per mode, no ellipsis.

Proof: display-profile test asserting `·` in the report payload and `|` in slow.pics
image names for the same fixture; viewer-format harness for the
HDR-word rule and explicit labels. Toolbar and stage-label appearance, truncation,
and the viewport/zoom matrix: review.

### B2 Proximity fade for the viewport palette

Owners: the module owning palette state (`viewport.js` or `viewer.js`), `viewer.css`.
Reference: `viewer-viewer.webp` (ghost), `viewer-lens.webp` (shown).

- `data-proximity="near"|"far"` on `.rv-viewport-palette`. CSS:
  `[data-proximity="far"]:not(:focus-within)` → `opacity: 0.18`; otherwise 1.
  `transition: opacity 150ms ease`; none under `prefers-reduced-motion: reduce`.
- One `pointermove` listener on the stage, throttled with `requestAnimationFrame`.
  Distance = shortest distance from the pointer to the palette's bounding rectangle
  (0 inside). Set `near` when distance ≤ 96 px; set `far` when distance ≥ 160 px;
  between those, keep the current state. `pointerleave` of the stage sets `far`.
- While a viewport drag/pan or slider drag is active, force `far` and ignore
  distance until the pointer is released.
- Force `near` for 3000 ms after load, and while `#align-popover` or
  `#lens-settings-popover` is open.
- Only when `matchMedia('(hover: hover) and (pointer: fine)')` matches; otherwise
  the attribute stays `near`. Re-evaluate on media-query change.
- Pointer events stay enabled in both states.

Proof: viewer/viewport harness for the state machine (thresholds, hysteresis,
drag override, popover and load overrides, coarse pointer). Feel of the fade,
opacity, reduced motion, and touch: review.

### B3 Inspector and Report Information

Owners: `renderer.py`, `inspector.js`, `viewer.css`. Reference:
`viewer-inspector-frame.webp`, `viewer-inspector-clips.webp`,
`viewer-report-info.webp`. The maintainer reviewed these mockups; implement to them.

- **Tabs:** segmented style matching the mode control (brass active tab). Keep the
  tablist/tab/tabpanel roles, ids, and roving focus.
- **Frame tab:** rows `Frame` (`{number} · {category}`; if the frame label is not
  `Frame {number}`, show the label instead) and `Position` (`{position} / {count} in
  {filter name}`). Show `Detail` only when it differs from the default
  `Selected comparison frame`. Remove the `Label`, `Number`, `Category`, and `Shown`
  rows.
- **Source frames:** a table of **all** sources with columns Source (compact
  name, and for visible sources a brass `Shown left` / `Shown right` /
  `Shown` line), Frame (`{source_frame} / {frame_count}`, mono, `Unknown` when
  missing), Type (`{picture_type}` plus ` · DV RPU` when true; `unknown` when
  missing). Visible rows get a brass left edge and a faint brass background. Note
  below the table: `Frame is each source's own frame number after alignment.
  Spatial image offsets stay under Image offset.`
- **Clip card** (one renderer used by the Clips tab and Report Information):
  header with role (`Reference` / `Comparison`), and, in the Clips
  tab only, placement (`shown left`, `shown right`, `shown`, `not shown`); a badge
  (`DV HDR` when the signal has a DV RPU and is HDR, `HDR`, or `SDR`); the standard
  name; the filename in mono; rows `Picture` (A2 active-picture text, including the
  ` · DV L5` provenance note), `Length`
  (`{frames} frames · {runtime}`), `Size`, and in the Clips tab only `Signal`
  (existing signal summary).
- **Shared line:** above the Clips tab cards, `All sources:` followed by the values
  identical across every clip, from: fps (A2 format with rational when known) and
  presentation (existing presentation text). In Report Information, show fps only.
  Omit a value that differs between clips; that value then appears on each card.
- Replace `View role: Active/Available` with the placement text above.
- **Report Information:** `Generated` uses A2; `Content` row
  `{frames} frames · {clips} sources`; `Opens in` row = default mode shown with the
  toolbar names (`slider`→`Slider`, `overlay`→`Single`, `diff`→`Diff`,
  `blink`→`Blink`, `grid`→`Grid`); `Default pair` row =
  the two default sources, one per line, each the compact name; remaining
  General rows unchanged; Advanced tonemap per A2.

Proof: Inspector harness for the table (all sources, visibility marks, missing
values), placement text, shared-line omission when values differ, and Detail
visibility. Layout and match to the reference images: review.

### B4 `run` terminal output

Owners: `cli/output.py`, `orchestration/progress.py`, `utils/progress.py` (Rich
reporter only), `orchestration/fps_report.py`, `orchestration/analysis_source.py`
(Sources panel analysis line text), `orchestration/selection_report.py`,
`orchestration/alignment_report.py`, `services/alignment.py` (evidence panel
render), `services/alignment_vsview.py` (review result line),
`services/alignment_reuse_prompt.py`, `vsview/output.py`, and the new
`utils/terminal_theme.py`. Reference: the `cli-*.svg` files.

General:

- Apply S3 everywhere in this owner list.
- Fix the blank lines after the Execution rule at their source: remove the extra
  blank line in `emit_execution_section_start` and the blank line printed before
  each measurable task in `RichProgressReporter._start_task`.
- Rich phase labels become title case (`Plan`, `Analyze`, `Align`, `Render`,
  `Metadata`, `Publish`, `Report`, `Confirm`, `Cleanup`) in the Rich reporter only;
  the plain and log reporters keep uppercase. Completed phase line:
  `{glyph} {Label:<9} {summary}` with the duration right-aligned and muted.
- Artifact paths (report, screenshots directory, shortcut) are Rich hyperlinks:
  `[link={path.resolve().as_uri()}]{display path}[/link]`.

Run plan panel (title `Run plan`, accent, border `dim`, rounded, title left).
Section names in accent; section value on the section row; sub-rows keyed in `dim`.
Blank line between sections. Row mapping (conditional rows appear under the same
conditions as today):

| Today | New |
| --- | --- |
| Workspace / root, config, input, generated | `Workspace` = root; `config`; `input`; `output` (was `generated`) |
| Frame selection / Frames `N total` + category line | `Frames` = `N total`; `mix` = non-zero categories `20 random · 10 dark · …` (today's order) |
| User frames | `user frames` = comma list |
| Analysis `Mode \| policy \| cache` | `analysis` = `{mode lower} profile · {policy} source` (+ ` · skipped for this run`); `cache` = `read and write` / `cache only` / `bypassed` |
| Window `lead=…, trail=…` / `none` | `skip` = `first {lead} · last {trail}` / `none` |
| Seed | `seed` |
| Rendering / Renderer | `Rendering` = `automatic · VapourSynth preferred` or `FFmpeg` |
| Output `X overlay \| Y geometry`, Active area | `overlay` = `{mode lower}`; `geometry` = `{geometry lower} geometry · active area {mode lower}` |
| Tone map `Preset \| N nits \| Curve` / `Disabled` | `tone map` = `{curve} {preset lower} · {N} nits` (as mocked: `BT.2390 reference · 100 nits`) / `disabled` |
| Alignment / Mode, Review | `Alignment` = `audio, then VSView review` / `audio, VSView required` / `audio` / `disabled` |
| FFmpeg audio, VSView status rows | `tools` = `{glyph} FFmpeg audio   {glyph} VSView`, each followed by muted `(unavailable)` or the existing probe-failure text when not available; omit VSView when not requested; FFmpeg shows `–` when alignment is disabled |
| Offsets | `offsets` = existing label, lower-case first letter |
| Review / Report, Metadata | `Review` = `HTML report · opens when done` / `HTML report` / `disabled`; `metadata` = `TMDB lookup` / `disabled` |
| Publishing / slow.pics | `Publishing` = `slow.pics · {visibility lower} · {mode}` where mode is `ask after the local report` / `automatic upload`; or `disabled` / `disabled by --no-upload` |
| Actions `k=v; …` | `after upload` = enabled actions `copy URL · open browser · create shortcut` / `none` |
| Webhook | `webhook` = `configured` / muted `not configured` |
| Cleanup | `cleanup` = existing text, lower-case first letter |

The `Creating lwi index file` lines are unchanged (D4).

Sources panel (`orchestration/fps_report.py`), title `Sources · {n} loaded`
(accent + muted), border `dim`:

- First line: content title (bold). Blank line.
- Per source: standard name (bold), followed by muted `reference` on the
  reference only; line 2: `{w}×{h} · {fps} fps · {frames:,} frames ({runtime}) · {size}`
  (omit the size segment when the size is unknown or zero);
  line 3: filename (muted). Blank line between sources.
- Length check: when any comparison's frame count differs from the reference,
  one warning line per distinct difference, grouping comparisons with the same
  count, using short names: `! Lengths differ: ThisBlockHasProblems and
  TheEndOfTheFuckingWorld are 464 frames (19.4 s) shorter than SCOPE.` (join three
  or more names as `A, B, and C`)
  (`longer` when positive; seconds with one decimal below 60 s, else `_format_duration`).
- Last line: `analysis source  {short name} (fastest to decode)` for the
  fastest-source policy, `{short name} (configured)` for the configured policy,
  replacing the current `diagnostic` row text.

Execution:

- Rule: `Execution` in accent, line `dim`, title left, no blank line after.
- Render progress description (`_render_progress_label` in
  `orchestration/phase_render.py`): terminal output, so pass `separator=" · "` to
  `format_micro_descriptor`.
- Alignment evidence panel (`services/alignment.py`): title `Audio alignment`
  (+ muted `· {n} needs review` when actionable), border yellow while any comparison
  needs a decision, else `dim`. Per comparison: heading = compact name (bold);
  frozen status line coloured by state (applied green, provisional/not applied
  yellow); detail lines muted; the review line (`Opening VSView…`) in accent
  prefixed by `›`; evidence rows keep their existing keys in `dim` under
  `--verbose`. `diagnostics  {path}` last. All frozen strings verbatim.
- Align phase summary before review, using short names:
  `ThisBlockHasProblems audio applied · TheEndOfTheFuckingWorld needs visual
  confirmation` (from the same states). After review: `{n} pairs confirmed in VSView`
  (+ ` · {k} kept` when k > 0); the frame-rate result stays its own line:
  `✓           frame rates match · 23.976 fps (24000/1001)` (the A2 terminal FPS
  format; this supersedes the shorter form in `cli-execution.svg`).
- VSView review result (`vsview/output.py`, `alignment_vsview.py`): replace
  `Accepted 2 confirmed pair(s); 0 comparison(s) kept…` with correct plurals:
  `Accepted 2 confirmed pairs; 1 comparison kept its current offset.` (omit the
  second clause when zero).
- Publish prompt: panel titled `› Publish to slow.pics?` (accent, border accent),
  body unchanged (`Review the local report before publishing.` / `visibility
  Public`); prompt line unchanged.
- Upload progress (Rich reporter only): label `Upload`, bar fill accent, `{done}/{total}`
  and muted `· {eta} left`.
- Publish line: `✓ Publish  {n} screenshots uploaded · {visibility}` / `– Publish
  declined` / existing skip details.

Summary panel (`print_result_summary`), title `✓ Comparison complete` (green) /
`! Comparison complete · {n} warnings` (yellow) / `✗ Comparison failed` (red),
matching border:

- Rows in order: `slow.pics` (URL, accent, underlined, when uploaded; muted
  `not uploaded (declined)` / existing skip text otherwise); an unlabelled row of
  follow-up results as `Columns`: `✓ URL copied`, `✓ opened in browser`, or
  `! browser didn't open` + muted reason; `  shortcut` path; `  webhook` only when
  configured: `✓ delivered` / `! delivery failed`; `report`; `screenshots` +
  muted `{n} files`; blank; `run` = `{frames} frames · {sources} sources · cache
  {status}`; `time` rows per B5.
- A warning tied to one of these rows (clipboard, browser, shortcut, webhook) is
  shown on that row and removed from the separate warnings panel. The separate
  `Warnings` panel remains for all other warnings with today's grouping and
  hidden-count behaviour, restyled per S3.
- Cover every publish state: declined, uploaded, uploaded with failed follow-up
  actions, upload failure, automatic upload without confirmation, and
  report-unavailable skip.

Proof: extend `tests/cli/test_run_output.py`, `test_cli_output.py`, progress,
alignment, and fps-report tests with semantic assertions; exact-match tests for the
frozen audio strings; `NO_COLOR`, ASCII-encoding fallback, `--quiet`, `--verbose`,
`--json`, and non-TTY (plain reporter unchanged) runs; `short_source_names` rule;
length-difference computation; publish-state selection of summary rows. Colours,
spacing, and wrapping at 60/80/120 columns: review. Update
`docs/current-cli-contract.md` (Run plan rows, Rich phase labels, summary) in this
unit.

### B5 Machine versus user time

Owners: `vsview/adapter.py`, `services/alignment_vsview.py`, orchestration result
plumbing (`RunResult`), `cli/output.py`.

- Measure wall time around the wait for the VSView process in
  `_run_vsview_command` and return it with the review result.
- Carry it to the human summary as an in-memory `RunResult` field. Do not add it
  to `phase_timings`, the persisted run record, or JSON output.
- Align line after review: `{align machine time} + {review time} review`, where
  machine time is `phase_timings["align"]` minus the review time.
- Summary `time` rows: `time` = `{total} total`; `  machine` = `Columns` of
  `setup {preflight + load_sources}`, `analyze`, `align` (machine), `render`,
  `upload` (publish, when it ran), each omitted when zero; `  you` = `Columns` of
  `VSView review {t}` and `prompts {confirm_slowpics_upload}`, omitted when both
  are zero.
- The total and the phase timings share the same start (`run_timer_start`
  precedes preflight), so no unmeasured remainder is shown.

Proof: adapter test with a fake clock; summary tests for the rows, omissions, and
the unchanged run-record and JSON output.

### B6 VSView session-script output

Owner: `vsview/session_script.py` (the generated self-contained script and its
`_style`, `_status_line`, `safe_print` helpers). The script runs in VSView's
process and cannot import Rich or `frame_compare` modules; mirror S3 in its own
helpers.

- Accent: `38;2;210;172;107` when `COLORTERM` is `truecolor` or `24bit` or
  `WT_SESSION` is set; else `38;5;180` when `TERM` contains `256color`; else `33`.
  Keep the `NO_COLOR` and TTY checks. Glyphs per S3 with the ASCII fallback when
  `sys.stderr.encoding` cannot encode them; `→` falls back to `->` the same way.
- Loading prints nothing on success. Failures and warnings keep their current text
  with `✗`/`!` glyphs.
- When ready, print (reference `cli-execution.svg`, "VSView is open" block):

```text
› VSView is open · waiting for you
  1  Open Tool Panel → Frame Compare Alignment Review.
  2  Unlink playheads, then position every source on the same visible moment.
  3  Save the alignment in the panel, then close VSView to continue Frame Compare.

  outputs  0  2160p · AMZN WEB-DL · HDR · SCOPE
           1  2160p · iT WEB-DL · DV HDR · ThisBlockHasProblems
           2  2160p · MA WEB-DL · DV HDR · TheEndOfTheFuckingWorld
  hints    ThisBlockHasProblems     Audio alignment accepted: +0f
           TheEndOfTheFuckingWorld  Provisional +0f - NOT APPLIED
```

  Output rows use standard names with `" · "` passed through the existing
  `presentation_names_by_stem`. Hint rows use S1 short names passed through a new
  `short_names_by_stem: dict[str, str] | None = None` parameter of
  `write_vsview_session_script`; hint names are padded to one column. Hint text is
  the existing hint string verbatim.
- Preserve byte-identical script content for identical inputs and the existing
  metadata contract.

Proof: `tests/vsview/test_session_script.py` (determinism; each colour tier; `NO_COLOR`;
ASCII fallback; ready block contains the steps, every output, and every hint
verbatim). Appearance and one real VSView launch where the host allows: review.

### B7 Other commands

Owners: `cli/doctor_command.py`, `cli/wizard_command.py`, `cli/history_command.py`,
`cli/preset_command.py`, `cli/cli_helpers.py`, error presentation in `cli/errors.py`
and `error_formatting.py`. Reference: `cli-doctor.svg`.

- **doctor (human mode):** section names in accent; each check as a row: glyph,
  check name (bold, fixed-width column), message; hint on the next row in the
  message column as muted `hint` + text, wrapping inside that column. Verdict moves
  to the end: `✓ Runtime is ready for comparisons.` / `✗ Runtime is not ready for
  comparisons.` followed by muted `{f} required check(s) failed · {w} warnings`
  (correct plurals; omit zero parts). Check messages and hint text unchanged; JSON
  output unchanged.
- **wizard, history, preset:** output content and streams unchanged. Status and
  confirmation lines (`Configuration written`, `Saved preset`, `Applied preset`,
  `Opened report`) gain the `✓` glyph; warnings gain `!`; headings and prompts
  such as `Reference:` use the accent. `history list` keeps its tab-separated
  machine-friendly rows unchanged.
- **Errors:** keep the existing `✗ Error [FC-xxxx]` shape; apply S3 colours and
  `highlight=False`.

Proof: extend `test_doctor_command.py`, `test_wizard_command.py`,
`test_history_command.py`, `test_preset_command.py` for unchanged streams, JSON,
and history's tab-separated rows; doctor verdict counts; ASCII fallback. Layout and
hint wrapping: review.

## Sequencing and review checkpoints

1. **Track A:** A1 → A2 → A3 → A4. **Checkpoint A** (controller review).
2. **Track B viewer:** B1 → B2 → B3. **Checkpoint B-viewer** (review with a
   generated report against the reference images).
3. **Track B terminal:** B4 → B5 → B6 → B7. **Checkpoint B-terminal** (review with
   rendered output at 80 and 120 columns and one real run where possible).

A1 precedes B1 and B4 because names flow into both. B1 precedes B4 because both
use the separator parameter in `release_identity.py`.

## Verification

Full Verification under the runbook: focused tests while editing, then one
integrated gate per checkpoint.

```bash
uv run --no-sync pyright --warnings
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync bandit -c pyproject.toml -r src --severity-level medium
uv run --no-sync pytest -q
uv run --no-sync lint-imports --config importlinter.ini
uv run --no-sync pytest -q -rs tests/browser/test_report_browser_smoke.py
```

Inspect skips; a green run with a skipped browser suite is not browser proof.
Use the locked Node harnesses through pytest. Assert semantic fragments and stream
separation, not whole-terminal snapshots.

### Test scope

Automated tests cover what can break silently. Visual presentation is obvious to a
person and is checked at each review checkpoint, not by tests.

- **Test:** parsing and formatting rules; state machines and saved-state handling
  (including old saved values); keyboard and interaction behaviour; data shown
  (which sources, which values, which rows are omitted); removed features staying
  removed; accessibility semantics (roles, `aria-checked`/`aria-pressed`, an
  accessible name exists); and the invariants (payload keys, `|` in slow.pics
  names, frozen strings verbatim, JSON/quiet/non-TTY output, run
  record, VSView script determinism).
- **Do not test:** element positions, sizes, widths, spacing, order on screen,
  colours, fonts, icon markup (`svg` presence), CSS `display` values, truncation,
  exact tooltip/Help/note wording, option label lists, or terminal layout and
  wrapping. Do not add debug attributes or diagnostic output to tests.
- **Browser smoke test:** only "the report loads without errors and core
  interactions work". Prefer the Node harnesses for viewer logic. Do not extend the
  smoke test with presentation checks; existing smoke coverage stays.
- **One place per rule:** do not re-test in the browser what a harness already
  covers.
- **Existing tests:** update existing assertions whose expected text or values the
  plan changes; do not delete existing coverage.
- **Review checks** (performed and recorded at each checkpoint, not automated):
  each unit's "review" items, a generated report compared with the reference
  images at 1440 px and in a narrow desktop window (about 760 px, which also
  covers 200% browser zoom; phones are not a target), and terminal output at 80 and 120 columns compared
  with the `cli-*.svg` references.

Documentation, in the unit that changes the behaviour: `docs/current-cli-contract.md`
(Run plan, phase labels, summary, doctor), `docs/guides/reports-and-overlays.md`
(viewer, Inspector, lens, shortcuts), `docs/guides/sources-and-labels.md` (source
names and services), and the architecture's viewer/Inspector sections. Then:

```bash
uv run --no-sync python scripts/generate_api_docs.py --check
uv run --no-sync zensical build --clean --strict
```

## Stop conditions

Stop and record the question for the maintainer when:

- a payload key, `phase_timings` key, run-record field, or JSON output would change;
- slow.pics names would change other than through A1, or burned-in screenshot text
  would change at all;
- a frozen audio string would change;
- a retained palette control would be removed or moved (beyond A4's `Fixed` text;
  D10 removes lens-settings controls only);
- a rule in this plan cannot be applied as written, or two rules conflict;
- verification fails for a reason outside the unit's owners.

## Deferred

Filmstrip per-category colour dots; Report ID copy button; merging the header and
toolbar rows; suppressing L-SMASH indexing output; regional streaming-service sets
(Asian, Dutch, French, UK, Misc).

## Execution record

- Planning: created September 23, 2026 from the conversation audit, rendered
  mockups (assets folder), locked decisions D1–D8, and code investigation of the
  display profiles, parser tokens, timing spans, keyboard bindings, VSView script,
  and command outputs. Revised the same day after maintainer review to add D7, D8,
  the reference assets, and decision-complete specifications. No product
  implementation performed.
- Second maintainer review (same day): viewer declutter (D9): removed the toolbar
  position counter, mode shortcut letters, viewer `#n` numbers, and stage-label side
  words; lens settings header wraps instead of truncating; vertical palette uses
  icon buttons for Source labels and Lens; frame select keeps frame-number order.
  Confirmed TRaSH codes `ATVP` and `HMAX` stay distinct from `ATV` and `MAX`, and
  approved the terminal mockups. Mockups regenerated to match.
- Third maintainer review (same day): removed viewer colour swatches; replaced
  terminal `#n` with release-group short names (S1); made the lens a plain
  magnifier with an opt-in caption showing service, source type, and group (D10).
  Mockups regenerated to match.
- Test-scope correction (September 23, after Track A): added the Test scope rules
  and moved presentation checks from Proof lists to review. Track A's
  presentation-only assertions are removed in a follow-up pass (handoff
  "Track A test-scope correction").
- Track A implementation (September 23): A1 streaming-service parsing, A2
  formatting policy, A3 grid shortcut, A4 plain-magnifier lens, each reviewed
  and committed separately. Follow-up test-scope correction removed the
  presentation-only assertions (commit `589d267c`); the lens caption was
  verified by looking in a real browser (Single/Slider/Diff all show). Full
  gate green: 3452 passed, 90 skipped; strict docs build clean. Track A Final
  report handed back for review; Track B not started.
- Checkpoint A review (September 23, controller): Track A accepted at `f711cb27`.
  Verified A1 table/rules/order/mappings line by line, A2–A4 against the plan, the
  test-scope correction, and a generated three-source report by eye (Slider, Single
  and Diff with lens, vertical palette, Inspector Clips, Report Information). Gate
  re-run with the `vsview` extra restored: pyright 0/0/0 (the session's "468
  pre-existing errors" were a missing `vsview` extra after a partial re-sync),
  ruff, bandit, lint-imports, strict docs build, full pytest all green. Carried
  into Track B: restore ` · DV L5` (B3), lens caption wraps with a two-line Diff
  form and UI face (B1), no `#n` in the lens accessible description (B1), Report
  Information mode names (B3), terminal frame-rate line uses the A2 format and
  unknown size is omitted (B4). Handoff setup and baseline rules tightened.
- Track B viewer implementation (September 23): B1 source identity (`f61e45bc`),
  B2 proximity fade (`8d270540`), B3 Inspector and Report Information
  (`104f55cc`), each reviewed and committed separately. Track-level review then
  added four fixup commits: info-modal roles from the default left clip
  (`2b35e8c0`), Default-pair stacking (`6ca16483`), grid UI-face type, range-word
  punctuation, and drag-docs correction (`e4f3d0c2`), and stale smoke-probe
  expectations (`91aed0eb`). Browser matrix in real Chrome at 1440 and 375 px
  against all four viewer webp references: chrome matches; open deviations are
  numbered `Comparison N` roles vs bare-mock roles and the unreachable fps
  rational `(24000/1001)` (payload carries float only). Full gate green
  (pyright, ruff, bandit, lint-imports, full pytest exit 0 incl. 17 browser
  smoke proofs, strict docs build). Track B Final report handed back for review;
  B4 not started.
- Checkpoint B-viewer review (September 23, controller + `reviewer` subagent):
  Track B viewer reviewed at `5bc5e620`. Gate re-run green (pyright 0/0, ruff,
  bandit, lint-imports, strict docs, pytest 3500 passed / 86 environment skips,
  browser smoke unskipped); report checked by eye at 1440 px and true mobile width
  (no overflow). B2 accepted as specified. Corrections required before Track B
  terminal (handoff Prompt 2b): bare `Comparison` role (D1 deviation); one
  clip-card renderer for Clips and Report Information; lens position accounts for
  the caption height; S2 mono for numeric values; remove the dead fps rational
  branch, two out-of-scope CSS tests, and dead `clipOverlayLabel`; test
  `frameFilterName`; Offset label spacing; Frame-table first-cell padding and
  Type nowrap; singular `1 frame`. D2 (bare fps) accepted: the payload has no
  rational. Plan corrected: the burned-in-text invariant (burned-in text is the
  clip label; `phase_render`'s descriptor is the terminal render-progress label,
  now assigned to B4).
- Track B viewer corrections C1–C11 (September 24, implementation session):
  three commits on `dev/v0.6.0-design-refresh`, each after plan-conformance
  review (plus regression review for commit 1) with findings fixed or recorded:
  `2eb059e5` roles + single clip-card renderer (C1, C2; bare
  `Reference`/`Comparison`, Report Information cards/`Opens in`/`Default pair`
  filled at startup by the Inspector builder, compact cards omit placement,
  Signal, and Presentation); `5f26e5e9` lens, typography, layout (C3, C4, C8,
  C9, C10; measured-footprint lens clamp, `--font-mono` value cells, offset
  flex gap, source-table padding/nowrap, singular `1 frame`); `d851a795`
  test cleanups (C5, C6, C7, C11; dead fps rational/`clipOverlayLabel`/CSS
  assertions removed, `frameFilterName` reuse + filtered-Position case,
  separator test renamed with the progress-label assertion dropped for B4).
  Gate: pyright 0/0, ruff check + format, bandit 0 medium+, lint-imports kept,
  full pytest exit 0 (environment skips only; exact counts unconfirmed — summary
  line not captured, re-check at handoff), browser smoke 17 passed / 0 skipped,
  API docs check + strict docs build clean. Reviewed by eye in real Chrome at
  1440 px on a generated three-source report (info cards/rows, mono values,
  `Offset: none`, Frame table, Diff lens with caption parked at the stage
  bottom, fully inside). Docs: guides clip-card wording, architecture lens
  clamp. Payload untouched. Known notes: header meta still reads `1 frames`
  for 1-frame reports (out of B3 scope); empty-payload info message nests a
  `div` in the list (DOM-constructed, degenerate path). B4 not started.
- Review of corrections C1–C11 (September 24, controller + `reviewer` subagent):
  accepted after follow-ups. Verified all eleven in code and by eye at 1440 px
  (bare roles, viewer-built Report Information cards, `1 frame · 3 sources`,
  mono values, `Offset: none`, Frame-table padding/nowrap, bottom-parked Diff
  lens inside the stage). Gate green: pyright 0/0, ruff, bandit, lint-imports,
  strict docs, pytest 3492 passed / 86 environment skips (8 fewer than before,
  from the tests these corrections deleted). Follow-ups in handoff Prompt 2c:
  lens size applied before placement (real clipping bug after a size change or
  on first render), restore the Offset live-region space, remove unused
  parameters, one default-pair rule, empty-list semantics, test-helper and
  class-name cleanups, a singular Content test, architecture wording, and
  stage-label meta no-wrap.
- Track B viewer follow-ups F1–F9 (September 24, implementation session): one
  commit `dfae7015` on `dev/v0.6.0-design-refresh` after plan-conformance review
  (all F1–F9 verified, no blockers/majors) plus regression review (1 major, 4
  minors): fixed the major (Python hook assertion for the new
  `data-info-clips-empty` container) and 2 minors (null-data guard in
  `defaultPairIndexes`, empty-message hidden flags in the non-empty harness
  case); rejected 2 with evidence (whole-meta nowrap is the prompt's "for
  example" and per-part spans would break the harness text concatenation;
  F4-mandated fixed-index stub, rule covered in the viewer-state harness).
  F1 verified as a true regression test (new harness case fails on the old
  order at the placement assertion, passes on the new). Gate: pyright 0/0,
  ruff check + format, bandit no issues, lint-imports kept, full pytest 3494
  passed / 86 environment skips, browser smoke 17 passed, API docs check +
  strict docs build clean. Reviewed by eye in headless Chrome at 1440 px on a
  generated three-source report (untracked scratch under /tmp/eyecheck):
  large lens parked bottom-right fully inside the stage (rect 1112,335–1432,657
  in stage 0,109–1440,665; border and margin visible), live-region text exactly
  `Offset: none`, stage-label meta `white-space: nowrap` with wraps only
  between values (`3840×1606`, `17.49 GiB` unbroken), Report Information modal
  with bare roles, viewer-built cards, `Opens in: Slider`, two-line Default
  pair, and `1 frame · 3 sources`. Residual risks: whole-meta nowrap could
  overflow between-value wrapping at 375 px (review accepted; check there if
  the layout is touched again); inspector stub bypasses the real pair rule
  for adversarial inputs (prompt-mandated shape). B4 not started.
- Review of follow-ups F1–F9 (September 24, controller + `reviewer` subagent):
  F1–F8 accepted. F9's whole-meta nowrap accepted: it only overflows at phone
  width, and the maintainer confirmed phones are not a target for this local
  report (narrow-width review checks now use a ~760 px desktop window, which also
  covers 200% zoom). Found in the controller's narrow-width check: B1 regression
  where the ≤768 px pair-control grid still has six columns for the removed
  `L:`/`vs`/`R:` elements, so the swap button overlaps the right select. Final
  follow-ups in handoff Prompt 2d (grid fix, remove one wording assertion);
  visual checks are done by the controller.
- Track B viewer final fixes G1–G2 (September 24, implementation session):
  commit `c2835710` on `dev/v0.6.0-design-refresh` after a read-only
  plan-conformance review (PASS, no findings): G1 changed the ≤768 px
  pair-control grid to three tracks (`minmax(0, 1fr) auto minmax(0, 1fr)`) for
  the three remaining children in `viewer.css`, and G2 removed the
  "No clips in payload." wording assertion while keeping the `data-info-*`
  hook and `hidden` assertions in `test_report_renderer_markup.py`; nothing
  else changed. Verification: focused suites
  (`test_report_renderer_markup.py`, `test_report_viewer_assets_css.py`,
  `test_report_browser_smoke.py`) 68 passed exit 0, `ruff check .` clean
  exit 0. B4 not started.
- Checkpoint B-viewer closed (September 24, controller): G1–G2 (`c2835710`)
  verified; diff is exactly the two fixes. Visual check at a 760 px window: the
  pair control lays out left select, swap, right select without overlap, no
  horizontal overflow, stage labels fit. Gate: pyright 0/0, ruff check and
  format, lint-imports, strict docs; pytest 3494 passed / 86 environment skips
  on a clean run (one earlier run had a single failure that did not reproduce
  in isolation or in a second full run; it coincided with concurrent browser
  automation). Track B viewer accepted; Track B terminal (Prompt 3) may start.
- Track B terminal B4 `run` output (September 24, implementation session):
  Shared S3/S1 plus the B4 owner list (`cli/output.py`, progress reporters,
  `fps_report.py`, `analysis_source.py`, `selection_report.py`,
  `alignment_report.py`, `services/alignment.py`, `alignment_vsview.py`,
  `alignment_reuse_prompt.py`, `vsview/output.py`, `phase_render.py`,
  `phase_alignment.py`, `phases.py`, `publishers.py`, `release_identity.py`).
  Run plan row table row by row, Sources panel, Execution rules, Summary rows
  with every publish state, frozen audio strings with exact-match tests
  (`tests/services/test_alignment_frozen_strings.py`), Rich-only changes
  (plain/log/JSON/quiet byte-identical), blank-line fixes at source,
  `separator=" · "` in `_render_progress_label`, A2 frame-rate line, size
  omitted when unknown/zero. Adversarial review in three narrow rounds
  (Run plan+Summary conformance: 2 major + 6 minor; Sources+Align
  conformance: 2 major + 1 minor; plumbing regression: 8 minor): accepted 14
  (S3 KEY/VALUE tokens, WARN glyph for unavailable tools, tools-before-offsets
  and webhook-before-cleanup order, no underline on artifact links, magenta
  removal, unconditional mix row, compact-identity `·` separator, reuse-prompt
  offset `·`, verbatim skip summaries, Rich skip-detail labels, test-double
  hardening, human_console test fidelity, JSON stderr diagnostic wording
  documented as intentional), rejected 3 with plan counter-evidence
  (auto-detection text stays value-styled as the carried-over probe-failure
  text; render-label `{role} | …` join is the S1-preserved collision shape;
  `zip(strict=True)` failure mode pre-exists), deferred 2 with triggers (Align
  pre-review/durable duplication and the `duration_text` producer, both to
  B5's Align-line work). One genuine regression found and fixed
  at the root cause (stale `align_clips_from_request` test fake missing the
  new `review_summary` kwarg surfaced as a swallowed TypeError shifting render
  frames). Gate: pyright 0/0, ruff check + format, lint-imports kept, full
  pytest 3515 passed / 86 environment skips. Rendered Run plan, Sources, and
  Summary at 80/120 columns match the `cli-*.svg` structure (deviations limited
  to the plan-mandated A2 format and size omission). No real media run on this
  host (no media fixtures). Docs: `current-cli-contract.md` (Run plan rows,
  Rich phase labels, summary, Sources/frame-rate rules, JSON stderr note),
  `sources-and-labels.md` short-names note. B5 not started.
- Track B terminal B5 machine vs user time (September 24, implementation
  session): wall time measured around the VSView wait in
  `_run_vsview_command` (monotonic, fake-clock tested) and returned with the
  review result as `tuple[session, float]`; carried memory-only through
  `AlignmentReviewSummary` / `AlignPhaseOutput` / `ExecutionState` /
  `RunResult.vsview_review_seconds` (no `phase_timings` key, no run-record or
  JSON change — both proven by exact-shape tests). Align line keeps its
  summary and shows the S3-grammar split `{machine} + {review} review` via
  the `duration_text` override (machine = `phase_timings["align"]` minus
  review, computed after the timing is recorded); summary `time` / `  machine`
  / `  you` rows with the omission rules (Columns per the S3 density rule).
  Review: round 1 (2 reviewers, 1 blocker + 2 majors + minors, all fixed:
  missed `tools/verify_docker_gui.sh` unpack, on-screen-order assertion
  removed per Test scope, single `_format_duration` grammar via the S3
  `terminal_theme.format_duration` move, render-boundary clamp, wait captured
  on rejected paths, exact leak-guard assertions, failure-path/narrow-width
  tests); round-2 wide re-review stalled without output and was replaced by a
  tight re-review of the changed parts: PASS, no findings. One round-1 minor
  rejected with evidence (no new durable-line render test: the B4
  duration-override render test already covers the path; retention is
  pre-existing B4 policy). Gate: pyright 0/0, ruff check + format,
  lint-imports kept. Rendered summary time rows and Align split line at
  80/120 columns (machine Columns wrap between items at 80, single line at
  120; `cli-*.svg` predate the B5 rows). No real media run on this host
  (interactive VSView review needs a desktop session). Docs:
  `current-cli-contract.md` (time rows, Align split line). B6 not started.
- Track B terminal B6 session-script output (September 24, implementation
  session): generated helpers only — accent tiers (`38;2;210;172;107` /
  `38;5;180` / `33` with `NO_COLOR` + TTY checks), S3 glyph mirror with ASCII
  fallback (`›`/`✗`/`→`, plus skipped/running entries), loading silent on
  success with failures/warnings keeping text under `✗`/`!` (colors kept), the
  `› VSView is open` ready block (steps, outputs with presentation names,
  hints with padded S1 short names and verbatim hint text), and
  `short_names_by_stem=None` threaded writer → clip data (`SHORT_NAMES`,
  `sort_keys`) fed by a new `VSViewSessionRequest` field populated from clip
  `short_name`. Byte-identical output for identical inputs; metadata contract
  untouched; overlays keep ASCII `->`. Consumers updated: Windows ps1 proof
  markers → `VSView is open`, contract diagnostics section. Review:
  conformance PASS + 5 minors (all fixed), regression PASS no findings (one
  earlier regression round wedged without output and was replaced). Gate:
  pyright 0/0, ruff check + format, lint-imports kept. Ready block executed
  and eyeballed (truecolor › line, steps, outputs, padded hints; longest line
  ~60 cols so 80/120 need no wrap; matches the `cli-execution.svg` block). No
  real VSView launch on this host (needs a display; covered by Docker/Windows
  proofs in CI). B7 not started.
- Track B terminal B7 other commands (September 24, implementation session):
  doctor grouped table + end verdict (`doctor_command.py` via S3
  `human_console`/`glyphs_for_console`: accent section names, one row per
  check with tier-coloured glyph + bold fixed-width name + message, hint on
  the next row as muted `hint` + verbatim text with `overflow="fold"` in the
  message column, verdict last as `✓/✗ Runtime is (not) ready for
  comparisons.` + muted `{f} required check(s) failed · {w} warnings` with
  correct plurals and zero parts omitted, SKIP counting toward warnings to
  preserve the old needs-attention signal); wizard/history/preset `✓`
  confirmations and `!` warnings with text, streams, JSON, and history
  tab-rows unchanged (glyphs by stream encoding, bold-accent wizard
  headings); errors keep the `✗ Error [FC-xxxx]` shape with identical-valued
  S3 tokens and `highlight=False` at the single human print site. Two genuine
  defects found and fixed: the message column defaulted to ellipsis overflow
  and truncated long hint URLs (fixed with `overflow="fold"`), and a missing
  `f` prefix left a literal `[{MUTED}]` tag raising MarkupError on the
  Details path (caught by the 19 error-contract tests). Tests updated to the
  plan format (whitespace-collapsed fragments, verdict-last ordering,
  wrap-insensitive hint matching) plus new verdict-count and ASCII-fallback
  cases; review follow-ups added wizard/preset glyph+stream assertions and
  made the history glyph assertion encoding-robust. Review: conformance PASS
  + 2 minors (both fixed), regression round stalled and replaced by a tight
  re-review: PASS, no findings. Gate: pyright 0/0, ruff check + format,
  lint-imports kept, tests/cli 311 passed. Rendered doctor at 80/120 columns
  matches the `cli-doctor.svg` structure (accent headings, tier glyphs, folded
  hints, verdict with counts); error render confirms tier colours and no
  auto-highlight of URLs/paths. No real media run on this host. Docs:
  `current-cli-contract.md` doctor section rewritten to the B7 format.
- Track B terminal review fixup (September 24, implementation session):
  track-conformance review returned TRACK CONFORMANT with 2 minors; M1
  (defined-but-unused S3 `BORDER_*` tokens) accepted and fixed by adopting
  `BORDER_NEUTRAL`/`BORDER_PENDING` at the six identical-valued
  `border_style` sites (`cli/output.py`, `fps_report.py`,
  `selection_report.py`, `alignment_report.py`, `services/alignment.py`);
  M2 (literal colour values in `test_style_token_values`) rejected with
  evidence (S3 mandates the exact values; same category as the required
  frozen-string exact-match tests). Track regression review (tight
  re-review after the wide round stalled): PASS, no findings. Separate
  fixup commit; full gate re-run green.
- Checkpoint B-terminal review (September 24, controller + two `reviewer`
  subagents): Track B terminal reviewed at `fb64dc52`. Gate green (pyright 0/0,
  ruff, bandit, lint-imports, strict docs, pytest 3546 passed / 86 environment
  skips). Rendered the real Run plan, Sources, Audio alignment, and summary
  (declined, uploaded, partial failure) at 80 and 120 columns. Accepted as
  specified: Run plan row mapping, S1 short names, S3 tokens and glyphs, B5
  memory-only timing with unchanged run record/JSON, most of B6/B7, and the
  out-of-owner packaging/Docker proof updates (correct, not weakened). Not
  accepted yet: skip detail printed twice on Rich; upload and analysis-source
  text changed for plain/log/JSON output (invariant); explicit labels dropped
  from Sources (invariant); row-tied warnings still in the unrestyled Warnings
  panel; alignment panel keeps its key column; VSView script ASCII fallback can
  never fire; doctor counts skips as warnings; plus smaller consistency, dead
  code, and Test scope items. Corrections in handoff Prompt 3b (T1–T20); the
  controller performs that pass's visual checks. Sub-minute summary durations
  ("48.0 s") follow the plan's "existing `_format_duration`" rule and stay.
- Checkpoint B-terminal corrections T1–T20 (September 24, implementation session):
  five commits on `dev/v0.6.0-design-refresh` (`5f5e3cbe` T1–T5 progress/upload,
  `d504a282` T6–T8 summary, `10812ba4` T9–T13 sources/alignment, `edd0cd71`
  T14–T18 script/doctor, `50360e1c` T19–T20 scope/cleanup), no pushes. Every
  correction applied as written; no review checks by eye (controller's pass).
  Adversarial review per commit (plan-conformance + regression subagents, no
  blockers/majors): Commit 1 fixed an import-order lint and strengthened the
  JSON diagnostics test, added plain-skip/end-to-end WARN/sub-second tests;
  Commit 2 added the singular-title test and removed an orphaned style token;
  Commit 3 unified Rich/plain evidence order (normal, verbose, review);
  Commit 4 closed a test stream; Commit 5 restored the no-candidate frozen
  variant as a parametrized real-path test. Judgment calls: T4 WARNED status
  also changes the plain `[OK]`/log `completed` markers for that edge case;
  T8 renders "0 files" for an existing-but-empty screenshots dir; T20 leaves
  `vsview/output.py`'s accent-valued `STYLE_HEADER` (S3-conformant, other
  module). Full gate: pytest 3521 passed / 90 environment (Windows/pwsh) skips;
  ruff check + format clean. Pyright reports 468 errors confined to
  `vsview/alignment_review_panel.py` (PySide6 not installed after
  `uv sync --group dev --frozen`); zero errors in every touched file. No real
  media run on this host.
