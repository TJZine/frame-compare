Status: Historical
Scope: Complete slow.pics naming, metadata, upload-field, and source-label parity with frame-compare-legacy using typed immutable owners and the current browser-compatible upload flow
Owner: Antigravity
Updated: 2026-07-10

# Slow.pics naming and upload parity execution plan

## 1. Executive decision

Implement the useful slow.pics and source-naming capabilities from
`frame-compare-legacy`, but express them through Frame Compare's current typed,
immutable, CLI-first architecture. Preserve the current browser-compatible
slow.pics flow, explicit upload-plan membership, safer local deletion policy,
public-by-default visibility matching legacy, lazy runtime imports, JSON stdout
contract, and report-first confirmation workflow.

The finished feature provides:

- literal, templated, and automatic slow.pics collection titles;
- a suffix applied consistently to every title source;
- filename, stem, parsed, and explicit per-source display labels;
- deterministic derived-label disambiguation and fail-fast explicit-label
  collision handling;
- automatic or explicit typed TMDB association;
- collection and row NSFW/hentai metadata;
- remote removal-after metadata, distinct from local screenshot deletion;
- a dedicated size-aware image upload timeout floor;
- one resolved title shared by the upload and `.url` shortcut paths;
- exact mapping to the current first-party slow.pics multipart vocabulary.

This is a high-risk public config, orchestration, output, and external-integration
change. It requires same-pass authority-document updates and full verification.

## 2. Goals and non-goals

### Goals

1. Reach functional parity with the legacy slow.pics and naming capabilities
   listed in the parity matrix below.
2. Replace mutable legacy config updates and ad hoc dictionaries with frozen,
   service-owned DTOs and pure resolution policy.
3. Preserve meaningful source names by default while supporting the legacy
   full-filename and parsed-label choices.
4. Keep physical screenshot filenames based on source stems and keep label-only
   changes out of analysis/cache identity.
5. Validate public config strictly and reject malformed templates, identifiers,
   control characters, and ambiguous explicit label/identity pairs before
   external side effects.
6. Keep slow.pics HTTP field names, identifier formatting, timeouts, response
   validation, and retry behavior inside `frame_compare.services.publishers`.
7. Keep title, template-context, source-label, and explicit-versus-automatic
   metadata precedence out of the publisher and in focused pure policy owners.

### Non-goals

- No legacy config-key aliases such as `collection_name`, `collection_suffix`,
  `is_public`, `delete_screen_dir_after_upload`, or string-form TMDB IDs.
- No arbitrary expression language, attribute access, format-spec execution, or
  user-defined template functions.
- No new slow.pics `run` flags, wizard prompts, or successful `run --json` keys.
- No physical screenshot rename, directory scanning for upload membership, or
  directory-wide deletion.
- No tags, metacollections, canvas/image-fit controls, image-format selector, or
  configurable optimization toggle; those were not public legacy config
  capabilities required by this workstream.
- No change to TMDB search/ranking policy, report auto-open rules, post-upload
  browser/clipboard gating, webhook security, Docker, VapourSynth, FFmpeg, or
  Windows packaging.
- No compatibility mutation of `SlowpicsConfig`, `RunContext`, `ClipState`, or
  resolved metadata after configuration validation.

## 3. Legacy parity matrix

| Legacy capability | Legacy behavior | Current behavior before this plan | Finished-state behavior | Parity decision |
| --- | --- | --- | --- | --- |
| Automatic upload | `slowpics.auto_upload` opt-in | Implemented, disabled by default | Preserve | Full parity, safer default retained |
| Collection title | `collection_name` accepted a literal or `${...}` template | Metadata title or screenshot directory basename; no config override | Separate strict `title` and `title_template`, plus deterministic automatic fallback | Full capability parity with safer configuration |
| Title template fields | `Title`, `OriginalTitle`, `Year`, `TMDBId`, `TMDBCategory`, `OriginalLanguage`, `Filename`, `FileName`, `Label` | Not available | Same field set through an allowlisted `${Name}` renderer | Full parity; unknown/malformed tokens now fail validation |
| Collection suffix | Appended only on the automatic-title path | Not available | `title_suffix` appends exactly once to literal, templated, or automatic titles | Parity with corrected consistent semantics |
| Filename display labels | `always_full_filename = true` used full filenames | Internal labels are `Reference`/`Encode N`; slow.pics columns use stems | `sources.label_mode = "filename"` is available | Full capability parity |
| Stem display labels | Not a distinct legacy mode | Slow.pics columns use stems | `sources.label_mode = "stem"` is the default | Current behavior retained as the safer default |
| Parsed display labels | `always_full_filename = false` used GuessIt/Anitopy metadata | Parser exists but is not used for clip display labels | `sources.label_mode = "parsed"` composes release group, title, episode marker, and episode title | Full parity |
| Parser preference | `prefer_guessit` selected the primary parser | Automatic bracket-aware parser order | `sources.label_parser` accepts `auto`, `guessit`, or `anitopy`; all modes keep deterministic fallback | Full capability parity with a clearer enum |
| Label deduplication | Version hints, then order suffixes | Generic labels are unique; custom labels unavailable | Explicit duplicates fail; derived collisions fall back deterministically to source-stem qualification, then stable source order | Full outcome parity with less surprising explicit-label handling |
| Per-source manual label | Indirectly possible through parsed metadata/override machinery | Not available | `sources.overrides.<selector>.label` has highest precedence | Improved parity |
| Screenshot filenames | Derived from a sanitized display label | Already use source stem through `filename_label` | Preserve source-stem filenames regardless of display label | Intentional safer difference |
| TMDB automatic association | Successful TMDB resolution populated slow.pics ID/category | Metadata is resolved but not sent to slow.pics | Resolved `TmdbMetadata` maps to canonical slow.pics identity | Full parity |
| TMDB explicit association | String ID/category, including loosely normalized forms | Not available | Strict positive integer `tmdb_id` plus required `tmdb_media_type` pair | Full capability parity without legacy string shims |
| TMDB title context | Resolution supplied title, original title, year, category, ID, and original language | `TmdbMetadata` lacks original language | Preserve all legacy template context, adding optional original language to typed metadata | Full parity |
| Hentai/NSFW | Collection `hentai` metadata | Hardcoded false | `is_hentai` maps to collection and every comparison row | Full parity against the current form |
| Visibility | `is_public`, default true | `visibility`, default unlisted | Preserve public/unlisted choices, change the default to public, and map unlisted to current slow.pics `LINK_ONLY` | Full legacy default and capability parity |
| Remote removal | `remove_after_days`; zero omitted | Hardcoded empty `removeAfter` | Strict `0..999999`; zero emits empty field, positive emits decimal days | Full parity |
| Local deletion | Deleted the whole screenshot directory | Deletes only successfully uploaded planned files when report-safe | Preserve current exact-file cleanup | Intentional safety improvement |
| Upload timeout | Dedicated 180-second image floor plus size estimate | One 60-second timeout for every request | Preserve general timeout and add a dedicated 180-second size-aware image write timeout floor | Full reliability parity |
| Upload concurrency | Bounded legacy worker pool | Sequential image upload with step-aware retry/idempotency handling | Preserve sequential upload | Same functional result; intentional reliability difference |
| Retry/error behavior | Requests/urllib3 retry policy | Step-specific HTTPX retry, unknown-state protection, response matrix validation | Preserve current behavior | Current implementation is stronger |
| Browser-compatible form | Older legacy multipart shapes | Current browser-compatible nested image shapes | Keep current shape and align all optional fields with the first-party form | Modern equivalent |
| Browser open | Enabled by default | Implemented with human/TTY gating | Preserve | Full parity with safer gating |
| Clipboard copy | CLI convenience | Implemented and configurable | Preserve | Current repo exceeds legacy config surface |
| URL shortcut | Named from collection title | Implemented but can use metadata/screenshot-dir title instead of final upload title | Use the single resolved final title | Full parity and consistency |
| Webhook | Configurable post-upload delivery | Implemented with isolated HTTPS/SSRF protections | Preserve | Full parity with stronger security |
| Report-confirmed upload | Not equivalent in legacy | Implemented | Preserve | Current repo exceeds legacy behavior |
| JSON diagnostics/tail | Legacy emitted a large slow.pics block | Successful JSON contains only `slowpics_url` | Preserve current stable JSON schema | Intentional public-contract difference |
| Tags/format/optimization switches | Not public legacy config; optimization was hardcoded | Modern fields are hardcoded | Preserve | Out of scope, no parity gap |

## 4. Frozen public config contract

### 4.1 `[slowpics]` additions

Add these config-only fields to `SlowpicsConfig`:

| Field | Type/default | Contract |
| --- | --- | --- |
| `title` | `str = ""` | Literal collection title. Trim surrounding whitespace. Mutually exclusive with `title_template`. Empty means unset. |
| `title_template` | `str = ""` | Strict allowlisted `${Name}` template. Mutually exclusive with `title`. Empty means unset. |
| `title_suffix` | `str = ""` | Trimmed suffix appended once with one ASCII space after the resolved base title. Empty means no suffix. |
| `is_hentai` | `bool = false` | Maps to collection and per-comparison `hentai` fields. |
| `tmdb_id` | integer or null; default null | Strict positive integer. Must be paired with `tmdb_media_type`. |
| `tmdb_media_type` | `movie`, `tv`, or null; default null | Must be paired with `tmdb_id`. |
| `remove_after_days` | `int = 0` | Strict integer from `0` through `999999`; remote slow.pics removal only. |
| `image_upload_timeout_seconds` | `float = 180.0` | Minimum 10 seconds; size-aware image write timeout floor. Does not replace `timeout_seconds` for navigation/metadata. |

Change the existing `slowpics.visibility` default from `unlisted` to `public` in
`SlowpicsConfig`, the checked-in default TOML, generated/written configuration,
preset round-trips, and wizard default selection. Keep both accepted values;
`unlisted` remains an explicit opt-in and serializes to slow.pics `LINK_ONLY`.
This restores the legacy public-by-default contract without adding a CLI flag.

Validation rules:

- Reject control characters/newlines in `title`, `title_template`, and
  `title_suffix`; do not silently delete them.
- Reject configurations that set both nonblank `title` and nonblank
  `title_template`.
- Reject unknown template identifiers, malformed placeholders, unescaped lone
  `$`, attribute/index access, and any placeholder outside the allowlist.
- Reject a TMDB ID without media type, a media type without ID, non-integer IDs,
  booleans, zero, and negative IDs.
- Reject non-integer or out-of-range `remove_after_days` values, including
  booleans and numeric strings.
- Keep every existing nested config table's `extra="forbid"` behavior.

### 4.2 Title-template contract

Support these exact, case-sensitive legacy-compatible placeholders:

```text
${Title}
${OriginalTitle}
${Year}
${TMDBId}
${TMDBCategory}
${OriginalLanguage}
${Filename}
${FileName}
${Label}
```

All allowlisted names always exist in the template context; unavailable values
resolve to `""`. `$$` produces a literal dollar sign. Rendering is substitution
only: no expressions, conversions, format specifications, attribute access, or
function calls. If a valid template renders to an empty/whitespace-only string,
continue through automatic-title fallback rather than uploading an empty title.

### 4.3 `[sources]` and override additions

Add these config-only fields:

| Field | Type/default | Contract |
| --- | --- | --- |
| `sources.label_mode` | `Literal["stem", "filename", "parsed"] = "stem"` | Select the default display-label source. |
| `sources.label_parser` | `Literal["auto", "guessit", "anitopy"] = "auto"` | Select parser priority for parsed labels; alternate parser remains deterministic fallback. |
| `sources.overrides.<selector>.label` | string or null; default null | Explicit display label with highest precedence. Trim; reject empty or control-containing values. |

Display-label semantics:

- `stem`: normalized `Path.stem`.
- `filename`: normalized `Path.name`, including extension, matching the legacy
  full-filename capability.
- `parsed`: `[release_group] title SxxExx – episode_title`, omitting unavailable
  components and falling back to the normalized stem.
- `label_parser = "auto"`: Anitopy first for bracket-prefixed names, GuessIt
  first otherwise; `guessit` and `anitopy` explicitly choose the primary parser.
  A missing/failed primary result uses the alternate parser.
- A configured override wins over every derived label mode.
- Configured labels are trimmed and rejected if empty or control-containing.
  Filename/parser-derived values replace control characters with spaces,
  collapse whitespace, and fall back to `comparison` only if no usable source
  text remains.
- Comparisons are exact and case-sensitive after normalization. Do not apply
  Unicode case-folding or compatibility normalization implicitly.
- Two colliding explicit labels are a typed source-selection failure before
  probing, metadata prefetch, run-folder reservation, rendering, or HTTP work.
- For derived-derived or explicit-derived collisions, preserve the explicit
  label and qualify derived labels with their normalized source stem. If a
  collision still remains, append a stable one-based source-order suffix.

Global label effects:

- The resolved label becomes `ClipState.label` and therefore drives overlay,
  progress, report, alignment-display, render-artifact-key, and slow.pics column
  presentation.
- Source selectors, source paths, fingerprints, analysis/cache identity,
  alignment identity, and physical screenshot filenames remain unchanged.
- Orchestrated render continues setting `filename_label=clip.path.stem`.

## 5. Frozen title and TMDB precedence

Resolve one immutable `SlowpicsCollectionMetadata` value before calling the
publisher. It carries the final collection title plus an optional typed TMDB ID
and media type; it contains no HTTP field names.

### 5.1 Template context

Build a sanitized context from:

- the resolved reference display label and reference filename/stem;
- parsed reference metadata;
- resolved `TmdbMetadata`, when usable for the chosen association;
- the explicit configured TMDB pair, when provided.

Context precedence:

- `Title`, `OriginalTitle`, `Year`, and `OriginalLanguage` prefer matching
  resolved TMDB metadata, then parsed reference metadata where applicable.
- `TMDBId` and `TMDBCategory` use the explicit pair when configured, otherwise
  resolved TMDB metadata.
- `Filename` is the reference stem; `FileName` is the reference filename;
  `Label` is the final resolved reference display label.
- `TMDBCategory` is `MOVIE` or `TV`; `TMDBId` is decimal digits.

If an explicit TMDB pair does not match automatically resolved metadata, the
explicit pair wins. Do not combine that pair with title/original-title/year/
language from the conflicting match; use parsed reference metadata for those
values and emit a sanitized structured warning. Do not mutate config or the
resolved TMDB object.

### 5.2 Final title precedence

Resolve the base title in this order:

1. nonblank literal `slowpics.title`;
2. nonblank rendered `slowpics.title_template`;
3. matching resolved TMDB title with ` (year)` only when `year > 0`;
4. parsed reference title with ` (year)` only when parsed year is positive;
5. normalized reference stem;
6. `Frame Comparison`.

Append nonblank `title_suffix` exactly once with one ASCII space. Apply a final
display-text normalization to runtime-derived values, without silently repairing
invalid configured values. The resulting title is used for:

- `collectionName` in slow.pics metadata;
- slow.pics upload logging/progress descriptions where a title is shown;
- deterministic `.url` shortcut naming;
- post-upload action inputs.

It does not rename run folders, screenshot directories, reports, or PNG files.

Canonical automatic example: with no configured `title` or `title_template`, a
resolved TMDB movie titled `Example Film`, released in `2024`, with ID `1234`
produces `Example Film (2024)`. A `title_suffix` of `[Source Comparison]`
produces `Example Film (2024) [Source Comparison]`, and the same upload sends
`tmdbId=MOVIE_1234`. If TMDB does not resolve, the same title/year shape is built
from parsed reference metadata when available, then falls back to the reference
stem. slow.pics exposes the association as `tmdbId`; title and year are not sent
as separate collection metadata fields.

## 6. Frozen slow.pics HTTP contract

Continue using:

1. `GET /comparison` for cookies/XSRF bootstrap;
2. `POST /upload/comparison` for metadata;
3. planned `POST /upload/image/{imageUuid}` requests in row-major order.

External contract evidence is the first-party
[slow.pics comparison upload page](https://slow.pics/comparison) and its loaded
upload script, inspected on 2026-07-10. Re-check that source before implementation
if the service has changed; do not copy obsolete legacy field spellings such as
`optimize-images` or `comparisons[i].imageNames[j]` into the modern adapter.

The metadata multipart request must preserve existing fields and add/correct:

| Field | Value |
| --- | --- |
| `collectionName` | final resolved title |
| `browserId` | existing browser ID behavior |
| `optimizeImages` | existing `true` |
| `desiredFileType` | existing `image/png` |
| `hentai` | lowercase configured boolean |
| `public` | `true` for public, `false` for unlisted |
| `visibility` | `PUBLIC` for public, `LINK_ONLY` for unlisted |
| `removeAfter` | empty for zero, decimal days for positive values |
| `tmdbId` | omitted when absent; otherwise `MOVIE_<id>` or `TV_<id>` |
| `comparisons[i].hentai` | lowercase configured boolean for every row |
| `comparisons[i].images[j].name` | resolved `ClipState.label` |

Preserve row/image sort order, response matrix validation, XSRF/browser cookie
handling, sensitive-value redaction, unknown-state metadata failure behavior,
`IMAGE_IS_COMPLETE` idempotency handling, and explicit upload-plan membership.

For image requests, use a write-timeout budget no lower than
`image_upload_timeout_seconds` and no lower than the deterministic size estimate
`file_size / 256 KiB/s + 15 seconds`. Keep general navigation/metadata timeout,
step-specific retries, and sequential upload ordering unchanged.

### 6.1 Frozen local cleanup contract

Keep `slowpics.delete_after_upload = false` as the default. When explicitly
enabled, cleanup runs only from the completed publisher handoff and receives the
exact `uploaded_file_paths` from the explicit upload plan:

- if reports are disabled, unlink those files after the completed upload;
- if reports are enabled, require successful report generation and
  `report.embed_images = true` before unlinking them;
- when a report references external screenshots (`embed_images = false`), keep
  the PNGs so the report remains usable;
- never scan or delete the screenshot directory, unrelated/stale PNGs, reports,
  run metadata, or the `.url` shortcut;
- handle each unlink independently and return a sanitized warning for failures
  without turning an otherwise successful run into a failure.

`remove_after_days` is independent remote slow.pics retention metadata. It does
not enable, disable, or broaden local file cleanup.

## 7. Ownership and architecture

### Config owners

- `src/frame_compare/config/schema_models.py`: public fields and Pydantic
  cross-field validation.
- `src/frame_compare/config/defaults.py`: checked-in default/template examples.
- New `src/frame_compare/config/slowpics.py`: allowlisted template syntax,
  validation, and substitution shared by schema/runtime title resolution.

### Metadata and naming owners

- `src/frame_compare/services/types.py`: optional `ParsedMetadata.episode_title`,
  optional `TmdbMetadata.original_language`, and the frozen primitive-only
  `SlowpicsCollectionMetadata` DTO.
- `src/frame_compare/services/metadata_parsing.py`: parser-priority input and
  extraction of label-relevant metadata. Existing callers retain automatic
  behavior by default.
- `src/frame_compare/services/tmdb_lookup.py`: map the optional first-party
  `original_language` value into `TmdbMetadata` without changing search/ranking.
- New `src/frame_compare/orchestration/source_labels.py`: source display-label
  policy, normalization, disambiguation, and typed pre-probe collision failure.
- `src/frame_compare/orchestration/preparation.py`: call the source-label owner
  after selector/override resolution and pass a per-path label map into clip
  construction.
- `src/frame_compare/orchestration/selection_domain.py`: construct each
  `ClipState` with the already-resolved label; do not own parsing policy.

### slow.pics policy and adapter owners

- New `src/frame_compare/orchestration/slowpics_metadata.py`: pure title,
  template-context, suffix, and explicit-versus-resolved TMDB precedence.
- `src/frame_compare/orchestration/phase_post_render.py`: thin wiring; build the
  upload plan using `clip.label`, pass resolved metadata to the publisher, and
  pass the same title to post-upload actions.
- `src/frame_compare/services/publishers.py`: slow.pics field serialization,
  canonical TMDB identifier, visibility adapter, request timeout, HTTP calls,
  retries, response validation, and redaction.
- `src/frame_compare/services/slowpics_post_upload.py` and
  `src/frame_compare/services/slowpics_shortcut.py`: accept one resolved title,
  not independent metadata-title and screenshot-directory fallbacks.

`services` must not import orchestration types. The boundary DTO uses primitives
and service-owned types only. No import-linter contract change is expected.

### Authority docs

- `docs/current-cli-contract.md`: exact config fields/defaults, source-label
  modes, template syntax, title/TMDB precedence, remote/local removal split,
  form mapping, persistence, and unchanged CLI/JSON surfaces.
- `docs/current-architecture.md`: source-label owner, resolved slow.pics metadata
  seam, publisher adapter ownership, and shortcut title propagation.

## 8. Files in scope

Expected production/doc files:

- `src/frame_compare/config/schema_models.py`
- `src/frame_compare/config/defaults.py`
- `src/frame_compare/config/slowpics.py` (new)
- `src/frame_compare/services/types.py`
- `src/frame_compare/services/metadata_parsing.py`
- `src/frame_compare/services/tmdb_lookup.py`
- `src/frame_compare/orchestration/source_labels.py` (new)
- `src/frame_compare/orchestration/preparation.py`
- `src/frame_compare/orchestration/selection_domain.py`
- `src/frame_compare/orchestration/slowpics_metadata.py` (new)
- `src/frame_compare/orchestration/phase_post_render.py`
- `src/frame_compare/services/publishers.py`
- `src/frame_compare/services/slowpics_post_upload.py`
- `src/frame_compare/services/slowpics_shortcut.py`
- `docs/current-cli-contract.md`
- `docs/current-architecture.md`

Expected test files:

- `tests/config/test_schema.py`
- new `tests/config/test_slowpics.py`
- `tests/config/test_loader.py`
- `tests/config/test_presets.py`
- `tests/cli/test_run_request_config.py`
- `tests/cli/test_run_slowpics_options.py`
- `tests/services/test_metadata_parsing.py`
- `tests/services/test_tmdb_lookup.py`
- new `tests/orchestration/test_source_labels.py`
- `tests/orchestration/test_preparation.py`
- `tests/orchestration/test_phase_tasks_outputs.py`
- new `tests/orchestration/test_slowpics_metadata.py`
- `tests/services/test_slowpics_upload_plan.py`
- `tests/services/test_publishers.py`
- `tests/services/test_slowpics_post_upload.py`
- `tests/services/test_slowpics_shortcut.py`
- `tests/test_cli_contract_docs.py`

Files explicitly out of scope unless implementation evidence proves a required
contract dependency:

- `src/frame_compare/analysis/**`
- `src/frame_compare/render/**`
- `src/frame_compare/cli/entry.py`
- `src/frame_compare/config/overrides.py`
- report viewer assets and payload schema
- Docker/Compose, FFmpeg/VapourSynth runtime, and Windows packaging
- release workflows and import-level API promotion

If an out-of-scope file must change, stop and update this active plan before
editing it.

## 9. Implementation packages

### P1 — Public schema, templates, and metadata primitives

- Add and validate the public config fields and default TOML examples.
- Change the persisted and wizard visibility default to `public` while retaining
  explicit `unlisted` support.
- Add strict allowlisted template validation/rendering.
- Extend parsed/TMDB metadata only for the legacy context values required here.
- Map optional TMDB original language without changing lookup/ranking behavior.
- Add the frozen service-owned collection metadata DTO.
- Prove config defaults, invalid inputs, TOML load/write, preset round-trip, and
  unchanged unknown-key behavior.

### P2 — Source display-label parity

- Add label modes/parser priority and explicit override handling.
- Resolve labels before probing and run-folder reservation.
- Preserve deterministic derived-label disambiguation and fail explicit
  duplicate labels through the typed source-selection/config path.
- Feed resolved labels into `ClipState` without changing source identity,
  analysis/cache identity, or filename labels.
- Prove overlay/report/upload label propagation and physical filename invariance.

### P3 — Resolved slow.pics metadata policy

- Build the strict template context.
- Resolve explicit-versus-automatic TMDB association without config mutation.
- Resolve one final title with suffix and automatic fallbacks.
- Keep policy pure and independently testable.

### P4 — Publisher and post-upload integration

- Map resolved metadata/config into the exact current multipart fields.
- Correct unlisted visibility to `LINK_ONLY` at the adapter boundary.
- Apply NSFW metadata at collection and row levels.
- Add remote removal and canonical optional TMDB association.
- Add the dedicated size-aware image timeout.
- Use resolved display labels for slow.pics image names.
- Pass the same final title into shortcut creation.

### P5 — Authority docs and contract closeout

- Update current CLI/config and architecture truth in the same pass.
- Prove no new flags, wizard prompts, JSON keys, report schema changes, or eager
  runtime imports.
- Run focused tests, then the full verification gate.

## 10. Verification strategy

Primary mode: `contract-first`.

Plan classification: `new regression/contract test required` for every changed
public config, output-label, title-resolution, and multipart mapping surface.

No default test may use live network, VapourSynth, FFmpeg, Docker, PowerShell, a
real browser, the clipboard, or user-global filesystem state. HTTP behavior must
use the existing injected HTTPX/RESPX boundary. A live slow.pics POST is not a
completion gate because it creates external state; it requires separate explicit
maintainer authorization.

### Required proof matrix

| Surface | Required automated proof |
| --- | --- |
| Config | Exact field order/defaults, including public visibility; strict types; bounds; control characters; title/template exclusivity; template token validation; TMDB pair coupling; nested unknown-key rejection |
| Template renderer | Every allowed placeholder, missing-value substitution, `$$`, unknown/malformed token rejection, literal text, and empty-render fallback signal |
| Persistence | Default TOML, loader, preset, and `--write-config` round-trips preserve new fields and unrelated sections |
| Parsed metadata | Parser priority/fallback, episode title, release group, season/episode marker, malformed parser result, parser exceptions |
| Labels | stem/filename/parsed modes; override precedence; normalization; explicit duplicate failure before loader/probe; derived collision qualification; stable order; Windows-style source selectors unchanged |
| Output propagation | Resolved label reaches overlay/report/render artifact/slow.pics plan; `filename_label` and resulting PNG path remain source-stem based |
| Title | literal, template, automatic TMDB, parsed metadata, stem, final fallback, suffix on every path, whitespace-only rendered template, missing/year-zero behavior |
| TMDB | explicit pair, auto pair, absent pair, canonical movie/TV string, explicit/auto mismatch isolation, no mutation, no-ID field omission |
| Multipart | current required fields preserved; `PUBLIC`/`LINK_ONLY`; top-level and row hentai true/false; zero/positive remove-after; resolved image names and sort order |
| Timeout | metadata uses general timeout; image write uses configured floor or larger deterministic size estimate; no unbounded request |
| Shortcut | final upload title is the first and only title input; filesystem sanitization/fallback remains safe |
| CLI/JSON | no new run option; help surface unchanged; wizard defaults to public while still accepting public/unlisted; successful JSON remains parseable with only existing keys; validation uses typed error mapping without traceback leakage |
| Architecture | no service-to-orchestration imports; lazy CLI import smoke remains green; authority docs match code |

### Focused verification

```bash
.venv/bin/pytest -q \
  tests/config/test_schema.py \
  tests/config/test_slowpics.py \
  tests/config/test_loader.py \
  tests/config/test_presets.py \
  tests/cli/test_run_request_config.py \
  tests/cli/test_run_slowpics_options.py \
  tests/services/test_metadata_parsing.py \
  tests/services/test_tmdb_lookup.py \
  tests/orchestration/test_source_labels.py \
  tests/orchestration/test_preparation.py \
  tests/orchestration/test_phase_tasks_outputs.py \
  tests/orchestration/test_slowpics_metadata.py \
  tests/services/test_slowpics_upload_plan.py \
  tests/services/test_publishers.py \
  tests/services/test_slowpics_post_upload.py \
  tests/services/test_slowpics_shortcut.py \
  tests/test_cli_contract_docs.py
```

Expected outcome: all focused tests pass without network/runtime skips, and the
tests prove semantic fields and parsed structures rather than multipart boundary
bytes, private call order, or broad snapshots.

### Full verification

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

Expected outcome: every command exits zero; Pyright remains strict; Ruff and
Bandit report no findings; the full suite preserves CLI/config/JSON/report/
runtime behavior; import-linter confirms sibling-domain independence and layer
direction.

Docker, Windows portable, and manual runtime gates are not required because the
frozen scope does not touch their owners. If implementation expands into one of
those surfaces, stop and update the verification route before proceeding.

## 11. Rollback and stop conditions

Rollback surface:

- Revert the workstream's dedicated implementation commit(s), or apply targeted
  inverse patches after inspecting `git status` and `git diff`.
- Preserve unrelated tracked and untracked workspace changes.
- Do not leave partially documented config fields or half-live template syntax.

Stop and replan before implementation continues if:

- first-party slow.pics behavior no longer accepts the documented
  `PUBLIC`/`LINK_ONLY`, nested image-name, `hentai`, `tmdbId`, or `removeAfter`
  contract;
- source display labels are discovered to participate in an identity/cache key
  rather than presentation only;
- preserving parsed-label parity requires a new dependency or import-layer
  exception;
- the safe template renderer cannot reject unknown/malformed placeholders at
  config validation time;
- explicit-versus-automatic TMDB mismatch cannot be isolated without mutating
  config or metadata;
- implementation requires new CLI flags, JSON fields, report schema changes,
  physical screenshot renaming, directory scanning/deletion, or changes to an
  out-of-scope runtime/release owner;
- a required focused test needs live network or platform-specific runtime state.

When implementation completes, update this plan to `Status: Historical` in the
same pass as final authority-doc synchronization.
