Status: Historical

# VapourSynth R76 Dependency Update Plan

Scope: VapourSynth R76 dependency update across Python lock state, Docker runtime, Windows portable/release paths, VapourSynth integration, diagnostics, and docs. This plan authorizes a full latest-stable/working update pass for Python dependencies, runtime dependencies, VapourSynth plugins, and bundled/pre-sourced artifacts, including FFmpeg, libplacebo, ffms2, and similar runtime artifacts, for the new R76 setup. Components may be held back only when the latest stable candidate is unsafe, incompatible, licensing-problematic, unsupported on target platforms, or unverifiable; every hold must be explicitly recorded with reason and reevaluation path.
Owner: frame-compare-cleanup-loop planning controller; implementation and review slices must be assigned from this plan.

Activation note: this document is now active execution authority for the scoped VapourSynth R76 dependency update. Activation does not approve a Python baseline bump; any baseline bump remains a separate Slice 1 maintainer checkpoint after compatibility proof, named release surfaces, and the additional gates below.

## Goal

Update Frame Compare to VapourSynth R76 and current compatible dependency/runtime artifacts while preserving existing functionality, defaults, CLI behavior, JSON contracts, source-loader policy, and release-path expectations.

This is a high-risk runtime/release-path migration, not a routine lockfile refresh. The main upgrade is from the R73-era VapourSynth layout to the R74+ packaging and plugin-loading model.

## Active Decisions

- Target VapourSynth R76, latest stable released 2026-05-14.
- Refresh Python lock dependencies to the accepted resolver output as a full Python dependency lock refresh.
- Update runtime dependencies, VapourSynth plugins, and bundled/pre-sourced artifacts to the latest stable/working versions that are safe, compatible, license-acceptable, supported on target platforms, and verifiable for the R76 setup.
- Include FFmpeg, libplacebo, ffms2, L-SMASH-Works, vs-placebo, VSPreview, Docker runtime artifacts, Windows portable artifacts, and similar bundled/pre-sourced components in the latest-stable/working update pass rather than holding them to R76-minimum compatibility by default.
- Any package, plugin, runtime component, or bundled/pre-sourced artifact not moved to latest stable must be listed in the held-back dependency/artifact ledger with the reason, verification evidence, and reevaluation path.
- Preserve current user-facing functionality and defaults.
- Keep `lsmas` / L-SMASH-Works as the primary source loader for this pass.
- Do not migrate to BestSource unless implementation proves `lsmas` cannot satisfy the R76 runtime path.
- Evaluate the latest stable Python release as a candidate baseline before broad implementation. Python 3.13 remains the current declared baseline while that decision is unresolved; bumping the baseline requires compatibility proof across project dependencies, tooling, Docker, Windows embeddable/portable artifacts, VapourSynth/VSPreview wheels, and verification, followed by explicit maintainer approval.
- Treat Docker, Windows portable/release artifacts, plugin manifests, generated files, import boundaries, and CLI/JSON behavior as production surfaces.

## Non-Goals

- No BestSource migration unless a stop-and-replan trigger fires.
- No intentional CLI command, flag, exit-code, or JSON schema changes.
- No config default changes or persistence behavior changes.
- No broad compatibility shim or legacy runtime abstraction beyond what is needed to keep supported behavior working.
- No unapproved Python baseline bump. A baseline bump may be proposed and activated only through the early Python baseline decision slice after compatibility proof and maintainer approval.
- No redesign of tonemapping, source loading, VSPreview UX, report output, slow.pics, TMDB, or audio-alignment policy.
- No repo-local `desloppify` skill or tracked scanner state.

## Current Evidence

- Observed on 2026-05-25: `uv lock --upgrade --dry-run` on the current Python baseline resolved successfully.
- Observed on 2026-05-25: `uv lock --upgrade --dry-run --python 3.14` also resolved successfully with the same package movement in this workspace.
- Dry-run/version evidence in this section is non-authoritative after 2026-05-25 and must be rerun immediately before implementation.
- Current lock and runtime surfaces are anchored to VapourSynth 73/R73.
- Observed on 2026-05-25: latest Python 3 release was Python 3.14.5, released 2026-05-10. This is the initial latest-stable candidate for the baseline decision, not an approved baseline bump.
- Observed on 2026-05-25: upstream VapourSynth R74 changed packaging/autoload behavior; R75 added plugin manifests and optimized plugin variant loading; R76 was the current stable target.

## Dependency Decision Matrix

| Category | Target / Decision | Notes / Stop Condition |
| --- | --- | --- |
| Python baseline | Decide early: keep `requires-python >=3.13` or propose latest stable Python as the new baseline | Python 3.13 is the current declared baseline and compatibility guard until the decision is approved. If latest stable Python is compatible across dependencies, tooling, Docker, Windows embeddable/portable, VapourSynth/VSPreview wheels, and verification, the implementer may propose a baseline bump for maintainer approval before broad implementation. |
| Python latest | Python 3.14.5 is the latest stable candidate observed on 2026-05-25 | Normal dependency/tool package upgrades may be accepted from the resolver. Do not update `requires-python`, classifiers, Pyright `pythonVersion`, Ruff `target-version`, Docker base images, Windows embeddable Python, CI Python version, docs, or doctor Python checks/tests to latest stable Python without explicit approval after proof. If latest stable Python is not adopted, add a held-back ledger entry for Python latest with the reason and reevaluation path. |
| Dependency/artifact update policy | Update to latest stable/working by default | Applies to Python packages, runtime dependencies, VapourSynth plugins, Docker runtime artifacts, Windows portable artifacts, and bundled/pre-sourced artifacts. Hold back only for safety, compatibility, licensing, target-platform support, or verification reasons. |
| Dependency/artifact inventory and held-back ledger | Required in this plan for every in-scope component | Implementation slices update the tables below as the durable record. Held-back decisions must not live only in worker handoff notes. |
| VapourSynth | R76 / PyPI package `vapoursynth==76` in lock | Package requires Python >=3.12 and has cp312-abi3 wheels. |
| VapourSynth packaging | Prefer R74+ model | Use `vapoursynth.get_plugin_dir()` where available and `VAPOURSYNTH_EXTRA_PLUGIN_PATH` for supplemental plugin dirs. Do not make old `VAPOURSYNTH_PLUGIN_PATH` the future source of truth. |
| Plugin manifests | Preserve `manifest.vs` and plugin subdirectories | R75 added manifest-based optimized variant loading; flattening or copying must not destroy manifests or variant groups. |
| Source loader | Keep L-SMASH-Works / `lsmas` primary | Latest known HomeOfAviSynthPlusEvolution release is `1282`. Stop if it cannot be made reliable on Docker and Windows portable. |
| BestSource | Hold / out of scope | Better aligned with the new packaging model, but changes loader namespace/API and cache/index behavior. Revisit only if `lsmas` blocks R76. |
| vs-placebo | Update to latest stable compatible, expected 2.0.2 | Must expose `core.placebo.Tonemap`; verify existing kwargs and fallback path. Implementation must choose and document the artifact/source per target/platform, because the current Windows manifest uses a GitHub binary artifact and PyPI may be available for R74+ layouts. |
| libplacebo | Update to latest stable/working compatible | Keep libplacebo optional/fallback-aware; do not make GPU/libplacebo success a default hard requirement. Hold back only with ledger entry for safety, compatibility, licensing, platform-support, or verification reasons. |
| VSPreview | Update to latest stable compatible, expected 0.20.1 | Current lock has 0.19.0 and transitively pins VapourSynth 73. Ensure R76 resolution removes that drag. |
| Lock resolver | Use `uv lock --upgrade`; compare latest stable Python dry-run | Known Python 3.13 and 3.14 dry-runs add `annotated-doc`, remove `vsengine`, and add `vsjetengine`; rerun because latest stable Python is time-sensitive. |
| FFmpeg | Update to latest stable/working compatible artifact | Windows manifest currently uses a BtbN LGPL 7.1 build. Docker may keep distro packages only after comparing the chosen distro package/version against the actual latest stable/upstream FFmpeg candidate. Preserve license posture unless a licensing review approves a change; hold back any FFmpeg candidate only with ledger entry and proof of incompatibility, licensing issue, platform issue, safety risk, or unverifiability. |
| ffms2 | In scope for latest-stable/working audit and update | Update ffms2 wherever it is currently used, bundled, pre-sourced, or pinned for a supported runtime path. Adding ffms2 to a target that deliberately excludes it today, such as Windows portable, remains a loader-policy/licensing decision and requires explicit approval. |
| Docker | Update build/runtime plugin paths and runtime pins/artifacts | Docker must prove real VS + plugin integration, not just import success. Docker runtime pins and pre-sourced artifacts are part of the latest-stable/working update pass. |
| Windows portable | Update manifest/artifact layout and bundled artifacts for R76-era packaging | Preserve full bundle and code-only update semantics; plugin manifests/subdirs are first-class. Bundled artifacts are part of the latest-stable/working update pass. |

## Expected Python Lock Movement

The dry-run dependency movement observed on 2026-05-25 was:

- Add: `annotated-doc 0.0.4`, `vsjetengine 1.2.0`.
- Remove: `vsengine 0.2.0`.
- Update: `certifi 2026.5.20`, `charset-normalizer 3.4.7`, `click 8.4.1`, `coverage 7.14.0`, `fonttools 4.63.0`, `idna 3.16`, `jetpytools 2.2.7`, `kiwisolver 1.5.0`, `markdown-it-py 4.2.0`, `matplotlib 3.10.9`, `packaging 26.2`, `pyright 1.1.409`, `rich 15.0.0`, `ruff 0.15.14`, `typer 0.25.1`, `vapoursynth 76`, `vsjetpack 1.5.0`, `vspreview 0.20.1`.

This movement is non-authoritative until rerun. Implementation must re-run the dry-runs immediately before editing, because latest dependency state is time-sensitive.

## Files In Scope

- `pyproject.toml`
- `uv.lock`
- `Dockerfile`
- `docker-compose.yml`
- `tools/verify_docker_integration.sh`
- `.github/workflows/ci.yml`, when the approved Python support policy changes the CI Python version
- `.github/workflows/docker-integration.yml`
- `tools/windows_portable/**`
- `.github/workflows/windows-portable.yml`
- `tests/workflows/test_github_workflows.py`, when GitHub workflow files change
- `src/frame_compare/vs/**`
- `src/frame_compare/render/**`, only for direct VS/plugin compatibility fixes required by this update
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/cli/doctor_command.py`
- `tests/vs/**`
- `tests/render/**`, only for direct VS/plugin compatibility fixes required by this update
- `tests/orchestration/test_doctor.py`
- `tests/orchestration/test_doctor_runner.py`
- `tests/windows_portable/**`
- `README.md`
- `CONTRIBUTING.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`, only if a public CLI/JSON contract actually changes
- `VAPOURSYNTH_UPGRADE_AUDIT.md`, as historical/supporting documentation only

Render scope note: `src/frame_compare/render/**` and `tests/render/**` are included only to unblock direct VapourSynth/plugin compatibility issues found during this update. Their inclusion does not authorize render redesign, report output redesign, unrelated render behavior changes, or cleanup in render code.

## Files Out Of Scope

- Source-loader replacement outside the existing `lsmas` path.
- Report layout/output redesign.
- slow.pics, TMDB, audio alignment policy, and browser-opening behavior unless tests reveal dependency-induced breakage.
- Unrelated cleanup from dependency churn.
- Generated API docs unless importable API docs drift because touched symbols change.
- New repo-local `desloppify` workflow or scanner state.

## Public Contract Invariants

- Existing CLI commands remain: `version`, `run`, `wizard`, `doctor`, `preset`.
- No intentional flag rename, removal, or semantic change.
- `doctor --json` remains machine-readable JSON only on stdout.
- Human diagnostics may mention updated dependency names/paths, but JSON key/schema changes require explicit contract review.
- `run --json` and `--diagnose-paths` remain clean JSON stdout surfaces.
- Simple CLI commands and help/version must not eagerly import VapourSynth-heavy runtime code.
- Existing config defaults and persistence rules remain unchanged.
- `lsmas` remains the required source-loading capability.
- libplacebo remains optional/fallback-aware according to current behavior.
- Windows portable and Docker flows remain first-class supported runtime paths.
- `VAPOURSYNTH_UPGRADE_AUDIT.md` must not become a new authority surface. Current truth remains `AGENTS.md`, `docs/ENGINEERING_RUNBOOK.md`, `docs/current-architecture.md`, `docs/current-cli-contract.md`, and an approved active plan when one exists.

## Plan Splitting Policy

Keep this as one active plan with implementation slices unless a stop-and-replan trigger fires. A broad latest-stable/working refresh of FFmpeg, libplacebo, ffms2, plugins, runtime dependencies, and bundled/pre-sourced artifacts is in scope for this plan and does not by itself require splitting. A Python baseline bump may remain in this plan only if Slice 1 proves compatibility, names all public/release surfaces, and receives explicit maintainer approval before broad implementation. Split into a separate plan before implementation continues only if the work requires BestSource migration, public CLI/config contract drift, a release artifact licensing/posture change, a Python baseline policy change beyond the surfaces named here, or an architecture change not already scoped here.

## Dependency / Artifact Inventory And Held-Back Ledger

This section is the durable dependency/artifact inventory and held-back ledger location for this plan. While the plan is active, implementation slices must update these tables in this file before their slice is complete. Handoff notes may summarize decisions, but they are not the source of truth.

Status values:

- `pending`: candidate/source not yet validated.
- `updated`: chosen version/artifact moved to the latest stable/working compatible candidate.
- `held`: latest candidate was not adopted; reason and reevaluation path are mandatory.
- `removed`: component intentionally removed from the target path.
- `none held back`: class-level reconciliation statement when an in-scope component class has no holds.

Every row must include current version/artifact, latest candidate/source, chosen version/artifact, URL/hash/license where applicable, status, reason, verification evidence, and reevaluation path before closeout. If a component has separate Docker, Windows, local Python, or release/update artifacts, use separate rows so platform decisions are explicit.

### Python Dependency Inventory

Slice 1 owns this table. The rows below reflect the non-authoritative 2026-05-25 dry-run movement and must be replaced or extended with the final resolver result. Any additional package added, removed, or version-changed by the final `uv lock --upgrade` output must get a row before Slice 1 is complete.

| Component | Current | Latest candidate/source | Chosen | URL/hash/license | Status | Reason / reevaluation |
| --- | --- | --- | --- | --- | --- | --- |
| `annotated-doc` | not present | 0.0.4 from PyPI/uv resolver | 0.0.4 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Added by final `uv lock --upgrade`; re-run resolver before future dependency slices if the lock ages. |
| `certifi` | 2025.11.12 | 2026.5.20 from PyPI/uv resolver | 2026.5.20 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `charset-normalizer` | 3.4.4 | 3.4.7 from PyPI/uv resolver | 3.4.7 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `click` | 8.3.1 | 8.4.1 from PyPI/uv resolver | 8.4.1 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; CLI contract sanity required because help/output may be affected. |
| `coverage` | 7.13.0 | 7.14.0 from PyPI/uv resolver | 7.14.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `fonttools` | 4.61.1 | 4.63.0 from PyPI/uv resolver | 4.63.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `idna` | 3.15 | 3.16 from PyPI/uv resolver | 3.16 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `jetpytools` | 2.2.5 | 2.2.7 from PyPI/uv resolver | 2.2.7 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; later VS/runtime slices must prove real runtime behavior. |
| `kiwisolver` | 1.4.9 | 1.5.0 from PyPI/uv resolver | 1.5.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `markdown-it-py` | 4.0.0 | 4.2.0 from PyPI/uv resolver | 4.2.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `matplotlib` | 3.10.8 | 3.10.9 from PyPI/uv resolver | 3.10.9 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; later VSPreview smoke remains part of runtime/plugin slices. |
| `packaging` | 25.0 | 26.2 from PyPI/uv resolver | 26.2 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; re-run resolver before future dependency slices if the lock ages. |
| `pyright` | 1.1.407 | 1.1.409 from PyPI/uv resolver | 1.1.409 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Package upgrade accepted; Pyright `pythonVersion` remains 3.13 until a baseline bump is approved. |
| `rich` | 14.2.0 | 15.0.0 from PyPI/uv resolver | 15.0.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; CLI contract sanity required because help/output may be affected. |
| `ruff` | 0.14.10 | 0.15.14 from PyPI/uv resolver | 0.15.14 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Package upgrade accepted; Ruff `target-version` remains `py313` until a baseline bump is approved. |
| `typer` | 0.21.0 | 0.25.1 from PyPI/uv resolver | 0.25.1 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; CLI contract sanity required because help/output may be affected. |
| `vapoursynth` | 73 | 76 from PyPI/uv resolver and upstream R76 release | 76 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Target Python package accepted in lock; Docker/Windows plugin/runtime compatibility remains for later slices. |
| `vsengine` | 0.2.0 | removed by resolver | removed | Removed from `uv.lock`; previous locked artifact no longer selected | removed | Removal is resolver-driven after VSPreview/VapourSynth movement; repo source/test import scan found no direct `vsengine` imports. Replacement distribution `vsjetengine` still installs the `vsengine` module namespace. |
| `vsjetengine` | not present | 1.2.0 from PyPI/uv resolver | 1.2.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Added by final resolver output; later VSPreview/import sanity must keep proving importability. |
| `vsjetpack` | 1.1.0 | 1.5.0 from PyPI/uv resolver | 1.5.0 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; later VS/runtime slices must prove real runtime behavior. |
| `vspreview` | 0.19.0 | 0.20.1 from PyPI/uv resolver | 0.20.1 | PyPI/files.pythonhosted URLs and hashes recorded in `uv.lock`; license from upstream package metadata | updated | Accepted final resolver output; R76 resolution no longer locks `vapoursynth` to 73. |

Slice 1 verification notes:

- `uv lock --upgrade --dry-run` and `uv lock --upgrade --dry-run --python 3.14` both resolved the same package movement before the lock update.
- Latest stable Python candidate was checked against python.org on 2026-05-25: Python 3.14.5, released 2026-05-10. Local `uv` used installed CPython 3.14.4 for the minor-version dry-run.
- Clean frozen Python 3.13 proof used `.venv-r76-lock-verify` with `UV_PROJECT_ENVIRONMENT=.venv-r76-lock-verify uv sync --group dev --extra vspreview --frozen --python 3.13`, then imported `frame_compare` on CPython 3.13.13.
- Focused CLI contract sanity passed with the clean venv: `tests/cli/test_cli_commands.py`, `tests/cli/test_exit_codes.py`, `tests/e2e/test_cli_version.py`, and `tests/test_cli_contract_docs.py`.
- Package import/version smoke passed for `vapoursynth`, `vspreview`, `vsjetpack`, `vsjetengine` metadata, and `frame_compare`.
- Import-linter passed with the clean venv.
- Additional Pyright probe with upgraded Pyright 1.1.409 reported existing source churn outside Slice 1 edit scope: `src/frame_compare/utils/perf.py` needs the `@contextmanager` return annotation updated from `Iterator[...]` to `Generator[...]` or an approved typing-policy alternative.
- Additional Ruff probe with upgraded Ruff 0.15.14 reported existing-rule churn outside Slice 1 edit scope: UP042 on string enums and UP047 on `_keep_existing`. Do not treat full Ruff as clean until a follow-up slice either updates lint config or makes approved source edits.

### Runtime, Plugin, And Bundled Artifact Inventory

Slices 2-5 own this table. Current artifact IDs and versions come from the present Dockerfile and Windows manifest. Latest candidates and chosen artifacts must be filled with exact source URLs, artifact URLs, hashes, and licenses where the component is downloaded, bundled, or pre-sourced.

| Component / target | Current version/artifact | Latest candidate/source | Chosen version/artifact/source | URL/hash/license | Status | Reason / reevaluation |
| --- | --- | --- | --- | --- | --- | --- |
| Local Python VapourSynth plugin discovery | R73-era fallback checked `VAPOURSYNTH_PLUGIN_PATH` before bundle `vs/plugins` paths | R74+ discovery via `vapoursynth.get_plugin_dir()` plus `VAPOURSYNTH_EXTRA_PLUGIN_PATH`; legacy env path retained only as migration compatibility | Runtime discovery now checks `vapoursynth.get_plugin_dir()`, then `VAPOURSYNTH_EXTRA_PLUGIN_PATH`, then existing bundle `vs/plugins`, then legacy `VAPOURSYNTH_PLUGIN_PATH` | Not a downloaded artifact; upstream behavior references the VapourSynth R74/R75/R76 packaging docs listed in Research Sources | updated | Slice 2 focused tests passed for discovery order and doctor diagnostics; real Docker/Windows plugin proof remains assigned to Slices 4-5. |
| Docker Python base | `python:3.13.1-slim-bookworm` | Docker Official Image `python:3.13.13-slim-trixie` for the approved Python 3.13 support policy | `python:3.13.13-slim-trixie` | Docker Hub tag last updated 2026-05-22; linux/amd64 digest `sha256:7ba5f5888fbe0014ab9edb2278922995c2201fc3752c46b0be24763eb46fa9f3`; Python license plus Debian base package licenses | updated | Moves within the approved Python 3.13 baseline, updates Debian runtime from Bookworm to Trixie so current FFmpeg/libav packages satisfy plugin builds, and does not adopt Python latest baseline. Slice 4 Docker gate passed. |
| Docker uv image | `ghcr.io/astral-sh/uv:0.8.22` | Latest stable uv release `0.11.16` from GitHub/GHCR | `ghcr.io/astral-sh/uv:0.11.16` | GHCR index digest `sha256:440fd6477af86a2f1b38080c539f1672cd22acb1b1a47e321dba5158ab08864d`; linux/amd64 digest `sha256:265d074d08ed8080bc578087ca68a8e94611f9c7be671d40e18b3d3b1ad0dad4`; upstream license from Astral uv metadata | updated | Latest stable uv image selected for lock export. Slice 4 Docker gate passed. |
| Docker VapourSynth runtime | Source build from `VAPOURSYNTH_REF=R73` | R76 upstream release and PyPI wheel `vapoursynth==76` | PyPI wheel `vapoursynth==76`; direct source build removed | PyPI manylinux x86_64 wheel sha256 `94986f4399b3ea8ab775abfbf5986dc58b93829fbf3db2a37e3b9e6454baf898`; source tarball sha256 `09835e819373a373b8cfebdab1219795074348a5843b53d5f9c6b42e1ad3ff7a`; LGPL-2.1 license file in wheel | updated | Uses the R74+ wheel/package model rather than the old autotools source install. Slice 4 Docker gate proved import/version, `get_plugin_dir()`, plugin loading, and real frames. |
| Docker zimg | `release-3.0.5` with sha256 | Latest upstream zimg `release-3.0.6` | No separately built Docker zimg artifact; removed from direct Docker build because the R76 VapourSynth wheel owns the runtime payload | Candidate source archive sha256 `be89390f13a5c9b2388ce0f44a5e89364a20c1c57ce46d382b1fcc3967057577`; zimg license from upstream repository | removed | R76 wheel/package model replaces the old source-built VapourSynth/zimg stack. Reevaluate only if Docker proof shows the wheel lacks required zimg-backed VS behavior. |
| Docker L-SMASH | `v2.14.5` with sha256 | Latest upstream tag remains `v2.14.5` | `v2.14.5` source build | Source archive sha256 `e6f7c31de684f4b89ee27e5cd6262bf96f2a5b117ba938d2d606cf6220f05935`; ISC/BSD-style upstream license | updated | Latest available upstream L-SMASH is unchanged; retained because L-SMASH-Works still links `liblsmash`. Slice 4 Docker gate passed. |
| Docker L-SMASH-Works | `20230716` source tag | Latest HomeOfAviSynthPlusEvolution release `1282` | Source build from tag `1282`, installed under `/opt/vapoursynth-extra-plugins/lsmas` with `manifest.vs` | GitHub release `1282`; release asset sha256 `704b97db3d74667d13d4fa2a5cd94e36f885cd0158366efa1b8e43bf9e426bd7`; plugin source license from upstream `VapourSynth/LICENSE` | updated | Updated to latest release and installed as an R75-style plugin subdirectory. Slice 4 Docker gate proved `core.lsmas` with `LWLibavSource` and rendered a frame. |
| Docker libplacebo | `v7.349.0` source tag | Latest upstream libplacebo `v7.360.1`; latest working Docker path is bundled through `vs-placebo==2.0.2` wheel | Bundled `libplacebo-8913bea6.so.360` from PyPI `vs-placebo==2.0.2` manylinux wheel; direct source build removed | `vs_placebo-2.0.2-py3-none-manylinux_2_28_x86_64.whl` sha256 `cb44a42df2c7e78d614b4b0415e9b4d3c40659f9d57ac18d65076101f364fa8e`; libplacebo LGPL-2.1-or-later upstream license | updated | Uses the plugin wheel's bundled libplacebo payload, avoiding a separate source build while preserving optional/fallback-aware app behavior. Slice 4 Docker gate proved `core.placebo.Tonemap` and a rendered tonemap frame. |
| Docker vs-placebo | commit `14083805df08cd478539c15464a7183da2c0032e` from GitHub source | Latest stable release `2.0.2` from GitHub/PyPI | PyPI wheel `vs-placebo==2.0.2` | `vs_placebo-2.0.2-py3-none-manylinux_2_28_x86_64.whl` sha256 `cb44a42df2c7e78d614b4b0415e9b4d3c40659f9d57ac18d65076101f364fa8e`; upstream license from `vs-placebo` metadata/source | updated | Uses R74+ plugin wheel layout under `vapoursynth/plugins`. Slice 4 Docker gate proved `core.placebo.Tonemap`. |
| Docker ffms2 | commit `45673149e9a2f5586855ad472e3059084eaa36b1` from GitHub source | Latest stable release `5.0` | Source build from tag `5.0`, installed under `/opt/vapoursynth-extra-plugins/ffms2` with `manifest.vs` | GitHub release `5.0`; source tag `7ed5e4d`; upstream MIT license | updated | Updated to latest stable and built against Debian Trixie FFmpeg/libav packages. Slice 4 Docker gate proved the overall VS plugin set even though ffms2 remains non-primary for loading. |
| Docker FFmpeg libraries | Debian Bookworm `libav*`/`ffmpeg` packages | Upstream latest stable FFmpeg `8.0.2`; Debian Trixie security source package `7:7.1.4-0+deb13u1` | Debian Trixie `ffmpeg` and `libav*`/development packages from the base distro repositories | Debian source package `ffmpeg 7:7.1.4-0+deb13u1`; Debian package copyright/license metadata; upstream FFmpeg latest-stable evidence from ffmpeg.org | held | Upstream FFmpeg 8.0.2 is not adopted in Docker because source-building FFmpeg would materially expand build complexity, licensing review, and artifact maintenance beyond the existing distro-package posture. Trixie packages are newer than Bookworm, satisfy ffms2 5.0's FFmpeg >=6.1 requirement, and keep distro security updates. Reevaluate when Debian stable/backports ship FFmpeg 8.x or a separately approved FFmpeg artifact policy exists. |
| Windows Python embeddable | `python-embed-amd64` 3.13.1 | Python 3.13.13 embeddable package from python.org for the approved Python 3.13 support policy | `python-embed-amd64` 3.13.13 | `https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip`; sha256 `8766a8775746235e23cf5aee5027ab1060bb981d93110577adcf3508aa0cbd55`; Python-2.0 license | updated | Patch update within the current Python 3.13 baseline. Local static tests passed; Windows bundle proof remains documented-only on macOS until a Windows host runs the portable gate. |
| Windows VapourSynth portable/core | `vapoursynth-portable-r73`, R73 GitHub binary zip | R76 GitHub portable zip and PyPI `vapoursynth==76` wheel model | `vapoursynth-portable-r76`; builder installs the included `vapoursynth-76-cp312-abi3-win_amd64.whl` into `app/site-packages` | `https://github.com/vapoursynth/vapoursynth/releases/download/R76/VapourSynth64-Portable-R76.zip`; sha256 `db41537f3eb3f92fe1ff92ae59b4728129199e2afe3ba3b93d8527b46a7ba30c`; LGPL-2.1-or-later license | updated | Moves Windows to the R74+ wheel/package model. Builder and workflow now assert `vapoursynth.get_plugin_dir()` and R76 import/version. Real Windows proof remains documented-only on macOS. |
| Windows L-SMASH-Works | `vs-plugin-lsmas-vA.3j`, AkarinVS GitHub binary zip | HomeOfAviSynthPlusEvolution release `1282` Windows archive | `vs-plugin-lsmas-1282`, copying `x64/LSMASHSource.dll` to `vs/extra-plugins/lsmas/libvslsmashsource.dll` with `manifest.vs` | `https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/releases/download/1282/L-SMASH-Works-r1282.0.0.0.7z`; sha256 `704b97db3d74667d13d4fa2a5cd94e36f885cd0158366efa1b8e43bf9e426bd7`; upstream `VapourSynth/LICENSE` | updated | Latest compatible Windows binary chosen and installed under `VAPOURSYNTH_EXTRA_PLUGIN_PATH` with a manifest so R75+ plugin loading preserves the subdirectory. Windows proof must verify `core.lsmas.LWLibavSource` against tiny media. |
| Windows vs-placebo | `vs-plugin-vs-placebo-1.4.4`, GitHub binary zip | vs-placebo 2.0.2 GitHub release and PyPI Windows wheel | `vs-plugin-vs-placebo-2.0.2-win-amd64-wheel`; installed as a wheel under `app/site-packages`, placing `libvs_placebo.dll` in `site-packages/vapoursynth/plugins` | `https://files.pythonhosted.org/packages/a2/50/db34253e55e082ca7d0632b264fc042b6afb7474ed4b936b3a297f190749/vs_placebo-2.0.2-py3-none-win_amd64.whl`; sha256 `5a08511dc9feaa48a76373e5e8869bef0d4a6c2096607f92364e6a72ce975f94`; LGPL-2.1-or-later | updated | PyPI wheel selected because the 2.0.2 GitHub release has no attached binary assets and the wheel uses the R74+ package plugin layout. Builder/workflow prove `core.placebo.Tonemap` plus `apply_tonemap` on Windows when run. |
| Windows FFmpeg | `ffmpeg-btbn-win64-lgpl-7.1-2026-05-19` | BtbN latest autobuild 2026-05-25 includes n8.1.1 LGPL-only Windows artifacts | `ffmpeg-btbn-win64-lgpl-8.1-2026-05-25` | `https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-05-25-14-02/ffmpeg-n8.1.1-8-gb21e00eda5-win64-lgpl-8.1.zip`; sha256 `a4d1b2ded47ddc7befc7b01dd0794a063e8e90a90efbd601989f2b93dd12489f`; LGPL-2.1-or-later/legal URL `https://ffmpeg.org/legal.html` | updated | Preserves LGPL-only posture while moving to the latest working BtbN stable-branch artifact observed on 2026-05-25. Builder/workflow use `ffmpeg.exe` to generate tiny media for `LWLibavSource` proof. |
| Windows ffms2 | deliberately excluded from baseline bundle | ffms2 5.0 source/latest compatible artifacts only if policy changes | deliberately excluded from Windows bundle | No artifact bundled; ffms2 5.0 source/license recorded in Docker row | held | Adding ffms2 to Windows remains a loader-policy/licensing decision outside this slice because Windows continues to require `lsmas` as the primary source loader and no explicit approval was given to add a second Windows source-loader binary. Reevaluate if `lsmas` blocks Windows proof or maintainer approves a Windows ffms2 policy. |
| Release/update package workflow | Current full bundle plus code-only update scripts | Same full bundle/code-only update behavior with R76 runtime artifacts | Full bundle workflow updated; code-only update scripts unchanged | Generated artifact hashes only after Windows bundle build; manifest and workflow updated in this slice | updated | Full bundle path now asserts R74+ plugin layout and runtime smoke. Code-only update/signing behavior is unchanged, so local macOS work only ran static tests; Windows full bundle proof remains required before release. |

#### Slice 4 Docker Verification Evidence

On 2026-05-25, Slice 4 Docker proof passed locally with `bash tools/verify_docker_integration.sh` on the available Docker platform. The image resolved the R76 wheel model on Python 3.13.13 and reported:

```text
DOCKER_PROOF vapoursynth_import=ok version=R76
DOCKER_PROOF plugin_dir=/home/framecompare/.local/lib/python3.13/site-packages/vapoursynth/plugins
DOCKER_PROOF extra_plugin_path=/opt/vapoursynth-extra-plugins
DOCKER_PROOF core_plugins=ffms2,lsmas,placebo,resize,std,text
DOCKER_PROOF lwlibavsource=ok namespace=lsmas loaded_path=None
DOCKER_PROOF placebo_tonemap=ok
DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,placebo
```

The same gate ran Docker pytest for the configured integration surface with zero skips and `124 passed`. The successful build used the R76 PyPI wheel for runtime and copied R76 source compatibility headers into the builder include directory only for compiling L-SMASH-Works 1282 against the wheel-provided `vapoursynth.pc`.

#### Slice 5 Windows Verification Evidence

On 2026-05-25, Slice 5 local macOS proof was limited to static/script/workflow checks because the runbook Windows portable gate requires a Windows host. The builder was updated so a Windows run must hard-fail unless these required runtime phases pass:

```text
WINDOWS_BUNDLE_PROOF package_imports=ok modules=frame_compare,rich,tomli_w,typer
WINDOWS_BUNDLE_PROOF vapoursynth_import=ok version=R76
WINDOWS_BUNDLE_PROOF plugin_dir=<app/site-packages/vapoursynth/plugins>
WINDOWS_BUNDLE_PROOF extra_plugin_path=<bundle>/vs/extra-plugins
WINDOWS_BUNDLE_PROOF core_plugins=<non-empty namespaces>
WINDOWS_BUNDLE_PROOF lwlibavsource=ok namespace=lsmas loaded_path=<path or None>
WINDOWS_BUNDLE_PROOF placebo_tonemap_api=ok namespace=placebo function=Tonemap
WINDOWS_BUNDLE_PROOF apply_tonemap=ok frame=rendered fallback_aware=true libplacebo_runtime_usable=<true|false>
```

The direct `core.placebo.Tonemap(...)` invocation and `get_frame(0)` smoke now run as an isolated optional diagnostic after the required R76, `lsmas`, placebo API availability, and application-level `apply_tonemap` proofs. If it succeeds, it emits `WINDOWS_BUNDLE_PROOF placebo_direct_frame=ok`; if the host lacks a compatible Vulkan driver and exits nonzero or access-violates, the build emits a named `placebo_tonemap_frame` failed marker and warning instead of failing the Windows portable build. This matches the production path because `apply_tonemap` uses the runtime probe/fallback boundary before asking libplacebo to render.

The `vspreview`/`PyQt6` import smoke also runs in an isolated optional subprocess after the required runtime proofs. If it succeeds, it emits `WINDOWS_BUNDLE_PROOF pyqt6_import=ok` and `WINDOWS_BUNDLE_PROOF vspreview_pyqt6=ok`; if it exits nonzero or access-violates, the build emits a named `vspreview_pyqt6_import` failed marker and warning instead of masking the mandatory runtime proof. Docker remains the hard gate for direct raw placebo frame rendering with a compatible runtime, and the Windows workflow no longer repeats the long VS clip smoke because `build_portable.ps1` owns the Windows proof contract.

The Windows host must run the runbook portable path and confirm `frame-compare.ps1 doctor --json`, R76 import/version, R74+ plugin directory, `VAPOURSYNTH_EXTRA_PLUGIN_PATH`, `core.lsmas.LWLibavSource` against generated tiny media, `core.placebo.Tonemap` API availability, and fallback-aware `apply_tonemap(...).get_frame(0)`. Direct `core.placebo.Tonemap(...)` invocation/frame rendering and `vspreview`/`PyQt6` import status remain diagnostic evidence until a Windows host with compatible Vulkan/UI support proves them.

### Held-Back Ledger

No holds are approved by plan activation. Add one row per held component before a slice can close; do not aggregate multiple components into one vague hold.

If latest stable Python is evaluated but not adopted as the project baseline, add a `Python latest baseline` held row that records the candidate version, the chosen support policy, the compatibility or risk reason, evidence, affected surfaces, and the next reevaluation trigger.

| Component / target | Latest candidate not adopted | Chosen version/artifact | Reason held | Evidence | Reevaluation path |
| --- | --- | --- | --- | --- | --- |
| Python latest baseline | Python 3.14.5, latest Python 3 stable on python.org on 2026-05-25 | Keep project baseline at Python 3.13 for Slice 1; lock includes Python 3.13 and 3.14 compatible artifacts where resolver selected them | Baseline bump not adopted in this slice because it requires explicit maintainer approval plus coordinated edits to `requires-python`, classifiers, Pyright, Ruff, Docker base image, Windows embeddable artifact, CI, docs, and doctor/tests. Resolver compatibility alone is enough to recommend a checkpoint, not enough to change release/support surfaces. | `uv lock --upgrade --dry-run` and `uv lock --upgrade --dry-run --python 3.14` both resolved the same 72-package movement; local uv used CPython 3.14.4 for the 3.14 dry-run; python.org lists Python 3.14.5 released 2026-05-10 as latest stable Python 3. | Reevaluate at the maintainer checkpoint or next support-policy slice by proving Python 3.14.5 across Python dependencies/tooling, Docker, Windows embeddable/portable artifacts, VapourSynth/VSPreview wheels, CI, and doctor/version checks before editing baseline surfaces. |
| Docker FFmpeg latest upstream | Upstream FFmpeg 8.0.2, latest stable on ffmpeg.org during Slice 4 research | Debian Trixie `ffmpeg`/`libav*` packages from source package `7:7.1.4-0+deb13u1` | Docker retains distro packages instead of building or bundling upstream FFmpeg 8.0.2 because changing to a custom FFmpeg artifact would expand licensing review, security update ownership, build time, and binary maintenance beyond the existing distro-package posture. | Debian Trixie package evidence shows FFmpeg 7.1.x security packages, and ffms2 5.0 requires FFmpeg 6.1 or newer; the selected Trixie package family satisfies that compatibility floor while preserving distro updates. Slice 4 Docker proof passed `LWLibavSource` frame rendering and the configured Docker pytest surface with zero skips. | Reevaluate when Debian stable/backports provide FFmpeg 8.x, or when a separate approved Docker FFmpeg artifact policy names license posture, source/build inputs, hashes, security update ownership, and verification gates. |
| Windows ffms2 bundle | ffms2 5.0 latest stable source/plugin | No Windows ffms2 artifact bundled | Windows loader policy still requires L-SMASH-Works/`lsmas` as the primary source loader, and adding ffms2 to a target that deliberately excluded it requires explicit approval per this plan. | Slice 5 manifest keeps ffms2 excluded and updates Windows `lsmas` to L-SMASH-Works 1282; builder/workflow now require `LWLibavSource` proof against generated tiny media when run on Windows. | Reevaluate if L-SMASH-Works 1282 fails Windows proof, source-loader policy changes, or maintainer approves a Windows ffms2 binary/license plan. |

## Implementation Slices

### Slice 1: Python Baseline Decision And Lockfile Audit

Scope:
- Decide the Python support policy before broad implementation: keep Python 3.13 supported, bump the project baseline to latest stable Python, or temporarily prove both during a compatibility transition.
- Treat a clean frozen Python 3.13 proof as a compatibility guard for the current declared baseline while the latest-stable Python decision is unresolved. It is not a decision to keep Python 3.13 fixed forever.
- Evaluate latest stable Python as a candidate baseline using the current release at implementation time, not only the 2026-05-25 Python 3.14.5 observation.
- If latest stable Python is compatible with project dependencies, tooling, Docker Python base images, Windows embeddable/portable artifacts, VapourSynth/VSPreview wheels, and verification gates, prepare a maintainer approval checkpoint that proposes activating the baseline bump.
- If the baseline bump is approved, update all owned support-policy surfaces together: `requires-python`, Python classifiers, Pyright `pythonVersion`, Ruff `target-version`, Docker Python base images, Windows portable embedded Python manifest/artifact, README/CONTRIBUTING/docs, CI Python version, and doctor Python check/tests.
- If the approved baseline bump path edits `Dockerfile`, `tools/windows_portable/manifest.windows-x64.json`, release/update package behavior, or any release-path surface, Slice 1 inherits the matching Docker and/or Windows release-path gates for those changed surfaces. Slice 1 cannot close with those edits unless those gates pass or the implementation handoff records explicit documented-only release-path gaps and does not claim full release-path verification.
- If latest stable Python is not adopted, add a held-back ledger entry for Python latest with the reason, evidence, affected surfaces, and reevaluation path.
- Refresh Python dependencies to the accepted resolver output for the R76-centered lock update.
- Confirm current declared baseline and latest stable Python dry-runs stay aligned, or document and adjudicate the difference before continuing.
- Keep Python baseline unchanged unless maintainer approval for the bump is recorded.

Files:
- `pyproject.toml`
- `uv.lock`
- `.github/workflows/ci.yml`, only if the approved Python support policy changes the CI Python version
- `Dockerfile`, only if the approved Python support policy changes Docker Python base images
- `tools/windows_portable/manifest.windows-x64.json`, only if the approved Python support policy changes the Windows embedded Python artifact
- `README.md`
- `CONTRIBUTING.md`
- `docs/current-architecture.md`
- `docs/current-cli-contract.md`, only if public CLI/JSON contract actually changes
- `src/frame_compare/orchestration/doctor.py`
- `tests/orchestration/test_doctor.py`
- `tests/orchestration/test_doctor_runner.py`

Verification:
- `uv lock --upgrade --dry-run`
- `uv lock --upgrade --dry-run --python <latest-stable-python>`
- After editing `uv.lock`, prove the updated lock from a clean environment rather than the current venv. The clean frozen install proof follows the chosen support policy:
  - prove Python 3.13 if it remains supported;
  - prove latest stable Python if the baseline bump is approved;
  - optionally prove both if the transition preserves backwards compatibility for a defined period.

Example for the current declared Python 3.13 baseline:

```bash
UV_PROJECT_ENVIRONMENT=.venv-r76-lock-verify uv sync --group dev --extra vspreview --frozen --python 3.13
.venv-r76-lock-verify/bin/python -c "import sys; assert sys.version_info[:2] == (3, 13), sys.version; import frame_compare; print(sys.version)"
```

- The clean frozen sync/install must use the updated lock and must show explicit proof for the selected Python support policy. A dry-run against the existing `.venv` is insufficient.
- If Typer/Rich/Click movement can affect command help, output, or exit behavior: `.venv/bin/pytest -q tests/cli/test_cli_commands.py tests/cli/test_exit_codes.py tests/e2e/test_cli_version.py tests/test_cli_contract_docs.py`
- If the baseline changes, run doctor tests for Python version handling and workflow tests covering the changed CI/portable surfaces.
- If the baseline bump path changes Docker base images, run the Docker gate from Slice 4 or record a documented-only Docker release-path gap for Slice 1 closeout.
- If the baseline bump path changes the Windows embedded Python artifact, Windows manifest, bundle layout, update behavior, release layout, or package/update surface, run the applicable Windows gate from Slice 5 or record a documented-only Windows release-path gap for Slice 1 closeout.
- After lock update: run focused CLI/import sanity, then the full local verification gate.

Stop conditions:
- Any dependency requires a Python version outside the chosen support policy.
- Latest stable Python produces lock movement or runtime/tooling behavior that cannot be adjudicated before broad implementation.
- A normal Pyright or Ruff package upgrade requires changing Pyright `pythonVersion` or Ruff `target-version` without an approved baseline decision.
- Tool upgrades require broad formatting/type churn unrelated to the dependency update.

### Slice 2: VapourSynth Runtime Path And Plugin Discovery

Scope:
- Align runtime discovery with R74+ packaging.
- Use `vapoursynth.get_plugin_dir()` as the canonical plugin location where available.
- Use `VAPOURSYNTH_EXTRA_PLUGIN_PATH` for supplemental plugin paths.
- Avoid making `VAPOURSYNTH_PLUGIN_PATH` the future source of truth.
- Preserve compatibility with existing bundle/runtime behavior where required during migration.

Files:
- `src/frame_compare/vs/**`
- `src/frame_compare/orchestration/doctor.py`
- `tests/vs/test_env.py`
- `tests/orchestration/test_doctor.py`

Verification classification:
- `new regression/contract test required` for plugin discovery and doctor diagnostics.
- `broader integration/manual proof required` for real VS/plugin loading.

### Slice 3: Source Loader And Tonemap Plugin Compatibility

Scope:
- Verify `lsmas` namespace and `LWLibavSource` continue to work.
- Verify `core.placebo.Tonemap` still exists and current fallback behavior is preserved.
- Adjust only compatibility needed for R76/current plugin APIs.

Files:
- `src/frame_compare/vs/source.py`
- `src/frame_compare/vs/env.py`
- `src/frame_compare/vs/tonemap.py`
- `src/frame_compare/vs/tonemap_libplacebo.py`
- Adjacent focused tests under `tests/vs/**`

Verification:
- Focused VS tests.
- Real runtime proof through Docker and/or local VS environment.
- Full verification.

Stop conditions:
- `lsmas` cannot load supported input in real runtime proof.
- vs-placebo no longer supports required `core.placebo.Tonemap` behavior.
- Required fixes imply a loader abstraction or BestSource migration.

### Slice 4: Docker Runtime Update

Scope:
- Move Docker from R73-era VapourSynth/plugin assumptions to R76-era runtime.
- Update Docker runtime dependencies, plugins, and pre-sourced/bundled artifacts to latest stable/working compatible versions, including L-SMASH-Works, vs-placebo, libplacebo, FFmpeg, ffms2 where currently used/sourced/pinned for Docker, and similar runtime components.
- Preserve plugin subdirectories and manifests.
- Update env vars away from old plugin-path authority.
- Record a held-back dependency/artifact ledger entry for any Docker package, plugin, runtime component, or pre-sourced artifact not moved to latest stable.
- For Docker FFmpeg, compare the chosen distro package/version against the actual latest stable/upstream FFmpeg candidate before accepting the Docker package path. If the distro package is retained below latest stable/upstream, add a held-back ledger row with the compatibility, licensing, platform-support, safety, or verification reason, concrete evidence, affected Docker package path, and reevaluation trigger.

Files:
- `Dockerfile`
- `docker-compose.yml`
- `tools/verify_docker_integration.sh`
- `.github/workflows/docker-integration.yml`

Verification classification:
- `broader integration/manual proof required`.

Required gate:

```bash
bash tools/verify_docker_integration.sh
```

The script itself must assert every runtime proof item below and fail if any item is absent. Import-only checks cannot satisfy this gate accidentally; the script output should name the evidence it observed for each item.

If `.github/workflows/docker-integration.yml` changes, also run:

```bash
.venv/bin/pytest -q tests/workflows/test_github_workflows.py
```

Runtime proof must include:
- `import vapoursynth`
- `vapoursynth.__version__` or equivalent core/version proof
- plugin directory discovery
- `core.plugins()`
- `core.lsmas` or `core.lw` with `LWLibavSource`
- `core.placebo.Tonemap`
- at least one real frame render

### Slice 5: Windows Portable / Release Path Update

Scope:
- Update Windows portable manifest and assembly to R76-compatible latest-stable/working artifacts.
- Update bundled/pre-sourced Windows runtime artifacts to latest stable/working compatible versions, including FFmpeg, VapourSynth plugins, vs-placebo/libplacebo-related artifacts, L-SMASH-Works, ffms2 if it is currently used/sourced/pinned for Windows, and similar bundled components.
- Choose and document artifact/source per Windows target, especially for vs-placebo where the current manifest uses a GitHub binary artifact and PyPI may be available for R74+.
- Preserve `manifest.vs`, plugin subdirectories, optimized variants, and required DLL layout.
- Keep full bundle and code-only update semantics intact.
- Ensure launcher/runtime env uses the R76 packaging model.
- Record a held-back dependency/artifact ledger entry for any Windows portable package, plugin, runtime component, or bundled/pre-sourced artifact not moved to latest stable.

Files:
- `tools/windows_portable/**`
- `.github/workflows/windows-portable.yml`
- `tests/windows_portable/**`

Verification classification:
- `broader integration/manual proof required`.

Required Windows proof:
- Validate public key.
- Build the full portable bundle. This is required for every Windows manifest, artifact, runtime layout, or packaging-path change.
- Run bundle smoke check: `frame-compare.ps1 doctor --json`.
- Run real VapourSynth core/plugin discovery from the bundle, including `vapoursynth.get_plugin_dir()` where available, `core.plugins()`, and the expected R76-era plugin directory/manifests.
- Prove `lsmas` source loading by creating or using a tiny media file in the Windows runner, calling the discovered L-SMASH-Works source loader namespace (`core.lsmas` or the actual exported namespace) with `LWLibavSource`, and rendering at least one frame.
- Prove vs-placebo/tonemap behavior by checking `core.placebo.Tonemap` and running the existing bundle Python VS clip + tonemap smoke through `frame_compare.vs.tonemap.apply_tonemap`, including `get_frame(0)`.
- Code-only update zip and signing path proof is required only if updater behavior, update manifest behavior, release-package behavior, or signed update distribution changes. If only runtime artifacts inside the full bundle change and updater/release-package behavior is unchanged, do not add update-signing work to this plan.
- If manifest schema, release layout, bundle directory layout, updater payload layout, or artifact placement semantics change, run the relevant package/update workflow tests, including `.venv/bin/pytest -q tests/windows_portable/test_windows_portable_update_scripts.py tests/windows_portable/test_windows_portable_update_apply_e2e.py tests/windows_portable/test_windows_portable_workflow.py tests/workflows/test_github_workflows.py` as applicable.
- Any required unsigned dry run must be explicit in the implementation handoff and use `pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_update.ps1 -BundleDir <built-bundle> -OutFile <update.zip>` against the built bundle. Signing proof still requires the signing path and configured signing key handling.
- Treat `doctor --json` as necessary but insufficient, because it does not check `core.placebo.Tonemap`.
- If `.github/workflows/windows-portable.yml` changes, preserve or extend the existing workflow VS clip + tonemap smoke and run `.venv/bin/pytest -q tests/workflows/test_github_workflows.py tests/windows_portable/test_windows_portable_workflow.py`.
- If no Windows runner is available, record this as documented-only and do not claim full release-path verification.

### Slice 6: CLI Doctor Contract And Docs

Scope:
- Keep doctor behavior stable while updating dependency names, paths, hints, and audit notes.
- Update authority docs only where actual behavior changes.
- Update the stale `VAPOURSYNTH_UPGRADE_AUDIT.md` status so it does not continue to call R75 latest stable, while keeping it clearly historical/supporting rather than a new authority surface.

Files:
- `src/frame_compare/cli/doctor_command.py`
- `src/frame_compare/orchestration/doctor.py`
- `docs/current-cli-contract.md`, only if contract changes
- `docs/current-architecture.md`
- `README.md`
- `CONTRIBUTING.md`
- `VAPOURSYNTH_UPGRADE_AUDIT.md`

Verification:
- CLI doctor tests for human and JSON modes.
- `tests/test_cli_contract_docs.py` if CLI contract doc changes.
- If Typer/Rich/Click movement or doctor/help changes can affect CLI output, help, version, or exit behavior: `.venv/bin/pytest -q tests/cli/test_cli_commands.py tests/cli/test_exit_codes.py tests/e2e/test_cli_version.py tests/test_cli_contract_docs.py`
- Full verification.

Slice 6 closeout notes:

- `doctor --json` schema stayed unchanged; only the stale `doctor.baseline_version`
  value was corrected from `R73` to `R76`.
- `VAPOURSYNTH_UPGRADE_AUDIT.md` is now explicitly historical/supporting and points
  readers to the active R76 plan and current docs instead of presenting the R75
  snapshot as current authority.
- `README.md` no longer advertises `VapourSynth R72+`; it names R76 for the primary
  renderer after the dependency/runtime migration.
- `docs/current-cli-contract.md`, `docs/current-architecture.md`, and
  `CONTRIBUTING.md` did not need content changes for this slice.
- Windows host proof remains documented-only until the runbook Windows portable
  gate is executed on a compatible Windows host.

## Verification Gates

Primary verification mode: `integration-ops` with `contract-first` checks for CLI/JSON and release artifacts.

Required local gates after implementation:

```bash
UV_PROJECT_ENVIRONMENT=.venv-r76-lock-verify uv sync --group dev --extra vspreview --frozen --python 3.13
.venv-r76-lock-verify/bin/python -c "import sys; assert sys.version_info[:2] == (3, 13), sys.version; import frame_compare; print(sys.version)"
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/bandit -c pyproject.toml -r src --severity-level medium
.venv/bin/pytest -q
UV_CACHE_DIR=./.uv_cache uv run --no-sync lint-imports --config importlinter.ini
```

The first clean frozen install command is policy-dependent:

- If Python 3.13 remains supported, prove Python 3.13 as shown.
- If the approved baseline bumps to latest stable Python, replace `--python 3.13` and the assertion with the approved latest-stable version.
- If the approved transition preserves backwards compatibility, run separate clean frozen sync/import proofs for both Python 3.13 and latest stable Python.

Required Docker gate:

```bash
bash tools/verify_docker_integration.sh
```

This script must assert each Docker runtime proof item from Slice 4: VapourSynth import/version, plugin directory discovery, `core.plugins()`, L-SMASH-Works `LWLibavSource`, `core.placebo.Tonemap`, and a real rendered frame. The gate fails if the script only proves imports.

Required Windows gate on compatible host:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/validate_update_public_key.ps1 -PublicKeyPath tools/windows_portable/update_public_key.xml
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/windows_portable/build_portable.ps1 -ManifestPath tools/windows_portable/manifest.windows-x64.json -OutDir dist/frame-compare-portable-win-x64 -CacheDir .portable_cache
dist/frame-compare-portable-win-x64/frame-compare.ps1 doctor --json
# Plus the bundle Python runtime proof from Slice 5:
# - VapourSynth import/core/plugin directory discovery and core.plugins()
# - lsmas/L-SMASH-Works LWLibavSource source loading against a tiny media file
# - core.placebo.Tonemap API availability
# - fallback-aware apply_tonemap(...).get_frame(0), with libplacebo runtime probe status in the marker
# - optional direct core.placebo.Tonemap(...) invocation/get_frame(0) diagnostic when the Windows host has compatible Vulkan support
```

Windows update package policy:

- Full bundle build proof is always required for Windows runtime/artifact/layout changes.
- Code-only update zip and signing path proof is required only when updater behavior, release-package behavior, update manifest behavior, signing behavior, or update payload layout changes.
- If the manifest schema, release layout, bundle directory layout, artifact placement semantics, or update payload layout changes, run the relevant package/update tests and any explicit unsigned dry run named by the implementation handoff.

Add focused tests where changed behavior is contract-relevant:

- plugin discovery path selection
- doctor JSON stability
- missing/malformed plugin path diagnostics
- import-time lightness for simple CLI commands if touched
- Windows portable manifest/layout assertions when bundle layout changes
- Docker integration script assertions when runtime proof changes
- `tests/workflows/test_github_workflows.py` whenever `.github/workflows/*.yml` files change
- `tests/cli/test_cli_commands.py`, `tests/cli/test_exit_codes.py`, `tests/e2e/test_cli_version.py`, and `tests/test_cli_contract_docs.py` when Typer/Rich/Click lock movement or CLI code/docs changes can affect command help, output, version, or exit behavior

## Final Reconciliation Gate

Before this plan can be called complete, the implementation controller must reconcile `Dependency / Artifact Inventory And Held-Back Ledger` against the final diff and verification evidence.

Required closeout checks:

- Every in-scope component class has completed rows: Python dependency movement, local/runtime VapourSynth integration, Docker runtime dependencies/plugins/artifacts, Windows portable dependencies/plugins/artifacts, bundled/pre-sourced artifacts, and release/update package surfaces.
- The Python baseline decision is recorded: approved baseline bump with updated surfaces and proof, or explicit Python latest held-back ledger row with reason and reevaluation path.
- Any Slice 1 baseline-bump edits to Docker, Windows portable, or release/update surfaces have matching release-path gate evidence, or are explicitly recorded as documented-only release-path gaps without claiming full release-path verification.
- Each completed row has current version/artifact, latest candidate/source, chosen version/artifact/source, URL/hash/license where applicable, status, reason/evidence, and reevaluation path.
- If a component class has no held-back decisions, add an explicit `none held back` statement for that class in the ledger or status summary.
- Every `held` row has a reason broad enough for review, concrete proof, affected target paths, and a reevaluation trigger. Worker handoff notes alone do not satisfy this requirement.
- Closeout must stop if any hold, missing candidate, missing hash/license, missing Windows/Docker proof, or undocumented artifact-source decision remains unresolved.

## Rollback Surface

Rollback must be possible by reverting, as a unit:

- `pyproject.toml`
- `uv.lock`
- Docker runtime files
- Windows portable manifest/scripts
- VS runtime integration changes
- doctor diagnostic changes
- docs updated for this plan

Runtime rollback expectations:

- Docker can return to prior R73/plugin pins.
- Windows portable can return to prior manifest artifact IDs and old assembly path.
- Python dependency rollback restores the previous lock and transitive VSPreview/VapourSynth set.
- No persistent user config migration should be introduced, so no user config rollback path should be required.

## Stop And Replan Triggers

Stop implementation and return to planning if any of these occur:

- R76 cannot load `lsmas` reliably on Docker or Windows portable.
- L-SMASH-Works latest release lacks a compatible Windows or Linux artifact/build path.
- vs-placebo 2.0.2 no longer supports the required `core.placebo.Tonemap` path or current fallback policy.
- Latest stable FFmpeg, libplacebo, ffms2, plugin, runtime, or bundled/pre-sourced artifact candidates require a licensing/posture change, unsupported target-platform drop, or unverifiable release path that cannot be handled by an explicit held-back ledger entry.
- A held-back dependency/artifact decision becomes broad enough to undermine the full latest-stable/working update goal.
- Examples of broad held-back thresholds that require stop/replan instead of continuing with ledger-only holds:
  - Two or more core runtime/plugin classes, such as FFmpeg plus L-SMASH-Works or libplacebo plus vs-placebo, must remain on old artifacts across a supported target.
  - Any entire target path, such as Docker or Windows portable, cannot adopt the R76-era plugin layout while local Python can.
  - Latest-stable candidates for both source loading and tonemapping are held back, leaving the migration mostly on old plugin behavior.
  - A held-back decision changes license posture, supported platforms, source-loader policy, Python baseline, or release/update package semantics.
  - The implementation cannot name a concrete reevaluation trigger for a hold beyond "try again later."
- Preserving plugin manifests/subdirectories conflicts with current bundle layout.
- R76 requires a public CLI/config/JSON behavior change.
- The chosen Python support policy cannot be proved by clean frozen install/import verification.
- Latest stable Python adoption would require a baseline bump, Pyright target change, Ruff target change, Docker base image change, Windows embedded Python artifact change, CI version change, or doctor/docs updates without maintainer approval.
- Python latest is not adopted but no explicit held-back ledger entry with reason and reevaluation path exists.
- Windows portable verification cannot identify a credible R76 artifact/source strategy.
- Docker verification passes imports but fails real source loading or tonemap runtime behavior.
- Implementation requires broad compatibility shims, new dependencies, or architecture changes not named here.
- Any generated artifact or release asset layout change affects documented user install/update behavior.
- Any dependency/artifact update would change current user-facing functionality/defaults, source-loader policy, Python baseline, or CLI/config contract without explicit maintainer approval.

## Handoff Rules For Cleanup Loop

- Implement one slice at a time unless the controller explicitly batches tightly coupled files.
- Every slice must report changed public surfaces, verification run, verification gaps, and rollback notes.
- Every slice that touches dependencies, plugins, runtime artifacts, bundled/pre-sourced artifacts, Docker, Windows portable, or release/update packaging must update the inventory/ledger tables in this plan before handoff. Held-back decisions left only in worker notes are incomplete.
- Review loops must treat Docker and Windows portable as production paths, not optional smoke checks.
- Worker implementation prompts must name exact files in scope and files out of scope.
- Do not mark this plan complete until lock, runtime code, Docker, Windows portable, docs, and verification evidence have all been reconciled.

## Research Sources

- VapourSynth releases: <https://github.com/vapoursynth/vapoursynth/releases>
- VapourSynth PyPI: <https://pypi.org/project/VapourSynth/>
- VapourSynth installation docs: <https://www.vapoursynth.com/doc/installation.html>
- VapourSynth packaging docs: <https://www.vapoursynth.com/doc/packaging.html>
- VapourSynth R74 packaging post: <https://www.vapoursynth.com/2026/03/26/new-packaging-and-install-methods-in-r74/>
- VapourSynth R75 plugin manifest post: <https://www.vapoursynth.com/2026/04/30/r75-sanding-of-the-r74-edges-and-plugin-manifests/>
- vs-placebo releases: <https://github.com/Lypheo/vs-placebo/releases>
- vs-placebo PyPI: <https://pypi.org/project/vs-placebo/>
- L-SMASH-Works releases: <https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/releases>
- zimg releases: <https://github.com/sekrit-twc/zimg/releases>
- L-SMASH tags: <https://github.com/l-smash/l-smash/tags>
- libplacebo releases: <https://github.com/haasn/libplacebo/releases>
- ffms2 releases: <https://github.com/FFMS/ffms2/releases>
- FFmpeg downloads: <https://www.ffmpeg.org/download.html>
- Debian Trixie FFmpeg package/source: <https://packages.debian.org/source/trixie/ffmpeg>
- Docker Official Python image tags: <https://hub.docker.com/_/python/tags>
- uv releases: <https://github.com/astral-sh/uv/releases>
- Python latest release: <https://www.python.org/downloads/latest/>
