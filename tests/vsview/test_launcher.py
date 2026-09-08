"""Tests for the managed-runtime VSView launcher."""

from __future__ import annotations

from frame_compare.vsview import launcher


def test_windows_portable_offscreen_launcher_disables_font_warmup_before_vsview(
    monkeypatch,
) -> None:
    events: list[str] = []
    monkeypatch.setenv("QT_QPA_PLATFORM", "OFFSCREEN")
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "windows-portable")
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: events.append("vapoursynth"),
    )
    monkeypatch.setattr(
        launcher,
        "disable_offscreen_cjk_warmup",
        lambda: events.append("disable-font-warmup"),
    )
    monkeypatch.setattr(
        launcher.runpy,
        "run_module",
        lambda module, *, run_name, alter_sys: events.append(
            f"run:{module}:{run_name}:{alter_sys}"
        ),
    )

    launcher.main()

    assert events == [
        "vapoursynth",
        "disable-font-warmup",
        "run:vsview:__main__:True",
    ]


def test_windows_portable_visible_launcher_keeps_font_warmup(monkeypatch) -> None:
    events: list[str] = []
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "windows-portable")
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: events.append("vapoursynth"),
    )
    monkeypatch.setattr(
        launcher,
        "disable_offscreen_cjk_warmup",
        lambda: events.append("disable-font-warmup"),
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
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr(launcher, "runtime_kind", lambda: "unmanaged")
    monkeypatch.setattr(
        launcher,
        "preload_vapoursynth_runtime",
        lambda: events.append("vapoursynth"),
    )
    monkeypatch.setattr(
        launcher,
        "disable_offscreen_cjk_warmup",
        lambda: events.append("disable-font-warmup"),
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


def test_disable_offscreen_cjk_warmup_replaces_vsview_worker(monkeypatch) -> None:
    class FakeApplication:
        _warmup_cjk_fallback = staticmethod(lambda _font: "original")

    class FakeModule:
        Application = FakeApplication

    monkeypatch.setattr(
        launcher.importlib,
        "import_module",
        lambda module: FakeModule if module == "vsview.app.main" else None,
    )

    launcher.disable_offscreen_cjk_warmup()

    assert FakeApplication._warmup_cjk_fallback(object()) is None
