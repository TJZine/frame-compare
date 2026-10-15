# Contributing to Frame Compare

Thank you for improving Frame Compare. This guide covers contributor setup and pull
request mechanics. The [repository profile](.agents/project.md) owns local contracts
and command routes. Shared skills own agent methodology; the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md) preserves complete specialist
verification, platform, release, and durable-plan procedures.

## Prerequisites

| Tool | Requirement | Purpose |
| --- | --- | --- |
| Python | 3.13 or newer | Application and test runtime |
| `uv` | Repository-selected compatible version | Locked dependency and command execution |
| Git | Recent release | Version control |
| Docker | Optional for ordinary work; required for Docker/runtime changes | Integration proof |
| PowerShell on Windows | Required for portable packaging changes | Windows build, install, update, and verification paths |

## Development setup

Clone the repository and install the canonical frozen contributor environment:

```bash
git clone https://github.com/TJZine/frame-compare.git
cd frame-compare
uv sync --group dev --extra vsview --frozen
```

A pip-only editable installation can run the application, but it does not reproduce the
complete contributor or CI toolchain.

Use the repository profile and relevant runbook recipe to establish the capabilities
needed for the task. Do not run unrelated gates merely to begin an edit.

### Optional Codanna setup

Codanna users should generate checkout-local settings before indexing. The generated
file is ignored because Codanna requires canonical absolute roots:

```bash
python3 scripts/bootstrap_codanna.py
codanna config
codanna index
```

Re-run the bootstrap after moving the checkout. Project-wide defaults remain in the
tracked `.codanna/settings.toml.in` template; never commit the rendered
`.codanna/settings.toml`.

## Branch and pull request workflow

1. Start from the base branch named in the issue, handoff, or maintainer request.
   Otherwise target `main`.
2. Create a focused branch:

   ```bash
   git switch -c feat/your-change
   ```

3. Keep the change bounded to one coherent outcome.
4. Select meaningful evidence for the changed behavior and update affected product
   documentation. Reuse sufficient proof; do not add tests merely to satisfy a step.
5. Run applicable verification from the repository profile and specialist runbook.
6. Open a pull request against the intended integration branch.

Do not assume `main`, `staging`, `cleanup`, or a version-development branch is the
correct target when the task names another base explicitly.

## Pull request titles

Use Conventional Commit format because the squash title becomes release history:

| Type | Use |
| --- | --- |
| `feat:` | New user-visible behavior |
| `fix:` | Bug fix |
| `docs:` | Documentation-only change |
| `refactor:` | Internal restructuring without a behavior change |
| `perf:` | Performance improvement |
| `test:` | Test-only change |
| `build:` | Build system or dependency change |
| `ci:` | Workflow change |
| `chore:` | Maintenance outside production and test behavior |
| `revert:` | Revert of an earlier change |

Scopes are optional:

```text
feat(cli): add structured history filtering
fix(render): preserve range metadata during tonemapping
docs: restructure the user guide
```

## Code style

### Python

- Use Python 3.13+ syntax and complete type annotations.
- Prefer `pathlib.Path` for filesystem paths.
- Keep public behavior at explicit owner boundaries.
- Add docstrings to public functions.
- Preserve the repository’s 100-character formatting target.

### Formatting and linting

```bash
uv run --no-sync ruff check .
uv run --no-sync ruff check --fix .
uv run --no-sync ruff format .
```

### Type checking

```bash
uv run --no-sync pyright --warnings
```

Pyright checks both `src/` and `tests/` under their configured typing policies.

## Tests and verification

Test markers include:

| Marker | Meaning |
| --- | --- |
| `unit` | Fast isolated coverage |
| `integration` | Module interaction |
| `e2e` | End-to-end CLI behavior in `tests/e2e/`; includes the runtime-free CLI tier and media tier |
| `vs_required` | Media-tier E2E scenarios that require a VapourSynth runtime |
| `slow` | Long-running proof |
| `network` | Requires external network access |
| `tier_a` | Contract/security tests without VS or network |

Examples:

```bash
uv run --no-sync pytest -q -n4 --dist loadgroup
uv run --no-sync pytest -m unit
uv run --no-sync pytest -m "not vs_required"
uv run --no-sync pytest -q tests/e2e/ -m "e2e and not vs_required"  # CLI tier
bash tools/verify_docker_integration.sh --pytest-path tests/e2e  # focused media scenarios
uv run --no-sync pytest --cov=src/frame_compare --cov-report=term-missing
```

The CLI tier runs without a media runtime. The media tier is Docker-only: the gate
sets `FRAME_COMPARE_E2E_REQUIRE_MEDIA=1` and `FRAME_COMPARE_E2E_ARTIFACTS` for the
pinned media runtime and its inspectable scenario artifacts.

The full Docker gate is `bash tools/verify_docker_integration.sh`: it runs E2E,
integration and VS tests with ten workers and `--dist loadgroup`, plus runtime and
production-image proofs. It excludes the long-running alignment resource module;
see the runbook's separate resource command when streaming alignment memory or
collector cleanup changes. Docker CI runs that proof separately. The focused media command above is for development and
scenario proof; use the full gate for the runbook's runtime, dependency and media
boundary triggers. Images build by default; rebuild after `docker-test` dependency
or `uv.lock` changes before using the new plugin. Use `--no-build` only with
known-current images.

The verifier sets `FRAME_COMPARE_TEST_MEDIA_CACHE` to
`/workspace/generated/test-media-cache` (host `generated/test-media-cache`) for u4
media only. Entries use `<cache>/<generator>/<key>/`, keyed by exact
`tests/integration/alignment_u4_media_recipes.py` source and complete `ffmpeg -version`
output. Assertion-only and store-only edits retain the cache. Recipes generate on
demand, publishing each file with temporary file + atomic replace; the complete gate
passes `FRAME_COMPARE_U4_MEDIA_FULL=1` to generate all 37 files. Focused
`--pytest-path` runs remain demand-driven. Temporary symlinks keep indexes outside the
cache; unset the cache variable for lazy temporary generation. Worker stats are
written as JSON under `FRAME_COMPARE_E2E_ARTIFACTS`; measurements live in
`tests/integration/NOTES-u4-media-preparation.md`. Run the
verifier one at a time from a checkout because cache pruning cannot overlap.
CI starts cold, adds no media cache, and retains Docker `--no-cache`.

New tests must be parallel-safe: use `tmp_path` and `monkeypatch`, avoid fixed paths
or ports, and use `xdist_group` only with a stated concrete reason. The local full
native count is four; focused runs may stay serial. Native CI uses
`-n auto --dist loadgroup`; Windows portable CI stays serial.

These examples do not replace the runbook. Changes to CLI/config contracts, runtime
owners, Docker, Windows portable packaging, release workflows, or architectural
boundaries require their documented complete verification paths.

## Documentation development

Authored documentation lives under `docs/`. `zensical.toml` owns site navigation and
theme features, and `overrides/` owns the theme templates. Generated site output belongs
in the ignored `site/` directory.

Install the locked documentation environment and run a strict build:

```bash
uv sync --only-group docs --locked
uv run --no-sync zensical build --clean --strict
```

Preview locally:

```bash
uv run --no-sync zensical serve
```

A docs-only sync replaces the ordinary contributor environment. Restore both groups
before continuing application checks:

```bash
uv sync --group dev --group docs --extra vsview --locked
```

### Documentation style

#### Scope

- **User pages:** `README.md`, `INSTALL-WINDOWS.md`, `docs/index.md`,
  `docs/getting-started/**`, `docs/guides/**`, `docs/reference/**`,
  `docs/internals/index.md`. Every rule applies.
- **Authority pages:** `docs/current-cli-contract.md`, `docs/current-architecture.md`,
  `docs/ENGINEERING_RUNBOOK.md`, `docs/supported-media-runtime.md`,
  `docs/media-runtime-windows-validation.md`, `docs/analysis-performance-validation.md`,
  `docs/analysis-benchmark-history.md`, `docs/DECISIONS.md`, `SECURITY.md`, and
  `CHANGELOG.md`. Only the terminology table, command blocks, and link rules apply to
  text you add. Their headings stay as they are, because guard tests, agent
  instructions, and release tooling match them.

- Keep task guides separate from maintainer contracts.
- Update the authoritative contract in the same change when public behavior changes.
- Redact private paths, source names, and secrets; prefer generic filenames and a clean
  capture workspace over redaction.

#### Voice

The reader is a technically capable person who runs command-line tools and compares
video encodes. They do not know Frame Compare's internals and do not want a pitch. Write
like the reference documentation of a mature command-line tool: plain, specific, and
calm.

**Rules**

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
    "schema 3") do not appear in user pages unless the reader must act on them or a test
    requires the literal.

**Patterns that are not allowed**

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

**Examples**

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

#### Headings

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

#### Page structure

Every user page has, in order:

1. Front matter with a `description:` of one sentence, 160 characters or fewer, written
   to the voice rules. Keep it to one sentence of 160 characters or fewer.
2. The H1.
3. A lead paragraph of one to three sentences that says what the page helps the reader
   do. The theme styles the first paragraph after the H1 as the lead; do not add a class.
4. Body sections.
5. Optionally a **Next steps** H2 with a cards block of two or three pages, when the page
   has natural follow-on pages.

#### Terminology

| Preferred term | Do not use | Definition |
| --- | --- | --- |
| source | clip (in prose), video, input file | One input video that takes part in a comparison. "Clip" appears only when quoting UI text ("3 clips", **Clips** tab) or the file `clip_probe.toml`. |
| reference | base, master, primary | The source whose frame numbers define the comparison and which appears first. |
| comparison | target, encode (as a role name) | Every source other than the reference. |
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

#### Command blocks

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

#### Terminal output

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

#### Configuration snippets

- Use ` ```toml `. Show only the tables and keys the section discusses.
- Every snippet must load with the configuration schema: `ConfigSchema(**tomllib.loads(snippet))` must succeed.
- Use the generic filenames `Reference.mkv`, `Encode-A.mkv`, and `Encode-B.mkv`, or the
  capture filenames `pq10-reference.ts` and `hlg10-comparison.ts` when the text must
  match a figure.
- Put a key's effect in the prose, never in a TOML comment.
- Add `title="config/config.toml"` when the snippet is a complete file to save.

#### Callouts

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

#### Steps

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

#### Key blocks

Configuration keys and command options in Reference use key blocks. Use this shape for
every key and option.

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

#### Cards

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

#### Tables

- Use tables for comparisons and lookups, not narrative.
- Header cells use sentence case. Literal values use code spans. Cells are one sentence.

#### Links

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

#### UI text, keys, and literals

- Quote UI labels in bold with exact capitalization: **Inspector**, **Report information**.
- Keyboard keys use `<kbd>`: <kbd>I</kbd>, <kbd>Esc</kbd>.
- Commands, options, config keys, values, file and directory names, error codes, and
  literal terminal output use code spans.
- Numbers and units are separated by a space: `100 nits`, `30 s`, `2 MiB`.

#### Figures

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

## Architecture and public contracts

Consult the relevant authority before changing a boundary:

- [Current Architecture](docs/current-architecture.md)
- [CLI Behavioral Contract](docs/current-cli-contract.md)
- [Supported Media Runtime](docs/supported-media-runtime.md)
- [Import contracts](importlinter.ini)

Do not create a second architecture summary, runbook, or current CLI contract.

## Contribution licensing

Submitted contributions are licensed under `GPL-3.0-only`. Contributors affirm that
they have the right to submit the work under those terms.

## Releases

Release Please owns reviewed version and changelog pull requests after project
initialization. The guarded Windows release workflow owns exact-commit publication,
mandatory assets, checksums, update signing, and final release creation.

Maintainer procedure and current branch policy live exclusively in the
[Engineering Runbook](docs/ENGINEERING_RUNBOOK.md). Historical initial-release steps
belong in release evidence, not this contributor onboarding guide.
