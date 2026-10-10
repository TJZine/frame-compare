---
search:
  exclude: true
---

Status: Historical
Scope: Subordinate specification for the completed
[documentation refresh](../2026-10-08-documentation-refresh.md).

The instructions below record that workstream's authoring requirements.
Current behavior is documented in the maintained guides and references.

# Documentation refresh: reference, authority, and repository files

Part of the [documentation refresh plan](../2026-10-08-documentation-refresh.md).
Owners: U7 (reference pages and the configuration guard test), U8 (authority and
project documents and the Windows docs test), U9 (repository files, internal-page
hygiene, and the docs workflow). Apply the [style guide](style-guide.md) to new
prose. "Verbatim" and "exactly" mean not one character changes. Line numbers refer to base commit `80beafdcdabc7ac556f78fada5e7593b89e8880c`.

## `docs/reference/commands.md` — new (U7)

```text
# Commands
## Command map
## Shared options
## Run
## Wizard
## Doctor
## Preset
## History
## Version
## Exit codes
## Automation
```

Source of truth: `frame-compare --help` and each subcommand's `--help` at the
integrated commit (captured in scratch on 2026-10-08 under
`.tmp/docs-refresh-2026-10-08/cli/`), `src/frame_compare/config/overrides.py`
(`CLI_OVERRIDE_MAP`), and `docs/current-cli-contract.md`. Before writing, rerun the
help commands and stop if any option differs from the tables below. "Differs" means a
different option name, short alias, value shape or choice list, or `--write-config`
persistence (compare with `CLI_OVERRIDE_MAP`). The Effect column is this plan's own
wording and is not compared with the help text.

- **Intro:** one sentence: this page lists every command and option; exact behavior
  is in the `[CLI behavioral contract](../current-cli-contract.md)`.
- **Command map:** this table, exactly:

  | Command | Purpose |
  | --- | --- |
  | `frame-compare version` | Print the installed version |
  | `frame-compare wizard` | Set the input directory, generated-data root, reference, and frame selection interactively |
  | `frame-compare doctor` | Check the media runtime and optional integrations |
  | `frame-compare run` | Compare sources and write screenshots and a report |
  | `frame-compare preset list` | List saved presets |
  | `frame-compare preset save <name>` | Save the selected configuration as a preset |
  | `frame-compare preset apply <name>` | Apply a preset to the selected configuration |
  | `frame-compare history list` | List recorded runs, newest first |
  | `frame-compare history open <run-name>` | Open one recorded report by its exact run name |

- **Shared options:** `--root`/`-r` (workspace root, default `.`) and
  `--config`/`-c` (config file; relative paths resolve from `--root`; default
  `config/config.toml`). Accepted by `run`, `wizard`, `preset apply`, `preset save`,
  `history list`, and `history open`. `preset list` accepts `--config` but ignores it
  and reads presets from `<root>/config/presets`. `doctor` and `version` accept
  neither. The installed Windows shim supplies the bundle or AppData config when you
  omit `--config` (link the contract's
  `[shared path rules](../current-cli-contract.md#shared-path-resolution-rules)`).
- **run:** one sentence: options apply to one run; `--write-config` saves the options
  marked "Saved" and exits without running. Then this table, exactly:

  | Option | Value | Effect | Saved by `--write-config` |
  | --- | --- | --- | --- |
  | `--root`, `-r` | path | Workspace root | No |
  | `--config`, `-c` | path | Config file | No |
  | `--input`, `-i` | path | Input directory | `paths.input_dir` |
  | `--frames` | `FRAME[,FRAME…]` | Reference source frames to render | `analysis.user_frames` |
  | `--random-frame-count` | count | Random frames | `analysis.random_frame_count` |
  | `--dark-frame-count` | count | Dark frames; needs analysis | `analysis.dark_frame_count` |
  | `--bright-frame-count` | count | Bright frames; needs analysis | `analysis.bright_frame_count` |
  | `--motion-frame-count` | count | Motion frames; needs analysis | `analysis.motion_frame_count` |
  | `--seed` | integer | Frame-selection seed | `analysis.random_seed` |
  | `--tm-preset` | preset name | Tonemap preset | `color.preset` |
  | `--tm-target` | nits | Tonemap target | `color.target_nits` |
  | `--tm-curve` | `bt2390`, `spline`, `reinhard` | Tonemap curve | `color.tone_curve` |
  | `--overlay` | `minimal`, `standard`, `diagnostic`, `none` | Baked overlay mode | `screenshots.overlay_mode` |
  | `--force-interactive-alignment` | — | Require a successful VSView review | `audio_alignment.force_interactive` and `audio_alignment.use_vsview` |
  | `--no-upload` | — | Turn slow.pics upload off | `slowpics.auto_upload = false` |
  | `--skip-analysis` | — | Skip metric analysis; dark, bright, and motion counts must be zero | No |
  | `--skip-metadata` | — | Skip the TMDB lookup | No |
  | `--no-cache` | — | Do not read or write the analysis cache | No |
  | `--from-cache-only` | — | Require valid cached analysis; never recompute | No |
  | `--dry-run` | — | Show what a run would use and create, without side effects | No |
  | `--write-config` | — | Save the effective configuration and exit | No |
  | `--diagnose-paths` | — | Print resolved paths as JSON and exit | No |
  | `--json` | — | Machine-readable output on stdout; diagnostics on stderr | No |
  | `--no-color` | — | Plain output | No |
  | `--quiet`, `-q` | — | Hide progress and detailed summaries | No |
  | `--verbose`, `-v` | — | Debug logging and detailed errors | No |

  Then: runs and dry runs reject `--no-cache` combined with `--from-cache-only`
  (`docs/current-cli-contract.md:930-932`); an invalid
  `--overlay`, `--tm-preset`, or `--tm-curve` value names the option and lists its
  choices before any work starts. Preset names: `reference`, `filmic`, `contrast`,
  `bt2390_spec`, `spline`, `bright_lift`, `highlight_guard`. Then exactly:
  "`frame-compare run --help` lists the same options under six headings: Workspace and
  configuration, Sources and frame selection, Rendering and alignment, Reports and
  publishing, Planning and diagnostics, and Output modes."
- **wizard:** one paragraph from the contract's wizard section: requires an
  interactive terminal; prompts for input directory, generated-data location,
  reference, and a frame goal (`Random spot check`, `Visual coverage`,
  `Specific frame numbers`, or `Keep current frame selection`); shows a review and
  writes only after you confirm; prints suggested next commands. Link
  `[Your first comparison](../guides/first-comparison.md)`.
- **doctor:** checks VapourSynth, L-SMASH-Works, vs-placebo, FFMS2, FFmpeg, VSView, and
  the optional slow.pics and TMDB integrations; `--json` emits the report as JSON; it
  exits with the dependency error code when a required check fails. The slow.pics
  check contacts the service.
- **preset:** presets live in `<root>/config/presets`; `save` omits secrets; link
  `[Presets, history, and generated data](../guides/presets-history-generated-data.md)`.
- **history:** `list` reads `run_result.toml` records under the generated-data root,
  `--json` for automation; `open` opens one report by exact name.
- **version:** prints `frame-compare <version>`.
- **Exit codes:** one sentence and a link:
  `[exit codes and error families](../current-cli-contract.md#exit-codes-and-error-families)`.
- **Automation:** current `commands-and-configuration.md:150-161`, kept (mechanical
  corrections apply).

## `docs/reference/configuration.md` — new (U7)

```text
# Configuration
## How settings combine
## Environment variables and secrets
## Paths
## Runtime
## Sources
## Analysis
## Audio alignment
## Screenshots
## Color
## Report
## slow.pics
## TMDB
## Logging
```

Source of truth: `src/frame_compare/config/schema.py` and
`src/frame_compare/config/schema_models.py` at the integrated commit. Every table row
below was checked against them on 2026-10-08. The H2 for each TOML table is the
outline name above; its anchor is `#paths`, `#runtime`, `#sources`, `#analysis`,
`#audio-alignment`, `#screenshots`, `#color`, `#report`, `#slowpics`, `#tmdb`, or
`#logging`. In each section's text, name the TOML table in a code span (`[paths]`).

- **How settings combine:** precedence, highest first: run options, environment
  variables, the TOML file, built-in defaults. The default file is
  `config/config.toml` under the workspace root. Unknown top-level tables are ignored;
  an unknown key inside a Frame Compare table fails validation. Use the wizard for
  common settings and edit TOML for the rest. Link
  `[config validation](../current-cli-contract.md#config-validation-logging-and-migration)`.
- **Environment variables and secrets:** names are `FRAME_COMPARE_` plus the table and
  key joined by `__`, upper case: `FRAME_COMPARE_SLOWPICS__WEBHOOK_URL`,
  `FRAME_COMPARE_TMDB__API_KEY`, `FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD`. Keep secrets
  in the environment; generated config and preset files never contain
  `slowpics.webhook_url` or `tmdb.api_key`, and every configuration error shows their
  values as `<redacted>` (`docs/current-cli-contract.md:1597-1599`). Example block:

  ```bash
  export FRAME_COMPARE_SLOWPICS__WEBHOOK_URL="<secret>"
  ```

- **Each table section:** one sentence naming the TOML table in a code span and the
  guide that explains it (for example "`[paths]` is explained in
  `[Presets, history, and generated data](...)`."), then the table. For the three
  sections without a guide, the sentence is exactly: `[runtime]`: "`[runtime]` controls
  VapourSynth's frame cache."; `[tmdb]`: "`[tmdb]` controls the optional TMDB metadata
  lookup; see the run command contract." (with that link); `[logging]`: "`[logging]`
  controls run log output." Every table uses the columns `Key | Values | Default | Effect`, and the Key
  cell is the full dotted key in a code span. The guard test reads these cells.

### Table content (copy exactly)

`paths` — guide: `[Presets, history, and generated data](../guides/presets-history-generated-data.md)`

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `paths.input_dir` | path | `"comparison_videos"` | Directory searched for sources; may be outside the workspace root |
| `paths.generated_dir` | path | `"generated"` | Generated-data root for run folders and shared caches; may be outside the workspace root |
| `paths.config_dir` | path | `"config"` | Configuration directory; must stay inside the workspace root |

`runtime` — no guide. Follow the table with: "The cap applies to VapourSynth's frame
cache, not to total process memory, and does not affect audio alignment buffers. A
smaller cache can increase decoding work." and this snippet:

```toml
[runtime]
memory_limit_mb = 4096
```

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `runtime.memory_limit_mb` | integer, at least `512` | unset | VapourSynth frame-cache cap in MiB for analysis, rendering, alignment checks, and the VSView session |

`sources` — guide: `[Sources, references, and labels](../guides/sources-and-labels.md)`

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `sources.reference` | selector, `"auto"`, or unset | unset (first discovered source) | Which source is the reference |
| `sources.analysis_source` | `"reference"`, `"fastest"`, or a selector | `"reference"` | Source used for luminance and motion metrics |
| `sources.match_fps` | `"disabled"`, `"assume_reference"`, `"majority"` | `"disabled"` | Common frame-rate interpretation policy |
| `sources.label_mode` | `"stem"`, `"filename"`, `"parsed"` | `"stem"` | How automatic labels are built |
| `sources.label_parser` | `"auto"`, `"guessit"`, `"anitopy"` | `"auto"` | Release-name parser for `parsed` labels |
| `sources.overrides` | table of selector tables | empty | Per-source settings in the rows below |
| `sources.overrides.<selector>.trim_start_frames` | integer, at least `0` | `0` | Frames removed from the start of that source |
| `sources.overrides.<selector>.trim_end_frames` | integer, at least `0` | `0` | Frames removed from the end of that source |
| `sources.overrides.<selector>.active_rect` | `{ x, y, width, height }` | unset | Explicit active picture; must fit the source |
| `sources.overrides.<selector>.effective_fps` | `"num/den"` | unset | Frame rate used to interpret that source's timing |
| `sources.overrides.<selector>.label` | text | unset | Exact label for that source |

`analysis` — guide: `[Frame selection and analysis](../guides/analysis-modes.md)`.
After the table: "User frames and the four counts must request at least 1 and at most
100 frames in total."

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `analysis.user_frames` | list of integers, at least `0` | `[]` | Reference source frames to render |
| `analysis.random_frame_count` | integer, at least `0` | `10` | Seeded random frames |
| `analysis.dark_frame_count` | integer, at least `0` | `0` | Darkest frames; needs metrics |
| `analysis.bright_frame_count` | integer, at least `0` | `0` | Brightest frames; needs metrics |
| `analysis.motion_frame_count` | integer, at least `0` | `0` | Highest-motion frames; needs metrics |
| `analysis.random_seed` | integer | `42` | Seed for random selection |
| `analysis.performance_mode` | `"quality"`, `"performance"` | `"quality"` | Every eligible frame, or a deterministic sample |
| `analysis.ignore_lead_seconds` | number, at least `0` | `0.0` | Seconds at the start excluded from selection |
| `analysis.ignore_trail_seconds` | number, at least `0` | `0.0` | Seconds at the end excluded from selection |
| `analysis.min_window_seconds` | number, at least `0` | `5.0` | Minimum selectable window; a shorter window is extended within the source |
| `analysis.dark_quantile` | `0.0` to `0.5` | `0.05` | Luminance quantile treated as dark |
| `analysis.bright_quantile` | `0.5` to `1.0` | `0.95` | Luminance quantile treated as bright |

`audio_alignment` — guides: `[Audio alignment](../guides/audio-alignment.md)` and
`[VSView alignment review](../guides/vsview-review.md)`

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `audio_alignment.enable` | `true`, `false` | `true` | Run audio alignment |
| `audio_alignment.max_offset_seconds` | number, at least `1` | `30.0` | Largest offset searched in either direction |
| `audio_alignment.use_vsview` | `true`, `false` | `false` | Open the VSView alignment panel after alignment |
| `audio_alignment.force_interactive` | `true`, `false` | `false` | Require a successful panel review |
| `audio_alignment.cache_results` | `true`, `false` | `true` | Store applied and confirmed offsets for reuse |
| `audio_alignment.previous_offsets` | `"disabled"`, `"prompt"`, `"always"` | `"disabled"` | Reuse of previously confirmed offsets |
| `audio_alignment.channel_strategy` | `"mono_downmix"`, `"best_channel"` | `"mono_downmix"` | Channel handling during audio extraction |
| `audio_alignment.reference_stream` | integer, at least `0`, or unset | unset | Reference audio stream number |
| `audio_alignment.comparison_streams` | table of stem = stream number | empty | Comparison audio stream numbers by filename stem |

`screenshots` — guides: `[Reports and overlays](../guides/reports-and-overlays.md)`
and the contract's
`[screenshot surface](../current-cli-contract.md#config-only-screenshot-surface)`

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `screenshots.use_ffmpeg` | `true`, `false` | `false` | Render with FFmpeg instead of VapourSynth; HDR sources then need `color.enable_tonemap = false` |
| `screenshots.overlay_mode` | `"minimal"`, `"standard"`, `"diagnostic"`, `"none"` | `"standard"` | Baked overlay detail |
| `screenshots.include_frame_number` | `true`, `false` | `true` | Include the frame number in baked overlays |
| `screenshots.png_compression` | `0` to `9` | `6` | PNG compression level |
| `screenshots.ffmpeg_timeout_seconds` | number, at least `5` | `30.0` | Timeout for FFmpeg frame extraction |
| `screenshots.geometry_mode` | `"native"`, `"aligned"` | `"native"` | Keep native frames, or scale sources onto one canvas |
| `screenshots.active_rect_detection` | `"provided"`, `"dimension"`, `"aspect_ratio"`, `"auto"` | `"auto"` | Evidence used to find the active picture |
| `screenshots.aligned_scale_policy` | `"largest_active"`, `"smallest_active"`, `"reference_active"`, `"explicit_size"` | `"largest_active"` | Canvas size in aligned mode |
| `screenshots.aligned_target_width` | positive even integer, or unset | unset | Canvas width for `explicit_size` |
| `screenshots.aligned_target_height` | positive even integer, or unset | unset | Canvas height for `explicit_size` |
| `screenshots.vs_writer` | `"auto"`, `"pillow"`, `"fpng"` | `"auto"` | VapourSynth PNG writer |

`color` — guide: `[HDR and tonemapping](../guides/hdr-tonemapping.md)`. After the table:
"`target_nits`, `tone_curve`, `gamma_lift`, and `contrast_recovery` override the preset
only when explicitly supplied in the configuration file or environment variables."

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `color.enable_tonemap` | `true`, `false` | `true` | Tonemap HDR sources to SDR |
| `color.preset` | `"reference"`, `"filmic"`, `"contrast"`, `"bt2390_spec"`, `"spline"`, `"bright_lift"`, `"highlight_guard"` | `"reference"` | Baseline tonemap settings |
| `color.target_nits` | integer, `100` to `1000` | from the preset | Output target luminance |
| `color.tone_curve` | `"bt2390"`, `"spline"`, `"reinhard"` | from the preset | Tone curve |
| `color.gamma_lift` | `true`, `false` | from the preset | Brighten midtones after tonemapping |
| `color.contrast_recovery` | `0.0` to `1.0` | `0.3` | Contrast recovery strength |

`report` — guide: `[Reports and overlays](../guides/reports-and-overlays.md)`

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `report.enable` | `true`, `false` | `true` | Write `report.html` |
| `report.default_mode` | `"slider"`, `"overlay"`, `"diff"`, `"blink"` | `"slider"` | View the report opens in; `overlay` is the Single view |
| `report.include_filmstrip` | `true`, `false` | `true` | Show the filmstrip |
| `report.embed_images` | `true`, `false` | `false` | Embed screenshots in `report.html` |
| `report.auto_open` | `true`, `false` | `true` | Open the report after an interactive local run |

`slowpics` — guide: `[Publishing and webhooks](../guides/publishing-and-webhooks.md)`
and the contract's `[slow.pics surface](../current-cli-contract.md#config-only-slowpics-surface)`

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `slowpics.auto_upload` | `true`, `false` | `false` | Upload after a successful run |
| `slowpics.confirm_upload_after_report` | `true`, `false` | `false` | Ask after the report is written; interactive runs only |
| `slowpics.visibility` | `"public"`, `"unlisted"` | `"public"` | Collection visibility |
| `slowpics.delete_after_upload` | `true`, `false` | `false` | Delete the uploaded local screenshots after the report is done |
| `slowpics.timeout_seconds` | number, at least `10` | `60.0` | Navigation and metadata request timeout |
| `slowpics.max_retries` | `1` to `10` | `3` | Retry budget per request |
| `slowpics.title` | text | `""` | Literal collection title |
| `slowpics.title_template` | template text | `""` | Title built from `${Title}` and other fields; not with `title` |
| `slowpics.title_suffix` | text | `""` | Text appended to the title |
| `slowpics.is_hentai` | `true`, `false` | `false` | slow.pics adult-content flag |
| `slowpics.tmdb_id` | positive integer, or unset | unset | TMDB ID for the collection; needs `tmdb_media_type` |
| `slowpics.tmdb_media_type` | `"movie"`, `"tv"`, or unset | unset | TMDB category for `tmdb_id` |
| `slowpics.remove_after_days` | `0` to `999999` | `0` | Days until slow.pics removes the collection; `0` keeps it |
| `slowpics.image_upload_timeout_seconds` | number, at least `10` | `180.0` | Minimum image upload timeout |
| `slowpics.copy_url_to_clipboard` | `true`, `false` | `true` | Copy the collection URL after upload |
| `slowpics.open_in_browser` | `true`, `false` | `true` | Open the collection URL after upload |
| `slowpics.create_url_shortcut` | `true`, `false` | `true` | Write a `.url` shortcut after upload |
| `slowpics.webhook_url` | HTTPS URL, or unset | unset | Discord-compatible webhook for the collection URL; keep it in the environment |

`tmdb` — no guide; link the contract's
`[run command contract](../current-cli-contract.md#run-command-contract)`.

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `tmdb.api_key` | text, or unset | unset | TMDB API key; keep it in the environment |
| `tmdb.enabled` | `true`, `false` | `true` | Look up TMDB metadata |
| `tmdb.unattended` | `true`, `false` | `false` | Never prompt for an unresolved match |
| `tmdb.timeout_seconds` | number, at least `1` | `10.0` | Request timeout |
| `tmdb.year_tolerance` | `0` to `5` | `2` | Release-year difference accepted for a match |
| `tmdb.category_preference` | `"movie"`, `"tv"`, or unset | unset | Category preferred when a title is ambiguous |

`logging` — no guide. Follow the table with exactly: "`--quiet` and `--verbose` override
the level for one run."

| Key | Values | Default | Effect |
| --- | --- | --- | --- |
| `logging.level` | `"DEBUG"`, `"INFO"`, `"WARNING"`, `"ERROR"` | `"INFO"` | Log level; `--quiet` and `--verbose` override it |
| `logging.format` | `"console"`, `"json"` | `"console"` | Log format |

Must not appear: `[diagnostics]`, `per_frame_nits`, `Pydantic-settings`.

## `tests/test_cli_contract_docs.py` — add a test (U7)

Append this test and the imports it needs (`BaseModel` from `pydantic`,
`ConfigSchema` from `frame_compare.config.schema`, `SourceOverrideConfig` from
`frame_compare.config.schema_models`). It protects the finding that nine keys were
documented nowhere.

```python
def test_configuration_reference_lists_every_config_key() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    reference = (repo_root / "docs" / "reference" / "configuration.md").read_text(
        encoding="utf-8"
    )
    documented = set(
        re.findall(r"^\| `([a-z_]+(?:\.[a-z_<>]+)+)` \|", reference, flags=re.MULTILINE)
    )

    expected: set[str] = set()
    for section, field in ConfigSchema.model_fields.items():
        model = field.annotation
        assert isinstance(model, type) and issubclass(model, BaseModel)
        expected.update(f"{section}.{key}" for key in model.model_fields)
    expected.update(
        f"sources.overrides.<selector>.{key}" for key in SourceOverrideConfig.model_fields
    )

    assert documented == expected
```

## `docs/reference/output-layout.md` — edit (U7)

1. Replace the canonical tree with:

   ```text
   <generated-data-root>/
   ├── cache/
   │   ├── analysis/
   │   │   └── <source-and-request-identity>.compframes
   │   ├── alignment/
   │   │   └── alignment_reuse.toml
   │   └── tmdb.toml
   ├── clip_probe.toml
   └── <run-name>/
       ├── report.html
       ├── screenshots/
       │   └── <frame> - <source-stem>.png
       ├── alignment_diagnostics/
       │   └── comparison-<n>.json
       ├── generated/
       │   ├── clip_probe.toml
       │   └── vsview_sessions/
       ├── run_info.toml
       └── run_result.toml
   ```

   (sources: the 2026-10-08 Docker run's `generated/` tree;
   `docs/current-architecture.md:364` and `:381-389`).
2. Ownership table: directly after the `<run>/generated/` row, add rows
   "`<run>/alignment_diagnostics/` | Per-comparison alignment evidence; diagnostic only"
   and "`<run>/generated/vsview_sessions/` | Generated VSView
   sessions and their saved panel results". Add after the table: "Files ending in
   `.lock` coordinate concurrent writers; leave them alone."
3. After the `.lwi` paragraph, add: "When media is mounted read-only, as on the default
   Docker route, no index file can be written and each run rebuilds the index; see
   `[Docker](../getting-started/docker.md#the-index-warning)`."
4. Keep the rest.

## `docs/reference/commands-and-configuration.md` — delete (U7)

Its content is now in `commands.md` and `configuration.md`. The VSView paragraph
(lines 98–122) is replaced by `docs/guides/vsview-review.md`. The `[diagnostics]`
paragraph (lines 93–96) is dropped.

## `docs/current-cli-contract.md` — edit (U8)

1. **New section** inserted between "## Command Surface" and
   "## Shared Path Resolution Rules":

   ```markdown
   ## Exit Codes And Error Families

   Commands exit with these codes (`src/frame_compare/cli/errors.py`,
   `src/frame_compare/cli/run_command.py:346-354`,
   `src/frame_compare/cli/cli_helpers.py:130-139`):

   | Code | Meaning |
   | --- | --- |
   | `0` | Success, including a dry run, `--write-config`, a wizard no-op, and a declined wizard confirmation |
   | `1` | Unexpected or unclassified error |
   | `2` | Configuration error (`FC-1xxx`) or command-line usage error |
   | `3` | Dependency error (`FC-2xxx`), including a `doctor` run with a failing required check |
   | `4` | Input error (`FC-3xxx`) |
   | `5` | Processing error (`FC-4xxx`), or a run that finished unsuccessfully |
   | `6` | Network error (`FC-5xxx`) |
   | `130` | A run or the wizard interrupted by Ctrl+C, or a wizard prompt aborted or reaching end of input |

   The first digit of an `FC-` code selects its family and exit code. Human output
   prints the code and message on stderr; `--json` prints the typed error document
   described under Output Modes.
   ```

   Add `- [Exit Codes And Error Families](#exit-codes-and-error-families)` to the
   Contents list after the Command Surface entry. Before writing, confirm in
   `src/frame_compare/cli/wizard_command.py` that a declined final confirmation
   returns normally (exit 0, lines 205–207) and that `KeyboardInterrupt`, `EOFError`,
   or `typer.Abort` exits 130 (lines 215–217); if not, stop.
2. **Tonemap Preset And Target Resolution:** append: "`tone_curve`, `gamma_lift`, and
   `contrast_recovery` follow the same rule as `target_nits`: each replaces the preset
   value only when explicitly present in config. `--tm-curve` overrides `tone_curve`
   for one run (`src/frame_compare/render/prepare.py:37-73`)."
3. **Video confirmation thresholds:** after the paragraph that ends "which are not
   scored." in "Config-Only Audio Alignment Surface", insert these four paragraphs
   exactly. They carry the thresholds from `docs/guides/audio-alignment.md:85-117`
   (base) without repeating the motion-selection rules the contract already states
   (`docs/current-cli-contract.md:1742-1747`). Constants verified against
   `src/frame_compare/utils/alignment_policy.py:12-15` and
   `src/frame_compare/services/alignment_video.py:58-60`.

   ```markdown
   Video confirmation runs whenever audio produces a global lag and uses the run's
   L-SMASH loader; there is no FFMS2 fallback. It scores 12 base positions across the
   middle 90% of the raw-frame overlap at offsets `r-2` through `r+2`. A strict local
   minimum must have a runner-up/best margin of at least 1.1. The exact frame is
   confirmed only within `r-1..r+1`, with at least 6 informative positions, at least
   75% wins, and a median winning margin of at least 1.5. Static, tied, repeated, or
   aliased frames are uninformative rather than false confirmation.

   After global confirmation, V5a checks frame-distinct disagreement regions with 12
   targeted positions in total: competing runs receive four positions first, single
   credible chunks receive four each in descending PSR order, and active non-credible
   chunks receive two each. At each position it compares the confirmed frame with the
   target's own compensated audio-frame neighbourhood, excluding the confirmed frame.
   Exact ties and two zero scores mean neither hypothesis wins. A non-credible
   neither-win is weak evidence and does not block. A credible chunk needs at least one
   confirmed-frame win and no alternative win; a run needs at least two confirmed-frame
   wins and no alternative win. Unexamined or unresolved credible evidence blocks.

   This is deliberately a sampling contract, not proof that every edit is found. A
   chunk that straddles an edit can resolve from sampled pre-edit motion while sampled
   post-edit frames are inconclusive; later shifted chunks usually expose the change,
   but the straddling chunk alone does not prove it. Active non-credible shifted audio
   is caught only when a target samples it and the alternative video wins. Fully silent
   or inactive shifted audio creates no target. Same-length replacement content is
   allowed because its constant offset remains correct.

   Level changes, compression, surround/downmix differences, stem changes, quiet
   sections, and local inconclusive evidence do not independently veto an otherwise
   confirmed offset. They remain review context. Credible evidence for another offset
   must still be resolved, and global audio/video confirmation is always required.
   ```
4. Leave the "## CLI Flag To Config Mapping" table and the text between it and
   "## Config-Only Analysis Surface" untouched (guard test).

## `docs/ENGINEERING_RUNBOOK.md` — edit (U8)

1. After the paragraph ending "Crossing a media-runtime fingerprint also requires a
   complete portable bundle reinstall." (Command Canon, Windows code-only update),
   insert `docs/windows-portable.md:244-249` (base) verbatim as its own paragraph.
2. Insert a new subsection `### Alignment Accuracy Benchmark` immediately before
   `### Windows Portable / Release-Path Verification`, containing
   `docs/guides/audio-alignment.md:359-391` (base) verbatim, with "Native macOS
   L-SMASH is broken, so run it in the Docker test service:" replaced by "Run it in the
   Docker test service:".

## `docs/media-runtime-windows-validation.md` — edit (U8)

1. Insert a new section `## 10. Native VSView panel acceptance` before
   "## 10. Completion record", and renumber that heading to
   `## 11. Completion record`.
2. Its content is `docs/windows-portable.md:320-351` (base), verbatim, with these
   edits only: delete "This feature run has not executed hosted Windows proof." and
   "This feature run has not completed the physical-Windows ergonomics checks above,
   so do not claim them from offscreen or hosted results."; keep the sentence
   containing "Hosted or macOS offscreen proof must not be reported as physical
   Windows desktop acceptance."

## `tests/windows_portable/test_windows_portable_docs.py` — edit (U8)

Replace the body of `test_windows_portable_docs_define_native_alignment_handoff` with:

```python
    portable = _read_text_or_fail(repo_root / "docs" / "windows-portable.md")
    review = _read_text_or_fail(repo_root / "docs" / "guides" / "vsview-review.md")
    validation = _read_text_or_fail(repo_root / "docs" / "media-runtime-windows-validation.md")

    assert "## VSView alignment review" in portable
    assert "frame-compare-alignment-review" in portable
    assert "self-contained Python" in portable
    assert "PATH-only VSView executable" in portable
    assert "](guides/vsview-review.md)" in portable
    assert "bundle_info.schema_version` 3" in portable
    assert "pre-native-panel schema-2 bundles" in portable
    assert "typed, atomic sibling sidecar" in review
    assert "Missing, malformed," in review
    assert "stale, mixed-session, duplicate, incomplete" in review
    assert "ordinary VSView session" in review
    assert "Confirm these aligned positions" in review
    assert "Keep current alignment" in review
    assert "Keep current offset" not in portable + review
    assert "## 10. Native VSView panel acceptance" in validation
    assert "Hosted or macOS offscreen proof must not be reported" in validation
    assert "physical Windows desktop acceptance" in validation
```

The other tests in the file stay unchanged and must still pass.

## `SECURITY.md` — edit (U9)

1. "Path Boundaries" bullet: replace with: "Media inputs may be read from outside the
   workspace. The selected config file and `paths.config_dir` must resolve inside the
   workspace root after symlink resolution. `paths.generated_dir` may name an external
   directory, and every run folder, cache, and report Frame Compare writes stays inside
   that resolved generated-data root. Outside it, Frame Compare writes only the
   selected config file (inside the workspace root), preset files under
   `<root>/config/presets` (`preset save` follows a user-authored symlink there), and
   its own L-SMASH-Works `.lwi` index beside each media file. The only selected-config
   exception is the
   installed Windows portable shim's exact
   `%LOCALAPPDATA%/Programs/FrameCompare/state/config.toml` fallback; a symlinked
   fallback that resolves elsewhere is rejected." (source:
   `docs/current-cli-contract.md:118-157`).
2. "Network Operations" bullet, exactly: "**Network Operations**: slow.pics upload and
   webhook delivery are opt-in, and TMDB lookups run only when an API key is
   configured. Webhook delivery requires an external HTTPS endpoint, follows no
   redirects, and keeps the URL out of diagnostics." (sources:
   `src/frame_compare/config/schema_models.py:269`,
   `src/frame_compare/services/tmdb_resolution.py:698`,
   `docs/current-cli-contract.md:1134-1176`)
3. Replace base lines 44–46 ("For implementation details, see:", the blank line, and
   the `Decisions` bullet) with exactly:
   `For implementation details, see [Current architecture](docs/current-architecture.md).`
4. Under "## Security-Related Error Codes", keep the header row and separator row and
   replace the three data rows with the single row
   `| FC-3009 | Path escapes its permitted root (blocked) |`, then one blank line and
   exactly:
   `All error families and exit codes are listed in the [CLI contract](docs/current-cli-contract.md#exit-codes-and-error-families).`

Must not appear: `FC-3012`, `FC-3xxx`, `Invalid path format`.

## `CHANGELOG.md` — edit Unreleased only (U9)

Add these bullets, worded exactly. Do not edit other sections.

Under `### Changed` (Unreleased), after the existing bullets:

- Refresh the report viewer: the Inspector has Frame, Clips, Image offset, and Review
  tabs with a per-source frame table; review export and import moved into the Review
  tab; the lens can caption the magnified source; source labels show file size; the
  header shows a localized generation time; and the fit-width control is removed.
- Refresh the terminal presentation of the run plan, sources, alignment, and the
  completion summary. Machine-readable JSON output is unchanged.
- The wizard prints suggested `doctor`, `run --dry-run`, and `run` commands for the
  exact workspace and config it saved.
- `run --help` groups options by purpose, and an invalid `--overlay`, `--tm-preset`,
  or `--tm-curve` value lists the allowed choices before any work starts.
- Update the supported runtime to VapourSynth R81, VSView 0.12.0, CPython 3.13.16,
  vsjetengine 1.8.0, vspackrgb 2.0.0, BestSource 22, and Windows FFmpeg
  `n8.1.3-9-g29e619e767`. Install a complete portable bundle for this runtime.

Under `### Fixed` (Unreleased), after the existing bullets:

- Reject `--no-cache` combined with `--from-cache-only` in runs and dry runs before any
  runtime work.
- Redact `slowpics.webhook_url` and `tmdb.api_key` inputs in every configuration
  error.
- Bound webhook DNS resolution and keep application secrets out of the resolver.
- Reap VSView review processes after interrupted waits.
- Discard pending Diff image loads after Grid navigation so a newer frame is never
  overwritten.

Sources: commits `d7b069d5`, `e9958270`, `1baf8100`, `11c70204`, `837b5e4a`,
`e4342501`, `8921a2c7`, `b592dc21`, `7f70bb98`, `33dbc6e7`, `e7b457dd`, `3ee93554`,
`78c38b6e`, `5c9c3de1`, and `docs/supported-media-runtime.md:8-30`.

## `CONTRIBUTING.md` — edit (U9)

1. Replace lines 205–212 (the "Documentation expectations:" line and its six bullets)
   with the block in [`contributing-docs-style.md`](contributing-docs-style.md),
   byte-for-byte.
2. No other change to `CONTRIBUTING.md`.

## `docs/release-evidence/2026-07-28-windows-initial-release.md` — edit (U9)

Prepend exactly these four lines followed by one blank line, before the existing H1:

```yaml
---
search:
  exclude: true
---
```

No other change.

## `docs/plans/2026-08-17-documentation-v2-screenshot-remediation.md` — edit (U9)

Change `Status: Active` to `Status: Historical` and insert directly after it this
line, exactly (the path is a code span, not a link):

```markdown
Superseded by `docs/plans/2026-10-08-documentation-refresh.md`.
```

No other change.

## `.github/workflows/docs.yml` and `tests/workflows/test_docs_workflow.py` — edit (U9)

1. In the "Check user documentation search scope" step, change the tuple
   `("TODO/", "plans/")` to
   `("TODO/", "plans/", "reviews/", "prompts/", "images/", "release-evidence/")`.
2. In `test_docs_workflow_builds_strictly_from_locked_docs_group`, change the asserted
   literal to the same tuple text.

## `docs/images/README.md` — rewrite (U1)

```text
# Documentation image capture record
## Capture sets
## Provenance record
## Asset policy
## Current asset set
## Deliberate capture decisions
## Privacy and integrity review
```

- Keep the front matter. Delete current lines 8–14 (the old intro, which links the
  superseded 2026-08-17 plan); the H1 is followed directly by "## Capture sets".
- **Capture sets:** two sets: (1) macOS with Docker, the official EBU/DVB streams, and
  headless Chrome (unit U1); (2) the physical Windows host for the installer output and
  the VSView panel (unit U10). Link the refresh plan as
  `../plans/2026-10-08-documentation-refresh.md` (the only plan link allowed in this
  internal file).
- **Provenance record:** one table per set with the fields: source title, rights basis,
  attribution (from current lines 62–64), physical filenames and SHA-256 (from the
  capture specification), display labels, frame and category (`1000`, `User`; 6
  frames, 2 sources), Frame Compare commit, Docker image ID or bundle SHA, Chrome and
  Node versions or Windows build, viewport (1600 × 1000 at scale 1) or display scaling,
  report theme (viewer default, dark), capture date, and captured by. U1 fills set 1;
  U10 fills set 2.
- **Asset policy:** viewer and photo captures WebP at quality 90 with metadata stripped;
  terminal captures SVG generated by the capture specification's converter; Windows
  terminal capture PNG; never upscale; every capture uses the capture specification.
- **Current asset set:** one row per file in the capture specification's asset table:
  file, role, pages, set.
- **Deliberate capture decisions:** the "Decisions and reasons" bullets from the
  capture specification, one sentence each (points rule applies).
- **Privacy and integrity review:** keep current lines 136–152.

Delete the "Canonical capture workspace" `C:\FrameCompareDemo` tree and the old
provenance values.
