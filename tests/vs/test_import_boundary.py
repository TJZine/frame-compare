import importlib
import sys

import pytest


def test_import_vs_does_not_import_submodules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing frame_compare.vs should not eagerly load submodules."""
    # Unload vs module and submodules to ensure we test fresh import behavior
    vs_modules = [m for m in sys.modules if m.startswith("frame_compare.vs")]
    for m in vs_modules:
        monkeypatch.delitem(sys.modules, m, raising=False)

    importlib.import_module("frame_compare.vs")

    assert "frame_compare.vs" in sys.modules
    assert "frame_compare.vs.tonemap" not in sys.modules
    assert "frame_compare.vs.color" not in sys.modules
    assert "frame_compare.vs.types" not in sys.modules


def test_import_with_blocked_vapoursynth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing frame_compare.vs must succeed even if vapoursynth is not available."""
    # Unload vs module and submodules to ensure we test fresh import behavior
    vs_modules = [m for m in sys.modules if m.startswith("frame_compare.vs")]
    for m in vs_modules:
        monkeypatch.delitem(sys.modules, m, raising=False)

    # Block vapoursynth in sys.modules
    monkeypatch.setitem(sys.modules, "vapoursynth", None)

    vs_mod = importlib.import_module("frame_compare.vs")

    # Accessing env/types that do not eagerly trigger vapoursynth loading at module level
    assert vs_mod.is_vapoursynth_available() is False

    # Accessing tonemap settings should succeed (as they only use dataclasses)
    settings = vs_mod.TonemapSettings(enabled=False)
    assert settings.enabled is False


def test_lazy_attribute_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that accessing attributes triggers submodule loading and resolves correctly."""
    # Unload vs module and submodules
    vs_modules = [m for m in sys.modules if m.startswith("frame_compare.vs")]
    for m in vs_modules:
        monkeypatch.delitem(sys.modules, m, raising=False)

    vs_mod = importlib.import_module("frame_compare.vs")

    # Access an attribute
    settings_cls = vs_mod.TonemapSettings
    assert settings_cls is not None
    assert "frame_compare.vs.types" in sys.modules


def test_lazy_decoder_options_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Decoder options remain available without eagerly importing VS source logic."""
    vs_modules = [m for m in sys.modules if m.startswith("frame_compare.vs")]
    for module_name in vs_modules:
        monkeypatch.delitem(sys.modules, module_name, raising=False)

    vs_mod = importlib.import_module("frame_compare.vs")

    assert "frame_compare.vs.source" not in sys.modules
    options = vs_mod.LWLibavSourceOptions(threads=0)

    assert options.threads == 0
    assert "frame_compare.vs.source" in sys.modules
