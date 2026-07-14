import pytest

from frame_compare.analysis.sampling import plan_performance_bursts


@pytest.mark.parametrize(
    ("start", "end", "expected_count", "expected_bursts"),
    [
        (0, 1, 1, 1),
        (0, 5, 2, 2),
        (10, 42, 8, 8),
        (100, 201, 26, 8),
    ],
)
def test_performance_plan_has_exact_ceil_quarter_budget(
    start: int,
    end: int,
    expected_count: int,
    expected_bursts: int,
) -> None:
    bursts = plan_performance_bursts(window_start=start, window_end_exclusive=end)

    assert sum(burst.frame_count for burst in bursts) == expected_count
    assert len(bursts) == expected_bursts
    assert all(start <= burst.start < burst.end_exclusive <= end for burst in bursts)
    assert all(burst.decode_start == max(0, burst.start - 1) for burst in bursts)
    assert list(bursts) == sorted(bursts, key=lambda burst: burst.start)


def test_centered_plan_is_deterministic() -> None:
    kwargs = {"window_start": 37, "window_end_exclusive": 154}

    assert plan_performance_bursts(**kwargs) == plan_performance_bursts(**kwargs)


@pytest.mark.parametrize("length", [1, 2, 7, 8, 9, 31, 32, 33, 100])
@pytest.mark.parametrize("start", [0, 53])
def test_performance_plan_covers_short_and_offset_windows(length: int, start: int) -> None:
    bursts = plan_performance_bursts(
        window_start=start,
        window_end_exclusive=start + length,
    )

    assert sum(burst.frame_count for burst in bursts) == (length + 3) // 4
    assert len(bursts) <= 8
    assert all(
        left.end_exclusive <= right.start for left, right in zip(bursts, bursts[1:], strict=False)
    )


@pytest.mark.parametrize(
    ("start", "end"),
    [(1, 1), (10, 9)],
)
def test_invalid_sampling_plan_is_rejected(start: int, end: int) -> None:
    with pytest.raises(ValueError):
        plan_performance_bursts(window_start=start, window_end_exclusive=end)
