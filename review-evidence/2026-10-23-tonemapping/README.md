# Portable tonemapping review evidence

This committed bundle repairs the original local-only handoff. Paths below mirror
`generated/verification/2026-10-23/`; use this directory when that ignored tree is
absent. Read `index.html` for portable comparison sheets and region crops.

- `highlight-implementation/implementation.diff`: exact implementation diff
  against base f1d3b9bf, independent of the current checkout state.
- `highlight-implementation/verification.json`: final verification ledger.
- `highlight-implementation/full-suite.xml` and `.log`: complete full-suite result.
- `highlight-implementation/baseline-lifecycle.*`: base-source failure reproduction.
- `highlight-study/real-media/REPORT.md` and `summary.json`: initial real scenes.
- `highlight-study/controller/`: independent repeats and synthetic adjudication.
- `highlight-study/synthetic/`: fixtures, harness, numeric/native receipts and arrays.
- `highlight-softclip-expanded/REPORT.md` and `summary.json`: additional scenes,
  metrics, controls, timeout and provenance.

JSON/text receipts, scripts, test outputs, labeled comparison images, regional
crops and synthetic arrays are copied byte-for-byte. `manifest.json` records hashes
of these copies. Historical manifests inside each study describe the original
local evidence and include files not copied here; use this bundle's root manifest
to validate the portable subset.

Source movies, decoder indexes, large real-media native arrays and source-sized
per-case PNGs are not committed. `omitted-local-artifacts.json` explicitly lists
excluded artifacts and sizes. Full-resolution remeasurement of real-media arrays
requires the retained local generated tree or a separate transfer. The committed
metrics, native/result receipts and comparison sheets support independent review
but do not replace unavailable source pixels. Original scripts require the media
and their recorded local paths; they are preserved for audit, not claimed portable
one-command reproductions. No original HTML viewers with missing image targets
are included; use this bundle's `index.html` instead.

Some receipts intentionally preserve original absolute paths and pre-commit source
status. They are historical observations, not instructions to locate the current
diff. Review the committed source against f1d3b9bf and the saved implementation.diff.
The research report's older generated paths map to this tree where included.

Diagnostic Python source is stored as `.py.txt` to keep archived probes out of
normal repository lint/test discovery. Restore `.py` names only in an isolated
working copy if reproducing the experiments.
