---
search:
  exclude: true
---

Status: Active
Scope: Design, structure, theme, and voice redesign of the documentation site
Owner: Maintainer; planned by a Claude session on 2026-10-12; implemented by a Codex
orchestrator with `worker` and `worker_luna` chats

# Documentation site redesign

Base: branch `v0.7.0` at `c537f94db4deaa5834c9d6a5fb31635b57860a0a`. Zensical
`0.0.69` (locked in `uv.lock`). This plan changes documentation, the site theme and
configuration, the docs workflow, the guard tests that read moved pages, and removes the
generated API reference. It changes no product code.

Implementers follow this plan and its assets exactly. Any ambiguity, any fact they
cannot verify, and any decision the plan does not make is a stop: report `blocked`.

## Assets

- [Style guide](2026-10-12-documentation-site-redesign-assets/style-guide.md): voice,
  terminology, and authoring rules for every component.
- [Theme specification](2026-10-12-documentation-site-redesign-assets/theme.md): the
  complete `zensical.toml`, templates, stylesheets, script, brand SVGs, and fonts.
- [Asset specification](2026-10-12-documentation-site-redesign-assets/assets.md): home
  images, the offset diagram, the social card, icons, and the image record.
- [Page specifications](2026-10-12-documentation-site-redesign-assets/pages.md): what
  changes on each page, guard strings, and page descriptions.
- [Repository changes](2026-10-12-documentation-site-redesign-assets/repository-changes.md):
  moves, the API generator removal, tests, workflow, and contributor instructions.
- [Scripts](2026-10-12-documentation-site-redesign-assets/scripts.md): one-time tools
  for relinking, reference conversion, troubleshooting conversion, and asset checks.

Design mockups the maintainer approved:
[Frame Compare docs directions](https://claude.ai/artifact/DxwGrYzPHK9y5GKyBVwczd)
(private canvas; direction A). The scratch prototype that proved the theme is at
`.tmp/docs-design-2026-10-12/proto/` (gitignored).

## Approved decisions (maintainer, 2026-10-12)

1. **Visual direction A, "Screening room".** Charcoal header, tabs, hero, and code;
   warm light pages in light mode and charcoal pages in dark mode; brass accents. The
   site follows the OS color scheme and keeps the manual toggle.
2. **Home hero is a live before/after slider** between the PQ10 reference and HLG10
   comparison at frame 1000, with keyboard support and a static 50/50 fallback.
3. **Reference keys use stacked key blocks**: one block per key with an anchor, its
   values, its default, and its effect.
4. **Source color coding:** brass marks the reference and light blue marks the
   comparison wherever both appear. Every current use is on a dark surface (the hero
   labels and the offset diagram). The pair differs in hue and lightness.
5. **Plain documentation voice.** No AI-styled wording: no slogans, buzzwords,
   eyebrow-and-tagline headings, rhetorical questions, or stacked negations. The home H1
   is "Frame Compare"; the earlier headline "Compare sources, not guesswork" is dropped.
6. **Internals tab** holds the maintainer documents with an overview page. The authority
   documents keep their file paths, because `AGENTS.md`, `.agents/project.md`, and guard
   tests name them. The generated Python API page, its generator, its CI step, and its
   tests are deleted.
7. **Terminal output is text**, in titled output blocks. The two terminal SVGs are
   deleted. This reverses decision 4 of the 2026-10-08 refresh for terminal captures.
8. **Consistent URLs with redirects.** `windows-portable.md` and
   `guides/first-comparison.md` move into `getting-started/`; `api.md` redirects to the
   Internals overview. Zensical's native redirects plugin keeps the old URLs working.
9. **Windows install redesign is documentation only**: numbered steps, a "Download the
   latest release" button, and the verification scripts in a collapsible block. A
   release-side verify script is out of scope.
10. **Self-hosted fonts**: Geist and Geist Mono (SIL Open Font License), pinned by
    version and SHA-256, served from the site. No third-party font requests.

Planner decisions within that approval, each tested in the prototype:

- Section overview pages ("Overview" under Guides, Reference, and Internals) instead of
  `navigation.indexes`, so every page appears in the sidebar.
- Release notes are an external navigation link to `CHANGELOG.md` on GitHub, not an
  included page, so release automation never has to keep site markers in the changelog.
- Social preview cards use one static image through `overrides/main.html`; Zensical's
  social-card plugin is not available yet ("in progress" in Zensical 0.0.69).
- The Mermaid flowchart on How Frame Compare works becomes a six-step pipeline strip, and
  the Mermaid fence configuration is removed because no page uses it.
- A banned-word style test guards the user pages (U9), because most future
  documentation edits will be written by agents.
- Voice-pass units use the `worker` preset, not `worker_luna`, because prose quality is
  the deliverable the maintainer cares most about.

## Audit

Evidence (2026-10-12): the live site and a local strict build of the base, inspected in
the built-in browser at 375, 390, 1440, and 1920 px in both color schemes; per-page
metrics from the built HTML; an in-browser scan of all 21 user pages for wrapped table
code at 1440 and 390 px; the search index; Zensical's installed templates and
configuration code. Severity: **P0** broken or illegible, **P1** materially
unprofessional or misleading, **P2** polish.

| ID | Sev | Finding | Evidence | Action (unit) |
| --- | --- | --- | --- | --- |
| L-01 | P0 | Article column 688 px at 1440 and 1920 px | Grid capped at 61rem | Grid 80rem, prose measure 42rem (U1) |
| L-02 | P0 | Table code split mid-token | 124 wrapped table code spans on 12 pages at 1440 px; 232 at 390 px | Key blocks and nowrap table code (U1, U3) |
| L-03 | P0 | Configuration tables clip their last column on phones | 390 px screenshots | Key blocks (U3) |
| L-04 | P0 | Home reserves an empty sidebar; hero off-centre | 1440 px screenshot | Home template, hidden sidebars (U1, U4) |
| L-05 | P0 | Terminal captures render at about 5 px | `terminal-run-complete.svg` natural 300 × 65 shown at 513 × 112 | Output blocks (U5) |
| L-06 | P1 | Home command grid wraps `run --dry-run` | 1440 px screenshot | Tabbed command block (U4) |
| L-07 | P1 | Long code lines overflow on phones | 13 overflowing blocks at 390 px | Titled, split blocks; scroll accepted for PowerShell (U5) |
| B-01 | P1 | Default book logo and favicon | Header markup | Brand mark and icons (U1, U2) |
| B-02 | P1 | Footer only "Made with Zensical" | Footer text | Footer partial with links and credits (U1) |
| B-03 | P1 | Header widget shows "☆0 ⑂0" | Header | `source.html` override (U1) |
| B-04 | P1 | No link-preview metadata | No `og:` or `twitter:` tags | `main.html` meta and social card (U1, U2) |
| B-05 | P1 | No page has its own description | All 29 pages use the site description | Front matter descriptions (U4–U8) |
| B-06 | P2 | Invalid `theme-color` value `#ffffff0007` | DOM | Charcoal header; the theme then derives a valid value (prototype: `#1b1b1a`) (U1) |
| B-07 | P1 | System font only | Computed styles | Self-hosted Geist (U1) |
| B-08 | P2 | Monospace capitals overused | Home | One kicker only (U1, U4) |
| B-09 | P2 | Home title "Home - Frame Compare" | `<title>` | "Documentation - Frame Compare"; link previews use "Frame Compare documentation" (U1, U4) |
| C-01 | P1 | Six callouts across 21 user pages; warnings in prose | Built HTML | Themed callouts and rules (U1, U5–U7) |
| C-02 | P1 | No steps component | Windows, Choose an installation | Steps blocks on both pages (U1, U5) |
| C-03 | P1 | Code blocks lack titles; setup and commands mixed | Docker page | Code titles; split blocks (U1, U5) |
| C-04 | P0 | Reference keys in four-column tables without anchors | Configuration, Commands | Key blocks (U3) |
| C-05 | P1 | Mermaid flowchart about 1,000 px tall | How it works | Pipeline strip (U6) |
| C-06 | P1 | Plain "Continue with" lists | Guides | Next-steps cards (U5) |
| C-07 | P1 | Troubleshooting is one table without anchors | Page | Entries with anchors and an error-code section (U7) |
| C-08 | P2 | Tables at about 12 px with heavy borders | Screenshots | Table restyle (U1) |
| C-09 | P1 | Route applicability only in prose | First comparison | Linked route tabs (U4, U5) |
| C-11 | P1 | Bare 404 page | `/this-does-not-exist/` | `404.html` override (U1) |
| C-12 | P2 | Section tabs open the first child page | Navigation | Overview pages (U4) |
| H-01 | P1 | Filmstrip of four near-identical frames | Home | Live slider and view tabs (U1, U4) |
| H-02 | P1 | No capability section | Home | Four features with visuals (U4) |
| H-03 | P2 | Credit paragraph between hero and routes | Home | Credit in hero caption and footer (U1) |
| H-04 | P2 | "Find an answer" plain list | Home | Reference cards (U4) |
| H-05 | P2 | Route cards duplicated on Choose an installation | Both pages | Same cards block (U5) |
| I-01 | P1 | Maintainer documents equal to user docs in navigation | Navigation | Internals tab (U1, U4) |
| I-02 | P1 | CLI contract (18,615 words) in user Reference; dominates search | Metrics; search "exit code" | Moved to Internals; manual Contents removed (U1, U8) |
| I-03 | P1 | Commands → Exit codes is a link only | `reference/commands.md:105-107` | Table inline (U8) |
| I-04 | P1 | Supported media runtime is maintainer detail in Reference | Metrics | Requirements page; record moves to Internals (U4) |
| I-05 | P1 | Thin generated API page with a "do not edit" note | `/api/` | Removed with its generator (U3) |
| I-06 | P2 | Inconsistent URLs | Navigation | Moves and redirects (U1, U3) |
| I-07 | P2 | Title Case H1s on Internals pages | Metrics | Out of scope: guard tests and agent files match them |
| I-08 | P2 | No release notes in the site | Navigation | External link to `CHANGELOG.md` (U1) |
| I-09 | P2 | No glossary | Navigation | Glossary page (U4) |
| I-10 | P2 | Contract "Contents" list in search results | Search | Removed (U8) |
| I-11 | P2 | Home links exit codes to the contract | `docs/index.md` | Links to Commands (U4) |
| W-01 | P1 | Windows page leads with internals; 25-line script before `install.cmd` | Page | Restructure (U5) |
| W-02 | P1 | First comparison repeats two paragraphs | Page | Delete repeats (U5) |
| W-03 | P1 | Defensive negation (Windows 20, Reports 16, Troubleshooting 13) | Counts | Voice pass (U5–U8) |
| W-04 | P1 | Paragraphs up to 152 words | Metrics | 70-word limit (U5–U8) |
| W-05 | P1 | 13 of 19 user pages have no visual | Metrics | Offset diagram, pipeline strip, home features (U2, U4, U6) |
| W-06 | P2 | Report views as one-sentence H3s | Reports | Views table (U7) |
| W-07 | P2 | Leads explain mechanism, not outcome | Most pages | Lead rule and rewrites (U5–U8) |
| W-09 | P1 | Windows update section narrates updater internals | Page | Disclosure block (U5) |

Verified fine and unchanged: skip link, `lang`, heading order, contrast of the current
palette, no page-level horizontal scroll, WebP image weights, search highlighting, and
the strict build (no issues on the base). Not verified on the base: screen-reader
output and print styles.

## Navigation

The complete `zensical.toml`, including the navigation and redirects, is in the
[theme specification](2026-10-12-documentation-site-redesign-assets/theme.md#zensicaltoml).
Tabs: Home, Get started, Guides, Reference, Internals. Reference ends with an external
"Release notes" link to `CHANGELOG.md`.

## Units

Every unit:

- reads `AGENTS.md`, `.agents/project.md`, this plan's Approved decisions, the
  [style guide](2026-10-12-documentation-site-redesign-assets/style-guide.md), and its own
  specification sections;
- edits only its owned files;
- runs no Git command that changes the index, history, or branch (moves and deletes use
  plain `mv` and `rm`; the orchestrator stages them);
- never commits and never chooses; reports `blocked` with the question and evidence for
  any ambiguity, unverifiable fact, failed check, or missing input;
- reports the files changed, the checks run with results, and anything `blocked`.

Units that write prose follow the **voice-pass procedure** in the
[page specifications](2026-10-12-documentation-site-redesign-assets/pages.md#how-to-edit-an-existing-page).

### Waves

| Wave | Units | Runs after |
| --- | --- | --- |
| A1 | U1, U3 (parallel) | Base |
| A2 | U4 | U3 reports done (U3's relink touches `docs/index.md`, which U4 replaces) |
| B | U2, U5, U6, U7, U8 (parallel) | Wave A integrated and reviewed |
| C | U9 | Wave B integrated and reviewed |

### U1 — Theme

- **Preset:** `worker_luna`.
- **Owns:** `zensical.toml`, `overrides/**`, `docs/stylesheets/extra.css`,
  `docs/stylesheets/fonts.css`, `docs/javascripts/compare-slider.js`,
  `docs/assets/brand/logo.svg`, `docs/assets/brand/favicon.svg`, `docs/assets/fonts/**`.
- **Inputs:** the [theme specification](2026-10-12-documentation-site-redesign-assets/theme.md).
- **Acceptance:** every file equals its specification block byte-for-byte, plus one
  final newline (the orchestrator extracts the blocks and diffs them); the four font files match their
  SHA-256; `zensical.toml` parses with `tomllib`.
- **Stops:** a font download fails or a hash differs.
- The strict build is not expected to pass until U3 and U4 land (the navigation names
  their pages).

### U2 — Images, social card, and icons

- **Preset:** `worker` (runs Chrome and image tooling; environment diagnosis may be
  needed). It may diagnose an environmental failure and rerun the same command; it
  changes no specified script, size, or text and installs nothing.
- **Owns:** `docs/images/home-*.webp`, `docs/images/diagram-audio-offset.svg`,
  `docs/assets/brand/social-card.jpg`, `docs/assets/brand/favicon-32.png`,
  `docs/assets/brand/apple-touch-icon.png`, `docs/images/README.md`.
- **Inputs:** the [asset specification](2026-10-12-documentation-site-redesign-assets/assets.md).
- **Acceptance:** all source hashes match; every output exists at its stated size and
  under its size limit; the diagram's SHA-256 equals the recorded value; the social card
  shows the elements the specification lists, in Geist, with no fallback glyphs; the
  image README edits are made exactly; privacy review recorded.
- **Stops:** a missing or mismatched source; a rendering that shows a fallback font or
  a missing image.

### U3 — Structure, reference conversion, and API removal

- **Preset:** `worker_luna`.
- **Owns:** the moves and deletions in
  [repository changes](2026-10-12-documentation-site-redesign-assets/repository-changes.md#page-moves-and-deletions-unit-u3);
  every file `relink.py` rewrites; `docs/reference/configuration.md` and
  `docs/reference/commands.md` (conversion only); the API generator files and tests;
  `.github/workflows/docs.yml`; `tests/workflows/test_docs_workflow.py`;
  `tests/test_cli_contract_docs.py` (wave A);
  `tests/windows_portable/test_windows_portable_docs.py`; `.agents/project.md`;
  `docs/ENGINEERING_RUNBOOK.md`; `CONTRIBUTING.md` (the U3 edits only);
  `docs/current-architecture.md` and `docs/media-runtime-windows-validation.md` (the two
  API-generator deletions only).
- **Inputs:** repository changes (U3 sections); [scripts](2026-10-12-documentation-site-redesign-assets/scripts.md)
  (`relink.py`, `convert_reference.py`).
- **Acceptance:** `relink.py` exits 0; `convert_reference.py` prints `converted`;
  `docs/reference/configuration.md` holds 84 `.fc-key` headings and `commands.md` holds
  26; `uv run --no-sync pytest -q tests/test_cli_contract_docs.py tests/windows_portable/test_windows_portable_docs.py tests/workflows/test_docs_workflow.py`
  passes; `uv run --no-sync ruff check`, `uv run --no-sync ruff format --check`, and
  `uv run --no-sync pyright` pass on the three edited test files; the workflow YAML parses;
  `rg -n --hidden "api_docs|generate_api_docs|docs/api\.md" --glob '!.git/**' --glob '!docs/plans/**' --glob '!docs/reviews/**' --glob '!docs/prompts/**' --glob '!docs/archive/**' --glob '!tests/fixtures/**'`
  returns nothing (it respects `.gitignore`, so `.tmp/`, `site/`, and `.venv/` are
  skipped).
- **Stops:** a script exits non-zero; a converted key count differs; a test fails for a
  reason other than a page that a later unit owns.

### U4 — New pages and the home page

- **Preset:** `worker_luna`.
- **Owns:** `docs/index.md`, `docs/guides/index.md`, `docs/reference/index.md`,
  `docs/internals/index.md`, `docs/reference/requirements.md`,
  `docs/reference/glossary.md`.
- **Inputs:** [page specifications](2026-10-12-documentation-site-redesign-assets/pages.md#unit-u4-new-and-replaced-pages).
- **Acceptance:** each file equals its specification block, ending with one newline;
  the strict build passes after wave A integration.
- **Stops:** a stated fact does not match its cited page.

### U5 — Get started pages and the repository front door

- **Preset:** `worker`.
- **Owns:** all six files in `docs/getting-started/`, `README.md`, `INSTALL-WINDOWS.md`,
  `docs/images/terminal-dry-run.svg` and `docs/images/terminal-run-complete.svg`
  (delete after replacing their figures).
- **Inputs:** [page specifications](2026-10-12-documentation-site-redesign-assets/pages.md#unit-u5-get-started-pages-and-repository-front-door).
- **Acceptance:** every structural change in the specification is present; every guard
  string remains; `uv run --no-sync pytest -q tests/windows_portable/test_windows_portable_docs.py tests/workflows/test_onboarding_docs.py`
  passes; the TOML check passes on edited pages; no paragraph exceeds 70 words (the
  orchestrator's paragraph check).
- **Stops:** a guard string cannot be kept; a capture `.ansi` file is missing.

### U6 — Guides, part one

- **Preset:** `worker`.
- **Owns:** `docs/guides/how-it-works.md`, `sources-and-labels.md`, `analysis-modes.md`,
  `audio-alignment.md`, `vsview-review.md`.
- **Inputs:** [page specifications](2026-10-12-documentation-site-redesign-assets/pages.md#unit-u6-guides-part-one).
- **Acceptance:** structural changes present; guard strings in `vsview-review.md`
  remain; pipeline-strip anchors resolve in the built site; TOML check passes.
- **Stops:** a rewrite would drop a fact that another page links to.

### U7 — Guides, part two

- **Preset:** `worker`.
- **Owns:** `docs/guides/hdr-tonemapping.md`, `reports-and-overlays.md`,
  `presets-history-generated-data.md`, `publishing-and-webhooks.md`, `troubleshooting.md`.
- **Inputs:** [page specifications](2026-10-12-documentation-site-redesign-assets/pages.md#unit-u7-guides-part-two);
  `convert_troubleshooting.py`.
- **Acceptance:** structural changes present; 20 troubleshooting entries; TOML check
  passes.
- **Stops:** the converter exits non-zero; a described UI control is not in
  `src/frame_compare/services/report/renderer.py`.

### U8 — Reference text and the contract contents list

- **Preset:** `worker`.
- **Owns:** `docs/reference/commands.md`, `docs/reference/configuration.md`,
  `docs/reference/output-layout.md` (text edits after U3's conversion);
  `docs/current-cli-contract.md` (Contents deletion only);
  `tests/test_cli_contract_docs.py` (wave B: the exit-code sync test only).
- **Inputs:** [page specifications](2026-10-12-documentation-site-redesign-assets/pages.md#unit-u8-reference-pages-and-the-contracts-contents-list).
- **Acceptance:** the exit-code table matches the contract's rows (the new sync test
  passes); key blocks unchanged except effect-sentence style fixes; `ruff check`,
  `ruff format --check`, and pyright pass on `tests/test_cli_contract_docs.py`;
  `uv run --no-sync pytest -q tests/test_cli_contract_docs.py tests/vs/test_runtime_contract.py`
  passes.
- **Stops:** the contract's exit-code section differs from the eight rows the
  specification expects.

### U9 — Contributor style rules and the style test

- **Preset:** `worker_luna`.
- **Owns:** `CONTRIBUTING.md` (Documentation style section),
  `tests/workflows/test_docs_style.py` (new).
- **Inputs:** [repository changes](2026-10-12-documentation-site-redesign-assets/repository-changes.md#contributing-md);
  the style guide.
- **Acceptance:** `uv run --no-sync pytest -q tests/workflows/test_docs_style.py` passes on
  the integrated pages; `ruff check`, `ruff format --check`, and pyright pass on the new
  test.
- **Stops:** the test finds a word in a page another unit owns (route it back to the
  orchestrator; do not edit the page or the word list).

## Verification

### Per unit

Listed under each unit. Every unit also runs `git diff --check` on its edited files,
checks its new files for trailing whitespace (`rg -n "[ \t]+$" <new files>` returns
nothing), and runs the TOML check below on each page it edits that contains
` ```toml `. The orchestrator runs `git diff --cached --check` after staging each unit.

TOML check, from the repository root. Replace `PAGES` with the space-separated page
paths:

```bash
mkdir -p .tmp/toml-check
uv run --no-sync python - PAGES <<'PY'
import os, re, sys, tomllib
from pathlib import Path
from frame_compare.config.schema import ConfigSchema
pages = [Path(p).resolve() for p in sys.argv[1:]]
os.chdir(".tmp/toml-check")
for page in pages:
    lines = page.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)```toml\b.*$", lines[i])
        if m:
            indent, start, body = m.group(1), i + 1, []
            i += 1
            while i < len(lines) and not re.match(r"^\s*```\s*$", lines[i]):
                body.append(lines[i][len(indent):])
                i += 1
            ConfigSchema(**tomllib.loads("\n".join(body)))
            print("OK", page.name, start)
        i += 1
PY
```

### Orchestrator, once per wave, serially

1. `uv run --no-sync zensical build --clean --strict` (from wave A2 on).
2. The docs workflow's search-scope check (the Python block in `.github/workflows/docs.yml`).
3. `python3 -I .tmp/docs-site-redesign/check_assets.py docs`. In wave A the only
   expected misses are U2's home images and diagram; from wave B on it must exit 0.
   It does not read templates, so also confirm the files the theme templates reference
   exist: `ls docs/images/home-frame-pq10.webp docs/images/home-frame-hlg10.webp docs/assets/brand/social-card.jpg docs/assets/brand/favicon-32.png docs/assets/brand/apple-touch-icon.png docs/assets/fonts/geist-latin-wght-normal.woff2`
   (from wave B on). Links in the repository-root pages are outside the build, so also
   confirm `rg -n "docs/windows-portable\.md|docs/guides/first-comparison\.md|docs/api\.md" README.md INSTALL-WINDOWS.md SECURITY.md`
   returns nothing from wave B on, and the same command with `CONTRIBUTING.md` added
   returns nothing in wave C (U9 replaces the style-section line that names the old
   path).
4. `uv run --no-sync pytest -q tests/test_cli_contract_docs.py tests/windows_portable/test_windows_portable_docs.py tests/workflows/test_docs_workflow.py tests/workflows/test_onboarding_docs.py tests/windows_portable/test_windows_portable_build_scripts.py tests/vs/test_runtime_contract.py`,
   plus `tests/workflows/test_docs_style.py` in wave C.
5. Redirects: `site/windows-portable/index.html`, `site/guides/first-comparison/index.html`,
   and `site/api/index.html` each contain a refresh to `getting-started/windows-portable/`,
   `getting-started/first-comparison/`, and `internals/` respectively.
6. Paragraph length, user pages only. It prints prose paragraphs over 70 words, ignoring
   code blocks at any indentation, tables, lists, headings, and HTML. None are expected
   after wave B:

```bash
uv run --no-sync python - <<'PY'
import re
from pathlib import Path
pages = [Path("README.md"), Path("docs/index.md")]
for d in ("docs/getting-started", "docs/guides", "docs/reference", "docs/internals"):
    pages += sorted(Path(d).glob("*.md"))
FENCE = re.compile(r"^[ \t]*(`{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.M | re.S)
for page in pages:
    text = FENCE.sub("", page.read_text(encoding="utf-8"))
    for block in re.split(r"\n[ \t]*\n", text):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines or re.match(r"([#|<\-*>!?=:]|\d+\.)", lines[0]):
            continue
        words = len(" ".join(lines).split())
        if words > 70:
            print(page, words, lines[0][:70])
PY
```

7. Rendered visual QA (below), from wave B on.

The docs group must already be installed; if `zensical` is missing, stop and ask the
maintainer before any `uv sync`.

### Rendered visual QA

Serve the built site (`uv run --no-sync zensical serve`) and check each row at
1440 × 900 and 390 × 844, in light and in dark (clear site storage between schemes so the
OS preference applies). The prototype passed every row on 2026-10-12.

| Page | Check | Expected |
| --- | --- | --- |
| Any | Header | Charcoal bar in both schemes; split-frame logo; tabs Home, Get started, Guides, Reference, Internals; "GitHub" without counts |
| Any | Fonts | Geist text and Geist Mono code; no request to `fonts.googleapis.com` (network panel) |
| Any | Footer | Links (GitHub, Release notes, Releases, Security, Contributing, Internals) and the copyright and footage line, readable on charcoal |
| Home | Hero | H1 "Frame Compare", lead, Install and Your first comparison buttons, slider with brass PQ10 label left and blue HLG10 label right; at 390 px the labels read "PQ10 · Reference" and "HLG10 · Comparison" without overlap |
| Home | Slider | Dragging moves the divider; Tab focuses it with a brass ring; arrow keys move it; with JavaScript disabled it shows a 50/50 split |
| Home | Sections | Report views tabs swap four captures; four feature cards (frame strip in one row of six at 1440 px, three per row at 390 px; offset diagram; HDR crop; run-folder tree); Install cards; command tabs; Reference cards |
| Get started › Windows portable | Install | Download button; five numbered steps; collapsed "Show the verification commands" opens to two titled PowerShell blocks with copy buttons; warning callout in brass tones |
| Reference › Configuration | Key blocks | Key name in Geist Mono, Values and Default aligned beneath, effect sentence; no key or value split mid-word at 1440 px; at 390 px names wrap only at dots |
| Guides › How it works | Pipeline | Six numbered tiles in one row at 1440 px, two per row at 390 px; each opens its section |
| Get started › Your first comparison | Output | Two output blocks titled `Output · …`, text selectable, the panel box drawing aligned |
| Guides › Troubleshooting | Entries | Each problem is an H3 in the page's table of contents |
| 404 | Page | "Page not found" with four links whose `href` starts with `/frame-compare/`; after deployment, each opens the right page |
| Shared link | Preview | Every page's `og:image` is `https://tjzine.github.io/frame-compare/assets/brand/social-card.jpg` and `site/assets/brand/social-card.jpg` exists (the absolute URL resolves only after deployment) |

### Asset checks

- Every row of the asset table has its file, size, and pages. Every file in
  `docs/images/` except `README.md` appears in the image README's "Current asset set"
  table (the `home-strip-<frame>.webp` row covers the six strip files), and the table
  names no file that is missing.
- No file in `docs/images/` is unreferenced.
- Privacy review recorded for every new file.

## Out of scope and follow-ups

- Authority-page headings and H1 case (I-07): guard tests and agent instructions match
  them. A later change can rename them together with those consumers.
- A release-side verification script for the Windows ZIP (maintainer decision 9).
- Versioned documentation, analytics, and page feedback widgets: no current need.
- Zensical's social-card plugin, when it ships, can replace the static card.
- The README hero image stays `report-overview.webp`.

## Review

### Round 1 (fresh `code-reviewer`, 2026-10-12)

The reviewer read the plan, its assets, the prototype, the dry run, and the repository
(read-only). Every finding was checked against the cited source before disposition. All
were accepted; none was rejected.

| Finding | Disposition | Change |
| --- | --- | --- |
| U3's `rg` acceptance cannot pass: `current-architecture.md:228`, `media-runtime-windows-validation.md:99`, and a test fixture still match | Accept | U3 deletes the two API-generator references; the fixture is excluded; `rg` searches hidden paths |
| Paragraph check counts indented code, so U5 must fail | Accept | Checker strips fences at any indentation; tested on the prototype |
| Home audio sentence omits the other authority checks | Accept | "…only when the video confirms it and every other check passes…"; diagram label changed to "offset between the two tracks" (new SHA-256) |
| Requirements overstates the Docker X11 panel | Accept | States that the profile is not yet verified on a visible desktop |
| Windows step 2 drops the GitHub CLI prerequisite, the file-name block, and a lead-in sentence | Accept | Exact contents of steps 1 and 2 specified |
| Run-option trailing paragraphs land under "Output modes" | Accept | U8 moves one and replaces the other with an exact sentence |
| Publishing callout sentences ambiguous | Accept | The "Do not commit a live webhook URL" paragraph becomes the callout body |
| U9 would invent replacement wording | Accept | Replacement table for every plan reference |
| Glossary would publish writer instructions | Accept | Glossary written in full for readers |
| Smaller wording calls (Docker, pipeline, analysis, README, first comparison, index, exit-code paragraph, runbook, native split, updater split, sources lead, Docker profiles, reports figure) | Accept | Each given exact text or an exact split point |
| Minor facts: Windows needs the GitHub CLI to verify; label wording; copyright years and SPDX; `og:image:alt`; "same commands on every route"; "two capture sets" | Accept | Corrected |
| Terminal output trailing whitespace versus `git diff --check` | Accept | Style guide and U5 strip trailing whitespace |
| Style-guide contradictions (card counts, callouts per section, figure credits, Internals anchors, Windows installer image, banned-word list, 88-column rule) | Accept | Rules aligned with the specified pages; credit added to home captions; test list aligned |
| `--fc-ref`/`--fc-cmp` defined but unused | Accept (modified) | Kept as the single source for the label colors, now used by the hero labels; light-surface variant removed |
| Duplicated exit-code table can drift | Accept | U8 adds `test_commands_reference_exit_codes_match_contract` |
| C-02 audit row names pages that get no steps | Accept | Row corrected to the two pages that get steps |
| SVG deletion owner, orchestrator check wording, template-referenced files, asset-list wording, pre-deployment `og:image` check, pre-written privacy result | Accept | Ownership fixed to U5; checks and wording corrected |

### Round 2 (fresh `code-reviewer`, 2026-10-12)

No blockers. Five major and several minor findings; all verified against the
repository and accepted.

| Finding | Disposition | Change |
| --- | --- | --- |
| Verbatim text overstates the dry run (output paths, final frames) | Accept | Home, style-guide example, and glossary now say it shows the sources, the reference, the frames you asked for, and what a run would create (`dry-run.ansi`, contract) |
| U9 replacement table incomplete; `CHANGELOG.md` heading note dropped | Accept | Two rows added; `SECURITY.md` and `CHANGELOG.md` restored to the style guide's authority scope with the release-tooling reason |
| Plan base behind the checkout | Accept | Base re-pinned to `c537f94d`; the intervening commits touch no user page; architecture reference moved to line 242; `relink.py` re-run on the new base with the same result; handoff stops if a later `HEAD` touches planned files |
| U5's stripping code keeps trailing whitespace | Accept | Per-line `rstrip()` added |
| Style test does not strip indented fences | Accept | Same indentation-aware fence pattern as the paragraph check |
| Windows sentences replaced by step titles not named | Accept | Both deletions specified |
| Trailing newline for byte-exact files | Accept | Files end with one newline |
| Image README attribution and `hdr-diagnostic-overlay.webp` pages | Accept | Exact replacement text; Pages cell updated |
| "Four stages" against "six stages"; Docker home tab missing setup | Accept | "four steps"; Docker tab includes the setup lines |
| Handoff `rg` matches its own text; check numbering; paragraph script indentation | Accept | Globs exclude prompts and reviews; checks 1 to 5; script moved out of list indentation |
| New files skip `git diff --check`; no `ruff format --check` | Accept | Trailing-whitespace check for new files; `git diff --cached --check` after staging; `ruff format --check` in test acceptance |
| Home description over 160 characters; `INSTALL-WINDOWS.md` H1 case; nested backticks; 404 history wording; U4 acceptance wording | Accept | Corrected (site description now 145 characters) |
| Repository-root links not checked after moves; 404 path check needs deployment | Accept | `rg` check for root pages; 404 check split into pre- and post-deployment |
| Existing errors the voice pass would keep: troubleshooting `NOT APPLIED` cause; dry-run checklist names the generated-data root | Accept | Exact replacement text for both |

### Round 3 (fresh `code-reviewer`, 2026-10-12)

The reviewer confirmed the round 2 changes and checked every verbatim sentence against
the source. Three new findings, plus two minor ones; all accepted.

| Finding | Disposition | Change |
| --- | --- | --- |
| Root-page link check expects `CONTRIBUTING.md` clean in wave B, but U9 rewrites that line in wave C | Accept | `CONTRIBUTING.md` joins the check in wave C |
| First-comparison checklist says "the expected reference is first"; the dry run lists sources by name and prints the reference separately (`src/frame_compare/cli/dry_run.py`) | Accept | Exact replacement item; style-guide example says "the sources it found, the reference" |
| Handoff baseline would stop on an untracked `.claude/launch.json` | Accept | The planner's scratch preview config was deleted; the tree holds only expected files |
| Troubleshooting replacement wrong when no candidate exists | Accept | Sentence covers both cases |
| Home run-folder tree showed `alignment_diagnostics/`, which the captured run does not have | Accept | Tree matches the captured run folder |
