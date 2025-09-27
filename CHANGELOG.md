# Changelog

## Unreleased
- add `generated.selection.v1.json` sidecar to short-circuit cached selections
- stream VapourSynth metrics sequentially to avoid random frame fetches
- skip SDR tonemapping when `analyze_in_sdr` is enabled and the source reports SDR transfer
