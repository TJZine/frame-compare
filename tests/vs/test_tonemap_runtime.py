"""Tests for libplacebo runtime probe policy."""

import subprocess

import pytest

import frame_compare.vs.tonemap_runtime as tonemap_runtime_module
from frame_compare.vs.tonemap_runtime import (
    LibplaceboRuntimeState,
    libplacebo_runtime_override,
    libplacebo_runtime_usable,
    probe_libplacebo_runtime,
)


def _clear_libplacebo_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)


def test_libplacebo_runtime_usable_caches_probe_result_for_state_lifetime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Probe results should be cached after the first non-overridden lookup."""
    _clear_libplacebo_env(monkeypatch)

    state = LibplaceboRuntimeState()
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return False

    assert libplacebo_runtime_usable(state, probe) is False
    assert libplacebo_runtime_usable(state, probe) is False
    assert calls == 1


def test_libplacebo_runtime_override_does_not_mutate_cached_probe_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime overrides should bypass, but not rewrite, the cached probe result."""
    _clear_libplacebo_env(monkeypatch)

    state = LibplaceboRuntimeState()
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return False

    assert libplacebo_runtime_usable(state, probe) is False
    monkeypatch.setenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", "1")
    assert libplacebo_runtime_usable(state, probe) is True
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    assert libplacebo_runtime_usable(state, probe) is False
    assert calls == 1


def test_libplacebo_runtime_override_reads_current_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The override helper should reflect per-call environment changes."""
    _clear_libplacebo_env(monkeypatch)
    assert libplacebo_runtime_override() is None

    monkeypatch.setenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", "1")
    assert libplacebo_runtime_override() is False

    monkeypatch.setenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", "1")
    assert libplacebo_runtime_override() is True


def test_libplacebo_probe_uses_current_vapoursynth_range_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}

    def fake_run(
        argv: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        captured["script"] = argv[2]
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(tonemap_runtime_module.subprocess, "run", fake_run)

    assert probe_libplacebo_runtime() is True
    assert "_Range=1" in captured["script"]
    assert "_ColorRange" not in captured["script"]


@pytest.mark.parametrize(
    "variable, probe_result, expected",
    [
        pytest.param("FRAME_COMPARE_REQUIRE_LIBPLACEBO", False, True, id="require"),
        pytest.param("FRAME_COMPARE_DISABLE_LIBPLACEBO", True, False, id="disable"),
        pytest.param("FRAME_COMPARE_LIBPLACEBO_PROBE", False, True, id="probe_child"),
    ],
)
def test_libplacebo_runtime_overrides_bypass_probe(
    monkeypatch: pytest.MonkeyPatch, variable: str, probe_result: bool, expected: bool
) -> None:
    _clear_libplacebo_env(monkeypatch)
    monkeypatch.setenv(variable, "1")
    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return probe_result

    assert libplacebo_runtime_usable(LibplaceboRuntimeState(), probe) is expected
    assert calls == 0
