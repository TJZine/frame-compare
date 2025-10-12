"""Audio alignment warning handling regression tests."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import pytest

from src import audio_alignment as aa


def _emit_flush_warning() -> None:
    warnings.warn_explicit(
        message="The value of the smallest subnormal is smaller than the smallest normal.",
        category=UserWarning,
        filename="dummy.py",
        lineno=1,
        module="numpy._core.getlimits",
    )


def test_numpy_warning_not_globally_suppressed() -> None:
    """Importing audio_alignment must not mute unrelated NumPy warnings."""

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _emit_flush_warning()

    assert caught, "NumPy flush-to-zero warnings should surface outside alignment contexts"


def test_warning_suppressed_within_context_manager() -> None:
    """The suppression context should silence the flush-to-zero warning."""

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with aa._suppress_flush_to_zero_warning():
            _emit_flush_warning()

    assert not caught, "Flush-to-zero warning leaked despite local suppression"


@dataclass
class FakeArray:
    values: list[list[float]] | list[float]

    @property
    def size(self) -> int:
        if self.ndim == 1:
            return len(self.values)  # type: ignore[arg-type]
        return sum(len(row) for row in self.values)  # type: ignore[arg-type]

    @property
    def ndim(self) -> int:
        if not self.values:  # pragma: no cover - defensive
            return 1
        first = self.values[0]  # type: ignore[index]
        return 2 if isinstance(first, list) else 1

    def flatten(self) -> list[float]:
        if self.ndim == 1:
            return [float(v) for v in cast(list[float], self.values)]
        flattened: list[float] = []
        for row in cast(list[list[float]], self.values):
            flattened.extend(float(v) for v in row)
        return flattened

    def __iter__(self):
        return iter(self.flatten())

    def __truediv__(self, other: float) -> "FakeArray":
        if other == 0:  # pragma: no cover - defensive
            raise ZeroDivisionError("division by zero in FakeArray")
        if self.ndim == 1:
            return FakeArray([float(v) / other for v in self.values])  # type: ignore[list-item]
        return FakeArray([[float(v) / other for v in row] for row in self.values])  # type: ignore[list-item]

    def astype(self, _dtype: object) -> "FakeArray":
        return FakeArray(self.flatten())


class FakeNpModule:
    float32 = "float32"

    @staticmethod
    def array(values: list[list[float]] | list[float]) -> FakeArray:
        return FakeArray(values)

    @staticmethod
    def abs(array: FakeArray) -> FakeArray:
        return FakeArray([[abs(v) for v in row] for row in array.values] if array.ndim == 2 else [abs(v) for v in array.values])  # type: ignore[list-item]

    @staticmethod
    def max(array: FakeArray) -> float:
        flattened = array.flatten()
        return max(flattened) if flattened else 0.0

    @staticmethod
    def mean(array: FakeArray, *, axis: int) -> FakeArray:
        if axis != 1:
            raise NotImplementedError("FakeNpModule only supports axis=1")
        assert array.ndim == 2
        return FakeArray([sum(row) / len(row) for row in array.values])  # type: ignore[list-item]


def test_onset_envelope_suppresses_dependency_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Audio onset extraction should silence dependency warnings without affecting callers."""

    calls: list[str] = []

    def emit_and_record(marker: str) -> None:
        calls.append(marker)
        _emit_flush_warning()

    fake_np = FakeNpModule()

    class FakeSoundFileModule:
        @staticmethod
        def read(path: str):  # type: ignore[override]
            emit_and_record("sf.read")
            return fake_np.array([[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]]), 24000

    class FakeOnsetModule:
        @staticmethod
        def onset_strength(**_: object):  # type: ignore[override]
            emit_and_record("librosa.onset_strength")
            return fake_np.array([0.5, 0.4, 0.3])

    class FakeLibrosaModule:
        onset = FakeOnsetModule()

        @staticmethod
        def resample(data: FakeArray, *, orig_sr: int, target_sr: int) -> FakeArray:
            emit_and_record("librosa.resample")
            assert orig_sr == 24000
            assert target_sr == 48000
            return data

    monkeypatch.setattr(aa, "_load_optional_modules", lambda: (fake_np, FakeLibrosaModule(), FakeSoundFileModule()))

    wav_path = tmp_path / "dummy.wav"
    wav_path.write_bytes(b"not-audio-but-ok")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        onset_env, hop = aa._onset_envelope(wav_path, sample_rate=48000, hop_length=512)

    assert not caught, "Warnings from dependencies should be contained within onset envelope"
    assert hop == 512
    assert isinstance(onset_env, FakeArray)
    assert calls == ["sf.read", "librosa.resample", "librosa.onset_strength"]
