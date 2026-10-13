---
search:
  exclude: true
---

# Documentation site redesign: style guide

Part of the [documentation site redesign plan](../2026-10-12-documentation-site-redesign.md).
Every unit that writes or edits prose applies these rules. Unit U9 installs the durable
version in `CONTRIBUTING.md` (see [repository changes](repository-changes.md#contributing-md)).

This guide replaces the voice, heading, admonition, and component rules of the
2026-10-08 style guide. The terminology table, command-block rules, configuration
snippet rules, and link rules from that guide still apply and are repeated here so
implementers read one file.

## Scope

- **User pages:** `README.md`, `INSTALL-WINDOWS.md`, `docs/index.md`,
  `docs/getting-started/**`, `docs/guides/**`, `docs/reference/**`,
  `docs/internals/index.md`. Every rule applies.
- **Authority pages:** `docs/current-cli-contract.md`, `docs/current-architecture.md`,
  `docs/ENGINEERING_RUNBOOK.md`, `docs/supported-media-runtime.md`,
  `docs/media-runtime-windows-validation.md`, `docs/analysis-performance-validation.md`,
  `docs/analysis-benchmark-history.md`, `docs/DECISIONS.md`, `SECURITY.md`, and
  `CHANGELOG.md`. Only the terminology table, command blocks, and link rules apply to
  text a unit adds. Their headings stay as they are, because guard tests, agent
  instructions, and release tooling match them.

## Voice

The reader is a technically capable person who runs command-line tools and compares
video encodes. They do not know Frame Compare's internals and do not want a pitch. Write
like the reference documentation of a mature command-line tool: plain, specific, and
calm.

### Rules

1. **Say what happens, in the order it happens.** Lead with what the reader does or gets.
   Mechanism comes after, and only if the reader acts on it.
2. **Use second person and the imperative for steps** ("Run the dry run"). Use present
   tense and active voice for behavior ("The wizard writes the file after you confirm").
3. **Name the actor.** "Frame Compare writes …", "The wizard asks …", "You choose …".
   Do not write sentences whose subject is an abstraction ("Selection intent is
   validated", "Authority is established").
4. **One fact, one sentence, one place.** Do not restate a fact in the same page. Link
   to the page that owns it.
5. **State limits once, positively when possible.** Prefer "The dry run reads only your
   configuration and file names" to a list of what it does not do. Keep a negative
   statement only when a reader would otherwise assume the opposite and lose work or
   trust the wrong result; then say it once.
6. **Keep sentences short.** Aim for 25 words or fewer. One clause per idea.
7. **Keep paragraphs short.** At most four sentences and 70 words. Split a long
   paragraph only at sentence boundaries, keeping the sentence order. A procedure is a
   numbered list or a steps block, never prose.
8. **Wrap Markdown prose at 88 columns.** Never wrap inside a link, a code span, a table
   row, or a string that a test matches; a guard string stays on one physical line.
9. **Use concrete nouns.** Write "the frames you listed", not "user-selected frame
   intent". Write "the config file", not "authored configuration".
10. **Describe current behavior only.** Do not narrate history ("now", "no longer",
   "previously", "has been removed", "was renamed", release numbers as a timeline) when
   describing how Frame Compare changed. These words remain correct for the reader's
   own earlier runs ("a previously accepted offset"). Upgrade notes belong in
   `CHANGELOG.md`.
11. **Version numbers live in one place.** Do not repeat component versions in guides;
    link to the Requirements page (`docs/reference/requirements.md`) for what a reader
    installs.
    Exception: `docs/getting-started/native.md` lists the versions a native installer
    must provide.
12. **Internal schema, payload, and policy versions** ("metadata v5", "payload v1.2",
    "schema 3") do not appear in user pages unless the reader must act on them or a
    guard string requires the literal (see [page specifications](pages.md#guard-strings)).

### Patterns that are not allowed

These patterns make text read as machine-written or as marketing. They are not allowed
in user pages. Reviewers check every page against this list.

| Pattern | Example to avoid | Write instead |
| --- | --- | --- |
| Slogan contrast ("X, not Y"; "X rather than Y" used as a framing device) | "A staged pipeline rather than a screenshot loop." | "Frame Compare runs in six stages. Each stage passes its result to the next." |
| "It's not just X, it's Y" and "more than just" | "Not just screenshots, but a full report." | "Each run writes screenshots and a report." |
| Eyebrow-plus-tagline headings | "The report: every difference, four ways" | "Report views" |
| Rhetorical questions | "Want reproducible frames?" | "Set `analysis.random_seed` to repeat a selection." |
| Reflexive triplets and stacked adjectives | "fast, reliable, and reproducible" | Name the one property that matters, with its evidence. |
| Abstract-noun phrasing | "validates selection intent and output intent" | "checks which frames you asked for and where the files will go" |
| Defensive stacks of negation | "It does not probe media, contact the runtime, or otherwise prove …" | "It reads only the configuration and file names. Run `doctor` to check the runtime." |
| Hedge and filler phrases | "It's worth noting that", "In order to", "Note that", "Please" | Delete them. |
| Dramatic punctuation | Em dashes for asides, exclamation marks, ellipses | A comma, parentheses, or a new sentence. Em dashes may appear only inside quoted UI labels (`EBU DVB PQ10 — Reference`). |
| Promotional adjectives | simply, just, easy, easily, powerful, seamless, robust, blazing, serious, effortless, intuitive, comprehensive, cutting-edge, state-of-the-art, best-in-class, world-class, game-changer, revolutionize, unlock, unleash, elevate, empower, supercharge, streamline, leverage, delve, harness, journey, landscape, realm, crucial, vital, trustworthy | Delete, or state the measurable fact. |
| Summary closers | "In summary", "Ultimately", "That's it" | End when the content ends. |

The words and phrases in the hedge, promotional, and summary rows are checked by
`tests/workflows/test_docs_style.py`. The other rows are checked by review.

### Examples

> Before: "Frame Compare is a staged comparison pipeline rather than a screenshot loop.
> Each stage owns a specific decision or artifact, and later stages consume the
> validated result instead of independently reinterpreting the same media."
>
> After: "Frame Compare runs a comparison in six stages. Each stage makes one decision,
> such as which frames to render or how far apart two sources are, and passes the
> result to the next stage."

> Before: "A dry run validates configuration, source discovery, reference and comparison
> order, selection intent, and output intent without entering the rendering pipeline.
> It does not probe media, contact the render or alignment runtime, or otherwise prove
> the runtime is ready to render; run `doctor` to confirm runtime readiness."
>
> After: "A dry run reads your configuration and the file names in the input directory.
> It shows the sources it found, the reference, the frames you asked for, and what a run
> would create.
> It does not open the videos, so run `doctor` to check the media runtime."

> Before: "Frame Compare keeps source identity separate from presentation."
>
> After: "Frame Compare identifies each source by its path. The label is the name it
> shows in reports, overlays, and output folder names."

## Headings

- Sentence case: capitalize the first word and proper nouns only. Proper nouns:
  Frame Compare, VSView, VapourSynth, L-SMASH-Works, FFmpeg, FFMS2, BestSource, Docker,
  Windows, PowerShell, macOS, Linux, NVIDIA, Vulkan, TMDB, slow.pics (always lower
  case), Dolby Vision, HDR, SDR, PQ, HLG, GitHub.
- A heading names the task or topic: "Install", "Report views", "Choose the reference".
  No taglines, no colons, no questions.
- One H1 per page; it equals the page's navigation label. The home page has no Markdown
  H1; its H1 is in the hero template.
- User pages use H2 and H3. H4 is used only by key blocks (see below).
- No links or trailing punctuation in headings. Code spans are allowed only in key-block
  headings and in troubleshooting entries that quote literal output.

## Page structure

Every user page has, in order:

1. Front matter with a `description:` of one sentence, 160 characters or fewer, written
   to the voice rules. The [page specifications](pages.md) give the exact text.
2. The H1.
3. A lead paragraph of one to three sentences that says what the page helps the reader
   do. The theme styles the first paragraph after the H1 as the lead; do not add a class.
4. Body sections.
5. Optionally a **Next steps** H2 with a cards block of two or three pages, when the page
   specification lists one.

## Terminology

| Preferred term | Do not use | Definition |
| --- | --- | --- |
| source | clip (in prose), video, input file | One input video that takes part in a comparison. "Clip" appears only when quoting UI text ("3 clips", **Clips** tab) or the file `clip_probe.toml`. |
| reference | base, master, primary | The source whose frame numbers define the comparison and which appears first. |
| comparison | target, encode (as a role name) | Every source other than the reference. The UI names them `Comparison 1`, `Comparison 2`. |
| input directory | media folder, videos folder | The directory set by `paths.input_dir` or `run --input`. |
| generated-data root | output directory, output folder | The directory set by `paths.generated_dir`; it holds run folders and shared caches. |
| run folder | output folder, run directory | The directory Frame Compare reserves for one run beneath the generated-data root. |
| report | HTML page, viewer page | The file `report.html`. Use "report viewer" for its interactive interface. |
| offset | lag, delay, shift | The signed difference `reference source frame − comparison source frame`. |
| trim | cut | Frames excluded from the start or end of a source. |
| active picture | crop area, active area | The image rectangle without letterbox or pillarbox bars; set explicitly with `active_rect`. |
| alignment | sync, synchronization | Finding and applying offsets between sources. |
| applied / not applied | accepted / rejected (for offsets) | Whether an offset changes the trims. Matches the terminal's `APPLIED` and `NOT APPLIED`. |
| audio candidate | estimate, guess | An offset found by audio correlation that has not yet been confirmed. |
| VSView alignment panel | VSView plugin, Frame Compare panel, VSPreview | The **Frame Compare Alignment Review** panel inside VSView. "The panel" after first use on a page. |
| user frames | manual frames, specific frames | Frames listed in `analysis.user_frames` or `run --frames`. Quote "Specific frames" only when citing dry-run or wizard text. |
| frame selection | frame picking | Choosing which frames to render. |
| tonemapping | tone mapping, tone-mapping | Converting HDR to an SDR presentation. |
| dry run | preview run, dry-run (as a noun) | The result of `frame-compare run --dry-run`. |
| workspace root | project directory | The directory set by `--root`. |
| Windows portable bundle | portable build, portable ZIP (as the install) | The complete Windows distribution. "Complete portable ZIP" names the download. |
| Single view | overlay mode, overlay view | The viewer's **Single** mode. Its config value is `overlay` (`report.default_mode`). |
| baked overlay | burned-in text, watermark | Text rendered into screenshot pixels (`screenshots.overlay_mode`). |
| source labels | captions, chips | The viewer's on-image source names toggled by **Source labels**. |
| slow.pics | Slowpics, SlowPics | The publishing service. The config table is `[slowpics]`. |

## Command blocks

- Use ` ```bash ` for macOS, Linux, and Docker commands and ` ```powershell ` for
  Windows commands. Use ` ```text ` for directory trees.
- No prompt characters (`$`, `>`, `PS>`). One command per line.
- Show the route prefix the reader needs: `uv run --no-sync frame-compare ...` for a
  native `uv` install and `docker compose run --rm frame-compare-run ...` for Docker.
- Use route tabs only when commands differ by route. Labels and order, exactly:
  `=== "Windows portable"`, `=== "Docker"`, `=== "Native with uv"`,
  `=== "Native with pip"`. The theme links tabs with the same label across pages.
- Placeholders use angle brackets and lower-case words: `<run-name>`, `<tag>`.
- A block that the reader runs in a specific place, or that is long enough that its
  purpose is not obvious from the first line, gets a title:
  ` ```powershell title="PowerShell · in the extracted folder" `. Titles are sentence
  case and name the shell and, when it matters, the folder.

## Terminal output

Frame Compare's own command output is text, never an image. (The Windows installer
capture stays an image because it shows the PowerShell window around the output.)

````markdown
``` { .text .fc-output title="Output · frame-compare run --dry-run" }
Will use
  Workspace: /workspace
```
````

- The title is `Output · ` followed by the exact command.
- Copy the output from a real run with ANSI escape codes and trailing whitespace removed.
  Do not edit it otherwise, except to cut whole lines, which you mark with a line
  containing only `…`.
- Introduce the block with one sentence that tells the reader what to check in it.

## Configuration snippets

- Use ` ```toml `. Show only the tables and keys the section discusses.
- Every snippet must load with the configuration schema (the TOML check in the plan's
  [verification section](../2026-10-12-documentation-site-redesign.md#verification)).
- Use the generic filenames `Reference.mkv`, `Encode-A.mkv`, and `Encode-B.mkv`, or the
  capture filenames `pq10-reference.ts` and `hlg10-comparison.ts` when the text must
  match a figure.
- Put a key's effect in the prose, never in a TOML comment.
- Add `title="config/config.toml"` when the snippet is a complete file to save.

## Callouts

Use callouts sparingly: at most one note, tip, warning, or danger per H2 section, and
never for a required step. Disclosures do not count toward that limit.

| Type | Use it for | Example title |
| --- | --- | --- |
| `!!! note` | Context the reader can skip | "Docker paths are container paths" |
| `!!! tip` | A shortcut or a better way to do the same task | "Reuse the wizard's suggested commands" |
| `!!! warning` | A consequence that produces a wrong or misleading comparison, or loses work | "The hashes must match exactly" |
| `!!! danger` | Data loss or a security exposure | "Keep webhook URLs out of config files" |
| `??? fc-disclosure "Title"` | Optional detail most readers skip, such as a long verification script | "Show the verification commands" |

Titles use sentence case, state the point, and never end with punctuation.

````markdown
!!! warning "The hashes must match exactly"

    If verification fails, delete both files and download them again.
````

## Steps

Use a steps block for a procedure of three to seven steps. Each step starts with a bold
sentence that names the action and ends with a period. Details follow in the same list
item.

````markdown
<div class="fc-steps" markdown>

1.  **Extract the ZIP into a fresh, empty folder.**

2.  **Run the installer from the extracted folder.**

    ```powershell title="PowerShell"
    .\install.cmd
    ```

</div>
````

Indent list-item content by four spaces. Leave a blank line after `<div …>` and before
`</div>`.

## Key blocks

Configuration keys and command options in Reference use key blocks. Unit U3 creates them
with `convert_reference.py`; later edits follow the same shape.

````markdown
#### `sources.match_fps` { #sources.match_fps .fc-key }

Values
:   `"disabled"`, `"assume_reference"`, `"majority"`

Default
:   `"disabled"`

How a common frame rate is chosen when sources disagree.
````

- The anchor equals the key, with `<selector>` written as `selector`
  (`#sources.overrides.selector.trim_start_frames`). Run options use `#run-<option>`
  without leading dashes (`#run-frames`).
- The definition list holds facts only (`Values`, `Default`, `Value`,
  `Saved by --write-config`). The effect is one paragraph after it.
- Link to a key with its anchor: ``[`sources.match_fps`](../reference/configuration.md#sources.match_fps)``.

## Cards

Use a cards block for links to two or more pages, on the home page, section overview
pages, and a page's **Next steps**. Each card is a link to the page and one or two
sentences.

````markdown
<div class="fc-cards" markdown>

- [Your first comparison](first-comparison.md)

    Run the wizard, check the runtime, preview, and compare.

- [Troubleshooting](../guides/troubleshooting.md)

    Problems listed by stage.

</div>
````

The link text is the target page's navigation label. The sentence starts with a verb or
a noun phrase and ends with a period.

## Tables

- Use tables for comparisons and lookups, not narrative.
- Header cells use sentence case. Literal values use code spans. Cells are one sentence.

## Links

- Link to documentation pages with relative `.md` paths. Link text is the target's
  navigation label or a descriptive phrase. Never "here" or "this page".
- Reference repository files outside `docs/` as code spans, never as links. Exceptions:
  `README.md`, `INSTALL-WINDOWS.md`, `CONTRIBUTING.md`, and `SECURITY.md` link to
  `docs/...` paths for GitHub, and pages may link to files by their GitHub URL.
- User pages link to Internals pages only where the reader needs exact behavior. Link to
  a specific section with its anchor when one section answers the question. Overview
  pages may link to whole Internals pages.
- User pages never link to `docs/plans/`, `docs/reviews/`, `docs/prompts/`,
  `docs/TODO.md`, `docs/images/README.md`, or `docs/release-evidence/`.

## UI text, keys, and literals

- Quote UI labels in bold with exact capitalization: **Inspector**, **Report information**.
- Keyboard keys use `<kbd>`: <kbd>I</kbd>, <kbd>Esc</kbd>.
- Commands, options, config keys, values, file and directory names, error codes, and
  literal terminal output use code spans.
- Numbers and units are separated by a space: `100 nits`, `30 s`, `2 MiB`.

## Figures

````html
<figure class="fc-figure">
  <img src="../images/report-grid.webp" alt="Report in Grid view showing the PQ10 reference and HLG10 comparison side by side at frame 1000." width="1600" height="1000" loading="lazy">
  <figcaption>Use Grid to find the source that differs, then compare it in Slider. Footage © EBU, CC BY 4.0.</figcaption>
</figure>
````

- Alt text says what the image shows in one sentence of 160 characters or fewer. Do not
  start with "Image of" or "Screenshot of".
- Captions tell the reader what to notice in one or two sentences, plus the credit
  sentence "Footage © EBU, CC BY 4.0." for EBU media. They do not repeat the alt text.
- Narrow figures (tall panel captures) add `fc-figure--narrow`.
