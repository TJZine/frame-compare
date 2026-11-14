# Supported Media Runtime

Frame Compare treats its media dependencies as one compatibility-sensitive runtime.
Decoder plugins, FFmpeg libraries, tone mapping, generated indexes, cache identities,
portable artifacts, and license/source metadata are selected and validated together.
A version shown here is supported only as part of the complete profile described below.

## Supported component matrix

| Component | Previous baseline | Selected component | Upstream date | Selection kind | Why this selection |
| --- | --- | --- | --- | --- | --- |
| Python | 3.13.17 | **3.13.18** (Docker), **3.14.10** (Windows portable) | 2026-10-25 | Stable security releases | Docker retains Python 3.13. Python.org distributes 3.13.18 as source and provides the official Windows embeddable ZIP for 3.14.10. |
| VapourSynth | R81 | **R82**, commit `e0fadcc1c8977e99b11ce2e478996a867a939874` | 2026-11-01 | Formal stable release | Retains API R4.3 and CPython 3.12 ABI3 wheels. Includes Matroska output metadata and GPU interoperability fixes. |
| VSView | 0.13.0 | **0.14.0** | 2026-10-26 | Stable Python release | Retains named outputs and the base dependency graph. The Frame Compare alignment panel uses the version-gated workspace bridge. |
| PySide6 | Previous Qt binding | **6.12.0** | 2026-10-08 | Locked Python resolution | VSView's documented Qt backend. The portable bundle pins the matching Qt runtime and requires native startup proof before release. |
| Qt PDF (Windows) | Qt 6.11.2 source bundle | **6.140.0**, source commit `d505fc23640d2bd6345e6483eb73daf4e19f5829` | SDK build 2026-09-28 | Paired installer source commit | PySide6-Pdf 6.12.0.140 uses the separately versioned Qt PDF product. PDF remains in the portable profile; WebEngine runtime files remain excluded. |
| Qt Multimedia FFmpeg (Windows) | 7.1.5 | **9.0.1** | PySide6 6.12.0 build | Wheel-bundled LGPL build | Distinct from the standalone BtbN FFmpeg and the L-SMASH decoder library lineage. |
| VSJetEngine | 1.8.1 | **2.0.0** | 2026-10-26 | Stable Python release | Required by VSView 0.14.0. |
| VSView support graph | Cyclopts 5.3.0; vsjetengine 1.8.1; BestSource 22 | **Cyclopts 5.4.2; jetpytools 3.2.0; vsjetengine 2.0.0; BestSource 23 (tag `R23`, commit `bca32dac44794d93f3e580f9573c58c4a0e7671f`); vspackrgb 2.0.0** | BestSource 2026-10-28 | Locked Python resolution | BestSource 23 requires VapourSynth R81 or newer. Its published Intel and Apple Silicon wheels require macOS 15 or newer. |
| L-SMASH-Works | 1296.0.0.0 | **1310.0.0.0**, commit `7e65185d3f08ba4ad191e9a5cbba3e2c6fd3bb67` | 2026-08-23 | Formal native release | Latest stable native release. It preserves the API 4 video source surface and adds audio source filters plus audio-gap corrections. |
| Windows L-SMASH-Works package | 1296.0.0.1 | **vapoursynth-lsmas 1310.0.0.0** | 2026-08-23 | Non-yanked official PyPI wheel | Official wheel for the 1310 native lineage. Its plugin DLL imports only Windows/UCRT system libraries; unlike the release archive DLL, it does not require external MSVCP140 or VCRUNTIME140 DLLs. |
| L-SMASH | commit `84740c5d960ab622f4c08b971dc59192bc27ef74` | commit **`d186eb95388710a7a91f6fd353169b457ebbb9db`** | 2026-07-28 | Pinned maintainer-fork commit, not a release | Exact L-SMASH revision selected and tested by L-SMASH-Works 1310. No newer appropriate formal stable tag supersedes it. |
| OBUParse (Docker) | Not present | commit **`a67fcab9cd9d56c866a7a860f8c4aeb91b8817e8`** | 2026-06-22 | Pinned commit, shared library | Required directly by the selected L-SMASH revision (`obuparse.h` and `-lobuparse`). Docker builds the shared target and preserves `libobuparse.so.2` plus its unversioned symlink. |
| FFMS2 | 5.0 | **5.0**, commit `7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04` | 2024-05-28 | Formal stable release | 5.0 remains the latest formal stable release. It is rebuilt for Docker against the selected VapourSynth and Debian FFmpeg stack and remains excluded from Windows. |
| vs-placebo | 2.0.4 | **2.0.5**, commit `e965afc70167b27924585737477fcd587942824d` | 2026-11-05 | Non-yanked stable release | Updates Dolby Vision mapping for libplacebo v7.387.0. |
| libplacebo used by vs-placebo | commit `a7a18af88ff0a17c04840dcb3246047bb6b46df3` | **v7.387.0**, commit `275f7dea27924cdd34ab2e6c20e448b6bc4fab65` | 2026-10-25 | Upstream-pinned tag | Version selected by vs-placebo 2.0.5. |
| libdovi used by vs-placebo | 3.3.2 | **3.3.2** for Docker, **3.4.0** for Windows portable | Platform-specific wheel builds | Upstream source tags | The Linux build explicitly selects 3.3.2. The Windows wheel uses the MSYS2 UCRT64 package. |
| Windows FFmpeg | `n8.1.3-9-g29e619e767` (September 2026 build) | **`n8.1.3-27-g8dca1586f4`**, BtbN build `autobuild-2026-10-31-12-59` | 2026-10-31 | Immutable retained release artifact | End-of-month Windows x64 LGPL-only artifact from the stable FFmpeg 8.1 branch. |
| Linux FFmpeg | Debian Trixie packages | **`7:7.1.5-0+deb13u1`** | Resolved during validation | GPL-enabled Debian package | Runtime and development packages remain aligned to Debian Trixie. Required Docker fixtures use the packaged `libx264` and `libx265` encoders; Frame Compare does not replace Debian FFmpeg with a custom upstream build. |

Primary upstream evidence is recorded in `Dockerfile` and
`tools/windows_portable/manifest.windows-x64.json`. Docker fetches each exact
40-character Git commit and verifies a deterministic SHA-256 over the complete tracked
tree; it does not rely on GitHub-generated archive bytes as an immutable boundary.
Windows binary/source artifacts remain fail-closed on exact downloaded byte size and
SHA-256. Both surfaces record source revisions and license metadata.

The official L-SMASH-Works, vs-placebo, and PySide6 wheels keep the library
versions actually used by their upstream builds. New standalone dav1d, libxml2,
libvpx, xxHash, nv-codec-headers, or libdovi releases do not change those binaries;
only a new verified upstream wheel can refresh their corresponding-source records.
The selected PySide6 6.12.0 graph includes the separately packaged WebEngine and
PDF distributions. The portable bundle retains its WebEngine/Chromium payload
exclusion and keeps PDF support. Physical Windows acceptance for this candidate
remains required.

Qt PDF's source is pinned to the [official installer source package](https://download.qt.io/online/qtsdkrepository/all_os/extensions/qtwebengine/6120/61400/src_doc_examples/extensions.qtwebengine.6120.61400.src/6.12.0-0-202609281005qtwebengine-everywhere-src-6.140.0.tar.xz)
paired with [Windows SDK build `6.12.0-0-202609281005`](https://download.qt.io/online/qtsdkrepository/windows_x86/extensions/qtpdf/6120/61400/msvc2022_64/Updates.xml).
The SDK's source inventory identifies commit `d505fc23640d2bd6345e6483eb73daf4e19f5829`,
also tagged `v6.140.0-rc`; this selection does not claim a formal final source tag.
The three PDF DLL images in the SDK and wheel match after excluding Authenticode
signing metadata. The manifest records the actual source archive's size and SHA-256;
the main Qt 6.12 source archive alone does not contain these PDF sources.

## Runtime profiles

Frame Compare owns two deterministic packaged deployment profiles. Unmanaged Windows,
Linux, and native macOS are reported as separate `unmanaged-windows`,
`unmanaged-linux`, and `native-macos` profiles so they cannot inherit portable Windows
or Debian package identity or reuse those decoder caches; they are not packaged support
profiles. Their fingerprints identify the selected Frame Compare runtime contract and
operating-system class, not independently verified installed native binaries.
Persistent cache compatibility is guaranteed only while an unmanaged installation
continues to satisfy that selected contract; replacing native decoder or FFmpeg
binaries outside the supported deployment profiles requires clearing generated caches
and Frame Compare-owned indexes before reuse.

### Windows x64 portable

- CPython 3.14.10 embeddable runtime.
- VapourSynth R82 portable runtime with the CPython 3.14 wheel layout.
- L-SMASH-Works 1310 through the official `vapoursynth-lsmas 1310.0.0.0`
  Windows wheel.
- vs-placebo 2.0.5 Windows wheel with its selected libplacebo and libdovi
  lineages.
- VSView 0.14.0 with its base dependency graph, PySide6 6.12.0, BestSource,
  vspackrgb, and the packaged `frame-compare-alignment-review` panel entry point
  for optional native interactive review. The runtime and panel metadata must come
  from the same environment; a PATH-only VSView executable is unsupported. BestSource
  remains UI-only; generated Frame Compare sessions continue to load media through
  L-SMASH-Works.
- Retained BtbN FFmpeg 8.1-branch Windows x64 LGPL-only artifact.
- FFMS2 intentionally excluded.
- Plugins load from the deterministic canonical VapourSynth package path; the
  standalone FFmpeg directory is not used for recursive DLL discovery.

### Debian Trixie / Docker

- CPython 3.13.18 slim-trixie image, with uv 0.13.8 pinned by image digest.
  Both images publish native AMD64 and ARM64 variants.
- VapourSynth R82 manylinux wheel.
- L-SMASH-Works 1310 built from source against VapourSynth API 4 and the Debian
  FFmpeg development ABI.
- OBUParse built as `libobuparse.so.2` from the pinned commit required by the
  selected L-SMASH source; the runtime image preserves the SONAME/symlink and
  verifies actual L-SMASH linkage.
- FFMS2 5.0 built from source against the same VapourSynth and Debian FFmpeg stack.
- vs-placebo 2.0.5 manylinux wheel.
- Debian Trixie FFmpeg runtime package `7:7.1.5-0+deb13u1`.
- Software Vulkan through Mesa is the canonical headless validation path.

VSView and the native Frame Compare alignment panel are optional for native and Docker
workflows. Its base package is the supported choice; the upstream `recommended` and
`full` extras add unrelated graph features and are intentionally excluded. Install
`frame-compare[vsview]` in the same environment as Frame Compare so the exact
`frame-compare-alignment-review` entry point is discoverable and loads
`AlignmentReviewPanel`. Generated Frame Compare sessions retain L-SMASH-Works source
loading and owned index paths; the panel reads only their trusted metadata and writes
an atomic typed sibling result sidecar. VSView's BestSource workspace is not a
migration of Frame Compare's analysis, probe, render, index, or cache-key source
loader.

The Linux build retains L-SMASH-Works' narrow VapourSynth-only Meson path even
though upstream marks Meson deprecated. The upstream CMake build enables several
optional dependencies by default; selecting it without an explicit option audit would
silently expand the runtime and licensing surface. This exception should be revisited
when upstream removes the Meson path or provides an equivalently narrow documented
CMake configuration. The Frame Compare maintainer owns this exception. Its stable
verification evidence is the exact-head, no-cache Docker integration workflow linked
from the active pull request and the corresponding `SOURCES.json` provenance artifact.

## Relevant compatibility changes

### VapourSynth R82

Runtime diagnostics read the release from `vapoursynth.__version__` and the API
version from `vapoursynth.__api_version__`. R82 reports API R4.3. L-SMASH-Works
1310 and FFMS2 5.0 use API 4 headers. The Linux and Windows runtimes use the
CPython 3.12 ABI3 wheels with their respective interpreters and continue to
use CPU frames for Frame Compare operations.

### VSView 0.14 and BestSource 23

VSView 0.14 uses VSJetEngine 2.0.0. The portable verifier checks the resolved
viewer graph, the `vsview.cli` entry point, and the `vspackrgb.rust` extension.
BestSource serves the VSView workspace. Frame Compare opens comparison sources
through L-SMASH-Works.

### L-SMASH-Works 1310

The selected release preserves the VapourSynth API 4 implementation and the video
source/index behavior established by 1296. It adds `LibavSMASHAudioSource` and
`LWLibavAudioSource` and fixes partial audio-gap rendering, post-resampling gap
coordinates, and lossy-audio pre-roll. Frame Compare does not consume the new audio
filters; its two required video functions must remain registered under `lsmas`:

- `LibavSMASHSource`
- `LWLibavSource`

Range validation follows VapourSynth's current H.273 `_Range` property and normalizes
the deprecated, inverse-numbered `_ColorRange` property through the application-owned
frame-property helper before comparing loader results.

A changed frame count, duration, or frame property is not automatically treated as a
Frame Compare regression; it must be classified against the upstream correction and
the media specification.

### FFMS2 5.0

Docker requires the `ffms2` namespace, `Source`, and `Version`. In the pinned FFMS2
source, the C++ callback is named `GetVersion` internally, but its registered
VapourSynth function is `Version`; the runtime version must report `5.0.0.0`.
Windows continues to use L-SMASH-Works only; FFMS2 is not added for artificial
cross-platform symmetry.

### Experimental native still reuse

`FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS=1` enables a default-off development
runtime policy for one reviewed patched UCRT build. Unset the variable to retain
the normal fresh-per-frame behavior; other nonempty values raise a typed tonemap
error. This is not a persisted color setting or a supported-runtime upgrade.
Selection checks the actual canonical loaded plugin's identifier, signature,
path and code-owned reviewed SHA256. Only fixed integer RGB48 HDR10/PQ-to-SDR
input without an enhancement layer is admitted. Retained base-layer Dolby Vision
RPU remains supported; HLG, explicit native DOVI and other unsupported classes
keep their existing route. Sequence behavior and tone settings stay unchanged.

The ordinary runtime safety child must resolve the same experimental plugin;
changing only the main process's Python import path is insufficient. Existing
runtime safety overrides keep their precedence but do not establish this proof.
Use an owned disposable runtime; do not overwrite installed native files or
alter registry/user VapourSynth configuration for acceptance.

The reviewed build record in `vs.tonemap_runtime` retains source/dependency
revisions and native source hashes. It is experimental provenance, not an
upstream wheel identity or accepted deployment fingerprint. Distribution still
requires an honestly identified downstream/upstream wheel, matching sources and
licenses, full runtime identity and artifact/physical-Windows acceptance. A native
replacement cannot be delivered through an unchanged code-only update identity.

### vs-placebo 2.0.5

The runtime requires the `placebo` namespace and `Tonemap`. Validation covers actual
filter invocation, software Vulkan in Docker, target nits, peak detection, range and
bit-depth preservation, and the existing Dolby Vision fallback path. Metric equality
alone is not evidence of perceptual equivalence; final Windows validation includes
objective output capture and manual visual review.

## Cache and index compatibility

`frame_compare.vs.runtime_contract` is the sole identity owner. It emits separate
fingerprints for:

| Scope | Included runtime surface | Intentionally excluded |
| --- | --- | --- |
| `analysis` | VapourSynth and the profile-specific L-SMASH-Works decoder lineage, including OBUParse on Docker | vs-placebo and standalone FFmpeg |
| `probe` | VapourSynth and the profile-specific L-SMASH-Works decoder lineage, including OBUParse on Docker, plus profile-specific standalone FFmpeg/ffprobe | vs-placebo |
| `alignment` | VapourSynth and the profile-specific L-SMASH-Works decoder lineage, plus profile-specific standalone FFmpeg/ffprobe | vs-placebo and tone mapping |
| `index` | L-SMASH-Works, L-SMASH, profile-specific decoder FFmpeg, Docker OBUParse, and index policy | standalone FFmpeg and tone mapping |
| `full` | Complete supported deployment profile | None |

This avoids both unsafe reuse and unnecessary invalidation. A tone-mapping-only update
does not discard metric arrays; a standalone FFmpeg update invalidates alignment reuse
without discarding L-SMASH-Works indexes.

The R82 refresh changes the VapourSynth decoder identity for every profile, so
`analysis`, `probe`, `alignment`, `index`, and `full` fingerprints change everywhere.
The Windows portable `alignment` fingerprint also changes because the retained BtbN
FFmpeg artifact moved to the October 2026 build. Existing entries and indexes under the previous
fingerprints miss and rebuild under the normal cache policy; there is no migration.

The shared alignment reuse cache is schema v2 after the viewer migration. It stores
neutral `computed` and `interactive_confirmed` origins. Existing schema-v1 entries are
ignored and recomputed; no v1 migration or compatibility reader is provided. Run-local
`manual_overrides.toml` uses canonical version "2" without a `confirmed` field,
retaining its path, ordering, atomic-write behavior, and offset semantics. Older or
unsupported versions are recoverable cache misses without migration; the next
manual save replaces them.

Frame Compare keys its managed L-SMASH-Works cache under
`<resolved paths.generated_dir>/cache/source-indexes/` by resolved source path and
profile-scoped decoder token. The current managed/portable Windows token is
`lsw1310-47d07506e489`, the unmanaged Windows token is `lsw1310-7a882880f599`, and the
Debian/Docker token is `lsw1310-9129a4cbb35a`. An unmanaged token does not attest to
the installed decoder ABI. Legacy media-adjacent indexes remain inert. See
[managed index behavior](current-architecture.md#shared-caches-and-decoder-indexes).

## Portable update boundary

A code-only update ZIP does not contain VapourSynth, L-SMASH-Works, vs-placebo,
FFmpeg, native manifests, or their licenses. The updater therefore compares the
installed bundle's full runtime fingerprint with the signed update manifest before
changing files. A missing, legacy, malformed, or different fingerprint blocks the update.

A pre-native-panel portable bundle may have matching runtime fingerprints but lacks
the native-panel capability recorded by `bundle_info.schema_version` 3. It requires
a complete portable bundle reinstall; a code-only update must fail closed rather than
mix the old dependency graph with the new application code.
Generated data should remain outside the bundle when it must survive replacement.

## Licensing and corresponding source

The Windows portable runtime remains free of GPL/nonfree FFmpeg artifacts. The
Docker runtime instead uses Debian's GPL-enabled FFmpeg package because its required
integration fixtures use `libx264` and `libx265`. Neither runtime selects nonfree
FFmpeg components.

| Component | License profile |
| --- | --- |
| VapourSynth | LGPL-2.1-or-later |
| L-SMASH-Works source | ISC; distributed plugin binary also carries linked-library obligations |
| L-SMASH | ISC |
| OBUParse | ISC |
| FFMS2 | MIT |
| vs-placebo | LGPL-2.1-only |
| libplacebo | LGPL-2.1-or-later |
| libdovi | MIT |
| VSView | EUPL-1.2 plus the bundled MIT/Apache-2.0/ISC/OFL-1.1 components declared by its distribution metadata |
| PySide6 family | LGPL-3.0-only or GPL-2.0-only or GPL-3.0-only, as advertised by the distribution metadata |
| Windows BtbN FFmpeg | LGPL-only |
| Docker Debian FFmpeg | GPL-2.0-or-later |

The Windows manifest vendors exact notices for the selected binaries and records the
corresponding source of statically bundled L-SMASH-Works dependencies. Build scripts
verify every artifact's exact byte size and SHA-256 and stop on mismatch. The bundle
inventory records installed distributions, native artifacts, source URLs, license
paths, and hashes. The Docker image also retains Debian FFmpeg's package copyright
file and records its GPL-2.0-or-later profile in runtime provenance.

The VSView Windows candidate is not release-ready solely because these top-level
expressions and source URLs are recorded. VSView requires Qt Multimedia from the
PySide6 Addons distribution, but does not use Qt WebEngine; the portable deployment
therefore excludes the pinned wheel's WebEngine/Chromium files and verifies their
absence from both the built and extracted bundle. Release remains blocked until that
absence is proved in the canonical ZIP and the deployed Qt subset has matching
third-party notices and SBOM/provenance, complete Qt Multimedia FFmpeg lineage, a
distributor-controlled corresponding-source offer, and legal adjudication. See the
[final-artifact security evidence](ENGINEERING_RUNBOOK.md#final-artifact-security-evidence)
release gate for native advisory coverage and the retained evidence.

This classification follows [FFmpeg's GPL configuration rule](https://ffmpeg.org/doxygen/7.1/md_LICENSE.html)
and the exact [Debian Trixie package copyright record](https://sources.debian.org/copyright/license/ffmpeg/7%3A7.1.5-0%2Bdeb13u1/).

## Validation boundary

GitHub-hosted Linux, Docker on AMD64 and ARM64, and Windows validation cover packaging,
plugin loading, generated fixtures, runtime identities, updater compatibility, and
deterministic layout. For generated HDR fixtures, `ffprobe` is the encoded
stream-signal authority;
the Docker gate separately proves that both source plugins retain at least 10-bit
decoded precision because L-SMASH-Works does not expose every stream color tag as a
frame property. The Linux GUI verifier contract requires the VSView 0.14.0 image to
discover and load the exact native panel entry point, construct its inactive panel
offscreen, load a production-generated L-SMASH session, register named
`Reference`/`Comparison 1` outputs, render frame 0 for both outputs, and round-trip a
typed sibling result while rejecting malformed data. The R81 dependency refresh
passed the inside-container offscreen proof with real L-SMASH media on macOS
Docker Desktop; its evidence is recorded in the
[Windows 10 handoff](https://github.com/TJZine/frame-compare/blob/eeaa0154bf5996c616b74ccf910d7cf1584e8297/docs/plans/2026-10-07-dependency-refresh-windows10-handoff.md).
The Linux X11 host wrapper and visible desktop launch remain unverified.
Offscreen proof does not replace final validation on the supported physical Windows system.
macOS offscreen or synthetic-panel proof exercises the Python/Qt/plugin contract only;
when the host does not provide `core.lsmas`, it is not native L-SMASH media proof and
must not be reported as such.
Before merge, that pass must still cover the RTX/Vulkan path, HDR10 and Dolby Vision
real media, perceptual comparisons, timing/VFR/interlacing/repeated-field cases, alpha
where available, audio synchronization, old/new index behavior, and an actual
old-bundle-to-full-reinstall transition.
