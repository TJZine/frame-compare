---
search:
  exclude: true
---

Status: Historical
Scope: Audit-driven refresh of user documentation, site design, navigation, and imagery
Owner: Maintainer; planned by a Claude session on 2026-10-08; implemented by a Codex
orchestrator with `worker` (U1) and `worker_luna` (U2–U10) chats

# Documentation refresh

Base: `agent/e2e-test-strategy` at `80beafdcdabc7ac556f78fada5e7593b89e8880c`, after
the review remediation (`docs/plans/2026-10-08-review-remediation.md`, implementation
complete). This plan changes documentation, the site stylesheet and configuration,
three documentation guard tests, and the docs workflow's search-scope check. It
changes no product code.

Implementers follow this plan and its assets exactly. Any ambiguity, any fact they
cannot verify, and any decision the plan does not make is a stop: report `blocked`.

## Assets

- [Style guide](2026-10-08-documentation-refresh-assets/style-guide.md): voice,
  terminology, and conventions for every unit.
- [Visual specification](2026-10-08-documentation-refresh-assets/visual-spec.md):
  complete `extra.css`, `docs/index.md`, palette block, and components.
- [Get started pages and README](2026-10-08-documentation-refresh-assets/pages-get-started.md)
- [User guide pages](2026-10-08-documentation-refresh-assets/pages-guides.md)
- [Reference, authority, and repository files](2026-10-08-documentation-refresh-assets/pages-reference.md)
- [Capture specification](2026-10-08-documentation-refresh-assets/capture-spec.md):
  media, workspace, scripts, and the asset table.
- [`CONTRIBUTING.md` block](2026-10-08-documentation-refresh-assets/contributing-docs-style.md):
  the permanent documentation style section, ready to paste.

## Approved decisions (maintainer, 2026-10-08)

1. **Visual direction B, viewer-matched.** Charcoal stage hero with the real report
   capture, brass split-line headline, four-view filmstrip; brass replaces indigo
   site-wide; the site follows the OS light/dark preference.
2. **Information architecture.** Merge the installation chooser and route comparison;
   move Advanced Docker Environments into Get started as Docker profiles; one VSView
   alignment review page; split the reference into Commands and Configuration; add an
   exit-code section to the CLI contract; move maintainer content (algorithm
   thresholds, the alignment benchmark, the physical Windows checklist, maintainer
   update-build rules) out of user pages; delete stale compatibility notes.
3. **Configuration recipes is dissolved** into the topic guides.
4. **Captures:** report and terminal captures on macOS from a Docker-generated report
   with headless Chrome; terminal captures as Rich SVG; the physical Windows host only
   for the installer output and a new VSView panel capture.
5. **Media:** only the official EBU/DVB PQ10 and HLG10 transport streams, unmodified.
   No synthetic, derived, or private media.
6. **Docker's read-only-media index warning** is documented as expected output.

## Audit

Base-state evidence (2026-10-08): the strict build, the four guard-test modules, and
the API-doc check passed; all 35 TOML snippets validated against `ConfigSchema`;
every internal link and anchor in the built site resolved. CLI help for every
command, `version`, `doctor --json`, a JSON and a human dry run, and a Docker run on
generated test media were captured under `.tmp/docs-refresh-2026-10-08/`. The site
was inspected at 1440 × 900 and 390 × 844 in both schemes.

### Findings

| ID | Severity | Location (base) | Evidence | Action and unit |
| --- | --- | --- | --- | --- |
| A-01 | High | `docs/guides/how-it-works.md:20-29`, `:74-79` | The flowchart and prose apply computed alignment without confirmation; only `trusted_automatic` results apply trims (`docs/current-cli-contract.md:1655-1659`) | Rewrite the diagram and section 4 (U4) |
| A-02 | High | `SECURITY.md:33-40` | Says generated paths must stay under the workspace; the generated-data root may be external (`docs/current-cli-contract.md:118-124`) | Rewrite the bullet (U9) |
| A-03 | High | `SECURITY.md:50-54` | FC-3012 is a source-selector error (`src/frame_compare/orchestration/errors.py:98`); `FC-3xxx` is the input family, not "security" | Replace the table (U9) |
| A-04 | High | `docs/index.md:33-40` | Hero uses `report-viewer-overview.webp`, which `docs/images/README.md:104-109` calls stale and intentionally unused; it is byte-identical to `report-slider.webp` | New hero capture and home page (U1, U2) |
| A-05 | High | `docs/reference/commands-and-configuration.md:75-88` | No complete key reference; `screenshots.include_frame_number`, `color.gamma_lift`, `color.enable_tonemap`, `report.default_mode`, `report.include_filmstrip`, `audio_alignment.enable`, `tmdb.enabled`, `tmdb.year_tolerance`, `tmdb.category_preference` are explained nowhere | New `reference/configuration.md` and guard test (U7) |
| A-06 | High | `docs/current-cli-contract.md` | No exit-code table; codes 0–6 and 130 live only in `src/frame_compare/cli/errors.py:13-41` | New contract section (U8) |
| A-07 | High | `docs/images/*` | Every capture predates the viewer and terminal refresh (`d7b069d5`, `1baf8100`, `e9958270`) and the installer change (`2350cf48`); the Inspector's "Align" tab (`docs/images/README.md:121`) no longer exists | Recapture (U1, U10) |
| A-08 | Medium | `docs/windows-portable.md:161-205`, `docs/guides/audio-alignment.md:194-331`, `docs/reference/commands-and-configuration.md:98-122`, `docs/guides/troubleshooting.md:25-28`, `:81-92` | The VSView panel workflow is written four times | One `guides/vsview-review.md` (U5); other pages link it (U3, U5, U7) |
| A-09 | Medium | `docs/guides/audio-alignment.md:46-192`, `:357-391` | Algorithm constants, schema versions, and a maintainer benchmark in a user guide | Thresholds to the contract and benchmark to the runbook (U8); guide rewritten (U5) |
| A-10 | Medium | `docs/windows-portable.md:244-249`, `:318-351` | Maintainer update-build rules and the physical acceptance checklist in the user guide | Move to the runbook and the Windows validation page (U8); delete from the guide (U3) |
| A-11 | Medium | `docs/getting-started/route-comparison.md:75`, `docs/guides/audio-alignment.md:202`, `docs/docker-environments.md:122` | User pages link the search-excluded `docs/plans/` handoff | Remove (U3, U5) |
| A-12 | Medium | `CHANGELOG.md:8-86` | Unreleased omits the viewer and terminal refresh, wizard next steps, run help, the R81 runtime, the cache-flag conflict, secret redaction, webhook DNS, VSView reaping, and the Diff race fix | Add bullets (U9) |
| A-13 | Medium | `README.md:29` | Lists an "overlay" view; the UI calls it Single (`overlay` is only the config value) | Fix (U3) |
| A-14 | Medium | Docker route | Read-only media mounts make every run print `Loading … without an L-SMASH index cache after index construction failed` (`src/frame_compare/vs/source.py:210`); undocumented | Document (U3, U5, U7) |
| A-15 | Medium | `docs/release-evidence/2026-07-28-windows-initial-release.md` | In the search index, not in the nav, no front matter | Exclude from search (U9) |
| A-16 | Medium | `.github/workflows/docs.yml` | The search-scope check covers only `TODO/` and `plans/`; `reviews/`, `prompts/`, `images/`, and `release-evidence/` are internal too | Extend the check and its test (U9) |
| A-17 | Medium | `docs/current-cli-contract.md:1870-1875` | States the explicit-override rule only for `target_nits`; `tone_curve`, `gamma_lift`, and `contrast_recovery` follow it too (`src/frame_compare/render/prepare.py:55-64`) | Add the sentence (U8); preset table in the HDR guide (U4) |
| A-18 | Medium | `docs/guides/reports-and-overlays.md:74-157`, `:224` | Implementation-level UI detail and payload-version narration in a user guide | Rewrite (U6) |
| A-19 | Medium | `docs/guides/configuration-recipes.md` | Repeats snippets from the sources and analysis guides; its memory section duplicates `commands-and-configuration.md:163-177` | Dissolve (U4, U6, U7) |
| A-20 | Low | `zensical.toml:73-81` | Palette has no `media`, so the site ignores the OS theme | New palette block (U2) |
| A-21 | Low | `docs/stylesheets/extra.css:3-15` | Brass exists only on the home page; links and navigation stay indigo | New stylesheet (U2) |
| A-22 | Low | `docs/guides/first-comparison.md:84-85`, `:155` | Duplicated doctor paragraph; an over-long line | Fix (U3) |
| A-23 | Low | `docs/getting-started/native.md:50-53`, `docs/guides/how-it-works.md:110`, `docs/reference/commands-and-configuration.md:93-96`, `docs/windows-portable.md:67-70`, `docs/guides/analysis-modes.md:121-122` | Stale compatibility and history notes | Delete (U3, U4, U7) |
| A-24 | Low | `zensical.toml:12-46` | Title-case nav labels against sentence-case page titles | New nav (U2) |
| A-25 | Low | `docs/plans/2026-08-17-documentation-v2-screenshot-remediation.md:6` | Still `Status: Active`; superseded by this plan | Mark Historical (U9) |
| A-26 | Low | `docs/docker-environments.md:38-41` | Refers to a "README route" that no longer exists | Fix in the move (U3) |
| A-27 | Low | `docs/reference/output-layout.md:9-26` | Tree omits `alignment_diagnostics/` and `generated/vsview_sessions/` (`docs/current-architecture.md:364`, `:381-389`) | Fix (U7) |
| A-28 | Low | `docs/guides/troubleshooting.md:13-36` | No entry for `NOT APPLIED`, the cache-flag conflict, or the Docker index warning | Add rows (U5) |
| A-29 | Low | `docs/guides/hdr-tonemapping.md:98-100` | User page links the internal `images/README.md` | Delete (U4) |

Agent files (`AGENTS.md`, `CLAUDE.md`, `.agents/`, `.claude/`, `.codex/`) were out of
scope; no problem there affects this plan. Product observations, also out of scope:
a non-TTY coloured run logs `fps_report` INFO lines that include full source paths;
the run-plan panel says "TMDB lookup" when `tmdb.enabled = false`.

### Change inventory

Baseline: the 2026-08-17 documentation pass (`f0f8553e`). Every user-visible change
since then and the pages that state it after this refresh:

| ID | Change (commits) | Pages |
| --- | --- | --- |
| C-01 | VSView replaces VSPreview; native panel (`18ca7837`, `1af8100c`) | `guides/vsview-review.md`, `windows-portable.md`, `getting-started/native.md`, `reference/configuration.md`, `getting-started/docker-profiles.md` |
| C-02 | Whole-track chunked audio with video confirmation; `APPLIED` / `NOT APPLIED` (`c568b91c`, `2102da63`) | `guides/how-it-works.md`, `guides/audio-alignment.md`, `guides/troubleshooting.md`, contract thresholds, `README.md` |
| C-03 | Retimed sources analysed on their effective timeline (`81b559b8`) | `guides/audio-alignment.md` |
| C-04 | Removed `[audio_alignment]` tuning keys | `reference/configuration.md` (current keys only); `CHANGELOG.md` upgrade note (present) |
| C-05 | Motion-selected video positions, shared-language reference stream, `active_rect_detection = "auto"` default (`a7332750`, `0203c989`) | `guides/audio-alignment.md`, `reference/configuration.md` |
| C-06 | `[runtime].memory_limit_mb` (`bdfa0c6c`) | `reference/configuration.md` |
| C-07 | Report viewer refresh (`11c70204`, `e9958270`, `1baf8100`, `d7b069d5`, `25b15ae8`, `5c9c3de1`) | `guides/reports-and-overlays.md`, captures, `CHANGELOG.md` |
| C-08 | Terminal presentation refresh (`d7b069d5`) | `guides/first-comparison.md` captures, `CHANGELOG.md` |
| C-09 | Wizard next-step suggestions (`837b5e4a`) | `guides/first-comparison.md` (present), `reference/commands.md`, `CHANGELOG.md` |
| C-10 | Grouped `run --help` and actionable choice errors (`e4342501`) | `reference/commands.md`, `CHANGELOG.md` |
| C-11 | `--no-cache` with `--from-cache-only` rejected (`33dbc6e7`) | `reference/commands.md`, `guides/troubleshooting.md`, `CHANGELOG.md` |
| C-12 | Secret inputs redacted in config errors (`e7b457dd`) | `reference/configuration.md`, `CHANGELOG.md` |
| C-13 | Webhook DNS resolution bounded (`3ee93554`) | `CHANGELOG.md` |
| C-14 | Runtime R80 then R81, VSView 0.12.0, CPython 3.13.16, Windows FFmpeg 8.1.3, vsjetengine 1.8.0 (`8921a2c7`, `7f70bb98`, `b592dc21`) | `supported-media-runtime.md` (present), `getting-started/native.md`, `CHANGELOG.md` |
| C-15 | Ctrl+C observed before work and publication; exit 130 (`ec2fc6ca`) | contract exit-code section, `CHANGELOG.md` (present) |
| C-16 | Windows PowerShell 7 source prerequisite, backup identity, fresh-folder reinstall (`2350cf48`) | `windows-portable.md`, `INSTALL-WINDOWS.md` (present) |
| C-17 | Typed config validation of malformed input (`ca432635`) | `CHANGELOG.md` (present) |
| C-18 | Per-run `alignment_diagnostics/` evidence | `reference/output-layout.md`, `guides/audio-alignment.md`, `guides/first-comparison.md` |
| C-19 | Docker read-only-media index fallback (behavior) | `getting-started/docker.md`, `reference/output-layout.md`, `guides/troubleshooting.md` |
| C-20 | Exit codes and error families (existing behavior, never documented) | contract, `reference/commands.md`, `guides/troubleshooting.md`, `SECURITY.md` |

## Navigation

U2 replaces the `nav` value in `zensical.toml` with exactly:

```toml
nav = [
  { "Home" = "index.md" },
  { "Get started" = [
    { "Choose an installation" = "getting-started/index.md" },
    { "Windows portable" = "windows-portable.md" },
    { "Docker" = "getting-started/docker.md" },
    { "Docker profiles" = "getting-started/docker-profiles.md" },
    { "Native source" = "getting-started/native.md" },
    { "Your first comparison" = "guides/first-comparison.md" },
  ] },
  { "User guide" = [
    { "How Frame Compare works" = "guides/how-it-works.md" },
    { "Sources, references, and labels" = "guides/sources-and-labels.md" },
    { "Frame selection and analysis" = "guides/analysis-modes.md" },
    { "Audio alignment" = "guides/audio-alignment.md" },
    { "VSView alignment review" = "guides/vsview-review.md" },
    { "HDR and tonemapping" = "guides/hdr-tonemapping.md" },
    { "Reports and overlays" = "guides/reports-and-overlays.md" },
    { "Presets, history, and generated data" = "guides/presets-history-generated-data.md" },
    { "Publishing and webhooks" = "guides/publishing-and-webhooks.md" },
    { "Troubleshooting" = "guides/troubleshooting.md" },
  ] },
  { "Reference" = [
    { "Commands" = "reference/commands.md" },
    { "Configuration" = "reference/configuration.md" },
    { "Output layout" = "reference/output-layout.md" },
    { "Supported media runtime" = "supported-media-runtime.md" },
    { "CLI behavioral contract" = "current-cli-contract.md" },
  ] },
  { "Project" = [
    { "Internal Python API" = "api.md" },
    { "Current architecture" = "current-architecture.md" },
    { "Engineering runbook" = "ENGINEERING_RUNBOOK.md" },
    { "Physical Windows runtime validation" = "media-runtime-windows-validation.md" },
    { "Performance evidence" = [
      { "Analysis performance validation" = "analysis-performance-validation.md" },
      { "Analysis benchmark history" = "analysis-benchmark-history.md" },
    ] },
    { "Historical decisions" = "DECISIONS.md" },
    { "Contributing" = "https://github.com/TJZine/frame-compare/blob/main/CONTRIBUTING.md" },
  ] },
]
```

Page H1s in `docs/getting-started/**`, `docs/guides/**`, and `docs/reference/**`
equal their nav labels. Authority and project pages keep their H1s.

## Units

U1 uses the `worker` preset (maintainer decision, 2026-10-09): it is the one wave-A
unit that runs real tooling (Docker, 8K HEVC decoding, headless Chrome), where
environment diagnosis is useful. Every other unit uses the `worker_luna` preset: each
is mechanical writing or capture against a decision-complete specification.

**Wave A** (parallel; disjoint file ownership): U1–U9.
**Wave B** (after wave A is integrated and reviewed): U10, on the physical Windows
host.

Every unit:

- reads `AGENTS.md`, `.agents/project.md`, this plan's Approved decisions, the
  [style guide](2026-10-08-documentation-refresh-assets/style-guide.md), and its own
  specification sections;
- edits only its owned files;
- writes prose under the **points rule**: where a specification gives content points
  instead of quoted text, write each point, in the given order, as one or more
  sentences that follow the style guide, adding no fact that the cited source does not
  state. This is writing, not a decision. Text marked "exactly" or "verbatim" is
  copied as given;
- runs no Git command that changes the index, history, or branch (moves and deletes
  use plain `mv` and `rm`; the orchestrator stages them);
- never commits, never chooses, and reports `blocked` with the question and evidence
  for any ambiguity, unverifiable fact, failed check, or missing input;
- reports the files changed, the checks run with their results, and anything
  `blocked`.

### U1 — Captures and image record (macOS)

- **Preset:** `worker`.
- **Environment failures:** when a specified command fails for an environmental
  reason (Docker daemon, image build, Chrome launch, a missing tool), U1 may diagnose
  the cause and rerun the same command once the cause is cleared. It changes no
  specified script, configuration, frame, crop, or asset decision, installs nothing,
  and reports `blocked` with the diagnosed cause when it cannot clear it.
- **Owns:** `docs/images/**` except `windows-portable-install.png` and
  `vsview-alignment-panel.webp`.
- **Inputs:** the capture specification (all macOS sections and the asset table);
  `pages-reference.md` "`docs/images/README.md` — rewrite".
- **Prerequisite:** the maintainer has placed the two DVB files (capture
  specification, Prerequisites). If they are absent, report `blocked` at once.
- **Acceptance:** both media hashes match; the three runs exit 0; the eight assets
  exist with the specified dimensions; the SVG grep checks find nothing; the five
  deleted files are gone; the privacy review is recorded in the report;
  `docs/images/README.md` has set 1 filled in and set 2 marked pending.
- **Stops:** hash mismatch; any run fails; frame 1000 missing; a capture shows a
  loading message, an error, or the wrong frame or pair; the HDR crop cuts a line;
  any private string found.

### U2 — Site frame

- **Owns:** `zensical.toml`, `docs/stylesheets/extra.css`, `docs/index.md`.
- **Inputs:** the visual specification; the Navigation section above.
- **Acceptance:** the three files equal the specified blocks; `zensical.toml` parses
  (`uv run --no-sync python -c "import tomllib;tomllib.load(open('zensical.toml','rb'))"`);
  no other key in `zensical.toml` changed (`git diff zensical.toml` shows only
  `nav` and the two palette tables).
- **Stops:** any specified block does not parse or conflicts with another theme key.

### U3 — Get started pages and README

- **Owns:** `README.md`, `INSTALL-WINDOWS.md`, `docs/getting-started/**`,
  `docs/windows-portable.md`, `docs/docker-environments.md` (moved with a plain `mv`),
  `docs/guides/first-comparison.md`.
- **Inputs:** `pages-get-started.md`.
- **Acceptance:** each page's outline matches; the "must not appear" strings are
  absent; `docs/getting-started/route-comparison.md` and `docs/docker-environments.md`
  no longer exist; `docs/getting-started/native.md` H1 is `# Native source`; the
  Windows guard strings listed in the spec are present verbatim;
  `uv run --no-sync pytest -q tests/workflows/test_onboarding_docs.py` passes (it
  asserts the native install text, which this plan keeps).
- **Stops:** a cited source line does not say what the spec says; a guard string
  cannot be kept.

### U4 — Guides: pipeline, sources, analysis, HDR, presets, publishing

- **Owns:** `docs/guides/how-it-works.md`, `sources-and-labels.md`,
  `analysis-modes.md`, `hdr-tonemapping.md`, `presets-history-generated-data.md`,
  `publishing-and-webhooks.md`, `configuration-recipes.md` (delete).
- **Inputs:** `pages-guides.md` (U4 sections).
- **Acceptance:** outlines match; snippets validate; Mermaid block equals the spec;
  "must not appear" strings absent; `configuration-recipes.md` deleted.
- **Stops:** the preset table or override rule disagrees with
  `src/frame_compare/vs/tonemap_presets.py` or `src/frame_compare/render/prepare.py`.

### U5 — Alignment guides and troubleshooting

- **Owns:** `docs/guides/audio-alignment.md`, `docs/guides/vsview-review.md` (new),
  `docs/guides/troubleshooting.md`.
- **Inputs:** `pages-guides.md` (U5 sections).
- **Acceptance:** outlines and tables match; required literal strings present;
  "must not appear" strings absent; snippets validate.
- **Stops:** a quoted UI label or terminal string is not found in `src/frame_compare`
  or the contract.

### U6 — Reports guide

- **Owns:** `docs/guides/reports-and-overlays.md`.
- **Inputs:** `pages-guides.md` (U6 section); capture specification asset table.
- **Acceptance:** outline matches; the shortcut table equals the spec; figures use
  `fc-figure` with the specified alt text and captions; "must not appear" strings
  absent.
- **Stops:** a described control is not in the generated report
  (`src/frame_compare/services/report/renderer.py`).

### U7 — Reference pages and configuration guard test

- **Owns:** `docs/reference/**`, `tests/test_cli_contract_docs.py`.
- **Inputs:** `pages-reference.md` (U7 sections).
- **Acceptance:** `commands.md` tables match a fresh `--help` run in option names,
  short aliases, value shapes and choices, and `--write-config` persistence (the
  Effect wording is the plan's own and is not compared);
  `configuration.md` tables equal the spec; `commands-and-configuration.md` deleted;
  `uv run --no-sync pytest -q tests/test_cli_contract_docs.py` passes;
  `uv run --no-sync pyright --warnings tests/test_cli_contract_docs.py` and
  `uv run --no-sync ruff check tests/test_cli_contract_docs.py` pass.
- **Stops:** an option name, alias, value shape, choice list, persistence, or schema
  default differs from the spec.

### U8 — Authority and project documents and the Windows docs test

- **Owns:** `docs/current-cli-contract.md`, `docs/ENGINEERING_RUNBOOK.md`,
  `docs/media-runtime-windows-validation.md`,
  `tests/windows_portable/test_windows_portable_docs.py`.
- **Inputs:** `pages-reference.md` (U8 sections). The moved text comes from the base
  commit (`git show 80beafdc:docs/guides/audio-alignment.md`,
  `git show 80beafdc:docs/windows-portable.md`).
- **Acceptance:** the inserted sections exist in the specified places; the contract's
  Contents list has the new entry;
  `uv run --no-sync pytest -q tests/test_cli_contract_docs.py -k "not configuration_reference"`
  passes (U7 owns the configuration test and its page);
  ruff and pyright pass on the edited test. The Windows docs test is run and its
  result reported; failures that name `docs/windows-portable.md` or
  `docs/guides/vsview-review.md` are expected until U3 and U5 land and are not a stop.
  `tests/windows_portable/test_windows_portable_build_scripts.py` and
  `tests/vs/test_runtime_contract.py` (which read the validation page and the
  contract) pass.
- **Stops:** the wizard exit-code check in the spec fails; the moved text is not at
  the cited base lines.

### U9 — Repository files and internal-page hygiene

- **Owns:** `SECURITY.md`, `CHANGELOG.md`, `CONTRIBUTING.md`,
  `docs/release-evidence/2026-07-28-windows-initial-release.md`,
  `docs/plans/2026-08-17-documentation-v2-screenshot-remediation.md`,
  `.github/workflows/docs.yml`, `tests/workflows/test_docs_workflow.py`.
- **Inputs:** `pages-reference.md` (U9 sections);
  `contributing-docs-style.md`.
- **Acceptance:** CHANGELOG edits only under Unreleased and worded exactly;
  `uv run --no-sync pytest -q tests/workflows/test_docs_workflow.py` passes; the
  workflow YAML parses; ruff and pyright pass on the edited test.
- **Stops:** a CHANGELOG bullet contradicts its cited commit.

### U10 — Physical Windows captures (wave B)

- **Owns:** `docs/images/windows-portable-install.png`,
  `docs/images/vsview-alignment-panel.webp`, set 2 of `docs/images/README.md`, the
  figure insertion in `docs/guides/vsview-review.md` ("Confirm the positions"), and the
  `width`/`height` of the install figure in `docs/windows-portable.md`.
- **Inputs:** capture specification, "Physical Windows captures" and the asset table.
- **Host:** the physical Windows 10/11 x64 capture host, interactive desktop,
  display scaling 100%. Steps that need a visible desktop are done by the maintainer
  or a session with desktop control; otherwise `blocked`.
- **Acceptance:** both files exist within the size limits; privacy review recorded;
  set 2 filled in; the figure uses `fc-figure fc-figure--narrow`.
- **Stops:** the bundle build fails; a kept terminal line shows the user name or a
  `C:\Users\` path; the panel does not reach the ready state; a size limit is
  exceeded.

## Verification

### Per unit

Listed under each unit. Every unit also runs `git diff --check` on its files and the
TOML check below on each page it edits that contains ` ```toml `.

TOML check, from the repository root. Replace `PAGES` with the space-separated
paths of the pages to check (for example `docs/guides/analysis-modes.md`):

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
        m = re.match(r"^(\s*)```toml\s*$", lines[i])
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

The script changes into the empty `.tmp/toml-check` directory so no real
`config/config.toml` is read. Any exception is a failure.

### Orchestrator, once per wave, serially

1. `uv run --no-sync python scripts/generate_api_docs.py --check`
2. `uv run --no-sync zensical build --clean --strict`
3. The docs workflow's search-scope check:
   ```bash
   uv run --no-sync python - <<'PY'
   import json
   from pathlib import Path
   items = json.loads(Path("site/search.json").read_text(encoding="utf-8"))["items"]
   internal = [i["location"] for i in items if i["location"].startswith(("TODO/", "plans/", "reviews/", "prompts/", "images/", "release-evidence/"))]
   raise SystemExit(f"leaked: {internal}" if internal else 0)
   PY
   ```
4. `uv run --no-sync pytest -q tests/test_cli_contract_docs.py tests/windows_portable/test_windows_portable_docs.py tests/workflows/test_docs_workflow.py tests/test_generate_api_docs.py tests/workflows/test_onboarding_docs.py tests/windows_portable/test_windows_portable_build_scripts.py tests/vs/test_runtime_contract.py`
5. Link residue: `rg -n "route-comparison|configuration-recipes|docker-environments|commands-and-configuration|fc-doc-figure|report-viewer-overview|report-slider|report-diff|first-run-" README.md docs --glob '!docs/plans/**' --glob '!docs/reviews/**' --glob '!docs/prompts/**'`
   returns nothing.
6. Rendered visual QA (below).

The docs group must already be installed; if `zensical` is missing, stop and ask the
maintainer before any `uv sync`.

### Rendered visual QA

Serve the built `site/` locally (`uv run --no-sync zensical serve`) and check each
row at 1440 × 900 and at 390 × 844, in light and in dark (clear site storage between
schemes so the OS preference applies):

| Page | State | Expected |
| --- | --- | --- |
| Home | Top of page | Charcoal stage with the brass split headline, kicker, primary button, text link, and the report capture; four-item filmstrip below |
| Home | Route cards | Three cards; hovering or tabbing to a card shows a brass border or ring; clicking anywhere on a card opens its page |
| Home | 390 px | Stage stacks; filmstrip is 2 × 2; one-column cards and steps; no horizontal scroll |
| Choose an installation | Route cards and tables | Same card component as home; three tables render with no page-level horizontal scroll (tables may scroll inside their wrapper) |
| Your first comparison | Figures | Both terminal SVGs render inside charcoal frames, text sharp, no missing font fallback boxes |
| Reports and overlays | Figures | Five figures in frames; Report information is narrow and centred; shortcut table keys render as `kbd` |
| Configuration | Tables | All tables render; long key cells wrap or scroll inside the table, not the page |
| Windows portable | Code and figure | The PowerShell blocks have copy buttons; the install figure renders in a frame |
| Any page | Dark scheme | Page background `#141414`; links amber; no indigo anywhere |
| Any page | Keyboard | Tab focus is visible on links, buttons, and route cards |

### Asset checks

- Every row of the capture specification's asset table has its file, dimensions, and
  pages; `docs/images/README.md` lists exactly those files.
- No file in `docs/images/` is unreferenced except `README.md`.
- Privacy review recorded for every new or replaced file.

## Review

### Round 1 (fresh `code-reviewer`, 2026-10-08)

27 findings: 2 blockers, 8 major, 17 minor. No over-engineering found. Every finding
was checked against the cited source before disposition.

| ID | Finding | Disposition | Evidence and change |
| --- | --- | --- | --- |
| F-01 | Windows install capture always prints the user-profile PATH | Accept | `tools/windows_portable/install.ps1:39-41,95-101`; capture runs with `LOCALAPPDATA` overridden to `C:\FrameCompareDemo\LocalAppData` for one tab, then `uninstall.cmd` cleans up |
| F-02 | Shim injects its own `--config`, so the panel run ignores the demo config | Accept | `tools/windows_portable/shim/frame-compare.ps1:170-187`; run the bundle launcher with explicit `--config` |
| F-03 | "Keep" left rewording to implementers | Accept | "Keep" is now byte-identical plus an exact mechanical-corrections table in the style guide |
| F-04 | Moving `docker-environments.md` breaks a relative link | Accept | `docs/docker-environments.md:53`; link rewrite, H3 renames, and version removal specified |
| F-05 | Style guide's `../../` path is wrong | Accept | Corrected to a page-relative path |
| F-06 | CONTRIBUTING copy not executable verbatim | Accept | New asset `contributing-docs-style.md` with the exact block |
| F-07 | Page units need sizes only U1 produces | Modify | Instead of reordering waves, the three variable-size figures omit `width`/`height`; no cross-unit dependency remains |
| F-08 | Reports delete instruction ambiguous | Accept | Exact replacement text and deletion range `11–149` |
| F-09 | U7 `--help` "match" would false-stop | Accept | Match defined as names, aliases, values, choices, persistence |
| F-10 | No visible CC BY 4.0 credit | Modify | Planner decision, not a design departure: credit line on the home page and README, "Footage © EBU, CC BY 4.0." in each EBU caption; license compliance is not optional |
| F-11 | Analysis H1 differs from nav label | Accept | H1 specified |
| F-12 | Kept sentence contains forbidden `payload` | Accept | Replacement sentence specified |
| F-13 | Troubleshooting edits ambiguous | Accept | Exact text specified |
| F-14 | Docker intro split unclear | Accept | Exact intro and first-section text |
| F-15 | Configuration headings and logging lead | Accept | Sentence-case H2s with listed anchors; logging sentence specified |
| F-16 | Several "one sentence"/"condense" instructions | Accept | Exact text supplied for every listed item |
| F-17 | Missing `Manually confirmed alignment reused` row | Accept | Row added (`src/frame_compare/services/alignment_presentation.py:85,105`) |
| F-18 | UI labels "default view" | Accept | Uses `Opens in` and `Report Information` (`renderer.py:415,424`) |
| F-19 | `contrast_recovery` default misleading | Accept | Default `0.3` |
| F-20 | Cache-flag conflict overstated | Accept | Scoped to runs and dry runs (`docs/current-cli-contract.md:930-932`) |
| F-21 | Wrong wizard line citation | Accept | Lines 205–207 and 215–217 |
| F-22 | "TMDB is opt-in" inaccurate | Accept | TMDB runs only with an API key (`src/frame_compare/services/tmdb_resolution.py:698`) |
| F-23 | Home page text against the style guide | Accept | Heading, link texts, and code spans fixed; home H1 and route-card heading links recorded as style-guide exceptions |
| F-24 | Orchestrator test list incomplete | Accept | Added `test_onboarding_docs.py`, `test_windows_portable_build_scripts.py`, `test_runtime_contract.py`; all pass at base |
| F-25 | Secret redaction (C-12) not specified | Accept | Sentence added to the Configuration spec |
| F-26 | ZIP nests the bundle folder | Accept | `Compress-Archive -Path "...\*"` and exact paths |
| F-27 | A-20 line numbers wrong | Accept | `zensical.toml:73-81` |

Evidence gaps raised by the reviewer: the terminal-SVG panel extraction and the
`#frame-select` option prefix were both exercised on 2026-10-08 against a
Docker-generated two-source HDR report (recorded in the capture specification); the
current `windows-portable-install.png` is 1200 × 165 (read with Pillow); Zensical's
handling of raw `<img>` paths does not matter because U1 runs in the same wave as the
pages that reference its images and the strict build runs only at wave end.

### Round 2 (fresh `code-reviewer`, 2026-10-08)

14 findings: 1 blocker, 5 major, 8 minor. The reviewer confirmed the round-1 fixes
(F-01, F-02, F-26), every configuration key and default, the commands table, the
preset table, all quoted UI and terminal strings, the guard-test strings, every
mechanical-correction line reference, and all new anchors.

| ID | Finding | Disposition | Evidence and change |
| --- | --- | --- | --- |
| R2-1 | Specs give content points, not exact text | Modify | The maintainer's brief has implementers write the prose while the plan makes every decision; added the explicit points rule to "Every unit" rather than scripting every sentence |
| R2-2 | Reports "Open and keep" ambiguous | Accept | Keep 3–6 and 213–215, drop 8–9 |
| R2-3 | Exit-code table overstates 130, 1, 5 | Accept | `run_command.py:346-354`, `cli_helpers.py:130-139`; rows reworded |
| R2-4 | SECURITY containment ignores the `.lwi` index | Accept | `src/frame_compare/vs/source.py:123-125`; sentence added |
| R2-5 | Index warning claimed for dry runs | Accept | "Every comparison run (not a dry run)" |
| R2-6 | CONTRIBUTING block drops redaction and screenshot rules; scope mismatch | Accept | Bullets restored; scope aligned; style-guide sentence corrected |
| R2-7 | Uncovered ranges and unspecified placements | Accept | Recommended workflow deleted; closing links kept; README bullets exact; SECURITY, release-evidence, superseded line, output-layout rows, and blind-comparison placement exact; "unchanged"/"apart from style" replaced |
| R2-8 | VSView panel figure size rule | Accept | U10 sets the saved size |
| R2-9 | Kept text against the style guide | Accept | Correction rows for "simply", "selected clips", "preferred-clip"; README Project status gets mechanical corrections; GitHub-URL link exception; sentence-case command H2s; caption credit exception |
| R2-10 | U8 test depends on U7's file | Accept | U8 runs with `-k "not configuration_reference"` |
| R2-11 | Install capture window size and profile | Accept | `wt --size 120,30 pwsh -NoProfile -NoLogo` |
| R2-12 | Citation mismatches | Accept | A-27 lines; "nine keys"; benchmark ranges reconciled |
| R2-13 | Contract insertion repeats motion-selection rules | Accept | Exact four-paragraph text without the duplicate clauses |
| R2-14 | C-10 grouping not covered | Accept | Grouping sentence added to the Commands spec |

Remaining evidence gaps (accepted): CHANGELOG bullets were written from commit bodies
and diffs read on 2026-10-08 (the reviewer could not run Git); Zensical rendering of
`primary = "custom"` and the raw-HTML home H1 were verified in the scratch prototype
build and browser on 2026-10-08.

### Round 3 (fresh `code-reviewer`, 2026-10-09)

8 findings: 1 major, 7 minor. The reviewer confirmed every cited line range and moved
span, the guard-test literals, the configuration and commands tables, the exit-code
table, all UI labels and shortcuts, and that no planned move or delete breaks a link
or anchor.

| ID | Finding | Disposition | Evidence and change |
| --- | --- | --- | --- |
| R3-1 | SECURITY text says the `.lwi` index is the only write outside the generated-data root | Accept | Config and preset writes under `config/` (`wizard_command.py:209`, contract 2050–2052); sentence rewritten |
| R3-2 | HDR point overstated run-option precedence | Accept | `src/frame_compare/render/prepare.py:52-74`; `--tm-preset` replaces only the preset |
| R3-3 | Ready-state string not literal in source | Accept | Composition cited (`alignment_review_panel.py:579,596`; contract 1425–1427) |
| R3-4 | Recipe sentence count ambiguous | Accept | Both sentences of lines 158–159, exactly |
| R3-5 | No-guide Configuration leads unspecified | Accept | Exact lead sentences for `[runtime]`, `[tmdb]`, `[logging]` |
| R3-6 | Docker-profiles support sentence placement | Accept | New paragraph directly after kept lines 55–58 |
| R3-7 | CONTRIBUTING scope wider than the style guide | Accept | Scope now the user-page list |
| R3-8 | Wrong anchor citation for `adapter.py` | Accept | Page link, not anchor |

### Round 4 (fresh `code-reviewer`, 2026-10-09): verdict READY

The reviewer confirmed all eight round-3 fixes and found no blocker or major issue.
All seven minor findings were accepted and fixed: an exact three-cell troubleshooting
row for the alignment guide; an explicit section order for "Archive or share a
report"; SECURITY now names the selected config file and `<root>/config/presets`
precisely; panel-confirmed offset reuse is tied to `previous_offsets`
(`src/frame_compare/services/alignment_previous_offsets.py:148-161`); the attribution
range in the images record is lines 62–64 and its old intro (lines 8–14) is deleted;
required guard literals stay on one physical line; and the CONTRIBUTING block carries
the GitHub-URL and caption-credit exceptions. These are wording-level corrections that
do not change scope, structure, or any decision, so no further review round was run.

## Out of scope and open items

- Product code, report viewer styling, and the observations under Audit.
- `docs/plans/2026-10-07-dependency-refresh-windows10-handoff.md` and
  `docs/plans/2026-10-08-review-remediation.md` keep their statuses (their physical
  acceptance is open). `docs/plans/2026-09-23-design-refresh-assets/` is left as
  historical input.
- Links from `docs/supported-media-runtime.md:304` and `docs/ENGINEERING_RUNBOOK.md:403`
  to the 2026-10-07 handoff stay: they are project pages citing evidence.
- When U10 lands and the maintainer accepts the assets, change this plan to
  `Status: Historical`.

## Execution record

### Baseline and dispatch (2026-10-09)

- Checkout: repository root; branch
  `agent/e2e-test-strategy`.
- Initial HEAD: `b9fcd82a66cd641520422e67e0e8ad338df49eae`. The specification
  base remains `80beafdcdabc7ac556f78fada5e7593b89e8880c`; subsequent cancellation
  and viewer fixes are preserved. Each child must stop on a specification conflict.
- Initial `git status --porcelain`: no tracked modifications; only the plan,
  its assets directory, and four untracked files under `docs/prompts/`. The three
  unrelated prompts remain untouched:
  `2026-10-08-documentation-refresh-planning-session.md`,
  `2026-10-08-followup-cancellation-viewer-codex.md`, and
  `2026-10-08-windows-acceptance-codex.md`.
- Initial plan commit: `e3f5681b6202645cd91ffd83f15d3788aec9dbfc` —
  `docs(plan): add the documentation refresh plan`. This is every child's
  dispatch HEAD and the wave-A integration base.
- The maintainer confirmed both DVB files are in place before U1 was dispatched.
  Zensical is available in the existing environment; no dependency sync ran.
- Orchestrator: `01a11f7a-6873-77c0-bad8-0be654bff75c`, host `local`.
  Callback authorization: original human message
  `01a11f7a-7eb0-7070-9170-67a9d7d26167` in turn
  `01a11f7a-7b6f-73b0-aa3d-e6d194b434e4`. Each child verifies that message,
  returns one terminal report, then stops. Acceptance and Git integration remain
  with the orchestrator.
- All nine chats were created in the local project with the model and reasoning
  settings below passed explicitly. U10 and wave reviews are not yet dispatched.

| Unit | Real thread ID | Preset | Model | Effort | Owned files |
| --- | --- | --- | --- | --- | --- |
| U1 | `01a11f7c-9ade-7362-a18b-3591d766d467` | `worker` | `gpt-6.1-sol` | `medium` | `docs/images/**` except `windows-portable-install.png` and `vsview-alignment-panel.webp`. |
| U2 | `01a11f7c-b63f-70f0-a362-3642d58e5962` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `zensical.toml`, `docs/stylesheets/extra.css`, `docs/index.md`. |
| U3 | `01a11f7c-c11a-7061-a26a-f6a5565ec6d7` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `README.md`, `INSTALL-WINDOWS.md`, `docs/getting-started/**`, `docs/windows-portable.md`, `docs/docker-environments.md` (moved with a plain `mv`), `docs/guides/first-comparison.md`. |
| U4 | `01a11f7c-d8b2-7f82-99c6-f5f2a6bf4c55` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `docs/guides/how-it-works.md`, `sources-and-labels.md`, `analysis-modes.md`, `hdr-tonemapping.md`, `presets-history-generated-data.md`, `publishing-and-webhooks.md`, `configuration-recipes.md` (delete). |
| U5 | `01a11f7c-ed09-76f3-84f8-8be7ed73c41a` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `docs/guides/audio-alignment.md`, `docs/guides/vsview-review.md` (new), `docs/guides/troubleshooting.md`. |
| U6 | `01a11f7c-fb89-7cd2-99ce-b6d7dceaaf43` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `docs/guides/reports-and-overlays.md`. |
| U7 | `01a11f7d-0a77-73b1-85ca-48eb406bb757` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `docs/reference/**`, `tests/test_cli_contract_docs.py`. |
| U8 | `01a11f7d-1ac5-7411-bc7f-ca71031d92d0` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `docs/current-cli-contract.md`, `docs/ENGINEERING_RUNBOOK.md`, `docs/media-runtime-windows-validation.md`, `tests/windows_portable/test_windows_portable_docs.py`. |
| U9 | `01a11f7d-2aaa-74d3-b6fd-0738025408d0` | `worker_luna` | `gpt-5.6-luna` | `xhigh` | `SECURITY.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/release-evidence/2026-07-28-windows-initial-release.md`, `docs/plans/2026-08-17-documentation-v2-screenshot-remediation.md`, `.github/workflows/docs.yml`, `tests/workflows/test_docs_workflow.py`. |

Wave-A unit acceptance is complete; rendered QA and review are pending. U10 awaits
completed and reviewed wave A and the maintainer's physical Windows patch.

### Integration progress and maintainer resolutions (2026-10-09)

| Unit | Commit | Acceptance observed by the orchestrator |
| --- | --- | --- |
| U2 | `8db21a2e3808b2b1b629c8751595ffcb271288bb` | Exact CSS, home, navigation, palette blocks; no unrelated TOML keys changed; TOML parse and whitespace passed; all 13 legacy-class exclusions passed. |
| U7 | `90bad26a` | Fresh command help, aliases, shapes, choices, persistence map, schema defaults, exact reference tables, forbidden strings, deletion, TOML, 4 documentation tests, pyright, ruff, and explicit-file hooks passed. |
| U6 | `45c474c5` | Exact outline, shortcut table, five figure specifications, retained spans, all forbidden strings, TOML, renderer controls, 47 markup tests, whitespace, and explicit-file hooks passed. |
| U8 | `ff1e6108` | Wizard exit paths, exact contract insertions and moved base spans, TOML, scoped documentation tests, runtime-contract tests, Windows docs/build-script tests, ruff, pyright, whitespace, and explicit-file hooks passed for available cases. Windows/PowerShell-only cases skipped. |
| U9 | `27f9c714` | Exact CHANGELOG bullets and Unreleased scope, contributor block, security strings, front matter/status edits, workflow tuple, YAML parse, 5 workflow tests, ruff, pyright, whitespace, and explicit-file hooks passed. |
| U4 | `b8ccaa9f` | Page outlines, exact Mermaid, live seven-preset table, override-source inspection, ordered prose, figure specification, 18 TOML snippets, every forbidden string, recipe deletion, whitespace, and explicit-file hooks passed. |
| U5 | `fb8cedee` | Outlines, exact tables, source/contract UI and terminal literals, ordered/kept prose, two TOML snippets, every forbidden string, whitespace, and explicit-file hooks passed. |
| U3 | `2a7bb794` | Route cards, outlines, retained installation and Docker spans, moved native block, guard literals, every forbidden string, figure specifications, 5 onboarding tests, whitespace, and explicit-file hooks passed. |
| U1 | `00aa052fae43acc1c0c1918f141958b82c6b7af9` | Media hashes, exact scripts/configuration, run-output evidence, six WebP dimensions and metadata, SVG dimensions and exclusions, both runs' frame-1000 screenshots, five deletions, retained privacy checklist, full-resolution image/SVG inspection, whitespace, and explicit-file hooks passed. |

U8 platform skip reasons: PowerShell 7 unavailable for the portable-build
regression; Windows with PowerShell unavailable for the generated-launcher
regression; Windows PowerShell process semantics unavailable; Windows process-tree
semantics unavailable. These checks do not establish physical Windows acceptance.
Exact wave-level skip counts will be recorded with the wave gate.

The orchestrator requested and independently checked these specification fixes:
U6 restored kept-text line breaks and closing-link text; U4 restored content-point
order and kept spans and wrapped eligible new prose; U5 restored unassigned table
rows, evidence-link order, kept spans, and ordinary-prose guard literals; U7 restored
the shared-options content-point order. None is a kept content deviation.

Maintainer resolutions in the original parent chat:

- U7 stopped after invoking an accidental nonexistent placeholder script (exit 2).
  The maintainer explicitly allowed it to resume; all remaining checks passed.
- U2's ad hoc comparator initially addressed `nav` at the TOML root rather than
  `project.nav`. U8's ad hoc span comparator found a line-wrap mismatch it corrected;
  U5's ad hoc anchor probe incorrectly required sentence-case heading text.
  The maintainer allowed acceptance with those procedural deviations recorded.
- U4 corrected stale line indexes in an ad hoc assertion. The maintainer explicitly
  allowed this and future verified checker bugs to be recorded and accepted only
  after independent checks pass. Real specification or acceptance failures still
  stop the affected unit. Orchestrator diagnostic-script bugs were also corrected:
  nested Markdown fence selection, a global status replacement, headings inside a
  shell fence, and a multiline source replacement; none was accepted as a pass
  until its corrected comparison passed.
- U2's normal commit hook temporarily saved/restored unstaged changes through
  pre-commit's patch mechanism. No `git stash` command was issued. The maintainer
  authorized explicit-file pre-commit runs followed by
  `git -c core.hooksPath=/dev/null commit` for subsequent commits to avoid that
  behavior while retaining hook checks. Ruff formatted one line in U7's new test
  and wrapped U9's long assertion; checks were rerun successfully afterward.
- The terminal-run-complete caption conflicted with the style guide's ban on
  "just". The maintainer chose to remove that word from both the capture
  specification and U3's figure caption. The specification change is
  orchestrator-owned and remains pending the final plan-record commit.

U1 stopped on a Docker out-of-memory event (comparison exit 137), after matching
both official media hashes, successfully building image
`sha256:c513ca2661974aa86d2eda0ed58e8bc88ae095d4422d4624cb89a5aa99faea2f`,
and a successful dry run. No U1-owned repository file changed. Docker had about
7.65 GiB allocated on the 32 GiB Mac with unrelated Supabase workloads running.
The maintainer confirmed increasing the memory cap. Docker reports
16,745,824,256 bytes (about 15.60 GiB). U1 was instructed to retry the unchanged
command under its environment-failure rule, clearing only its known partial
outputs and preserving the OOM evidence. The comparison retry and diagnostic run
exited 0. The original successful dry run was retained with the same source,
image, configuration, and media. The orchestrator rehashed the media, inspected
the run artifacts and output, and independently checked the assets. U1 diagnosed `TERM=dumb` affecting Rich's width,
cleared that process environment to `TERM=xterm-256color`, and reran the unchanged
converter. Capture decisions and scripts stayed fixed. Explicit-file hooks removed
trailing whitespace from both SVGs. U1 regenerated scratch outputs and the parent
confirmed that only trailing ASCII spaces/tabs differed; both final SVGs rendered
correctly and all checks passed.

All wave-A units are accepted and committed. API-reference drift, strict build,
search scope, the full guard-test list, and link residue passed, in order. The guard
tests skipped 32 cases: 1 needs PowerShell 7 for the portable build, 1 needs Windows
with PowerShell for the generated launcher, 27 need Windows PowerShell process
semantics, and 3 need Windows process-tree semantics. Those skips establish no
physical Windows acceptance. The asset inventory and page references pass for
available files; the panel file and embed are explicitly deferred to U10. An initial
inventory probe incorrectly required that pending embed and was corrected. The QA
harness's initial lazy-image wait was corrected before any rendered-QA verdict.
Rendered QA produced screenshots for every checklist row at both required sizes
and schemes under `.tmp/docs-refresh-qa/wave-a/`, with DOM evidence and verdicts
in `metrics.json`, `behavior-probe.json`, and `QA.md`. Three dark component rows
fail: home route descriptions, mobile home step prose, and installation-route
descriptions inherit light-root `--fc-muted = #0000008c`; the route borders likewise
inherit `--fc-line = #0000000d`. U2's stylesheet still exactly matches the supplied
specification. The maintainer approved the recommended correction in the parent
chat ("yes u2 can do what it needs if thats what you recommend"). The orchestrator
amended the exact visual-spec slate block with those two aliases and instructed U2
to apply only that correction. U2's two-line fix passed exact-block matching,
every legacy-class exclusion, whitespace, and explicit-file hooks independently
in both child and parent. Commit: `1106ee2c25d0dad0af71df8ea2d37ab276eb8e18` —
`docs(site): correct dark-scheme tokens (U2)`. The strict rebuild passed with no
issues. Initial QA evidence is preserved under
`.tmp/docs-refresh-qa/wave-a/initial-css/`. Corrected rendered QA passes every
checklist row for available assets, in all four required contexts, with 34 original
viewport screenshots per context. Extra 960 × 900 evidence confirms the stacked
hero and two-column step breakpoint. Dark aliases now equal the theme's dark
muted-text and border values. Privacy-reviewed physical Windows recaptures and the
VSView panel remain U10. The local preview and owned Chrome processes were stopped
after QA.
The remaining rows pass for available assets.
The initial clipboard and toggle probes used outdated/wrong selectors; corrected
checks confirm 10 copy buttons for 10 code blocks and theme-toggle persistence in
all four contexts. Card focus rings live on the card; screenshot evidence confirms
visibility. All checked pages have zero horizontal overflow and all images load.

For the explicit independent-run requirement, the orchestrator preserved the five
known U1 generated entries in ignored `capture/accepted-u1-generated/`, confirmed
the configured `generated/` empty, and reran the commands unchanged, with separate
logs in ignored `capture/parent-acceptance/`. The dry run exited 0, but the comparison
exited 137 during rendering after successful analysis. Docker still reports about
15.60 GiB. The Docker event query retained only the most recent 256 records and no longer
covered the failing container. U1's read-only diagnosis found coincident OOM
notifications in Docker Desktop backend log line 3426 and VM console lines 305–306,
at 07:49:27 UTC, immediately before removal of the exact comparison container.
That strongly supports VM memory exhaustion; no retained process-specific kernel
report or OOMKilled flag was accessible. The diagnostic command was not started.
The maintainer was asked to confirm 24 GiB is applied for an unchanged retry, or
explicitly accept the original successful runs with the failed repeat recorded. Its successful
capture artifacts and committed assets remain preserved. Thus independent U1 run
acceptance is blocked despite the original successful child run.

The independent reviewer chat has not run while these blockers remain.

The maintainer confirmed applying a 20 GiB Docker cap to leave RAM for Codex and
other host work, and explicitly authorized stopping the Gridrace containers.
Docker reports 20,940,111,872 bytes (about 19.50 GiB). The orchestrator identified
and stopped the 11 running containers belonging to the single
`gridrace-remediation-u3-20261008` Compose/Supabase project; stop exited 0 and no
container remained running. Containers and volumes were retained. The four known
failed-parent output entries were preserved in ignored
`capture/parent-failed-16g-generated/`, and `generated/` was confirmed empty.
All three unchanged parent commands passed: dry run, comparison retry, and
diagnostic run, with separate logs in `capture/parent-acceptance-20g/`. Frame-1000
screenshots exist for both sources in both expected folders; the diagnostic PNGs
are 3840 × 2160, and an independently inspected 1920 × 1080 crop shows the complete
diagnostic block. This resolves the U1 independent acceptance blocker. The original
successful capture assets remain unchanged. Every wave-A gate and available QA row
now passes; the documented Windows/PowerShell skips and U10 deferrals remain.

### Wave A independent review dispatch

- Review chat: `01a11fbd-c715-7f33-ae1c-7fdb9b841d77`, host `local`.
- Preset: `reviewer`, read from `.codex/agents/reviewer.toml`; actual model
  `gpt-6.1-sol`, effort `high`, both passed explicitly to `create_thread`.
- Scope: `e3f5681b6202645cd91ffd83f15d3788aec9dbfc` through
  `1106ee2c25d0dad0af71df8ea2d37ab276eb8e18`, with the current human-amended
  capture/visual specifications and execution record. Owned write files: none.
- Inputs: complete plan and assets, applicable repository instructions, current
  source/authority, and `.tmp/docs-refresh-qa/wave-a/` screenshots and evidence.
- Required report: plan fidelity and deviations register; full style and exclusion
  checks; every changed statement verified against code/authority with file:line
  evidence and coverage limits; visual specification/checklist review of screenshots.
- One terminal callback to this orchestrator, authorized by the original human
  message cited under Baseline and dispatch. Review adjudication is pending; no
  implementation child is active. U10 still awaits reviewed wave A and the physical
  Windows patch; assets have not been accepted and this plan remains Active.

### Wave A review adjudication (in progress)

R1 (P2): the HDR guide and configuration reference prescribe that four tonemap
values override the preset only when written in the file. The reviewer traced
environment settings through `schema.py:52-72`, `loader.py:92-112`,
`preflight.py:410-411`, and `render/prepare.py:55-65`. The orchestrator verified
that source path and reproduced it with a temporary config file: all four
environment values are explicit even when absent from TOML; an environment target
of 160 overrides a TOML target of 100; the actual resolver applies all four values
and still gives CLI target/curve precedence. This is a specification/source
conflict, not an implementer departure. Disposition: accepted after the maintainer
approved the wording correction. The orchestrator amended the two specification
passages to include explicitly supplied file or environment values and preserve
CLI target/curve precedence. Focused corrections were dispatched to the same U4
and U7 children, each owning only its affected page. Integration and affected gates
are pending, then the same independent reviewer will resume.

The reviewer stopped at R1 as required. Its other factual coverage, style and
every exclusion check, and screenshot review remain incomplete; none is accepted
as passed. Its read-only diagnostic invocation errors (oversized thread turn
limit and two guessed nonexistent paths) were corrected and reported; they are
recorded under the maintainer's approved verified-checker-bug handling, not as
passing repository checks. No reviewer edit or Git mutation occurred.
U10 has not run and assets have not been accepted; this plan remains Active.

R1 integration: U4's HDR paragraph and U7's configuration sentence match the
human-approved specification amendments, with no other page changes. The parent
verified the complete diff, each unit's exclusions separately, both TOML snippets,
the CLI documentation guard (4 passed), whitespace, and explicit-file hooks.
An ad hoc U7 comparator initially expected a different line wrap; the corrected
comparison proves the entire file equals HEAD with only the approved sentence
replacement. This is recorded under the approved verified-checker-bug handling.
Commits:

- `c7f1f0a38e87b075922595b48af507d25e175c51` —
  `docs(guides): correct explicit tonemap overrides (U4)`.
- `81d6d00c24d20d8af256866d66aea21c86ad6d0f` —
  `docs(reference): include environment tonemap overrides (U7)`.

The strict build, rebuilt search-scope check, full seven-module guard list, and
link-residue check pass after R1; the same 32 Windows/PowerShell skips remain.
API documentation and product code were unchanged, so the existing API-drift pass
remains applicable. Focused rendered QA refreshes Configuration and HDR in all
four required contexts; unchanged rows retain their prior screenshot evidence.

R1 focused QA passes: both changed paragraphs render in light and dark at
1440 × 900 and 390 × 844, with zero page overflow. Configuration's eleven tables
remain contained by their wrappers, and the HDR figure loads in its frame.
`r1-metrics.json`, refreshed `07-config-*` screenshots, and extra `r1-hdr-*`
screenshots record the new evidence; QA.md explains reuse of unchanged rows.
All external requests were blocked before delivery. The same reviewer is resumed
against `e3f5681b6202645cd91ffd83f15d3788aec9dbfc` through
`81d6d00c24d20d8af256866d66aea21c86ad6d0f` to complete the previously unfinished
coverage. R1 is resolved; independent review remains pending.

R2 (P2, QA evidence): the reviewer found that the original light-phone primary
button screenshot lacks the focus ring recorded separately in browser metrics.
Disposition: accepted as an evidence inconsistency; no CSS defect was established.
The original pass evidence for that image is withdrawn and preserved, together
with the four original button images and metrics, in `r2-initial-focus/`.
The parent recaptured all four button contexts after keyboard focus and compositor
frames, recording focus immediately before and after each screenshot. Every new
image visibly shows the brass ring; every synchronized state records the same
focused primary button, `:focus-visible`, a 2 px brass outline, 4 px offset, and
no intervening focus-out event. Replacement originals and
`r2-focus-metrics.json` support the keyboard pass. The old helper sampled state
separately before scrolling and delaying; it cannot establish state at screenshot
time. The exact old discrepancy mechanism remains unproven. No site or CSS change
was needed. QA.md and metrics now distinguish replacement evidence from superseded
images/contact sheets. The same reviewer resumes all remaining coverage; no
complete review pass has been issued. A parent diagnostic search named a nonexistent
JavaScript directory; this read-only invocation error changed nothing and is
recorded under approved checker-bug handling.

R3 (P3, Output layout link labels): accepted. The two retained labels
`Current Architecture` and `CLI Behavioral Contract` at
`docs/reference/output-layout.md:100-101` miss the style guide's mandatory
mechanical corrections for kept text. `pages-reference.md` says to keep the rest,
which explicitly includes these listed corrections; neither label has a verbatim
exception. Both targets are already correct. The same U7 child is assigned only
these two label replacements. No specification amendment or new human decision
is needed. The reviewer reports all available Wave A visual rows passing,
including R2 replacements; final retained-span reconciliation and complete review
verdict remain pending at its required R3 stop.

R3 integration: the parent independently proved the complete Output layout file
equals its previous revision with only those two labels corrected and both targets
unchanged. The CLI-doc guard passes (4 tests), pyright reports no errors/warnings,
ruff and whitespace pass, and explicit-file hooks pass. TOML validation is not
applicable because this page contains no TOML fence. Each relevant exclusion was
checked independently and is absent. Commit:
`5b62ebc7bb4c1de46e8881f1122183c4fe6067c9` —
`docs(reference): correct retained link labels (U7)`.
The strict build, rebuilt search-scope check, and residue scan pass after R3.
API/product inputs, other guard-test obligations, and every visual-checklist row
are unchanged; their prior passing evidence and documented skips remain applicable.
The same reviewer resumes against the range ending at this commit to complete its
remaining reconciliation and final verdict.

R4 (P3, retained Sources page wrapping): accepted and assigned to U4. The
complete-page reconstruction from the specification base contains the prescribed
report-control replacement and source terminology correction; the current page
additionally splits the retained reference sentence across two physical lines.
The keep rule permits only the listed changes. No evidence establishes that this
extra wrapping is strictly better, so it will be reverted to the base line break
while preserving both required phrase replacements. No specification decision or
human approval is needed. Prior factual/visual coverage remains applicable; the
reviewer's final retained-byte and net-scope reconciliation is still pending.

R4 integration: the parent proved the entire Sources page equals HEAD with only
the extra newline removed, and equals the specification base with only the two
prescribed phrase replacements. All nine isolated TOML snippets pass; `v1.2` is
absent; whitespace and explicit-file hooks pass. Commit:
`d0d1189c4d7aca2519481ff5916dba7c4d661ce8` —
`docs(guides): restore specified retained wrapping (U4)`.
Strict build, rebuilt search scope, and residue pass. This source newline produces
the same rendered paragraph and changes no product/API/test input or visual
checklist page; prior guard/API/visual evidence and skip reasons remain applicable.
The parent initially misstated that this page had no TOML fences in the correction
packet, immediately corrected that instruction before acceptance, and validated all
nine snippets independently. The same reviewer resumes through the R4 commit.

### Wave A completion and Windows handoff

The independent reviewer completed its final reconciliation at
`d0d1189c4d7aca2519481ff5916dba7c4d661ce8`: plan fidelity, style and every exclusion,
changed-statement factual evidence, and all available rendered QA rows pass.
Its final net-scope audit accounts for all 53 assigned path endpoints, confirms
the nine old endpoints are absent, and finds no changes to product code, tools,
dependencies, lockfiles, repository instructions, or U10-owned files. The parent
accepts the completed review against its independent unit/gate/fix evidence.
The review used `reviewer` / `gpt-6.1-sol` / `high` throughout in the single chat
`01a11fbd-c715-7f33-ae1c-7fdb9b841d77`.

All four review findings are adjudicated and resolved:

| Finding | Disposition and evidence |
| --- | --- |
| R1 | Accepted source/specification conflict; human-approved environment/file wording, corrected by U4/U7 and independently verified |
| R2 | Accepted QA-evidence inconsistency; initial image pass withdrawn, synchronized replacement screenshots and state show the required focus ring; no CSS change |
| R3 | Accepted mandatory kept-text link corrections; U7 changed only two labels, with complete-page equality and unchanged targets |
| R4 | Accepted unauthorized retained wrapping; U4 reverted only the newline, with full specification-base reconstruction |

No unauthorized content/design deviation remains. The human-approved caption-word,
dark-token and tonemap-wording amendments are current specification decisions.
U1's approved environmental retries and output-preserving terminal/whitespace
normalization, approved checker-bug handling, and explicit-file hook/commit procedure
remain recorded procedural exceptions with evidence and limits. No absent Windows
case was treated as a platform pass. The unknown cause of the superseded R2 image
discrepancy is not represented as proven; current synchronized evidence resolves
the required visual check.

Wave A is complete at the SHA above. The maintainer will make that commit available
on the physical Windows host and run the committed prompt's "Physical Windows host"
section, then return `u10.patch`. No push, branch switch, or Windows job is performed
by this orchestrator. The approved unstaged plan/asset amendments will be committed
with the final outcome record, as authorized by the closing step; U10's physical
capture instructions themselves are unchanged by those amendments. U10, its fresh
review, maintainer asset acceptance, and the closing outcome commit remain open.
Status stays Active. The final seven-module guard result retains 32 skips:
1 PowerShell 7 portable build, 1 Windows/PowerShell generated launcher,
27 Windows PowerShell process semantics, and 3 Windows process-tree semantics.
All available QA checklist rows pass at both specified widths and schemes, with
physical Windows recaptures and the visible native panel explicitly deferred.

### Wave B integration and verification (2026-10-10)

The maintainer completed U10 in a single existing Windows session, explicitly
overriding the model-preset, clean-clone and no-commit requirements. Actual model
and effort, confirmed by the maintainer: `gpt-6.1-sol` / `medium`; selection was by
the maintainer, not an implementation preset. No child chat was dispatched by
this orchestrator for U10; the Windows chat ID was not provided.
U10 was committed and pushed on that host, and the maintainer fast-forwarded this
checkout to `e6808eabd719c6175c6cf32cc2a871e7ae727687` —
`docs(images): add physical Windows captures (U10)`. The maintainer explicitly
directed skipping `git apply --check`/`git apply` because the commit is already
present. The orchestrator performed no push or fast-forward and will not create
a duplicate U10 commit.

The parent `9edf1a4c65ad3cb2da9a885c8b866447ac97da80` — doctor slow.pics probe
removal — is separate work expressly excluded from this plan and review. The
U10 review range is only that parent through `e6808eab`, not a range including
the doctor's source or authority changes. U10's recorded bundle-source commit
correctly identifies that parent.

The parent independently verifies exactly the five U10-owned paths, only the
VSView figure insertion and install figure dimensions on their pages, unchanged
Set 1 provenance/privacy text, and Set 2 completion. The only extra separator
newline precedes Set 2's replacement review; a comparator initially included that
separator in its kept-span assertion and was corrected under approved checker-bug
handling. No repository content was changed by that diagnostic correction.
Both original images were inspected at full resolution: installer checksum and
successful final instruction, generic paths; panel ready with 2/2 positions
captured at frame 1000 and provisional audio explicitly NOT APPLIED. No private
strings are visible. Dimensions are 1109 × 119 PNG and 748 × 1142 WebP, within
1200/900 px width limits, with matching figure dimensions. WebP contains only a
VP8 chunk; PNG contains only image, sRGB, gamma and DPI chunks. The complete
ten-asset inventory is present. Windows execution details and cleanup are recorded
in Set 2; they are reported host evidence, not commands rerun on this Mac.

Rerun checks pass: API-doc drift, strict build, rebuilt search scope, the full
seven-module guard list, whitespace, and link residue. The same 32 native
Windows/PowerShell tests skip on the Mac, with the four reasons/counts above.
Those skips are not claimed as covered by the captures. Fresh rendered evidence
for Windows portable and VSView alignment review is saved in
`.tmp/docs-refresh-qa/wave-b/` at 1440 × 900 and 390 × 844, light and dark, with
site storage cleared and external requests blocked before delivery. Both rows
pass: loaded framed images, matching dimensions, centred narrow panel, contained
code overflow, ten copy buttons, zero page overflow, appropriate light shadow and
dark ring. A fresh reviewer will independently inspect this evidence and U10 only.

Wave B fresh review dispatch:

- Real chat ID: `01a124ee-22de-7941-b950-8180f7639a8f`, host `local`.
- Preset read from this checkout: `reviewer`; actual `gpt-6.1-sol` / `high`,
  both passed explicitly to `create_thread`.
- Reviewed range: `9edf1a4c65ad3cb2da9a885c8b866447ac97da80` through
  `e6808eabd719c6175c6cf32cc2a871e7ae727687` (U10 only; parent change excluded).
- Write ownership: none. Inputs: full current plan and assets, actual U10 diff,
  original captures, committed host record, and Wave B screenshot/evidence folder.
- Required coverage: plan fidelity/deviations, style/every exclusion, every changed
  factual statement with file:line/source/host-evidence limits, and actual visual QA.
- One terminal callback to the original orchestrator under the original human
  authorization. Review/adjudication and the final outcome commit remain pending;
  explicit maintainer acceptance of the asset set has not been recorded, so the
  plan remains Active.

### Wave B review adjudication

The fresh reviewer completed U10-only review in chat
`01a124ee-22de-7941-b950-8180f7639a8f` with `reviewer` / `gpt-6.1-sol` / `high`.
No findings or requested fixes remain. The parent accepts the report against its
independent scope, metadata, pixel, source, and gate evidence. Whole-file
reconstruction confirms exactly U10's five paths and sections; Set 1 remains
unchanged. The separator newline is retained at the owned Set 2 replacement
boundary because it separates the two capture-set paragraphs and changes no
kept prose. It is not a content or design deviation. Both exact captions/alt texts,
all applicable exclusions, image references and dimensions, all changed factual
fields, and all 20 rendered viewport screenshots were reviewed. The reviewer
independently repeated original-image privacy and metadata checks, and identified
no source/specification conflict or misleading visible state.

Windows build, scaling, original stream/ZIP hashes, conversion quality, unscaled
export and exact PATH/no-sidecar cleanup are bounded reported host execution
facts; neither reviewer nor Mac orchestrator claims to have reproduced those host
operations. The bundle checksum is visible in the installer image and matches the
record; frame 1000, both captured roles, readiness and provisional audio NOT APPLIED
are visible in the native panel. The gray `linkColor` metrics field samples the
breadcrumb, not body-link palette; it is not used as evidence of amber body links.
An oversized reviewer thread-read request/parser error was corrected with supported
pagination under approved diagnostic-bug handling; no failed invocation counted
as acceptance. There are no unresolved U10 review findings or implementation stops.

### Final outcome record (2026-10-10)

Implementation and both independent wave reviews are complete. The closing commit
is `docs(plan): record the documentation refresh outcome` (this record and the
four human-approved specification amendments). The already present Windows U10
commit is retained without duplication. The separate doctor commit `9edf1a4c` is
excluded from this plan's commit manifest and review scope. No orchestrator push,
PR, branch switch, worktree, dependency/lockfile change, or live-service request was
performed. The three unrelated untracked prompts remain untouched. The authorized
Gridrace stack stop remains in effect; no restart is performed by this plan.

Final asset acceptance: the maintainer explicitly accepted the full ten-asset set
from U1 and U10 on 2026-10-10. Status is Historical; implementation, both reviews,
and asset acceptance are complete. Acceptance arrived after outcome commit
`cec4bfcd9bbac633b4d87de8fdb754e50b513161`, so a follow-up status commit records it
without rewriting history.

| Unit | Preset/selection | Actual model | Actual effort |
| --- | --- | --- | --- |
| U1 | worker | gpt-6.1-sol | medium |
| U2 | worker_luna | gpt-5.6-luna | xhigh |
| U3 | worker_luna | gpt-5.6-luna | xhigh |
| U4 | worker_luna | gpt-5.6-luna | xhigh |
| U5 | worker_luna | gpt-5.6-luna | xhigh |
| U6 | worker_luna | gpt-5.6-luna | xhigh |
| U7 | worker_luna | gpt-5.6-luna | xhigh |
| U8 | worker_luna | gpt-5.6-luna | xhigh |
| U9 | worker_luna | gpt-5.6-luna | xhigh |
| U10 | Maintainer-selected single Windows session; preset requirement overridden | gpt-6.1-sol | medium |
| Wave A review | reviewer | gpt-6.1-sol | high |
| Wave B review | reviewer | gpt-6.1-sol | high |

| Gate | Final result and limits |
| --- | --- |
| API-doc drift | Pass; Wave A and current Wave B check |
| Strict documentation build | Pass; no issues, including affected-fix and Wave B reruns |
| Search scope | Pass; no internal-page leakage |
| Seven-module guard list | All available cases pass; 32 skips below, unchanged after Wave B |
| Link residue | Pass; no matches, expected rg exit 1 |
| Asset inventory/dimensions/privacy | All ten assets and specified embeddings present; both sets inspected, width limits and figure dimensions match |
| Wave A rendered checklist | All ten rows pass at 1440 × 900/390 × 844, light/dark; extra 960 px breakpoint evidence; archived failed images excluded |
| Wave B rendered checklist | Windows portable and VSView alignment review pass in all four required contexts; original physical captures and 20 viewport images inspected |
| Windows patch application | Skipped by explicit maintainer instruction: pushed commit already present after externally performed fast-forward |
| Repeating Windows host operations on Mac | Not performed; physical execution reported by maintainer/Set 2 record and independently inspected as images/source |

Guard skips remain: 1 PowerShell 7 portable-build test; 1 Windows/PowerShell
generated-launcher test; 27 Windows PowerShell process-semantics cases; 3 Windows
process-tree cases. Physical captures do not replace these tests, and no full
Windows runtime-profile or release acceptance is claimed.

Review adjudications: R1 accepted and corrected with human-approved environment
wording; R2 accepted evidence inconsistency, original pass withdrawn and replaced
by synchronized focus captures; R3 required sentence-case link labels corrected;
R4 unapproved wrapping reverted. Wave B has no findings. No unauthorized content
or design deviation remains. The three human-approved specification amendments
and the recorded procedural exceptions are retained with their evidence; no failed
acceptance was converted to a pass. Known historical limitations remain explicit,
including the unproven cause of the superseded R2 screenshot discrepancy.

Implementation/open status: U1–U10 and both reviews complete, no blocked unit.
The complete asset set is accepted; no item remains open for this documentation
refresh. Unrelated physical release/runtime acceptance plans retain their statuses
and are outside this documentation refresh.

| Commit SHA | Subject |
| --- | --- |
| `e3f5681b6202645cd91ffd83f15d3788aec9dbfc` | docs(plan): add the documentation refresh plan |
| `8db21a2e3808b2b1b629c8751595ffcb271288bb` | docs(site): apply the viewer-matched site frame (U2) |
| `90bad26aa8d6fef34b6b67dccb4dfd7a5a0a4650` | docs(reference): split commands and configuration (U7) |
| `45c474c52783af965290e1198f95e4bf3c59316c` | docs(reports): refresh the report guide (U6) |
| `ff1e6108c1dce20a16b050a164d7e9285f3fc6a6` | docs(contracts): consolidate authority and validation text (U8) |
| `27f9c71454a667d1db64d91b6d925f9a868b9411` | docs(project): refresh repository docs and search hygiene (U9) |
| `b8ccaa9f70d0eae986678e75fb62bfb4b6bfbace` | docs(guides): refresh pipeline and topic guides (U4) |
| `fb8cedee85ff2391c615e603ba0b062b7f172ade` | docs(alignment): consolidate alignment and VSView guidance (U5) |
| `2a7bb79471f4bc5cfe293246ed2b6b4e10e580e1` | docs(onboarding): refresh installation and first comparison (U3) |
| `00aa052fae43acc1c0c1918f141958b82c6b7af9` | docs(images): refresh macOS report and terminal captures (U1) |
| `1106ee2c25d0dad0af71df8ea2d37ab276eb8e18` | docs(site): correct dark-scheme tokens (U2) |
| `c7f1f0a38e87b075922595b48af507d25e175c51` | docs(guides): correct explicit tonemap overrides (U4) |
| `81d6d00c24d20d8af256866d66aea21c86ad6d0f` | docs(reference): include environment tonemap overrides (U7) |
| `5b62ebc7bb4c1de46e8881f1122183c4fe6067c9` | docs(reference): correct retained link labels (U7) |
| `d0d1189c4d7aca2519481ff5916dba7c4d661ce8` | docs(guides): restore specified retained wrapping (U4) |
| `e6808eabd719c6175c6cf32cc2a871e7ae727687` | docs(images): add physical Windows captures (U10) |
| `cec4bfcd9bbac633b4d87de8fdb754e50b513161` | docs(plan): record the documentation refresh outcome |
