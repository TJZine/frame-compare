---
search:
  exclude: true
---

Status: Active
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
