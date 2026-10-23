# Unit A: current real-media diagnostic results

Completed 23 October 2026 by chat `01a16827-6663-7cb1-911f-a4a3e2d9fc86`.
Controller remains responsible for acceptance and defaults.

Source: `f1d3b9bf4c3406e3d0cddbfbbc536e0ac8a9279e`, no source/config drift.
Only this evidence root was written, plus owned temporary decoder-index directories.
Pre-existing untracked plans/research were preserved. Final `git diff --check` exit 0.

## Executed evidence

- Installed `.venv/Scripts/frame-compare.exe doctor --json`: exit 0, success true.
- 28 isolated case processes: every exit 0; no skipped/failed native cases.
- Runtime: Python 3.13.7, Windows 10 build 19045, VapourSynth R81/API4.3,
  vs-placebo distribution 2.0.4, native libplacebo v7.371.0, RTX5080, NVIDIA621.01.
- Loaded placebo DLL SHA256 `b0a0689946e03f6f7467b798fba4678018bb28ba6b1caecdded8d08945049310`;
  decoder DLL SHA256 `98ce1bc67218bd09bf84f45d7fc726bbf0972a90dd4c29d68f0797dd1606e7ea`.
  Full native signature and source-file hashes are in each result receipt.
- Native16 and corrected sRGB float taps execute upstream of the SAME final RGB8
  evaluation. Native16 compressed arrays, full final PNGs, hashes and fixed-region
  measurements are retained. Instrumented porch baseline equals a separate
  uninstrumented product path byte for byte. This proves tap/logging neutrality
  for that baseline, not all conceivable inputs.
- Tiny image assertion exits 0 on baseline/knee1. Its deliberate substitution of
  baseline as candidate exits 1 at the intended endpoint-reduction assertion.
  `verification-receipt.json`, `verify-positive.txt`, `verify-negative.txt` record it.
- All copied/original index before/after hashes agree; all owned scratch paths
  have cleanup receipts. Every native process has exited and been reaped.
  **NATIVE RESOURCE LEASE RELEASED.**

Open `comparison.html`, `summary.json`, and the six `*-labeled.png` sheets.
`stage*/invocations.json` contains exact commands/exits; individual case directories
contain source metadata, provenance, settings, actual native kwargs, images,
native arrays, stdout/stderr and cleanup. `artifact-manifest.json` hashes artifacts.

## Main observations

All numbers below are sampled picture code values: x stride4, y250 onward stride4,
excluding the historical top-overlay boundary, with no overlay in these images.
They are not calibrated luminance or fidelity scores.

| Porch frame12382 variant | All RGB8=255 % | Any RGB8=255 % | Mean code8 |
|---|---:|---:|---:|
| Current knee0.5 | 7.3305 | 8.3500 | 139.13 |
| Knee1 | 0.8216 | 0.9625 | 135.67 |
| Spline100 / parameter0.5 | 0.0003 | 0.0003 | 121.68 |
| Only metadata2 | 0.0012 | 0.0015 | 132.18 |
| Measured99.995, stripped RPU/PLScene | 8.5814 | 9.9864 | 139.40 |
| Measured100, stripped RPU/PLScene | 7.3286 | 8.3472 | 139.13 |
| Controlled static448 | 0.1510 | 0.2031 | 136.96 |
| Knee1 + softclip2 | 0.8216 | 0.9446 | 135.57 |
| Knee1 + darken7 | 0 | 0 | 123.30 |
| Knee1 + contrast recovery0 | 0.0003 | 0.0003 | 135.63 |
| Baseline + contrast recovery0 | 7.6532 | 8.5820 | 139.13 |

Knee1 remains a useful narrow candidate. Close-up frame14943 white occupancy falls
3.8773% → 1.3952%; spline falls to0.0404% but mean falls86.53 →75.67.
Dark/control frame110257 has no all-channel white in either knee case, but any-channel
RGB8 endpoint occupancy is18.2255% →16.4300%, so a white-only metric misses its issue.

Peak-policy controls clearly change current output. The measured cases explicitly
use metadata4 (CIE_Y), detection on, use_dovi false, and remove DolbyVisionRPU,
PLSceneMax and PLSceneAvg. Their source arrays/props receipts establish those removals.
Metadata4 is confirmed in the retained pinned libplacebo colorspace.h; detected
statistics populate max_pq_y/avg_pq_y in shaders/colorspace.c. Percentile100 improves
the measured branch but leaves almost the same white occupancy as the original
automatic/RPU baseline. It is not a stand-alone fix for this scene.

The static448 branch uses float CLL/FALL/mastering-max props, source_peak448,
metadata2, detector off, use_dovi false and stripped RPU/PLScene props. Its product
frame policy is shared_stateless (appropriate for detector off); other candidates
use independent_frames. The isolated metadata2 case retains original RPU and
detector settings and changes only metadata selection (plus common diagnostic logging).

Important trace limit: despite log_level6, the current fresh-still graphs did not
emit the numerical `tone map (peak ->100)` timing descriptions retained historically.
Raw logs and extracted trace files are kept. **Effective numerical peaks are
unavailable for these new cases.** Neither src_max448 nor historical285/1001 values
are substituted as current observed peaks. Source-backed branch selection plus
pixel differences is weaker than a current explicit effective-peak receipt.

Softclip merits further color evaluation. Spider-Verse retained excerpt1 frame72
(strict MP4 preserving DV configuration) with knee1 has3.6893% any-channel RGB8
endpoints; softclip2 reduces that to0.3387%, with mean111.97 →111.63. All-channel
white stays0.2062%. Darken7 reduces any-channel endpoints to0.1889% but mean to101.73.
Visual inspection confirms broader appearance changes, particularly with darken.

Contrast recovery must be judged alongside detail, not white counts alone.
Knee1/recovery0 removes nearly all porch endpoints, but the fixed upper-center
highlight patch has horizontal code-luma gradient1.9068 →1.1234 and distinct RGB8
triplets728 →434. Near-white occupancy remains76.20% →76.68%. Visually the background
still looks very bright. Baseline/recovery0 is an especially strong counterexample:
native16 any-channel endpoints fall5.3982% →0.0003%, while final8 white rises
7.3305% →7.6532%. Absence of native endpoints is not proof of visible separation.
Close-up knee1/recovery0 white is0.8580%; Spider-Verse0.1297%.

Substance and Immaculate retained excerpt1 frame72 were each run baseline/knee1;
both pairs are byte-identical and have no sampled endpoints. This establishes
unchanged output for those exact controls, not broad cross-title highlight quality.
The excerpts' current SHA256 matches the historical packet-provenance receipt.
Those receipts include source packet timestamp/profile/DV configuration; packet
equality itself was not rerun. A brighter existing excerpt from either title would
be a useful bounded expansion if the controller needs active cross-title shoulders.

## Independent controller rerun

Run from `C:/Software/video/frame-compare`, using a fresh owned output path:

```powershell
$probe = 'generated/verification/2026-10-23/highlight-study/real-media/probe.py'
$check = 'generated/verification/2026-10-23/highlight-study/real-media/verify_results.py'
$accept = 'generated/verification/2026-10-23/highlight-study/controller/a-rerun'
.venv/Scripts/python.exe $probe run porch:baseline porch:knee1 --out $accept
.venv/Scripts/python.exe $check $accept
.venv/Scripts/python.exe $check $accept --negative-control
```

Expected exits:0,0,1; the negative control substitutes the baseline image as the
candidate and must fail. Add `porch:plain` to prove tap neutrality afresh or
`porch:baseline-contrast0` to reproduce the native16/final8 endpoint counterexample.
Do not reuse an existing case directory: the harness refuses overwriting it.

No performance claim, product/default adoption, full Dolby Vision reconstruction,
Docker/packaged acceptance, calibrated physical-display claim, or SDR-grade golden
is established. Parent adjudication remains required.
