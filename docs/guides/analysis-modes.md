# Analysis modes

Frame Compare offers two deterministic metric-analysis modes. Choose the tradeoff in
`config.toml`:

```toml
[analysis]
performance_mode = "quality"
```

| Mode | Metric coverage | Use it when |
| --- | --- | --- |
| `quality` (default) | Every eligible frame | You want the highest-confidence automatic dark, bright, and motion selection. |
| `performance` | 25% of eligible frames, rounded up, across as many as eight deterministic contiguous bursts | Faster analysis matters and approximate metric-selected frames are acceptable. |

Both modes use full-resolution luma PlaneStats, respect source trims and the shared
leading/trailing exclusion window, and leave configured user and random frames
eligible across the full selectable window.

!!! warning
    Performance mode can choose materially different automatic dark, bright, and
    motion frames, or miss brief events between sampled bursts. It is deterministic
    for the same inputs and window, but it is not expected to match quality mode
    frame-for-frame.

The mode is configuration-only; there is no dedicated `run` flag. For exact
selection, window, active-picture, and cache behavior, see the
[analysis configuration contract](../current-cli-contract.md#config-only-analysis-surface).
For measured, hardware-dependent evidence, see
[Analysis Performance Validation](../analysis-performance-validation.md) and the
[retained benchmark history](../analysis-benchmark-history.md).
