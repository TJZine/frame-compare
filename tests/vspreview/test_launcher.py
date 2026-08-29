from __future__ import annotations

import sys
import types
from enum import Enum

import pytest

from frame_compare.vspreview import launcher


def test_prepare_vspreview_compatibility_restores_removed_apis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vs_object = object()
    set_output = object()

    class DitherType(Enum):
        SIERRA_2_4A = "sierra"
        STUCKI = "stucki"
        ATKINSON = "atkinson"
        OSTROMOUKHOV = "ostromoukhov"
        QUASIRANDOM = "quasirandom"
        ERROR_DIFFUSION = "error_diffusion"

    vstools = types.SimpleNamespace(VSObject=vs_object, DitherType=DitherType)
    vspreview = types.SimpleNamespace(set_output=set_output)
    monkeypatch.setitem(sys.modules, "vstools", vstools)
    monkeypatch.setitem(sys.modules, "vspreview", vspreview)

    launcher.prepare_vspreview_compatibility()

    assert vstools.vs_object is vs_object
    assert vstools.set_output is set_output
    assert DitherType.STUCKI.is_fmtc is True
    assert DitherType.ERROR_DIFFUSION.is_fmtc is False


def test_prepare_vspreview_compatibility_preserves_existing_apis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_vs_object = object()
    existing_set_output = object()
    existing_is_fmtc = object()

    class DitherType:
        SIERRA_2_4A = object()
        STUCKI = object()
        ATKINSON = object()
        OSTROMOUKHOV = object()
        QUASIRANDOM = object()
        is_fmtc = existing_is_fmtc

    vstools = types.SimpleNamespace(
        VSObject=object(),
        vs_object=existing_vs_object,
        set_output=existing_set_output,
        DitherType=DitherType,
    )
    monkeypatch.setitem(sys.modules, "vstools", vstools)
    monkeypatch.setitem(sys.modules, "vspreview", types.SimpleNamespace(set_output=object()))

    launcher.prepare_vspreview_compatibility()

    assert vstools.vs_object is existing_vs_object
    assert vstools.set_output is existing_set_output
    assert DitherType.is_fmtc is existing_is_fmtc


def test_windows_portable_launcher_preloads_runtime_before_vspreview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: events.append("vapoursynth"),
    )
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "windows-portable")
    monkeypatch.setattr(
        launcher,
        "prepare_vspreview_compatibility",
        lambda: events.append("compatibility"),
    )

    def fake_run_module(module: str, *, run_name: str, alter_sys: bool) -> None:
        events.append(f"run:{module}:{run_name}:{alter_sys}")

    monkeypatch.setattr(launcher.runpy, "run_module", fake_run_module)

    launcher.main()

    assert events == [
        "vapoursynth",
        "compatibility",
        "run:vspreview:__main__:True",
    ]


def test_unmanaged_launcher_does_not_preload_vapoursynth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "unmanaged")
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: pytest.fail("unmanaged VSPreview must register its own policy"),
    )
    monkeypatch.setattr(
        launcher,
        "prepare_vspreview_compatibility",
        lambda: events.append("compatibility"),
    )
    monkeypatch.setattr(
        launcher.runpy,
        "run_module",
        lambda module, *, run_name, alter_sys: events.append(
            f"run:{module}:{run_name}:{alter_sys}"
        ),
    )

    launcher.main()

    assert events == ["compatibility", "run:vspreview:__main__:True"]
