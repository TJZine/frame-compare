"""Audio alignment warning handling regression tests."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import pytest

from src import audio_alignment as aa


def _emit_flush_warning() -> None:
    """
    Emit a reproducible UserWarning that mimics NumPy's flush-to-zero (subnormal vs normal) warning for tests.
    
    This triggers an explicit UserWarning with the message "The value of the smallest subnormal is smaller than the smallest normal." and metadata (filename, lineno, module) set to match NumPy's flush-to-zero warning so tests can verify suppression and propagation behavior.
    """
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
        """
        Return the total number of elements represented by this FakeArray.
        
        For a 1-dimensional FakeArray this is the length of `values`. For a 2-dimensional FakeArray this is the sum of lengths of each row.
        
        Returns:
            int: Total number of elements.
        """
        if self.ndim == 1:
            return len(self.values)  # type: ignore[arg-type]
        return sum(len(row) for row in self.values)  # type: ignore[arg-type]

    @property
    def ndim(self) -> int:
        """
        Determine the number of dimensions represented by the stored values.
        
        Returns:
            int: `1` if the data is one-dimensional or empty, `2` if the data is two-dimensional.
        """
        if not self.values:  # pragma: no cover - defensive
            return 1
        first = self.values[0]  # type: ignore[index]
        return 2 if isinstance(first, list) else 1

    def flatten(self) -> list[float]:
        """
        Flatten the array-like object's stored values into a single list of floats.
        
        Converts either a 1D sequence or a 2D sequence of sequences into a single list, preserving row-major order.
        
        Returns:
            list[float]: A list containing every element from the underlying values as floats.
        """
        if self.ndim == 1:
            return [float(v) for v in self.values]  # type: ignore[list-item]
        flattened: list[float] = []
        for row in self.values:  # type: ignore[assignment]
            flattened.extend(float(v) for v in row)
        return flattened

    def __iter__(self):
        """
        Iterate over the array's flattened values.
        
        Returns:
        	iterator: An iterator that yields the array's values as floats in row-major (flattened) order.
        """
        return iter(self.flatten())

    def __truediv__(self, other: float) -> "FakeArray":
        """
        Return a new FakeArray with each element divided by the given scalar.
        
        Parameters:
            other (float): The divisor.
        
        Returns:
            FakeArray: A new FakeArray whose values are the element-wise result of dividing by `other`.
        
        Raises:
            ZeroDivisionError: If `other` is zero.
        """
        if other == 0:  # pragma: no cover - defensive
            raise ZeroDivisionError("division by zero in FakeArray")
        if self.ndim == 1:
            return FakeArray([float(v) / other for v in self.values])  # type: ignore[list-item]
        return FakeArray([[float(v) / other for v in row] for row in self.values])  # type: ignore[list-item]

    def astype(self, _dtype: object) -> "FakeArray":
        """
        Create a new FakeArray containing this array's flattened values; the requested dtype is ignored.
        
        Parameters:
            _dtype (object): Desired dtype (accepted for API compatibility but ignored).
        
        Returns:
            FakeArray: A new FakeArray constructed from the flattened values.
        """
        return FakeArray(self.flatten())


class FakeNpModule:
    float32 = "float32"

    @staticmethod
    def array(values: list[list[float]] | list[float]) -> FakeArray:
        """
        Create a FakeArray from a 1D or 2D sequence of floats.
        
        Parameters:
            values (list[list[float]] | list[float]): 1D list of floats or 2D list (rows of floats) to wrap.
        
        Returns:
            FakeArray: A FakeArray wrapping the provided values.
        """
        return FakeArray(values)

    @staticmethod
    def abs(array: FakeArray) -> FakeArray:
        """
        Return a FakeArray with element-wise absolute values.
        
        Parameters:
            array (FakeArray): 1D or 2D array-like of numeric values.
        
        Returns:
            FakeArray: New FakeArray where each element is the absolute value of the corresponding input element.
        """
        return FakeArray([[abs(v) for v in row] for row in array.values] if array.ndim == 2 else [abs(v) for v in array.values])  # type: ignore[list-item]

    @staticmethod
    def max(array: FakeArray) -> float:
        """
        Return the maximum numeric value contained in a FakeArray.
        
        Parameters:
            array (FakeArray): Array-like container (1D or 2D) of numeric values.
        
        Returns:
            max_value (float): The largest value found in `array`, or 0.0 if `array` is empty.
        """
        flattened = array.flatten()
        return max(flattened) if flattened else 0.0

    @staticmethod
    def mean(array: FakeArray, *, axis: int) -> FakeArray:
        """
        Compute the mean of each row (axis=1) of a 2D FakeArray.
        
        Parameters:
            array (FakeArray): A 2-dimensional FakeArray whose row means will be computed.
            axis (int): Must be 1; only row-wise mean is supported.
        
        Returns:
            FakeArray: A 1-dimensional FakeArray containing the mean of each row.
        
        Raises:
            NotImplementedError: If `axis` is not 1.
        """
        if axis != 1:
            raise NotImplementedError("FakeNpModule only supports axis=1")
        assert array.ndim == 2
        return FakeArray([sum(row) / len(row) for row in array.values])  # type: ignore[list-item]


def test_onset_envelope_suppresses_dependency_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Audio onset extraction should silence dependency warnings without affecting callers."""

    calls: list[str] = []

    def emit_and_record(marker: str) -> None:
        """
        Record a call marker and emit the flush-to-zero UserWarning used by the tests.
        
        Parameters:
            marker (str): Label appended to the shared `calls` list to record the invocation.
        """
        calls.append(marker)
        _emit_flush_warning()

    fake_np = FakeNpModule()

    class FakeSoundFileModule:
        @staticmethod
        def read(path: str):  # type: ignore[override]
            """
            Return a small two-channel fake audio array and its sample rate for the given path.
            
            Parameters:
                path (str): Path to the audio file (ignored by this fake implementation).
            
            Returns:
                tuple: A pair (audio, sr) where `audio` is a 2x3 FakeArray of sample values
                [[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]] and `sr` is the sample rate 24000.
            """
            emit_and_record("sf.read")
            return fake_np.array([[0.1, 0.2, 0.3], [0.3, 0.2, 0.1]]), 24000

    class FakeOnsetModule:
        @staticmethod
        def onset_strength(**_: object):  # type: ignore[override]
            """
            Produce a deterministic onset strength array used in tests and record that the onset_strength path was called.
            
            Parameters:
                **_ (object): Ignored catch-all for positional and keyword arguments.
            
            Returns:
                FakeArray: A FakeArray containing onset strengths [0.5, 0.4, 0.3].
            """
            emit_and_record("librosa.onset_strength")
            return fake_np.array([0.5, 0.4, 0.3])

    class FakeLibrosaModule:
        onset = FakeOnsetModule()

        @staticmethod
        def resample(data: FakeArray, *, orig_sr: int, target_sr: int) -> FakeArray:
            """
            Mock resampling function used in tests that records the call and returns the input unchanged.
            
            Parameters:
                data (FakeArray): Input audio data to be (nominally) resampled.
                orig_sr (int): Original sample rate of `data`.
                target_sr (int): Desired sample rate after resampling.
            
            Returns:
                FakeArray: The same `data` instance, unmodified.
            """
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