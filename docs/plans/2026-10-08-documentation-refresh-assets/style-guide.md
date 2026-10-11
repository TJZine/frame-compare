---
search:
  exclude: true
---

# Documentation refresh: style guide

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
Every unit applies these rules to the prose it writes. Unit U9 installs the
permanent version of these rules in `CONTRIBUTING.md` from
[`contributing-docs-style.md`](contributing-docs-style.md), which adapts "Durable
rules" for a permanent home; this file is the reference for implementers during the
refresh.

## Scope

- **User pages:** `README.md`, `INSTALL-WINDOWS.md`, `docs/index.md`,
  `docs/getting-started/**`, `docs/windows-portable.md`, `docs/guides/**`,
  `docs/reference/**`. Every rule applies.
- **Authority and project pages:** `docs/current-cli-contract.md`,
  `docs/current-architecture.md`, `docs/ENGINEERING_RUNBOOK.md`,
  `docs/supported-media-runtime.md`, `docs/media-runtime-windows-validation.md`,
  `SECURITY.md`, `CHANGELOG.md`. Only the terminology table, the command-block rules,
  and the link rules apply to text a unit adds. Existing headings keep their current
  case because guard tests match some of them exactly.

## Durable rules

### Audience and voice

- Write for a technically capable reader who runs command-line tools and compares
  video encodes, but does not know Frame Compare's internals.
- Use second person and the imperative for procedures ("Run the dry run"). Use
  present tense and active voice for behavior ("The wizard writes the file only
  after you confirm").
- Describe current behavior only. User pages never narrate the product's history:
  no "now", "no longer", "previously", "former", "has been removed", "was renamed", or
  release numbers used as a timeline, when they describe how Frame Compare changed.
  These words remain correct for the reader's own earlier runs ("a previously accepted
  offset"). Upgrade notes belong in `CHANGELOG.md`.
- Never use "simply", "just", "easy", "easily", "powerful", "seamless", "robust",
  "blazing", or "serious".
- Do not repeat component version numbers in user guides. Link to the Supported media
  runtime page (`supported-media-runtime.md`, with the relative path from the page:
  `../supported-media-runtime.md` from `docs/guides/` or `docs/getting-started/`)
  instead. Exception:
  `docs/getting-started/native.md` lists the versions a native installer must
  provide.
- Internal schema, payload, and policy versions (for example "metadata v5",
  "payload v1.2", "schema v4") do not appear in user pages unless the reader must act
  on them.

Example:

> Bad: "Frame Compare now simply applies the offset, which was previously reviewed in
> VSPreview."
>
> Good: "Frame Compare applies the offset only when the video confirms the audio
> match."

### Sentences and paragraphs

- Aim for sentences of 25 words or fewer. Split longer sentences unless they hold a
  single list of literal values.
- Keep paragraphs to four sentences or fewer.
- Wrap Markdown prose at 88 columns. Never wrap inside a link, code span, or table
  row, or inside a phrase a page specification lists as a required literal string
  (guard tests match those phrases on one physical line).
- One idea per paragraph. Put a procedure in a numbered list, not in prose.

### Headings

- Sentence case: capitalize the first word and proper nouns only
  ("Run the four stages", "VSView alignment review", "HDR and tonemapping").
  Proper nouns: Frame Compare, VSView, VapourSynth, L-SMASH-Works, FFmpeg, FFMS2,
  BestSource, Docker, Windows, PowerShell, macOS, Linux, NVIDIA, Vulkan, TMDB,
  slow.pics (always lower case), Dolby Vision, HDR, SDR, PQ, HLG.
- One H1 per page; it equals the page's navigation label. Exception: the home page's
  H1 is its headline.
- User pages use H2 and H3 only. Do not add H4 or deeper.
- Do not put code spans, links, or trailing punctuation in headings, except
  existing contract headings and the H3 link inside a route card (visual
  specification), which makes the whole card clickable.

### Terminology

| Preferred term | Do not use | Definition |
| --- | --- | --- |
| source | clip (in prose), video, input file | One input video that takes part in a comparison. "Clip" appears only when quoting UI text ("3 clips", **Clips** tab) or the file `clip_probe.toml`. |
| reference | base, master, primary | The source whose frame numbers define the comparison and which appears first. |
| comparison | target, encode (as a role name) | Every source other than the reference. The UI names them `Comparison 1`, `Comparison 2`. |
| input directory | media folder, videos folder | The directory set by `paths.input_dir` or `run --input`. |
| generated-data root | output directory, output folder | The directory set by `paths.generated_dir`; it holds run folders and shared caches. |
| run folder | output folder, run directory | The directory Frame Compare reserves for one run beneath the generated-data root. |
| report | HTML page, viewer page | The file `report.html`. Use "report viewer" for its interactive interface. |
| offset | lag, delay, shift | The signed difference `reference source frame − comparison source frame`. "Lag" is allowed only inside the contract's algorithm text. |
| trim | cut | Frames excluded from the start or end of a source. |
| active picture | crop area, active area | The image rectangle without letterbox or pillarbox bars; set explicitly with `active_rect`. |
| alignment | sync, synchronization | Finding and applying offsets between sources. |
| applied / not applied | accepted / rejected (for offsets) | Whether an offset changes the trims. Matches the terminal's `APPLIED` and `NOT APPLIED`. |
| audio candidate | estimate, guess | An offset found by audio correlation that has not yet been confirmed. |
| VSView alignment panel | VSView plugin, Frame Compare panel, VSPreview | The **Frame Compare Alignment Review** panel inside VSView. "The panel" after first use on a page. |
| user frames | manual frames, specific frames | Frames listed in `analysis.user_frames` or `run --frames`. Quote "Specific frames" only when citing the dry-run or wizard text. |
| frame selection | frame picking | Choosing which frames to render. |
| tonemapping | tone mapping, tone-mapping | Converting HDR to an SDR presentation. |
| dry run | preview run, dry-run (as a noun) | The result of `frame-compare run --dry-run`. |
| workspace root | project directory | The directory set by `--root`. |
| Windows portable bundle | portable build, portable ZIP (as a noun for the install) | The complete Windows distribution. "Complete portable ZIP" names the download. |
| Single view | overlay mode, overlay view | The viewer's **Single** mode. Its config value is `overlay` (`report.default_mode`). |
| baked overlay | burned-in text, watermark | Text rendered into screenshot pixels (`screenshots.overlay_mode`). |
| source labels | captions, chips | The viewer's on-image source names toggled by **Source labels**. |
| slow.pics | Slowpics, SlowPics | The publishing service. The config table is `[slowpics]`. |

### Command blocks

- Use ` ```bash ` for macOS, Linux, and Docker commands and ` ```powershell ` for
  Windows commands. Use ` ```text ` for directory trees and literal output.
- No prompt characters (`$`, `>`, `PS>`). One command per line.
- Show the route prefix the reader needs: `uv run --no-sync frame-compare ...` for a
  native `uv` install and `docker compose run --rm frame-compare-run ...` for Docker.
- Use route tabs (`=== "Windows portable"`, `=== "Docker"`, `=== "Native with uv"`,
  `=== "Native with pip"`, in that order) only when the commands differ by route.
- Placeholders use angle brackets and lower-case words: `<run-name>`, `<tag>`.

Example:

````markdown
```bash
frame-compare run --dry-run
frame-compare run
```
````

### Configuration snippets

- Use ` ```toml `. Show only the tables and keys the section discusses.
- Every snippet must validate with the TOML check in the plan's
  [verification section](../2026-10-08-documentation-refresh.md#verification).
- Use the generic filenames `Reference.mkv`, `Encode-A.mkv`, and `Encode-B.mkv`, or
  the capture filenames `pq10-reference.ts` and `hlg10-comparison.ts` when the text
  must match a figure.
- Put the key's effect in the prose before or after the snippet, never in a TOML
  comment.

Example:

````markdown
```toml
[analysis]
performance_mode = "performance"
```
````

### Admonitions

- Use only `!!! note "Title"` and `!!! warning "Title"`. Titles use sentence case.
- `note` adds context the reader can skip. `warning` marks a consequence that can
  produce a wrong or misleading comparison, or lose data.
- At most one admonition per H2 section. Never put a required step inside an
  admonition.

Example:

```markdown
!!! warning "FPS matching is not conversion"
    These settings do not create frames or repair variable timing.
```

### Tables

- Use tables for comparisons and reference lookups, not for narrative.
- Header cells use sentence case. Literal values in cells use code spans.
- Keep cells to one sentence. Link from a cell only to another page or anchor.

### Links and cross-references

- Link to other documentation pages with relative `.md` paths. Link text is the
  target page's navigation label in sentence case, or a descriptive phrase
  (`the [webhook policy](../current-cli-contract.md#slowpics-webhook-policy)`).
  Never use "here" or "this page" as link text.
- Link to a specific contract section with its anchor when the reader needs exact
  behavior.
- Reference repository files outside `docs/` as code spans
  (`tools/open_docker_host_target.py`), never as Markdown links. Exceptions:
  `README.md`, `INSTALL-WINDOWS.md`, `CONTRIBUTING.md`, and `SECURITY.md` live at the
  repository root and link to `docs/...` paths for GitHub; and pages may link
  `CONTRIBUTING.md` by its GitHub URL, as the site navigation does.
- User pages never link to `docs/plans/`, `docs/reviews/`, `docs/prompts/`,
  `docs/TODO.md`, `docs/images/README.md`, or `docs/release-evidence/`.
- Each fact has one home page. Other pages state the one sentence they need and
  link to the home.

### UI text, keys, and literals

- Quote UI labels in bold with their exact capitalization: **Confirm these aligned
  positions**, **Inspector**, **Report information**.
- Keyboard keys use `<kbd>`: <kbd>I</kbd>, <kbd>Esc</kbd>.
- Commands, options, config keys, config values, file and directory names, error
  codes, and literal terminal output use code spans.
- Write numbers with units separated by a space: `100 nits`, `30 s`, `2 MiB`.

### Figures, alt text, and captions

- Use the figure markup from the [visual specification](visual-spec.md#figures).
- Alt text states what the image shows in one sentence of 160 characters or fewer,
  naming the view, the sources, and the frame where visible. Do not start with
  "Image of" or "Screenshot of".
- Captions are one or two sentences that tell the reader what to notice, plus the
  media credit sentence where the capture specification requires it. They do not
  repeat the alt text.

Example:

```html
<figure class="fc-figure">
  <img src="../images/report-grid.webp" alt="Report in Grid view showing the PQ10 reference and HLG10 comparison side by side at frame 1000." width="1600" height="1000" loading="lazy">
  <figcaption>Grid view keeps every source on screen; pick the outlier, then switch to Slider.</figcaption>
</figure>
```

## Mechanical corrections in kept text

"Keep" in a page specification means byte-identical, except for the edits that
specification lists and the corrections in this section. Apply them only to the files
your unit owns, only outside code spans, code blocks, UI quotes in bold, and URLs.
Apply nothing else.

### Link text

Replace link text that equals a left-column value (any capitalization) with the
right-column value. Keep the link target unless the page specification changes it.

| Old link text | New link text |
| --- | --- |
| Choose an Installation | Choose an installation |
| Your First Comparison | Your first comparison |
| Windows Portable | Windows portable |
| Native Source | Native source |
| Advanced Docker Environments, Advanced Docker environments | Docker profiles (target `getting-started/docker-profiles.md`) |
| How Frame Compare Works | How Frame Compare works |
| Sources, References, and Labels | Sources, references, and labels |
| Frame Selection and Analysis, Frame selection and analysis modes | Frame selection and analysis |
| Audio Alignment and VSView, Audio alignment and VSView | Audio alignment |
| HDR and Tonemapping | HDR and tonemapping |
| Reports and Overlays | Reports and overlays |
| Presets, History, and Generated Data | Presets, history, and generated data |
| Publishing and Webhooks | Publishing and webhooks |
| Supported Media Runtime | Supported media runtime |
| Output Layout | Output layout |
| CLI Behavioral Contract | CLI behavioral contract |
| Current Architecture | Current architecture |
| Engineering Runbook | Engineering runbook |
| Analysis Performance Validation | Analysis performance validation |
| Benchmark History | Analysis benchmark history |

### Words

| File (base line) | Replace | With |
| --- | --- | --- |
| `README.md:16` | validates the clips | validates the sources |
| `README.md:51`, `docs/getting-started/index.md:71`, `docs/getting-started/native.md:76` | supported clips | supported video files |
| `docs/windows-portable.md:120` | Put input clips in | Put source videos in |
| `docs/windows-portable.md:254`, `:282` | input clips | source videos |
| `docs/windows-portable.md:306` | supported clips | supported video files |
| `docs/guides/sources-and-labels.md:25` | The clip used to compute | The source used to compute |
| `docs/guides/analysis-modes.md:84` | short clips | short sources |
| `docs/guides/analysis-modes.md:15`, `docs/guides/first-comparison.md:189` | tone-mapping | tonemapping |
| `docs/guides/first-comparison.md:107` | probes the clips | probes the sources |
| `docs/guides/hdr-tonemapping.md:71`, `:93` | clip-level | source-level |
| `docs/guides/reports-and-overlays.md:151` | selected clips | selected sources |
| `docs/guides/reports-and-overlays.md:159` | preferred-clip fields | **Preferred clip** fields |
| `docs/guides/reports-and-overlays.md:183` | are simply omitted | are omitted |

No other wording in kept text changes.
