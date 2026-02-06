# Phase 8.2 — Pinned Artifact Set Report (2026-02-05)

This report captures the initial **Windows portable bundle** baseline pins for Phase 8.2.

Policy decisions (confirmed):

- Baseline target: Windows 10/11 x64 only.
- VapourSynth baseline: keep parity with Docker baseline (`R73`).
- FFmpeg policy: ship **LGPL-only** FFmpeg in the portable bundle; advanced users may BYO FFmpeg best-effort.
- Pin strategy: prefer upstream pinned binaries (URLs + sha256); do not use “latest” pointers.
- Baseline plugins: include `lsmas` (required for current loader) and `vs-placebo` (optional tonemap plugin); **exclude ffms2** in baseline.

## Artifact Pins (Windows x64 baseline)

Source-of-truth file for the pins:

- `tools/windows_portable/manifest.windows-x64.json`

Schema:

- `tools/windows_portable/manifest.schema.json`

### Hashing method

Local (macOS) hashing used for this report:

```bash
shasum -a 256 <file>
```

Windows CI equivalent (planned for Phase 8.3):

```powershell
certutil -hashfile <file> SHA256
```

### Pinned artifacts (URL + sha256)

- Python embeddable (amd64) `3.13.1`
  - URL: `https://www.python.org/ftp/python/3.13.1/python-3.13.1-embed-amd64.zip`
  - sha256: `7b7923ff0183a8b8fca90f6047184b419b108cb437f75fc1c002f9d2f8bcec16`
  - bytes: `10847803`
  - License: PSF (`Python-2.0`) — `https://docs.python.org/3/license.html`

- VapourSynth portable `R73`
  - URL: `https://github.com/vapoursynth/vapoursynth/releases/download/R73/VapourSynth64-Portable-R73.zip`
  - sha256: `3326f10d0fdcdec45649a474cbc9810795ab3da422634d0f134bca6089afbb91`
  - bytes: `13580181`
  - License: `LGPL-2.1-or-later` — `https://raw.githubusercontent.com/vapoursynth/vapoursynth/master/COPYING.LESSER`

- L-SMASH Works (VapourSynth plugin) `vA.3j` (lsmas)
  - URL: `https://github.com/AkarinVS/L-SMASH-Works/releases/download/vA.3j/release-x86_64-cachedir-cwd.zip`
  - sha256: `7bb449f960c8071819994f802b3f175bf1593315b6b2bca89d68739d5af46047`
  - bytes: `8223503`
  - License: ISC + VS LGPL notice — `https://raw.githubusercontent.com/AkarinVS/L-SMASH-Works/master/VapourSynth/LICENSE`

- vs-placebo (VapourSynth plugin) `1.4.4`
  - URL: `https://github.com/Lypheo/vs-placebo/releases/download/1.4.4/libvs_placebo-1.4.4.zip`
  - sha256: `81302071eacd0fce5f85cfb3a2267b78e825e179a87b1d5567818f3a057ca6b6`
  - bytes: `4097183`
  - License: `LGPL-2.1-or-later` — `https://raw.githubusercontent.com/Lypheo/vs-placebo/master/COPYING`

- FFmpeg (BtbN build) `n7.1.3-39-g1a501728ed` (tag: `autobuild-2026-02-04-14-23`, win64, **LGPL-only**)
  - URL: `https://github.com/BtbN/FFmpeg-Builds/releases/download/autobuild-2026-02-04-14-23/ffmpeg-n7.1.3-39-g1a501728ed-win64-lgpl-7.1.zip`
  - sha256: `6dcf7e7126eec312213dd26b8a02f40a53f42dbe477236275df4f854c576cc35`
  - bytes: `137350575`
  - License reference: `LGPL-2.1-or-later` — `https://ffmpeg.org/legal.html` (archive includes `LICENSE.txt`)

## Notes / Followups

- ffms2 is intentionally excluded from the baseline portable bundle:
  - Current code requires `lsmas` for source loading (`src/frame_compare/vs/source.py`).
  - ffms2 binary licensing can depend on how FFmpeg is built; we keep the baseline bundle license surface smaller.
