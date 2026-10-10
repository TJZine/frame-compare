---
search:
  exclude: true
---

# Documentation refresh: `CONTRIBUTING.md` block

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
Unit U9 replaces `CONTRIBUTING.md` lines 205–212 (base; the "Documentation
expectations" list and its lead-in line) with the content of the block below,
byte-for-byte, inside the existing "## Documentation development" section.

`````markdown
### Documentation style

These rules apply to the user pages: `README.md`, `INSTALL-WINDOWS.md`,
`docs/index.md`, `docs/getting-started/**`, `docs/windows-portable.md`,
`docs/guides/**`, and `docs/reference/**`. Text added to the authority and project
documents, `SECURITY.md`, and `CHANGELOG.md` follows the terminology, command-block,
and link rules; their existing headings stay as they are because guard tests or
release tooling may match them.

- Begin with user goals and observable outcomes.
- Keep task guides separate from maintainer contracts.
- Update the authoritative contract in the same change when public behavior changes.
- Use screenshots only when they add information that text cannot convey
  efficiently.
- Redact private paths, source names, and secrets; prefer generic filenames and a
  clean capture workspace over redaction.
- Avoid decorative emoji and diagrams that merely restate a sentence.

#### Audience and voice

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

#### Sentences and paragraphs

- Aim for sentences of 25 words or fewer. Split longer sentences unless they hold a
  single list of literal values.
- Keep paragraphs to four sentences or fewer.
- Wrap Markdown prose at 88 columns. Never wrap inside a link, code span, or table
  row, or inside a phrase that a guard test matches.
- One idea per paragraph. Put a procedure in a numbered list, not in prose.

#### Headings

- Sentence case: capitalize the first word and proper nouns only
  ("Run the four stages", "VSView alignment review", "HDR and tonemapping").
  Proper nouns: Frame Compare, VSView, VapourSynth, L-SMASH-Works, FFmpeg, FFMS2,
  BestSource, Docker, Windows, PowerShell, macOS, Linux, NVIDIA, Vulkan, TMDB,
  slow.pics (always lower case), Dolby Vision, HDR, SDR, PQ, HLG.
- One H1 per page; it equals the page's navigation label. Exception: the home page's
  H1 is its headline.
- User pages use H2 and H3 only. Do not add H4 or deeper.
- Do not put code spans, links, or trailing punctuation in headings, except
  existing contract headings and the H3 link inside an `fc-route` card, which makes
  the whole card clickable.

#### Terminology

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

#### Command blocks

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

#### Configuration snippets

- Use ` ```toml `. Show only the tables and keys the section discusses.
- Every snippet must load into `frame_compare.config.schema.ConfigSchema` without an
  error. Test it from an empty working directory so no real `config/config.toml` is
  read.
- Use the generic filenames `Reference.mkv`, `Encode-A.mkv`, and `Encode-B.mkv`, or
  the filenames shown in a figure when the text must match it.
- Put the key's effect in the prose before or after the snippet, never in a TOML
  comment.

Example:

````markdown
```toml
[analysis]
performance_mode = "performance"
```
````

#### Admonitions

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

#### Tables

- Use tables for comparisons and reference lookups, not for narrative.
- Header cells use sentence case. Literal values in cells use code spans.
- Keep cells to one sentence. Link from a cell only to another page or anchor.

#### Links and cross-references

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

#### UI text, keys, and literals

- Quote UI labels in bold with their exact capitalization: **Confirm these aligned
  positions**, **Inspector**, **Report information**.
- Keyboard keys use `<kbd>`: <kbd>I</kbd>, <kbd>Esc</kbd>.
- Commands, options, config keys, config values, file and directory names, error
  codes, and literal terminal output use code spans.
- Write numbers with units separated by a space: `100 nits`, `30 s`, `2 MiB`.

#### Figures, alt text, and captions

- Wrap every image in `<figure class="fc-figure">` with an `<img>` and a
  `<figcaption>`, as in the example below. Give `width` and `height` for fixed-size
  images.
- Alt text states what the image shows in one sentence of 160 characters or fewer,
  naming the view, the sources, and the frame where visible. Do not start with
  "Image of" or "Screenshot of".
- Captions are one or two sentences that tell the reader what to notice, plus a
  media credit sentence where the footage's license requires attribution. They do
  not repeat the alt text.

Example:

```html
<figure class="fc-figure">
  <img src="../images/report-grid.webp" alt="Report in Grid view showing the PQ10 reference and HLG10 comparison side by side at frame 1000." width="1600" height="1000" loading="lazy">
  <figcaption>Grid view keeps every source on screen; pick the outlier, then switch to Slider.</figcaption>
</figure>
```
`````
