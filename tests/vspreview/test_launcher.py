from __future__ import annotations

import types

import pytest

from frame_compare.vspreview import launcher


def test_launcher_preloads_plugins_before_starting_vspreview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    core = types.SimpleNamespace(plugins=lambda: events.append("plugins") or ())
    monkeypatch.setattr(
        launcher,
        "ensure_vs_environment",
        lambda: events.append("vapoursynth") or core,
    )

    def fake_run_module(module: str, *, run_name: str, alter_sys: bool) -> None:
        events.append(f"run:{module}:{run_name}:{alter_sys}")

    monkeypatch.setattr(launcher.runpy, "run_module", fake_run_module)

    launcher.main()

    assert events == ["vapoursynth", "plugins", "run:vspreview:__main__:True"]
