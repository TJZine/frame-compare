# Changelog

## Unreleased
- add `generated.selection.v1.json` sidecar to short-circuit cached selections
- stream VapourSynth metrics sequentially to avoid random frame fetches
- skip SDR tonemapping when `analyze_in_sdr` is enabled and the source reports SDR transfer
- add optional canvas padding (`pad_to_canvas`) to resolve micro aspect ratio mismatches when targeting a fixed canvas (defaults to `off`, so existing configs need no changes)
