---
search:
  exclude: true
---

# Documentation refresh: user guide pages

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
Owners: U4 (how-it-works, sources, analysis, HDR, presets, publishing, recipes
deletion), U5 (audio alignment, VSView review, troubleshooting), U6 (reports). Apply
the [style guide](style-guide.md) to new prose. "Keep" means byte-identical except for
the listed edits and the style guide's
[mechanical corrections](style-guide.md#mechanical-corrections-in-kept-text);
"verbatim" and "exactly" mean not one character changes. Text in quotation marks
after "exactly" is the text to write. Line numbers refer to base commit
`80beafdcdabc7ac556f78fada5e7593b89e8880c`.

## `docs/guides/how-it-works.md` — edit (U4)

Outline unchanged.

1. Replace the Mermaid block with exactly:

   ```text
   flowchart TD
       A["Input sources"] --> B["Discovery and configuration validation"]
       B --> C["Probe cache and source loading"]
       C --> D["Initial selectable window"]
       D --> E["Active-picture resolution"]
       E --> F{"Frame request needs metrics?"}
       F -->|No| G["User and deterministic random frame plan"]
       F -->|Yes| H["Quality or performance analysis"]
       H --> I["Runtime-scoped analysis cache"]
       I --> J["Dark, bright, and motion selection"]
       G --> K["Audio alignment"]
       J --> K
       K --> L{"Accepted offset reusable?"}
       L -->|Yes| M["Reuse the accepted offset"]
       L -->|No| N["Audio correlation and video confirmation"]
       N --> O{"Audio and video agree?"}
       O -->|Yes| Q["Apply the automatic offset"]
       O -->|No| P["Keep the current alignment"]
       M --> V{"VSView review enabled?"}
       Q --> V
       P --> V
       V -->|Yes| W["VSView alignment panel"]
       V -->|No| S["Finalize shared aligned overlap and frame mapping"]
       W --> S
       S --> T{"HDR tonemapping required?"}
       T -->|No| U["Render SDR screenshots and overlays"]
       T -->|Yes| X["VapourSynth and vs-placebo tonemapping"]
       X --> U
       U --> Y["Run metadata and offline HTML report"]
       Y --> Z{"Publishing enabled?"}
       Z -->|No| AA["Local result"]
       Z -->|Yes| AB["Optional slow.pics upload and webhook"]
   ```

   (Inside the page the fence language is `mermaid`.)
2. **4. Alignment:** rewrite to these points, in order (sources:
   `docs/current-cli-contract.md` "Config-Only Audio Alignment Surface";
   `src/frame_compare/services/alignment.py:1274-1278`):
   - The frame plan is mapped into the aligned comparison domain.
   - Audio correlation proposes an offset; Frame Compare applies it only when decoded
     video confirms the same frame offset. Otherwise the candidate is shown as
     `NOT APPLIED` and the current alignment stays.
   - An offset accepted in an earlier run is reused while the sources and settings
     still match.
   - With VSView review enabled, the panel opens after alignment unless a complete set
     of previously confirmed offsets was reused. The panel works only from the same
     environment as Frame Compare.
   - Keep the existing "Correlation is evidence, not certainty" paragraph.
   - Link `[Audio alignment](audio-alignment.md)` and
     `[VSView alignment review](vsview-review.md)`.
3. **Owned persistent artifacts** table: change the "Alignment reuse cache" row's
   purpose to "Reuse accepted computed or confirmed offsets while sources and settings
   match"; add a row after it: "`alignment_diagnostics/` | Record each comparison's
   alignment evidence for review; never changes trims"; change the sidecar row's
   purpose to "Store the saved panel decision beside the generated VSView session;
   see `[VSView alignment review](vsview-review.md)`".

Must not appear: `schema-v1`, `VSView migration`, `Apply computed alignment`.

## `docs/guides/sources-and-labels.md` — edit (U4)

Outline unchanged.

1. Line 86–87: replace "Report v1.2 similarly derives collision-safe control and
   constrained labels" with "The report derives collision-safe control and compact
   labels".
2. Keep all snippets (they validate). Keep everything else.

Must not appear: `v1.2`.

## `docs/guides/analysis-modes.md` — edit (U4)

Outline unchanged except the H1, which becomes exactly `# Frame selection and analysis`.

1. **Choosing between modes:** after the "Use `performance` when" list, add exactly
   "A faster iteration setup for a long source:", then the snippet from
   `configuration-recipes.md:76-83` (the fenced block only), then exactly "Brief events
   can fall between sampled bursts. Switch back to `quality` for a final
   publication-bound run."
2. **A practical starting point:** after the snippet, add exactly "Short media with
   large lead or trail exclusions may not have enough eligible frames; reduce the
   counts or the exclusions."
3. **Reproducibility boundaries:** delete lines 121–122 ("Automatic frame choices may
   also differ from releases that predate temporal stratification…").

## `docs/guides/hdr-tonemapping.md` — edit (U4)

```text
# HDR and tonemapping
## What the pipeline does
## Runtime requirements
## Configure the result
## HDR versus SDR sources
## Dolby Vision considerations
## Overlays and measurements
## Common problems
```

1. **Configure the result:** replace lines 38–52 with, in order:
   - The wizard does not configure tonemapping. Choose a preset in `[color]`, save it
     in a preset, or override it for one run with `--tm-preset`, `--tm-target`, and
     `--tm-curve`.
   - The preset sets every value; `target_nits`, `tone_curve`, `gamma_lift`, and
     `contrast_recovery` override it only when explicitly supplied in the
     configuration file or environment variables. `--tm-target` and `--tm-curve`
     take precedence for one run; `--tm-preset` replaces only the preset, and
     explicitly supplied configuration values still override it
     (source: `src/frame_compare/render/prepare.py:37-74`).
   - This table, exactly (source: `src/frame_compare/vs/tonemap_presets.py`):

     | Preset | Curve | Target | Gamma lift |
     | --- | --- | --- | --- |
     | `reference` (default) | `bt2390` | 100 nits | Off |
     | `bt2390_spec` | `bt2390` | 100 nits | Off |
     | `filmic` | `spline` | 203 nits | Off |
     | `spline` | `spline` | 203 nits | Off |
     | `contrast` | `reinhard` | 203 nits | Off |
     | `highlight_guard` | `spline` | 180 nits | Off |
     | `bright_lift` | `bt2390` | 250 nits | On |

   - This snippet:

     ```toml
     [color]
     preset = "filmic"
     target_nits = 160
     ```

     with the sentence: "This keeps the `filmic` curve and replaces only its target."
   - `enable_tonemap = false` renders HDR sources without conversion; the FFmpeg
     screenshot path (`screenshots.use_ffmpeg = true`) requires it for HDR sources
     (source: `src/frame_compare/render/prepare.py:283`,
     `src/frame_compare/vs/errors.py:63`).
   - Keep "Use one consistent target and preset…" and link the
     `[Configuration](../reference/configuration.md#color)` reference.
2. **Overlays and measurements:** delete lines 98–100 (the paragraph linking
   `images/README.md`). Replace the figure with `hdr-diagnostic-overlay.webp` in
   `fc-figure` markup with the capture specification's alt text and caption,
   `width="1920" height="1080"`.
3. Keep the other sections.

Must not appear: `images/README.md`, `physical-Windows`, `Physical-Windows`,
`fc-doc-figure`.

## `docs/guides/presets-history-generated-data.md` — edit (U4)

Outline unchanged.

1. **Run-folder layout:** replace the tree with the one from
   `docs/guides/first-comparison.md` (U3's version, item 7) with `generated/` replaced
   by `<generated-data-root>/` at the top, and keep the "See Output layout" link.
2. **Choose a durable generated-data location:** after the snippet, add both
   sentences of `configuration-recipes.md:158-159`, exactly.
3. Keep everything else.

## `docs/guides/publishing-and-webhooks.md` — edit (U4)

```text
# Publishing and webhooks
## Turn on publishing
## Confirm after reviewing the report
## Webhook notification
```

1. **Turn on publishing:** current lines 3–15 up to and including "`--no-upload`
   forces upload off for a run."; delete the rest of that paragraph (lines 15–17 from
   "For an interactive"). Then lines 19–25 (upload concurrency, timeouts, retries).
2. **Confirm after reviewing the report:** exactly "Set
   `confirm_upload_after_report = true` with `auto_upload = true` to render locally,
   review the report, and then confirm the upload:", then the snippet from
   `configuration-recipes.md:207-212` (the fenced block only), then exactly "This needs
   an interactive run with the report enabled; JSON, quiet, and non-interactive runs
   cannot prompt."
3. **Webhook notification:** keep lines 29–56.

## `docs/guides/configuration-recipes.md` — delete (U4)

Each recipe's home after deletion: three named sources, trims, FPS, and active
picture → `sources-and-labels.md` (already present); exact frames, mixed coverage,
intro/credits → `analysis-modes.md` (present, plus the additions above); faster
iteration → `analysis-modes.md`; generated data outside the bundle →
`presets-history-generated-data.md`; single-file report and diagnostic overlays →
`reports-and-overlays.md` (U6); disabling and confirming upload →
`publishing-and-webhooks.md`; limited memory → `reference/configuration.md` (U7).
Inbound links: run
`rg -n "configuration-recipes" README.md docs --glob '!docs/plans/**' --glob '!docs/reviews/**' --glob '!docs/prompts/**'`
after all units; it must return nothing (U2 replaces the home page; U7 replaces the
reference page).

## `docs/guides/audio-alignment.md` — rewrite (U5)

```text
# Audio alignment
## When alignment helps
## What the results mean
## Choose the audio streams
## Sources with different frame rates
## Reuse an accepted offset
## Review the evidence
## Common problems
```

Sources: current page; `docs/current-cli-contract.md` "Config-Only Audio Alignment
Surface" and "VSView Native Alignment Diagnostics"; `src/frame_compare/config/schema_models.py:112-125`.

- **Intro:** two sentences: Frame Compare estimates the offset between the reference
  and each comparison from their audio and applies it only when the video confirms it.
  Alignment changes which source frames are compared; it never retimes or rewrites
  the files.
- **When alignment helps:** keep lines 10–19.
- **What the results mean:** new. A short lead-in, then this table, exactly:

  | Terminal result | Meaning | What to do |
  | --- | --- | --- |
  | `Audio alignment accepted: +Nf - APPLIED` | Audio and video agree on the offset; the trims use it | Check a few frames in the report |
  | `Provisional audio candidate: +Nf - NOT APPLIED` | Audio found an offset that the video did not confirm | Review it in the VSView alignment panel, or keep the current alignment |
  | `No usable audio candidate (<reason>) - NOT APPLIED` | No offset could be established | Check the audio streams, or align manually in the panel |
  | `Accepted audio alignment reused: +Nf - APPLIED` | An offset accepted in an earlier run still matches | Nothing |
  | `Manually confirmed alignment: +Nf - APPLIED` | An offset confirmed in the panel is in use | Nothing |
  | `Manually confirmed alignment reused: +Nf - APPLIED` | An offset confirmed in the panel in an earlier run still matches | Nothing |

  Then: each line starts with `Comparison N - `; a `+0f` result is a real zero offset,
  not a missing one; `--verbose` adds the evidence counts and `--quiet` keeps only
  actionable warnings (sources: current guide lines 225–246; contract
  `docs/current-cli-contract.md:600-630`). Then two sentences: the audio is decoded
  whole and compared in chunks, then a sample of decoded frames confirms the exact
  offset; the exact thresholds live in the
  `[contract](../current-cli-contract.md#config-only-audio-alignment-surface)`.
- **Choose the audio streams:** current lines 35–44, plus the
  `reference_stream`/`comparison_streams` snippet:

  ```toml
  [audio_alignment]
  reference_stream = 1
  comparison_streams = { "Encode-A" = 0 }
  ```

  with: "`comparison_streams` keys are filename stems. Stream numbers count audio
  streams from 0."
- **Sources with different frame rates:** current lines 67–72 rewritten without the
  word "analysed": set `match_fps` or `effective_fps` first; the audio is then stretched
  onto the effective timeline, so a 24 fps release of 23.976 content or a PAL 25 fps
  release keeps a constant offset; drift for other reasons is not applied. Link
  `[Sources, references, and labels](sources-and-labels.md#correct-timing-metadata)`.
- **Reuse an accepted offset:** points: an applied automatic offset is cached and
  reused whenever the source files, trims, effective FPS, stream choices, alignment
  settings, and runtime still match; a miss recomputes; corrupt entries are ignored
  with a warning. Offsets confirmed in the panel are also cached, but reused only when
  `previous_offsets` is `prompt` or `always`; the default `disabled` never reuses them
  (sources: contract `previous_offsets` bullet;
  `src/frame_compare/services/alignment_previous_offsets.py:148-161`). Provisional and unavailable results are never
  cached.
- **Review the evidence:** points: each run writes
  `alignment_diagnostics/comparison-<n>.json` in the run folder for every computed
  attempt; it contains no media paths, audio, or credentials, its source digests are
  pseudonymous, and editing or deleting it changes nothing. Then the existing
  "inspect multiple evidence points" list (lines 333–342). Link
  `[VSView alignment review](vsview-review.md)` for visual confirmation.
- **Common problems:** the table from lines 346–355 without the four panel rows
  (launch, inactive, closes, rejected), plus this three-cell row exactly:
  "The VSView panel will not open or rejects a result | Panel setup or session problem |
  See `[VSView alignment review](vsview-review.md#troubleshooting)`" (the link is a
  real link in the page).
- **Validation standard (closing paragraph):** keep lines 395–397 as the last
  paragraph of "Review the evidence".
- **Recommended workflow (base lines 21–31):** delete; its steps are covered by "What
  the results mean", "Review the evidence", and the VSView page.

Moved out (U8 receives them): lines 85–117 → contract (rewritten text in
`pages-reference.md`); the "Labelled-pair benchmark" section (heading at line 357,
text at 359–391) → runbook under a new heading.
Deleted because the contract already states them: lines 46–63, 74–81, 119–192
(except the facts kept above), 194–331. Must not appear: `V5a`, `PSR`, `GCC-PHAT`,
`schema v`, `metadata v5`, `whole-track-chunked`, `rows_omitted`,
`alignment_benchmark`, `plans/`, `macOS L-SMASH`, `Labelled`.

## `docs/guides/vsview-review.md` — new (U5)

```text
# VSView alignment review
## Before you start
## Open the panel
## Confirm the positions
## Enter known values
## Keep the current alignment
## What happens next
## Troubleshooting
```

Sources: current `docs/windows-portable.md:161-205`,
`docs/guides/audio-alignment.md:194-331`, `docs/guides/troubleshooting.md:25-28`,
`docs/current-cli-contract.md` "VSView Native Alignment Diagnostics"; panel labels
verified in `src/frame_compare/vsview/`.

- **Intro:** the panel is the only place to confirm or enter alignment by eye; it
  runs inside VSView and saves one decision for the whole set of sources.
- **Before you start:** availability (Windows portable bundle includes it; native
  installs need the `vsview` extra in the same Python environment; the default Docker
  route has no desktop); a PATH-only VSView executable is not supported; turn review on
  with `audio_alignment.use_vsview = true` or require it with
  `--force-interactive-alignment`; if optional review cannot start, Frame Compare keeps
  the current alignment and points you to `doctor`, while forced review fails.
  Include this snippet:

  ```toml
  [audio_alignment]
  use_vsview = true
  ```

- **Open the panel:** numbered steps: (1) run the comparison; Frame Compare generates
  a session and opens VSView; (2) open **Frame Compare Alignment Review** from VSView's
  Tool Panel; (3) the workspace shows one `Reference` output and one `Comparison N`
  output per comparison. One sentence: the panel stays inactive in an ordinary VSView
  session. Required literal: `ordinary VSView session`.
- **Confirm the positions:** numbered steps: unlink the playheads; visit every output
  and leave each on the same visible moment; watch the source lineup reach the ready
  state (`{n}/{total} positions captured — ready to confirm`, composed at
  `src/frame_compare/vsview/alignment_review_panel.py:579,596`; contract lines
  1425–1427); select **Confirm these
  aligned positions**. Then: the panel distinguishes the frame you are viewing from
  the captured position, previews the signed offset and which source is trimmed, and
  shows the audio candidate under **Audio evidence** without applying it. Insert the
  figure `vsview-alignment-panel.webp` here only when U10 has produced it (U10 owns
  that insertion).
- **Enter known values:** expand **Enter alignment manually...** and choose
  **Source frames** (one non-negative untrimmed frame per source) or **Known offsets**
  (one signed integer per comparison, `reference − comparison`). Source frames use
  **Confirm these aligned positions**; known offsets use **Confirm these known
  offsets** (source: `src/frame_compare/vsview/alignment_review_panel.py:572-583`).
  With no base trims, a positive offset
  trims the reference and a negative offset trims the comparison; base trims do not
  change the value you enter.
- **Keep the current alignment:** **Keep current alignment** keeps existing applied
  offsets and leaves a provisional candidate unconfirmed.
- **What happens next:** after either action the panel shows `Alignment choices saved`
  and `Close VSView to resume Frame Compare.`; Frame Compare writes one typed, atomic
  sibling sidecar named `vsview_*.alignment-result.json` for the complete source set,
  checks it against the session, and applies it. Closing VSView without saving writes
  no result. Missing, malformed, stale, mixed-session, duplicate, incomplete, and
  out-of-bounds results fail closed. Required literals: `typed, atomic sibling sidecar`,
  `Missing, malformed, stale, mixed-session, duplicate, incomplete, and out-of-bounds`.
- **Troubleshooting:** this table, exactly:

  | Symptom | Action |
  | --- | --- |
  | `doctor` reports the alignment panel is missing | Install the `vsview` extra in the environment that runs Frame Compare, or reinstall the complete Windows portable bundle |
  | VSView will not launch | Run `frame-compare doctor`; check that a desktop session is available; continue without review, or use the Windows portable bundle |
  | The panel stays inactive | Open the session Frame Compare generated; ordinary sessions and hand-written scripts stay inactive |
  | VSView closed before saving | No result was written; run again, visit every source, and choose **Confirm these aligned positions** or **Keep current alignment** |
  | The saved result is rejected | Run again to generate a fresh session; Frame Compare rejects stale, mixed, duplicate, incomplete, and out-of-bounds results |

Must not appear: `metadata v5`, `v1`, `0.12.0`, `BestSource`, `Keep current offset`,
`plans/`.

## `docs/guides/troubleshooting.md` — edit (U5)

Outline unchanged.

1. **Common problems** table:
   - Replace rows at lines 25–28 (panel missing, inactive, closed, rejected) with one
     row: "The VSView alignment panel is missing, inactive, or rejects a result | See
     `[VSView alignment review](vsview-review.md#troubleshooting)`".
   - Add after the "Automatic alignment is weak or incorrect" row:
     "An alignment line says `NOT APPLIED` | The audio candidate was not confirmed by the
     video; see `[what the results mean](audio-alignment.md#what-the-results-mean)`".
   - Add after the "A cache hit appears stale" row:
     "`--no-cache` and `--from-cache-only` are rejected together | Choose one: the first
     disables cache use, the second requires it".
   - Add a final row: "Docker prints `without an L-SMASH index cache` | Expected on the
     default Docker route; see `[Docker](../getting-started/docker.md#the-index-warning)`".
2. **Alignment** stage section: replace its whole body (lines 83–92) with exactly:
   "Check that the selected audio streams contain corresponding material. A constant
   offset cannot fix drift, different edits, or mismatched cadence; review early,
   middle, and late frames. To confirm or enter an offset by eye, use
   `[VSView alignment review](vsview-review.md)`." (the link is a real link in the page).
3. **Collect safe diagnostics:** after the bullet "sanitized run warnings and error
   code;", add exactly the bullet "`alignment_diagnostics/` files when alignment is
   involved (they hold no media paths or credentials);".
4. Platform links: replace "Advanced Docker Environments" with
   `[Docker profiles](../getting-started/docker-profiles.md)`.
5. Replace the final sentence (lines 149–150) with exactly: "For exact error streams,
   JSON shape, and exit codes, see the `[CLI behavioral contract](../current-cli-contract.md)`
   and its `[exit-code table](../current-cli-contract.md#exit-codes-and-error-families)`."
   (both links are real links in the page).

## `docs/guides/reports-and-overlays.md` — rewrite (U6)

```text
# Reports and overlays
## Open and keep a report
## Views
### Slider
### Single
### Diff
### Blink
### Grid
## Navigate and inspect
### Inspector
### Lens
### Report information
### Keyboard shortcuts
## Review notes
## Screenshot overlays
## Recommended review sequence
## Archive or share a report
```

Sources: current page; `src/frame_compare/services/report/renderer.py:456-800`;
`src/frame_compare/config/schema_models.py:328-337`; contract "Report And Overlay
Metadata Contract" and "Report Auto-Open Ownership"; the 2026-10-08 viewer inspection.

- **Intro:** exactly "The report is a static HTML page for comparing every rendered
  frame across your sources; it opens in any current browser without a server.", then
  the `report-overview.webp` figure (alt text and caption from the capture
  specification, `width="1600" height="1000"`).
- **Open and keep a report:** keep base lines 3–6; drop lines 8–9. Then keep base
  lines 213–215 ("`report.auto_open = true` is the default…"). Then exactly "Set
  `report.embed_images = true` when one HTML file is more convenient than a folder;
  the file becomes much larger.", then the snippet from
  `configuration-recipes.md:165-168` (the fenced block only).
- **Views:** before the H3s, exactly "`report.default_mode` sets the view a report
  opens in: `slider` (default), `overlay` (Single), `diff`, or `blink`. Grid cannot be
  the default." Then, exactly:
  - **Slider:** "Slider reveals one source against another across a draggable divider.
    Use it for spatial differences such as crop, scaling, haloing, texture, denoising,
    grain, and subtle tone changes."
  - **Single:** "Single shows one source at a time for source-specific checks."
  - **Diff:** "Diff highlights pixel differences between the selected pair. Use it to
    find where sources diverge, then judge the difference in Slider or Blink." (no
    figure)
  - **Blink:** "Blink alternates the selected pair, which reveals grain structure, small
    exposure changes, and differences a stationary divider hides. Browser timing is not
    frame-accurate playback."
  - **Grid:** "Grid shows every source together so outliers stand out. Scan here first,
    then pick a pair for Slider, Diff, or Blink." followed by the `report-grid.webp`
    figure.
- **Navigate and inspect:** exactly these three paragraphs:
  1. "Move between frames with the frame selector, the arrow buttons, or the
     filmstrip, which filters by category and has Compact, Normal, and Large sizes.
     Choose the pair with the two source selectors and swap them with the button
     between them. The floating palette over the image holds zoom, fit, viewport reset,
     fullscreen, **Source labels**, and **Lens**. `report.include_filmstrip = false`
     hides the filmstrip, and `Offset: none` in the toolbar refers to a spatial image
     offset, not to timing alignment."
  2. Current lines 142–149 (source selectors, source labels, and baked overlays serve
     different contexts), kept.
  3. "Source labels show each source's complete file size. File size is context, not
     bitrate or a measure of quality. The header shows when the report was generated in
     your browser's locale; hover it for the exact timestamp."
  - **Inspector:** exactly "Open the Inspector with **Inspector** or <kbd>I</kbd>. Its
    **Frame** tab lists every source's own frame number and picture type for the
    current comparison frame. **Clips** shows each source's name, filename, picture
    size, length, file size, presentation, and signal. **Image offset** shifts a source
    spatially and never changes timing. **Review** holds bookmarks, tags, notes, and the
    preferred source." Then the `report-inspector.webp` figure.
  - **Lens:** exactly "Turn the lens on with **Lens** or <kbd>L</kbd> to magnify the
    area under the pointer. Lens settings can add a caption naming the magnified
    source; in Diff it names both sources. Drag the lens window's grip to move it."
    Then the `report-lens.webp` figure.
  - **Report information:** exactly "The **Report information** button in the header
    opens the Report Information dialog: the title, report ID, generated time, content,
    the **Opens in** view, the default pair, the slow.pics link when uploaded, every
    source, and a Rendering section that states whether tonemapping was applied and
    with which settings." Then the `report-information.webp` figure with
    `class="fc-figure fc-figure--narrow"` and no `width` or `height`.
  - **Keyboard shortcuts:** this table, exactly (source: `renderer.py:780-796`):

    | Action | Keys |
    | --- | --- |
    | Previous or next frame | <kbd>←</kbd> <kbd>→</kbd> |
    | First or last frame | <kbd>Home</kbd> <kbd>End</kbd> |
    | Cycle the source | <kbd>↑</kbd> <kbd>↓</kbd> |
    | Select a source directly | <kbd>1</kbd>–<kbd>9</kbd> |
    | Swap the pair | <kbd>X</kbd> |
    | Slider, Single, Diff, Blink, Grid | <kbd>S</kbd> <kbd>O</kbd> <kbd>D</kbd> <kbd>B</kbd> <kbd>G</kbd> |
    | Toggle source labels | <kbd>H</kbd> |
    | Toggle the filmstrip | <kbd>F</kbd> |
    | Toggle the Inspector | <kbd>I</kbd> |
    | Toggle the lens | <kbd>L</kbd> |
    | Pause Blink or change its speed | <kbd>Space</kbd> <kbd>[</kbd> <kbd>]</kbd> |
    | Zoom in or out | <kbd>+</kbd> <kbd>-</kbd> |
    | Reset the viewport | <kbd>R</kbd> or double-click |
    | Open help | <kbd>?</kbd> |
    | Close a panel or exit fullscreen | <kbd>Esc</kbd> |

- **Review notes:** current lines 151–154 up to "can remove that local state.", then
  exactly "Exported review JSON applies only to the report it came from.", then current
  lines 159–167, kept. (Lines 154–157 from "Existing v1.1" to "migration format." are
  dropped.)
- **Screenshot overlays:** keep lines 171–195 (mode table and paragraphs). After the
  mode table, add exactly "Bake the extra evidence into every screenshot:", then the
  snippet from `configuration-recipes.md:177-180` (the fenced block only), then exactly
  "`screenshots.include_frame_number = false` removes the frame number from baked
  overlays."
- **Recommended review sequence:** keep lines 202–209.
- **Archive or share a report:** in this order: base lines 219–223 (the bullets
  before "Version 1.2 report metadata…"), kept; then base lines 197–198 ("The ordinary
  report is not a blind-comparison artifact…"), kept; then base lines 227–229 (the
  closing links), kept with mechanical corrections to their link text. Base lines
  224–225 are dropped.

Delete: base lines 11–149 (the old "Viewer modes" and "Navigation and inspection"
sections). The only text carried forward from them is the text specified above. Must
not appear: `v1.1`, `v1.2`, `payload`, `report-diff.webp`,
`brass`, `ghost`, `fc-doc-figure`.
