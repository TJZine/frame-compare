# U4 video-check cost

Measured in the Docker L-SMASH runtime on 2026-09-27 with the deterministic
10-minute `replacement-4` fixture. The audio attempt was collected once, one
video-check warm-up built/reused the L-SMASH index, then three direct
`alignment_video.check_video_alignment` calls were timed with
`time.perf_counter()`.

- Samples: 3 warmed per-comparison checks
- Observed durations: 2.801 s, 2.720 s, 3.014 s
- Mean: 2.845 s per comparison
- Command: `bash tools/verify_docker_integration.sh --no-build --pytest-path tests/integration/test_alignment_u4_acceptance.py`
- Runtime: Docker FFmpeg 7.1.5, VapourSynth R80, L-SMASH-Works 1310

This is below the plan estimate of about 4 seconds of extra video-check cost
per comparison.
