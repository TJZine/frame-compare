# VapourSynth Upgrade Audit

Date: 2026-05-25

Status: Historical research report only. This audit was an input to the VapourSynth
R76 dependency update and is no longer current authority for supported versions,
runtime layout, plugin paths, or implementation status. Current truth lives in
`docs/current-architecture.md`, `docs/current-cli-contract.md`, and the active
plan `docs/plans/2026-05-25-vapoursynth-r76-dependency-update.md` while that plan
remains active.

Scope:
- Audit the upstream VapourSynth changes from the project's then-current baseline (`R73`) to the upstream line available when the audit was written.
- Map those changes onto Frame Compare's then-current codebase, runtime layout, bundle logic, tests, and release surfaces.
- Identify compatibility-sensitive areas and open questions that must be answered before implementation planning.

Out of scope:
- Exact code changes
- Sequenced implementation plan
- Migration schedule
- Final technical design decisions

## Executive Summary

At the time this audit was written on 2026-05-25, Frame Compare was still materially aligned to a pre-R74 VapourSynth world.

The then-current project baseline was anchored to `R73` in more than one place:
- Windows portable bundle manifest: `tools/windows_portable/manifest.windows-x64.json`
- Docker build pin: `Dockerfile`
- Locked Python dependency state: `uv.lock`

Upstream VapourSynth changed its distribution and runtime model substantially in `R74` on 2026-04-05. The most important change was not a minor bugfix or plugin update; it was a packaging-model change:
- `pip install vapoursynth` became the recommended install path
- configuration/bootstrap changed
- plugin autoloading changed
- Windows install/portable expectations changed
- the project explicitly improved virtual-environment support

`R75` on 2026-04-30 then continued that direction, including more changes to plugin packaging and portable behavior.

The practical conclusion was that upgrading this repo to the current upstream line was not a "bump a version string" exercise. It was a cross-surface runtime audit involving:
- Windows portable bundle assembly
- bundle launcher environment variables
- plugin placement and discovery
- doctor/runtime diagnostics
- Docker/runtime pinning
- frame-property compatibility expectations
- CI smoke tests that currently encode older layout assumptions

This report does not prescribe the implementation. It is meant to establish the factual upgrade surface.

## Historical Upstream Status Snapshot

Original audit snapshot from early 2026-05-25, before the R76 update plan became
the active authority:

- Latest stable upstream release observed by this audit: `R75` (released 2026-04-30)
- Latest upstream prerelease observed by this audit: `R76RC1` (released 2026-05-09)
- Frame Compare baseline observed by this audit: `R73` (released 2025-11-24)

This section is historical evidence only. It must not be used to conclude that
R75 is the latest stable VapourSynth release or that Frame Compare's current
baseline is R73.

At the time of this audit, that meant the repo was behind:
- one major stable release transition (`R74`)
- one additional stable release (`R75`)
- one current prerelease line (`R76RC1`)

## What Changed Upstream

### `R73` (2025-11-24)

`R73` was the project's baseline when this audit was written and was the last release with Windows 7 support. It belongs to the older portable/runtime model that Frame Compare assumed at that time.

Relevant upstream notes:
- last release with Windows 7 support
- older portable-layout era
- pre-`pip install vapoursynth` transition

### `R74` (2026-04-05)

`R74` is the major transition release.

Relevant upstream notes:
- AVFS moved to a separate repository/download
- configuration and autoloading handling were "completely reworked"
- the application can now be installed with `pip install vapoursynth`
- virtual-environment support was greatly improved
- a new `_Range` property was added and `_ColorRange` was deprecated for API 4.2+ filters
- Windows binaries now require Windows 10
- support for Python versions older than 3.12 was dropped

This is the release that changes the assumptions Frame Compare currently encodes in its portable bundle and some of its VS-related runtime logic.

### `R75` (2026-04-30)

`R75` was the latest stable release observed when this audit snapshot was written.

Relevant upstream notes:
- plugins can ship multiple optimized copies for x64 and the best one is auto-selected
- simple plugin manifests were introduced
- portable-version behavior was improved
- `vsrepo` is installed by default again in the portable experience
- forwarding `.bat` files were added to more closely match pre-R74 paths

This mattered because Frame Compare implemented its own portable layout
normalization and command shims at the time of this audit. Upstream portable
behavior moved again after `R74`, not back to the exact `R73` model.

### `R76RC1` (2026-05-09, prerelease observed by this audit)

`R76RC1` was not a stable release when this audit snapshot was written, but it
indicated where upstream was moving at that time.

Relevant upstream notes:
- cache limits were reworked
- thread-count behavior was changed to reduce memory pressure
- config-location handling using `XDG_CONFIG_HOME` was corrected again

This looked less disruptive for Frame Compare than `R74`, but it confirmed that
upstream runtime/config behavior was still evolving after the packaging transition.

## Historical Upstream Distribution Model Snapshot

Upstream documentation available when this audit was written described a different
default installation model than the one Frame Compare bundled around at that time.

### General installation

The official docs reviewed for this audit recommended:
1. install Python 3.12+
2. run `pip install vapoursynth`
3. run `vapoursynth config`
4. on Windows, update the Visual Studio redistributable if prompted

Optional commands now include:
- `vapoursynth register-install`
- `vapoursynth register-legacy-install`
- `vapoursynth register-vfw`

Important implication:
- upstream now treats configuration/bootstrap commands as part of normal installation
- Frame Compare's current portable flow bypasses that model entirely and builds its own self-contained runtime

### Portable installation

The official docs reviewed for this audit described Windows portable setup through an automatic PowerShell script that sets up:
- embedded Python
- pip
- VapourSynth
- VSRepo

The docs also note that the portable script deletes hardcoded `Scripts` entry points and provides forwarding batch files in the root instead.

Important implication:
- upstream portable is now a script-generated environment, not simply "extract the old portable zip and treat its internal layout as stable forever"
- Frame Compare currently consumes a pinned portable archive and then post-processes its contents into a repo-specific layout

### Plugin autoloading

The official docs reviewed for this audit described plugin autoloading from:
- `<site-packages>/vapoursynth/plugins`

They also document:
- `VAPOURSYNTH_EXTRA_PLUGIN_PATH` as an additional path layered after the normal plugin path

Important implication:
- Frame Compare currently centers its bundle layout and runtime detection around a separate `vs/plugins` directory
- it also uses `VAPOURSYNTH_PLUGIN_PATH`, which is not the environment variable documented in the current official installation docs

### Plugin packaging

The plugin-packaging docs reviewed for this audit explicitly encouraged wheel-based packaging, with native plugin binaries installed into:
- `vapoursynth/plugins/` inside `site-packages`

Important implication:
- upstream is now steering plugin distribution toward Python-wheel packaging conventions
- Frame Compare still copies standalone plugin DLLs into a separate tree and manually normalizes bundle layout around them

### VSRepo

The docs reviewed for this audit said VSRepo could simply be installed with:
- `pip install vsrepo`

The `vsrepo` repository README still documents portable usage via:
- `-p` switch

Important implication:
- upstream still supports portable-oriented VSRepo usage
- but the distribution and installation expectations around VSRepo are now more packaging-centric than the old archive-centric model

## Historical Frame Compare State Observed By This Audit

## 1. Hard pins to the old line

At the time of this audit, Frame Compare was not only "using VapourSynth"; it was
explicitly pinned to the old distribution model.

Relevant local evidence:
- `tools/windows_portable/manifest.windows-x64.json`
  - `vs_ref` is `R73`
  - artifact id is `vapoursynth-portable-r73`
  - URL points to `VapourSynth64-Portable-R73.zip`
- `Dockerfile`
  - `ARG VAPOURSYNTH_REF=R73`
- `uv.lock`
  - contained `vapoursynth==73`

This means the portable bundle, Docker runtime, and Python lock state are not aligned to separate upstream generations by accident. They are intentionally pinned to the same old baseline.

## 2. Bundle layout assumptions

At the time of this audit, the Windows portable build script assumed an older
portable archive shape and then transformed it into Frame Compare's own layout.

Relevant local evidence:
- `tools/windows_portable/manifest.windows-x64.json`
  - notes that the archive includes `vs-coreplugins/` and `vs-plugins/`
  - expects assembly into a project-owned layout using `vs/core` and `vs/plugins`
- `tools/windows_portable/build_portable.ps1`
  - `Consolidate-VapourSynthPlugins`
  - copies DLLs out of `vs-coreplugins` and `vs-plugins`
  - deletes those original directories after consolidation

This is a strong signal that the project is not merely consuming upstream portable behavior. It is normalizing an older layout into its own single source of truth.

## 3. Bundle launcher environment assumptions

At the time of this audit, the generated bundle launcher configured VapourSynth
through a hand-built set of environment variables and PATH entries.

Relevant local evidence:
- `tools/windows_portable/build_portable.ps1`
  - sets `VAPOURSYNTH_CONF_PATH` to `vs/core/portable.vs`
  - sets `VAPOURSYNTH_PLUGIN_PATH` to `vs/plugins`
  - searches recursively for `VSScript.dll`
  - sets `VAPOURSYNTH_HOME`
  - prepends `vs/core`, `vs/plugins`, `python`, `ffmpeg`, and subdirectories onto `PATH`

This is not a generic "use the official R74+ bootstrap". It is a custom runtime contract.

## 4. Python wheel installation assumptions

At the time of this audit, the build script installed the VapourSynth Python
module from a wheel extracted out of the pinned portable bundle.

Relevant local evidence:
- `tools/windows_portable/build_portable.ps1`
  - expects exactly one wheel in `vs/core/wheel`
  - looks for `vapoursynth-*-abi3-win_amd64.whl`
  - installs that wheel into `app/site-packages`
  - then normalizes `vapoursynth.dll` placement

This is a high-risk upgrade area because it assumes:
- a wheel exists inside the portable artifact
- the wheel path is stable
- the wheel naming pattern is stable
- `vapoursynth.dll` may need manual relocation beside the extension module

Any of those assumptions may differ in the current upstream portable/bootstrap model.

## 5. Runtime import and plugin detection assumptions

At the time of this audit, the project's VS runtime helper module reflected the
custom bundle model.

Relevant local evidence:
- `src/frame_compare/vs/env.py`
  - searches Windows DLL candidates under `vs/core`
  - treats `VAPOURSYNTH_HOME` as a primary signal
  - reads `VAPOURSYNTH_PLUGIN_PATH`
  - hardcodes `bundle_root/vs/plugins/libvslsmashsource.dll` as a candidate plugin path

This creates a direct dependency between bundle layout and runtime import behavior.

## 6. Doctor assumptions

At the time of this audit, the doctor surface was tightly coupled to the loader
contract.

Relevant local evidence:
- `src/frame_compare/orchestration/doctor.py`
  - treats VapourSynth as a core dependency check
  - treats `lsmas` as a core dependency check
  - if autoload misses `lsmas`, it attempts fallback loading through the current plugin-path logic

This means an upstream change in plugin autoloading or plugin placement affects not only runtime success, but diagnostic correctness and user-facing installation guidance.

## 7. Frame property assumptions

The project currently uses `_ColorRange` heavily in Python-side code.

Relevant local evidence:
- `src/frame_compare/vs/color.py`
- `src/frame_compare/vs/tonemap_conversion.py`
- `src/frame_compare/vs/tonemap_runtime.py`
- `src/frame_compare/vs/types.py`

Upstream `R74` explicitly introduced `_Range` and deprecated `_ColorRange` for API 4.2+ filters.

Important nuance:
- this does not automatically prove that Frame Compare is broken today
- but it does prove there is an API-contract audit item that is broader than Windows portable alone

## 8. Docker/runtime coupling

The repo's non-Windows runtime surface also stays on `R73`.

Relevant local evidence:
- `Dockerfile`
  - clones and builds VapourSynth from `R73`
  - populates `/usr/local/lib/vapoursynth`
  - sets `VAPOURSYNTH_PLUGIN_PATH=/usr/local/lib/vapoursynth`

This matters because any serious upstream alignment decision probably affects:
- Windows portable bundle logic
- Docker runtime behavior
- test environments that rely on one or both

## 9. CI and smoke-test assumptions

The Windows portable workflow tests current bundle behavior rather than current upstream behavior.

Relevant local evidence:
- `.github/workflows/windows-portable.yml`
  - builds the bundle with the repo script
  - smoke-tests `frame-compare.ps1 doctor --json`
  - manually recreates the bundle runtime environment
  - sets `VAPOURSYNTH_PLUGIN_PATH`
  - searches for `VSScript.dll`
- `tests/windows_portable/test_windows_portable_workflow.py`
  - protects zip layout assumptions

This means the CI surface will need review whenever the underlying runtime model changes, even if no user-facing CLI changes occur.

## macOS-First Development Constraint

This audit should explicitly account for the likely execution model:
- first research and first implementation passes may happen on macOS
- Windows remains the authoritative validation surface for the current portable-bundle path

That constraint matters because the upstream `R74+` world is more cross-platform than the current Frame Compare portable path.

### What macOS can validate well

Current official VapourSynth docs describe binary-wheel installation for Windows, Linux, and OSX through:
- `pip install vapoursynth`
- `vapoursynth config`

That means a macOS-first spike is a valid place to evaluate:
- the modern pip-first core install model
- config/bootstrap behavior in the `R74+` line
- Python environment assumptions
- whether newer plugin-packaging paths are structurally easier to consume

### What macOS cannot close for this repo

Frame Compare's current Windows portable runtime depends on Windows-only behavior that macOS cannot prove:
- PowerShell installers and bundle assembly
- `.cmd` and `.ps1` launchers
- `VSScript.dll` discovery
- `os.add_dll_directory(...)` fallback logic in `src/frame_compare/vs/env.py`
- Windows DLL placement and DLL search-path behavior
- bundle-specific `PATH`, `VAPOURSYNTH_HOME`, and plugin-directory wiring
- Windows portable smoke tests in `.github/workflows/windows-portable.yml`

So a macOS-first implementation pass can validate upstream direction, but it cannot be treated as final proof that the Windows bundle path is correct.

### Practical implication for this audit

Any future work should distinguish between:
- core/package-model validation that can happen on macOS
- final bundle/runtime validation that must happen on Windows

This is especially important for plugin loading, because current Frame Compare Windows behavior is tied to bundled DLLs and Windows-specific loader behavior.

## Essential Plugin Compatibility and Sourcing

The upgrade surface is not just the core VapourSynth package. Frame Compare currently depends on specific plugin contracts that are essential to normal operation.

The critical plugins are:
- `lsmas` / L-SMASH Works
- `vs-placebo`

Local evidence for that dependency:
- `src/frame_compare/vs/source.py` requires `lsmas` and specifically resolves `LWLibavSource`
- `src/frame_compare/vs/env.py` and `src/frame_compare/orchestration/doctor.py` treat `lsmas` as a core runtime capability
- Frame Compare tonemap paths depend on the `placebo` namespace exposed by `vs-placebo`

### Current plugin sourcing in this repo is already split

The repo does not currently use one single source/version policy for the essential plugins.

#### `lsmas` / L-SMASH Works

Windows portable bundle:
- `tools/windows_portable/manifest.windows-x64.json`
- pins `vs-plugin-lsmas-vA.3j`
- downloads from `AkarinVS/L-SMASH-Works`

Docker/runtime path:
- `Dockerfile`
- pins `LSMASH_WORKS_REF=20230716`
- builds from `HomeOfAviSynthPlusEvolution/L-SMASH-Works`

Current upstream maintained release line:
- `HomeOfAviSynthPlusEvolution/L-SMASH-Works` latest release is `20260326 1282.0.0.0` as of this audit

Audit implication:
- the same essential plugin is already sourced differently across Windows portable and Docker
- that source/version divergence should be treated as part of the upgrade audit, not as an afterthought

#### `vs-placebo`

Windows portable bundle:
- `tools/windows_portable/manifest.windows-x64.json`
- pins `1.4.4` from `Lypheo/vs-placebo`

Current upstream release line:
- `Lypheo/vs-placebo` latest release is `2.0.2` as of this audit
- `2.0.1` release notes explicitly state that `vs-placebo` is available on PyPI and can be installed with `pip install vs-placebo` for VapourSynth `R74+`

Audit implication:
- `vs-placebo` has already crossed into the newer `R74+` packaging model
- Frame Compare is still pinned to an older standalone release artifact

### Plugin compatibility is a first-class upgrade concern

A successful core VapourSynth upgrade is not sufficient if the plugins Frame Compare actually relies on no longer match the runtime assumptions.

The upgrade must preserve, or deliberately replace, all of the following:
- `lsmas` namespace/function availability
- `LWLibavSource` behavior relied on by the current loader contract
- `placebo.Tonemap` availability and behavior
- Windows binary compatibility for the bundled plugin artifacts

### Why this matters even more with macOS-first implementation

A macOS-first spike may be useful for validating the modern pip-first model, especially for `vs-placebo` now that it has a PyPI path in the `R74+` world.

But macOS cannot validate:
- the Windows DLL artifacts that the current portable bundle consumes
- the current Windows-only plugin loading path
- the final Windows bundle source/version choices for `lsmas` and `vs-placebo`

So plugin compatibility needs to be audited at two levels:
- packaging-model compatibility
- Windows bundle artifact compatibility

## Highest-Relevance Mismatch Inventory

### 1. Distribution model mismatch

Upstream today is pip-first.

Frame Compare today is still portable-archive-first plus custom post-processing.

This is the single biggest structural mismatch.

### 2. Plugin location mismatch

Upstream docs now center plugin autoloading on:
- `site-packages/vapoursynth/plugins`

Frame Compare centers it on:
- `vs/plugins`

This affects:
- bundle layout
- autoloading behavior
- fallback plugin loading
- doctor behavior
- plugin upgrade expectations

### 3. Environment-variable mismatch

Upstream docs now explicitly document:
- `VAPOURSYNTH_EXTRA_PLUGIN_PATH`

Frame Compare currently uses:
- `VAPOURSYNTH_PLUGIN_PATH`

This does not prove the current variable stopped working, but it is an immediate contract-drift warning.

### 4. Bootstrap/config mismatch

Upstream now documents:
- `vapoursynth config`
- registration commands for interoperability

Frame Compare currently bypasses that model and directly wires:
- `VAPOURSYNTH_CONF_PATH`
- `VAPOURSYNTH_HOME`
- `PATH`

This creates risk that the repo is depending on older bootstrap behavior rather than the supported current flow.

### 5. Portable artifact shape mismatch

Frame Compare expects:
- an archive containing `vs-coreplugins`, `vs-plugins`, and a wheel folder

Upstream portable docs now describe:
- an automatic install script
- root forwarding batch files
- installed VSRepo

The exact shape of the current official portable deliverable therefore needs validation before any implementation work starts.

### 6. VSRepo expectation mismatch

Upstream `R75` says portable behavior again installs `vsrepo` by default and includes forwarding batch files.

Frame Compare:
- does not currently expose upstream-style `vsrepo` behavior as part of its own bundle contract
- instead ships only the repo's own app launchers and updater shims

This is not necessarily wrong, but it is a deliberate divergence that must be understood before upgrade work begins.

### 7. Frame property contract mismatch

Upstream `R74` introduced `_Range` and deprecated `_ColorRange` for newer filters.

Frame Compare still uses `_ColorRange` pervasively.

This is a likely compatibility audit item for:
- HDR/SDR conversion
- tonemap paths
- overlay/report metadata correctness
- any future plugins built only against the newer property expectations

### 8. Runtime pin mismatch outside Windows

Even if Windows portable is upgraded, Docker would still remain on `R73` unless audited in the same effort.

That means "upgrade VapourSynth for the project" is broader than the portable bundle.

## What Looks Favorable

Not everything points toward a hard reset.

There are some facts in Frame Compare's favor:
- project Python baseline is already `3.13`, which fits upstream's current `3.12+` requirement
- the repo already treats VapourSynth imports lazily in the CLI and centralizes runtime ownership in `frame_compare.vs.env`
- plugin fallback is centralized instead of scattered
- the Windows bundle build already has a dedicated assembly layer rather than assuming raw upstream layout throughout the app

In other words, the repo has a reasonable containment boundary for this migration. The problem is not "VapourSynth assumptions are everywhere equally"; the problem is "the assumptions that do exist are strong and explicit."

## Open Questions That Need Validation Before Code Planning

These are research questions, not implementation instructions.

1. What exactly are the official Windows release assets for `R75` today?
   - Is there still a portable archive with a stable internal structure?
   - Is the PowerShell portable installer now the only supported portable path?

2. If a portable asset still exists, does it still contain:
   - a wheel directory
   - `VSScript.dll` in a discoverable location
   - plugin directories analogous to `vs-coreplugins` / `vs-plugins`

3. If the official modern path is script-generated rather than archive-based, should Frame Compare continue:
   - consuming upstream artifacts directly
   - or generating its own normalized layout from the pip-installed model

4. Does current upstream still honor `VAPOURSYNTH_PLUGIN_PATH` on Windows in the way this repo currently relies on, or is `VAPOURSYNTH_EXTRA_PLUGIN_PATH` the supported future-facing path?

5. Which plugin source/version policy should be considered authoritative for `lsmas` across:
   - Windows portable
   - Docker
   - any future macOS-first development environment

6. For `vs-placebo`, is the correct long-term source:
   - standalone release zips
   - PyPI packaging for `R74+`
   - or a project-controlled pinned binary strategy

7. How much of Frame Compare's current `_ColorRange` handling is:
   - harmless legacy compatibility
   - semantically deprecated but still functioning
   - or actively wrong against newer plugin/filter expectations

8. Does the Docker path want to remain a separate curated build from source, or should it eventually align with the pip-first upstream runtime model as well?

## Source Inventory

Primary upstream sources used for this audit:
- VapourSynth releases page:
  - https://github.com/vapoursynth/vapoursynth/releases
- `R74` release notes:
  - https://github.com/vapoursynth/vapoursynth/releases/tag/R74
- `R75` release notes:
  - https://github.com/vapoursynth/vapoursynth/releases/tag/R75
- `R76RC1` prerelease notes:
  - https://github.com/vapoursynth/vapoursynth/releases/tag/R76RC1
- Current official installation docs:
  - https://www.vapoursynth.com/doc/installation.html
- Current official plugin-packaging docs:
  - https://www.vapoursynth.com/doc/packaging.html
- VSRepo repository README:
  - https://github.com/vapoursynth/vsrepo
- Upstream packaging-rationale discussion:
  - https://github.com/vapoursynth/vapoursynth/issues/1177
- L-SMASH Works releases:
  - https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/releases/
- vs-placebo releases:
  - https://github.com/Lypheo/vs-placebo/releases

Primary local sources used for this audit:
- `tools/windows_portable/manifest.windows-x64.json`
- `tools/windows_portable/build_portable.ps1`
- `tools/windows_portable/README.txt`
- `src/frame_compare/vs/env.py`
- `src/frame_compare/orchestration/doctor.py`
- `src/frame_compare/vs/color.py`
- `src/frame_compare/vs/source.py`
- `Dockerfile`
- `.github/workflows/windows-portable.yml`
- `tests/windows_portable/test_windows_portable_workflow.py`
- `docs/current-architecture.md`
- `docs/DECISIONS.md`
- `uv.lock`

## Bottom Line

The upgrade target is not just "newer VapourSynth binaries." It is a move from the `R73` distribution/runtime model to the modern `R74+` model.

For Frame Compare, that means the real audit boundary includes:
- portable bundle assembly
- runtime bootstrap
- plugin discovery
- plugin source/version policy
- plugin binary compatibility
- doctor diagnostics
- frame-property handling
- Docker pinning
- CI smoke-test assumptions

The repo is still early enough in development that taking this upgrade seriously now makes sense. But the evidence does not support treating it as a narrow version bump. The current codebase has multiple deliberate, valid, but older-model assumptions that will need explicit re-evaluation against the upstream `R74+` world, and the plugin story is part of that upgrade surface rather than a separate follow-up item.
