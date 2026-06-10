# Analysis Performance Validation

Use `tools/benchmark_analysis_tiers.py` to compare `balanced` and `fast` against
`quality` on local clips that are not committed to the repository.

Example:

```bash
.venv/bin/python tools/benchmark_analysis_tiers.py \
  --root /path/to/workspace \
  --config config/config.toml \
  --output generated/analysis-tier-benchmark.json \
  --window-start 0 \
  --window-end-exclusive 2400 \
  reference.mkv comparison.mkv
```

The script writes deterministic JSON with the quality baseline, candidate tier
comparisons, selected-frame overlap, nearest-frame distances, miss rates,
Spearman rank correlations, top-K overlap, total analysis wall-clock time,
algorithm identity, and warnings for unavailable runtime details.

When source trims, effective FPS overrides, or shared selection windows matter,
pass the exact source-frame window used for review with `--window-start` and
`--window-end-exclusive`. If an orchestration selection-domain token is available
from a prepared run, pass it with `--selection-domain` so cache identity matches
that run. Without those arguments, the script records warnings and compares the
full analysis metric domain.

## Clip Classes

Manual validation should cover local examples of:

- SDR 8-bit live action.
- HDR PQ or HLG high-bit-depth source.
- Animation with flat fills and line art.
- Grainy or noisy film source.
- Static low-motion scene.
- High-motion action scene.
- Rapid camera pan.
- Hard cuts.
- Fades to black and from black.
- One-frame or very short flashes.
- Letterboxed or pillarboxed source.
- Subtitles, credits, logos, or UI overlays.
- Clipped highlights and near-black shadow detail.
- Short clip near `analysis.min_window_seconds`.
- Source trims and effective FPS overrides.

If a class is unavailable locally, record it as unavailable in the handoff. Do
not treat absent classes as validated.

## Review Labels

Inspect category misses beyond tolerance and label each as one of:

- `acceptable near-duplicate`
- `downscale lost small local feature`
- `temporal sampling missed event`
- `tie/ranking ambiguity`
- `source trim/window issue`
- `bug requiring implementation fix`

Balanced tolerances are 2 frames for dark/bright and 3 frames for motion. Fast
tolerances are 3 frames for dark/bright and 5 frames for motion.
