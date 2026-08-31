"""Tests for the managed-runtime VSView launcher."""

from __future__ import annotations

from frame_compare.vsview import launcher


def test_windows_portable_launcher_preloads_vapoursynth_before_vsview(
    monkeypatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "windows-portable")
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: events.append("vapoursynth"),
    )
    monkeypatch.setattr(
        launcher.runpy,
        "run_module",
        lambda module, *, run_name, alter_sys: events.append(
            f"run:{module}:{run_name}:{alter_sys}"
        ),
    )

    launcher.main()

    assert events == ["vapoursynth", "run:vsview:__main__:True"]


def test_unmanaged_launcher_only_runs_vsview(
    monkeypatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "unmanaged")
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: events.append("vapoursynth"),
    )
    monkeypatch.setattr(
        launcher.runpy,
        "run_module",
        lambda module, *, run_name, alter_sys: events.append(
            f"run:{module}:{run_name}:{alter_sys}"
        ),
    )

    launcher.main()

    assert events == ["run:vsview:__main__:True"]


def test_preload_vapoursynth_runtime_uses_managed_environment(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(launcher, "ensure_vs_environment", lambda: calls.append("ensure"))

    launcher.preload_vapoursynth_runtime()

    assert calls == ["ensure"]
