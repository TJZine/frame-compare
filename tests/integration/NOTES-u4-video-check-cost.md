# U4 video-check cost

Measured in the Docker L-SMASH runtime on 2026-09-27 with the deterministic
10-minute `replacement-4` fixture. The audio attempt was collected once, one
video-check warm-up built/reused the L-SMASH index, then three direct
`alignment_video.check_video_alignment` calls were timed with
`time.perf_counter()`.

- Samples: 3 warmed per-comparison checks
- Observed durations: 2.863 s, 2.758 s, 2.690 s
- Mean: 2.770 s per comparison
- Command: `docker compose run --rm frame-compare-test -lc 'export LIBGL_ALWAYS_SOFTWARE=1 PATH="/home/framecompare/.local/bin:$PATH"; export VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json; pytest -s -q tests/integration/test_alignment_u4_acceptance.py -k video_check_cost'`
- Runtime: Docker FFmpeg 7.1.5, VapourSynth R80, L-SMASH-Works 1310

This is below the plan estimate of about 4 seconds of extra video-check cost
per comparison.
