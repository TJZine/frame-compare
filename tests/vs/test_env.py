"""Tests for VapourSynth environment detection."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from frame_compare.errors import PluginNotFoundError, VapourSynthError, VapourSynthNotFoundError
from frame_compare.vs.env import (
    detect_plugins,
    ensure_vs_environment,
    is_vapoursynth_available,
    require_plugin,
)


def make_mock_core(*, lsmas: bool = False, libplacebo: bool = False) -> SimpleNamespace:
    """Create a mock VS core with specified plugins."""
    core = SimpleNamespace()
    if lsmas:
        core.lsmas = SimpleNamespace(LWLibavSource=lambda: None)
    if libplacebo:
        core.placebo = SimpleNamespace(Tonemap=lambda: None)
    return core


def test_is_vapoursynth_available_returns_bool() -> None:
    """Verify function returns bool type."""
    assert isinstance(is_vapoursynth_available(), bool)


def test_is_vapoursynth_available_no_vs_returns_false(mocker) -> None:
    """Patch importlib to simulate missing VapourSynth."""
    mocker.patch("frame_compare.vs.env.importlib.import_module", side_effect=ModuleNotFoundError)
    assert is_vapoursynth_available() is False


def test_ensure_vs_environment_missing_vs_raises_not_found_error(mocker) -> None:
    """Verify VapourSynthNotFoundError raised when module missing."""
    mocker.patch("frame_compare.vs.env.importlib.import_module", side_effect=ModuleNotFoundError)
    with pytest.raises(VapourSynthNotFoundError) as exc:
        ensure_vs_environment()
    assert exc.value.code == "FC-2001"


def test_ensure_vs_environment_core_failure_raises_vs_error(mocker) -> None:
    """Verify VapourSynthError raised when core creation fails."""
    mock_module = MagicMock()
    type(mock_module).core = mocker.PropertyMock(side_effect=Exception("Core init failed"))
    mocker.patch("frame_compare.vs.env.importlib.import_module", return_value=mock_module)

    with pytest.raises(VapourSynthError) as exc:
        ensure_vs_environment()
    assert exc.value.code == "FC-2002"


def test_detect_plugins_all_present() -> None:
    """Verify all plugins detected when present."""
    core = make_mock_core(lsmas=True, libplacebo=True)
    # Cast to MagicMock/Core for typing if needed, or rely on duck typing
    plugins = detect_plugins(core)  # type: ignore
    assert set(plugins.keys()) == {"lsmas", "libplacebo"}
    assert plugins["lsmas"] is True
    assert plugins["libplacebo"] is True


def test_detect_plugins_none_present() -> None:
    """Verify no plugins detected when missing."""
    core = make_mock_core()
    plugins = detect_plugins(core)  # type: ignore
    assert set(plugins.keys()) == {"lsmas", "libplacebo"}
    assert all(not v for v in plugins.values())


def test_detect_plugins_lsmas_alias() -> None:
    """Verify lsmas alias detection (lw)."""
    core = SimpleNamespace()
    core.lw = SimpleNamespace(LWLibavSource=lambda: None)
    plugins = detect_plugins(core)  # type: ignore
    assert plugins["lsmas"] is True


def test_require_plugin_missing_raises_error() -> None:
    """Verify error raised for missing plugin."""
    core = make_mock_core()
    with pytest.raises(PluginNotFoundError) as exc:
        require_plugin(core, "libplacebo")  # type: ignore
    assert exc.value.code == "FC-2003"


def test_require_plugin_present_passes() -> None:
    """Verify no error raised for present plugin."""
    core = make_mock_core(lsmas=True)
    require_plugin(core, "lsmas")  # type: ignore
