# Supported Media Runtime

Frame Compare treats its media dependencies as one compatibility-sensitive runtime.
Decoder plugins, FFmpeg libraries, tone mapping, generated indexes, cache identities,
portable artifacts, and license/source metadata are selected and validated together.
A version shown here is supported only as part of the complete profile described below.

## Supported component matrix

| Component | Previous baseline | Selected component | Upstream date | Selection kind | Why this selection |
| --- | --- | --- | --- | --- | --- |
| VapourSynth | R78 | **R79**, commit `acabf605b2205b32d65859bb2736405719d2fafd` | 2026-08-07 | Formal stable release | Latest non-prerelease release. It supplies CPython 3.13-compatible ABI3 wheels, keeps API R4.2, and improves cache cycling, `vspipe` MKV output, and zimg API validation. |
| VSPreview | 0.20.1 | **0.20.1** | 2026-07-17 | Stable Python release | The UI release is unchanged; Frame Compare's launcher restores the three VSJetPack 1.x APIs it still uses before starting it with the locked graph below. |
| VSJetEngine | 1.2.0 | **1.7.0** | 2026-08-21 | Stable Python release | Current locked VSPreview dependency resolution. |
| VSJetPack | 1.5.0 | **2.2.2** | 2026-08-18 | Stable Python release | Current locked resolution; Frame Compare provides a bounded VSPreview compatibility bootstrap for the removed `vs_object`, `set_output`, and `DitherType.is_fmtc` APIs. |
| Akarin | 1.4.1 | **vapoursynth-akarin 1.5.0**, commit `a72584a969972b4cfd1b1fd11a4b0e3350f83432` | 2026-08-27 | Official PyPI wheels and upstream tag | Bundled native plugin surface with Windows x64 and Linux x86_64/aarch64 wheels. The Windows wheel's zstd DLL still matches MSYS2 CLANG64 zstd 1.5.7-2 exactly; Linux wheel SBOMs still identify Ubuntu libzstd1 1.4.8+dfsg-3build1. Namespace loading, source provenance, and the combined LGPL-3.0-only/BSD-3-Clause license surface are verified. |
| VSZip | Not bundled | **vapoursynth-vszip 22.1.0**, commit `beb7a0ab0e4166580b76560ae3f7c7f5e376ac90` | 2026-07-16 | Official PyPI wheels and upstream tag | Bundled native plugin surface with Windows x64 and Linux x86_64/aarch64 wheels. Its build manifest pins statically compiled vapoursynth-zig commit `b87ff61ce680fa5a4cf7d44a9cb4b605c5037432` and zigimg commit `0bbe201a5591219177f2444371c2897746b47774`; loading, provenance, and the combined MIT/LGPL-2.1-only license surface are verified. |
| VSJetPack support graph | jetpytools 2.2.7; psutil absent | **jetpytools 3.1.1; psutil 7.2.2** | Resolved 2026-08-15 | Locked Python resolution | Accepted current dependency graph; these versions are hash-locked on every supported Python platform. |
| L-SMASH-Works | 1296.0.0.0 | **1310.0.0.0**, commit `7e65185d3f08ba4ad191e9a5cbba3e2c6fd3bb67` | 2026-08-23 | Formal native release | Latest stable native release. It preserves the API 4 video source surface and adds audio source filters plus audio-gap corrections. |
| Windows L-SMASH-Works package | 1296.0.0.1 | **vapoursynth-lsmas 1310.0.0.0** | 2026-08-23 | Non-yanked official PyPI wheel | Official wheel for the 1310 native lineage. Its plugin DLL imports only Windows/UCRT system libraries; unlike the release archive DLL, it does not require external MSVCP140 or VCRUNTIME140 DLLs. |
| L-SMASH | commit `84740c5d960ab622f4c08b971dc59192bc27ef74` | commit **`d186eb95388710a7a91f6fd353169b457ebbb9db`** | 2026-07-28 | Pinned maintainer-fork commit, not a release | Exact L-SMASH revision selected and tested by L-SMASH-Works 1310. No newer appropriate formal stable tag supersedes it. |
| OBUParse (Docker) | Not present | commit **`a67fcab9cd9d56c866a7a860f8c4aeb91b8817e8`** | 2026-06-22 | Pinned commit, shared library | Required directly by the selected L-SMASH revision (`obuparse.h` and `-lobuparse`). Docker builds the shared target and preserves `libobuparse.so.2` plus its unversioned symlink. |
| FFMS2 | 5.0 | **5.0**, commit `7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04` | 2024-05-28 | Formal stable release | 5.0 remains the latest formal stable release. It is rebuilt for Docker against the selected VapourSynth and Debian FFmpeg stack and remains excluded from Windows. |
| vs-placebo | 2.0.2 | **2.0.4**, commit `3cfd23f257ecb62b0cbd81eaaca092e18ae8e579` | 2026-07-14 | Non-yanked stable release | Latest non-yanked stable wheel; 2.0.3 is yanked. Requires Python 3.12+ and VapourSynth R74+. |
| libplacebo used by vs-placebo | older 2.0.2 lineage | commit **`a7a18af88ff0a17c04840dcb3246047bb6b46df3`** | 2026-07-08 | Upstream-pinned commit | Revision selected by the vs-placebo 2.0.4 wheel build. It includes a correction for luminance clipping when no tone mapping is needed. |
| libdovi used by vs-placebo | older wheel lineage | **3.3.2**, commit `4fd2b2235c9f93582dd4a00e65ee34a07800afd7` | 2025-06-04 | Upstream-pinned tag | Tag selected by the vs-placebo 2.0.4 wheel build for Dolby Vision metadata handling. |
| Windows FFmpeg | earlier retained 8.1 build | **`n8.1.2-34-g9b6c8969e0`**, BtbN build `autobuild-2026-07-31-14-10` | 2026-07-31 | Immutable retained release artifact | Newest selected end-of-month Windows x64 LGPL-only artifact from the stable FFmpeg 8.1 branch. It is not a master snapshot. |
| Linux FFmpeg | Debian Trixie packages | **`7:7.1.5-0+deb13u1`** | Resolved during validation | GPL-enabled Debian package | Runtime and development packages remain aligned to Debian Trixie. Required Docker fixtures use the packaged `libx264` and `libx265` encoders; Frame Compare does not replace Debian FFmpeg with a custom upstream build. |

Primary upstream evidence is recorded in `Dockerfile` and
`tools/windows_portable/manifest.windows-x64.json`. Docker fetches each exact
40-character Git commit and verifies a deterministic SHA-256 over the complete tracked
tree; it does not rely on GitHub-generated archive bytes as an immutable boundary.
Windows binary/source artifacts remain fail-closed on exact downloaded byte size and
SHA-256. Both surfaces record source revisions and license metadata.

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

- VapourSynth R79 portable runtime and CPython 3.13 wheel layout.
- L-SMASH-Works 1310 through the official `vapoursynth-lsmas 1310.0.0.0`
  Windows wheel.
- vs-placebo 2.0.4 Windows wheel with its selected libplacebo and libdovi
  lineages.
- Akarin 1.5.0 and VSZip 22.1.0 Windows wheels, including their native plugin
  payloads, bundled zstd/vapoursynth-zig/zigimg lineages, license files, and
  upstream source provenance.
- Retained BtbN FFmpeg 8.1-branch Windows x64 LGPL-only artifact.
- FFMS2 intentionally excluded.
- Plugins load from deterministic VapourSynth package and extra-plugin paths with
  `manifest.vs`; the standalone FFmpeg directory is not used for recursive DLL
  discovery.

### Debian Trixie / Docker

- VapourSynth R79 manylinux wheel.
- L-SMASH-Works 1310 built from source against VapourSynth API 4 and the Debian
  FFmpeg development ABI.
- OBUParse built as `libobuparse.so.2` from the pinned commit required by the
  selected L-SMASH source; the runtime image preserves the SONAME/symlink and
  verifies actual L-SMASH linkage.
- FFMS2 5.0 built from source against the same VapourSynth and Debian FFmpeg stack.
- vs-placebo 2.0.4 manylinux wheel.
- Akarin 1.5.0 and VSZip 22.1.0 manylinux wheels, loaded and inspected through
  their VapourSynth namespaces by the Docker integration gate; the gate also
  verifies Akarin's auditwheel zstd SBOM and the statically compiled VSZip inputs.
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

### VapourSynth R79

R79 keeps API R4.2 and adds cache-cycle improvements, Matroska output support in
`vspipe`, and a fix for the zimg API check. The refresh also preserves the R78-era
CPython 3.13-compatible ABI3 wheel and C++20 native-build requirements. Runtime
diagnostics read the public release identity from `vapoursynth.__version__` and the
API identity separately from `vapoursynth.__api_version__`.

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

### Akarin 1.5.0

The selected release adds floating-point precision formatting to `akarin.Text`, fixes
numeric-prefix parsing, and changes JIT allocation to named anonymous mappings. The
`akarin` namespace remains compatible with the runtime proof. The Windows wheel keeps
the exact zstd 1.5.7-2 DLL used by 1.4.1, and both Linux wheels retain the same
auditwheel-recorded Ubuntu zstd lineage.

### FFMS2 5.0

Docker requires the `ffms2` namespace, `Source`, and `Version`. In the pinned FFMS2
source, the C++ callback is named `GetVersion` internally, but its registered
VapourSynth function is `Version`; the runtime version must report `5.0.0.0`.
Windows continues to use L-SMASH-Works only; FFMS2 is not added for artificial
cross-platform symmetry.

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
| `analysis` | VapourSynth and the profile-specific L-SMASH-Works decoder lineage, including OBUParse on Docker | vs-placebo, Akarin, VSZip, and standalone FFmpeg |
| `probe` | VapourSynth and the profile-specific L-SMASH-Works decoder lineage, including OBUParse on Docker, plus profile-specific standalone FFmpeg/ffprobe | vs-placebo, Akarin, and VSZip |
| `alignment` | Profile-specific standalone FFmpeg lineage | VapourSynth and tone mapping |
| `index` | L-SMASH-Works, L-SMASH, profile-specific decoder FFmpeg, Docker OBUParse, and index policy | standalone FFmpeg and tone mapping |
| `full` | Complete supported deployment profile | None |

This avoids both unsafe reuse and unnecessary invalidation. A tone-mapping-only update
does not discard metric arrays; a standalone FFmpeg update invalidates alignment reuse
without discarding L-SMASH-Works indexes.

Frame Compare-owned L-SMASH-Works indexes use a profile-scoped filename:

```text
<media>.frame-compare-lsw1310-<12-hex-index-fingerprint>.lwi
```

The current managed/portable Windows token is `lsw1310-56c451f754fd`; the unmanaged
Windows token is `lsw1310-a619e5ff5505`; and the Debian/Docker token is
`lsw1310-b86875cb61bd`. Legacy `<media>.lwi` files adjacent to the media file
are ignored rather than deleted. A corrupt Frame Compare-owned index is removed and
rebuilt once, with a warning when removal or rebuilding fails and a cache-free source
open as the last recovery path for an unusable index location.

## Portable update boundary

A code-only update ZIP does not contain VapourSynth, L-SMASH-Works, vs-placebo,
FFmpeg, native manifests, or their licenses. The updater therefore compares the
installed bundle's full runtime fingerprint with the signed update manifest before
changing files. A missing, legacy, malformed, or different fingerprint fails closed,
even when an unsafe Python-dependency override was requested.

Crossing from the previous R79/1296/2.0.4/Akarin 1.4.1/VSZip runtime to the selected
R79/1310/2.0.4/Akarin 1.5.0/VSZip runtime requires a complete portable bundle reinstall
because the runtime fingerprints and Frame Compare-owned index tokens change.
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
| Akarin | LGPL-3.0-only |
| Akarin-bundled zstd | BSD-3-Clause |
| VSZip | MIT |
| VSZip-bundled vapoursynth-zig | LGPL-2.1-only |
| VSZip-bundled zigimg | MIT |
| Windows BtbN FFmpeg | LGPL-only |
| Docker Debian FFmpeg | GPL-2.0-or-later |

The Windows manifest vendors exact notices for the selected binaries and records the
corresponding source of statically bundled L-SMASH-Works dependencies. Build scripts
verify every artifact's exact byte size and SHA-256 and stop on mismatch. The bundle
inventory records installed distributions, native artifacts, source URLs, license
paths, and hashes. The Docker image also retains Debian FFmpeg's package copyright
file and records its GPL-2.0-or-later profile in runtime provenance.
This classification follows [FFmpeg's GPL configuration rule](https://ffmpeg.org/doxygen/7.1/md_LICENSE.html)
and the exact [Debian Trixie package copyright record](https://sources.debian.org/copyright/license/ffmpeg/7%3A7.1.5-0%2Bdeb13u1/).

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
