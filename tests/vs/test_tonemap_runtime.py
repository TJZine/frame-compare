"""Tests for tonemapping module."""

import importlib.util
from unittest.mock import patch

import pytest

import frame_compare.vs.tonemap as tonemap_module  # noqa: E402, I001


def _vs_spec_available() -> bool:
    try:
        return importlib.util.find_spec("vapoursynth") is not None
    except ValueError:
        return False


def _reset_libplacebo_runtime_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        tonemap_module,
        "_LIBPLACEBO_RUNTIME_STATE",
        tonemap_module._LibplaceboRuntimeState(),
    )


def test_libplacebo_runtime_usable_require_env_forces_true_without_probe(monkeypatch) -> None:
    """Require override should bypass the cached subprocess probe."""
    _reset_libplacebo_runtime_state(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", "1")
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)

    with patch.object(tonemap_module, "_probe_libplacebo_runtime") as mock_probe:
        assert tonemap_module._libplacebo_runtime_usable() is True

    mock_probe.assert_not_called()


def test_libplacebo_runtime_usable_caches_probe_result_for_process_lifetime(monkeypatch) -> None:
    """Probe results should be cached after the first non-overridden lookup."""
    _reset_libplacebo_runtime_state(monkeypatch)
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)

    with patch.object(
        tonemap_module, "_probe_libplacebo_runtime", return_value=False
    ) as mock_probe:
        assert tonemap_module._libplacebo_runtime_usable() is False
        assert tonemap_module._libplacebo_runtime_usable() is False

    mock_probe.assert_called_once_with()


def test_libplacebo_runtime_usable_disable_env_forces_false_without_probe(monkeypatch) -> None:
    """Disable override should bypass the cached subprocess probe."""
    _reset_libplacebo_runtime_state(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", "1")
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)

    with patch.object(tonemap_module, "_probe_libplacebo_runtime") as mock_probe:
        assert tonemap_module._libplacebo_runtime_usable() is False

    mock_probe.assert_not_called()


def test_libplacebo_runtime_usable_probe_env_forces_true_without_probe(monkeypatch) -> None:
    """Child probe processes should bypass the runtime probe recursion guard."""
    _reset_libplacebo_runtime_state(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_LIBPLACEBO_PROBE", "1")
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)

    with patch.object(tonemap_module, "_probe_libplacebo_runtime") as mock_probe:
        assert tonemap_module._libplacebo_runtime_usable() is True

    mock_probe.assert_not_called()


def test_libplacebo_runtime_override_does_not_mutate_cached_probe_result(monkeypatch) -> None:
    """Runtime overrides should bypass, but not rewrite, the cached probe result."""
    _reset_libplacebo_runtime_state(monkeypatch)
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)

    with patch.object(
        tonemap_module, "_probe_libplacebo_runtime", return_value=False
    ) as mock_probe:
        assert tonemap_module._libplacebo_runtime_usable() is False
        monkeypatch.setenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", "1")
        assert tonemap_module._libplacebo_runtime_usable() is True
        monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
        assert tonemap_module._libplacebo_runtime_usable() is False

    mock_probe.assert_called_once_with()


@pytest.mark.parametrize("probe_result", [True, False])
def test_libplacebo_runtime_usable_delegates_to_probe_without_overrides(
    monkeypatch, probe_result: bool
) -> None:
    """Without overrides, the wrapper should return the probe result."""
    _reset_libplacebo_runtime_state(monkeypatch)
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)

    with patch.object(
        tonemap_module,
        "_probe_libplacebo_runtime",
        return_value=probe_result,
    ) as mock_probe:
        assert tonemap_module._libplacebo_runtime_usable() is probe_result

    mock_probe.assert_called_once_with()
