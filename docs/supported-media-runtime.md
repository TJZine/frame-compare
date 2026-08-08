# Supported Media Runtime

Frame Compare treats its media dependencies as one compatibility-sensitive runtime.
Decoder plugins, FFmpeg libraries, tone mapping, generated indexes, cache identities,
portable artifacts, and license/source metadata are selected and validated together.
A version shown here is supported only as part of the complete profile described below.

## Supported component matrix

| Component | Previous baseline | Selected component | Upstream date | Selection kind | Why this selection |
| --- | --- | --- | --- | --- | --- |
| VapourSynth | R76 | **R78**, commit `c2f5751a412347f306eb7f6a5985dd9a719f3896` | 2026-07-24 | Formal stable release | Latest non-prerelease release. It supplies CPython 3.13-compatible ABI3 wheels, uses VapourSynth API 4, and moves native builds to C++20. |
| L-SMASH-Works | 1282.0.0.0 | **1296.0.0.0**, commit `a83318210c183c8ebbe703d975ffc76fb499ef07` | 2026-07-07 | Formal native release | Latest stable native release and first selected lineage using the VapourSynth API 4 implementation. |
| Windows L-SMASH-Works package | 1282 lineage | **vapoursynth-lsmas 1296.0.0.1** | 2026-07-08 | Non-yanked official PyPI wheel | Packaging follow-up for the 1296 native lineage. Its plugin DLL does not require a separately bundled MSVC redistributable DLL, unlike the release archive DLL inspected during this refresh. |
| L-SMASH | v2.14.5 | commit **`84740c5d960ab622f4c08b971dc59192bc27ef74`** | 2025-07-05 | Pinned commit, not a release | Exact L-SMASH revision selected and tested by L-SMASH-Works 1296. No newer appropriate formal stable tag supersedes it. |
| OBUParse (Docker) | Not present | commit **`a67fcab9cd9d56c866a7a860f8c4aeb91b8817e8`** | 2026-06-22 | Pinned commit, shared library | Required directly by the selected L-SMASH revision (`obuparse.h` and `-lobuparse`). Docker builds the shared target and preserves `libobuparse.so.2` plus its unversioned symlink. |
| FFMS2 | 5.0 | **5.0**, commit `7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04` | 2024-05-28 | Formal stable release | 5.0 remains the latest formal stable release. It is rebuilt for Docker against the selected VapourSynth and Debian FFmpeg stack and remains excluded from Windows. |
| vs-placebo | 2.0.2 | **2.0.4**, commit `3cfd23f257ecb62b0cbd81eaaca092e18ae8e579` | 2026-07-14 | Non-yanked stable release | Latest non-yanked stable wheel; 2.0.3 is yanked. Requires Python 3.12+ and VapourSynth R74+. |
| libplacebo used by vs-placebo | older 2.0.2 lineage | commit **`a7a18af88ff0a17c04840dcb3246047bb6b46df3`** | 2026-07-08 | Upstream-pinned commit | Revision selected by the vs-placebo 2.0.4 wheel build. It includes a correction for luminance clipping when no tone mapping is needed. |
| libdovi used by vs-placebo | older wheel lineage | **3.3.2**, commit `4fd2b2235c9f93582dd4a00e65ee34a07800afd7` | 2025-06-04 | Upstream-pinned tag | Tag selected by the vs-placebo 2.0.4 wheel build for Dolby Vision metadata handling. |
| Windows FFmpeg | earlier retained 8.1 build | **`n8.1.2-34-g9b6c8969e0`**, BtbN build `autobuild-2026-07-31-14-10` | 2026-07-31 | Immutable retained release artifact | Newest selected end-of-month Windows x64 LGPL-only artifact from the stable FFmpeg 8.1 branch. It is not a master snapshot. |
| Linux FFmpeg | Debian Trixie packages | **`7:7.1.5-0+deb13u1`** | Resolved during validation | Debian-supported package | Runtime and development packages remain aligned to Debian Trixie. Frame Compare does not replace them with a custom upstream FFmpeg build. |

Primary upstream evidence is recorded in `Dockerfile` and
`tools/windows_portable/manifest.windows-x64.json`. Docker fetches each exact
40-character Git commit and verifies a deterministic SHA-256 over the complete tracked
tree; it does not rely on GitHub-generated archive bytes as an immutable boundary.
Windows binary/source artifacts remain fail-closed on exact downloaded byte size and
SHA-256. Both surfaces record source revisions and license metadata.

## Runtime profiles

Frame Compare owns two deterministic deployment profiles. Unmanaged native macOS is
reported as the separate `native-macos` profile so it cannot inherit Debian package
identity or reuse Debian decoder caches; it is not a packaged support profile.

### Windows x64 portable

- VapourSynth R78 portable runtime and CPython 3.13 wheel layout.
- L-SMASH-Works 1296 through the official `vapoursynth-lsmas 1296.0.0.1`
  Windows wheel.
- vs-placebo 2.0.4 Windows wheel with its selected libplacebo and libdovi
  lineages.
- Retained BtbN FFmpeg 8.1-branch Windows x64 LGPL-only artifact.
- FFMS2 intentionally excluded.
- Plugins load from deterministic VapourSynth package and extra-plugin paths with
  `manifest.vs`; the standalone FFmpeg directory is not used for recursive DLL
  discovery.

### Debian Trixie / Docker

- VapourSynth R78 manylinux wheel.
- L-SMASH-Works 1296 built from source against VapourSynth API 4 and the Debian
  FFmpeg development ABI.
- OBUParse built as `libobuparse.so.2` from the pinned commit required by the
  selected L-SMASH source; the runtime image preserves the SONAME/symlink and
  verifies actual L-SMASH linkage.
- FFMS2 5.0 built from source against the same VapourSynth and Debian FFmpeg stack.
- vs-placebo 2.0.4 manylinux wheel.
- Debian Trixie FFmpeg runtime package `7:7.1.5-0+deb13u1`.
- Software Vulkan through Mesa is the canonical headless validation path.

The Linux build retains L-SMASH-Works' narrow VapourSynth-only Meson path even
though upstream marks Meson deprecated. The upstream CMake build enables several
optional dependencies by default; selecting it without an explicit option audit would
silently expand the runtime and licensing surface. This exception should be revisited
when upstream removes the Meson path or provides an equivalently narrow documented
CMake configuration. The Frame Compare maintainer owns this exception. Its stable
verification evidence is the exact-head, no-cache Docker integration workflow linked
from the active pull request and the corresponding `SOURCES.json` provenance artifact.

## Relevant compatibility changes

### VapourSynth R78

The refresh reviews changes since R76 that affect plugin/API validation, frame-property
validation, chroma-location handling, cache/threading behavior, Python object lifetime,
half-float formats, and native compiler requirements. Runtime diagnostics read the
public release identity from `vapoursynth.__version__` and the API identity separately
from `vapoursynth.__api_version__`.

### L-SMASH-Works 1296

The selected release moves the VapourSynth plugin implementation to API 4. Relevant
upstream changes include alpha-format handling, `av_sync=true` undefined-behavior
fixes, aspect-ratio behavior, MPEG-1 repeated-field/duration behavior, and source/index
handling. Both supported functions must register under `lsmas`:

- `LibavSMASHSource`
- `LWLibavSource`

Range validation follows VapourSynth's current H.273 `_Range` property and normalizes
the deprecated, inverse-numbered `_ColorRange` property through the application-owned
frame-property helper before comparing loader results.

A changed frame count, duration, or frame property is not automatically treated as a
Frame Compare regression; it must be classified against the upstream correction and
the media specification.

### FFMS2 5.0

Docker requires the `ffms2` namespace, `Source`, and `Version`. The runtime version
must report `5.0.0.0`. Windows continues to use L-SMASH-Works only; FFMS2 is not added
for artificial cross-platform symmetry.

### vs-placebo 2.0.4

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
| `probe` | VapourSynth and the profile-specific L-SMASH-Works decoder lineage, including OBUParse on Docker | vs-placebo and standalone FFmpeg |
| `alignment` | Profile-specific standalone FFmpeg lineage | VapourSynth and tone mapping |
| `index` | L-SMASH-Works, L-SMASH, profile-specific decoder FFmpeg, Docker OBUParse, and index policy | standalone FFmpeg and tone mapping |
| `full` | Complete supported deployment profile | None |

This avoids both unsafe reuse and unnecessary invalidation. A tone-mapping-only update
does not discard metric arrays; a standalone FFmpeg update invalidates alignment reuse
without discarding L-SMASH-Works indexes.

Frame Compare-owned L-SMASH-Works indexes use a profile-scoped filename:

```text
<media>.frame-compare-lsw1296-<12-hex-index-fingerprint>.lwi
```

The current Windows token is `lsw1296-e3c074652ffb`; the current Debian/Docker token
is `lsw1296-4ea22a0b0598`. Legacy adjacent `<media>.lwi` files are ignored rather
than deleted. A corrupt Frame Compare-owned index is removed and rebuilt once, with a
warning when removal or rebuilding fails and a cache-free source open as the last
recovery path for an unusable index location.

## Portable update boundary

A code-only update ZIP does not contain VapourSynth, L-SMASH-Works, vs-placebo,
FFmpeg, native manifests, or their licenses. The updater therefore compares the
installed bundle's full runtime fingerprint with the signed update manifest before
changing files. A missing, legacy, malformed, or different fingerprint fails closed,
even when an unsafe Python-dependency override was requested.

Crossing from the older R76/1282/2.0.2 runtime to this R78/1296/2.0.4 runtime requires
a complete portable bundle reinstall. Generated data should remain outside the bundle
when it must survive replacement.

## Licensing and corresponding source

The baseline remains free of GPL/nonfree FFmpeg artifacts:

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
| Windows BtbN FFmpeg | LGPL-only |

The Windows manifest vendors exact notices for the selected binaries and records the
corresponding source of statically bundled L-SMASH-Works dependencies. Build scripts
verify every artifact's exact byte size and SHA-256 and stop on mismatch. The bundle
inventory records installed distributions, native artifacts, source URLs, license
paths, and hashes.

## Validation boundary

GitHub-hosted Linux, Docker, and Windows validation proves packaging, plugin loading,
generated fixtures, runtime identities, updater compatibility, and deterministic
layout. For generated HDR fixtures, `ffprobe` is the encoded stream-signal authority;
the Docker gate separately proves that both source plugins retain at least 10-bit
decoded precision because L-SMASH-Works does not expose every stream color tag as a
frame property. It does not replace final validation on the supported physical Windows system.
Before merge, that pass must still cover the RTX/Vulkan path, HDR10 and Dolby Vision
real media, perceptual comparisons, timing/VFR/interlacing/repeated-field cases, alpha
where available, audio synchronization, old/new index behavior, and an actual
old-bundle-to-full-reinstall transition.
