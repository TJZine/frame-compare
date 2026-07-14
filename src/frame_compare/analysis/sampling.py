"""Deterministic temporal sampling plans for performance analysis."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

PERFORMANCE_SAMPLING_FRACTION = Fraction(1, 4)
PERFORMANCE_BURST_COUNT = 8


@dataclass(frozen=True, slots=True)
class SamplingBurst:
    """One sampled contiguous run and its optional motion-lookbehind frame."""

    start: int
    end_exclusive: int
    decode_start: int

    @property
    def frame_count(self) -> int:
        return self.end_exclusive - self.start


def plan_performance_bursts(
    *,
    window_start: int,
    window_end_exclusive: int,
) -> tuple[SamplingBurst, ...]:
    """Plan 25% coverage rounded up to a whole frame.

    Uses at most eight centered deterministic bursts.
    """
    window_length = window_end_exclusive - window_start
    if window_length <= 0:
        raise ValueError("Sampling window must contain at least one frame")
    budget = min(
        window_length,
        (
            window_length * PERFORMANCE_SAMPLING_FRACTION.numerator
            + PERFORMANCE_SAMPLING_FRACTION.denominator
            - 1
        )
        // PERFORMANCE_SAMPLING_FRACTION.denominator,
    )
    burst_count = min(PERFORMANCE_BURST_COUNT, budget)
    base_size, larger_bursts = divmod(budget, burst_count)
    bursts: list[SamplingBurst] = []
    for index in range(burst_count):
        stratum_start = window_start + window_length * index // burst_count
        stratum_end = window_start + window_length * (index + 1) // burst_count
        run_size = base_size + (1 if index < larger_bursts else 0)
        if run_size > stratum_end - stratum_start:
            raise ValueError("Sampling burst does not fit its deterministic stratum")
        start = stratum_start + (stratum_end - stratum_start - run_size) // 2
        bursts.append(
            SamplingBurst(
                start=start,
                end_exclusive=start + run_size,
                decode_start=max(0, start - 1),
            )
        )
    return tuple(bursts)


__all__ = [
    "PERFORMANCE_BURST_COUNT",
    "PERFORMANCE_SAMPLING_FRACTION",
    "SamplingBurst",
    "plan_performance_bursts",
]
