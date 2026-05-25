"""Tests for libplacebo runtime probe policy."""

from frame_compare.vs.tonemap_runtime import (
    LibplaceboRuntimeState,
    libplacebo_runtime_override,
    libplacebo_runtime_usable,
)


def _clear_libplacebo_env(monkeypatch) -> None:
    monkeypatch.delenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_LIBPLACEBO_PROBE", raising=False)


def test_libplacebo_runtime_require_env_forces_true_without_probe(monkeypatch) -> None:
    """Require override should bypass the cached subprocess probe."""
    _clear_libplacebo_env(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", "1")

    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return False

    assert libplacebo_runtime_usable(LibplaceboRuntimeState(), probe) is True
    assert calls == 0


def test_libplacebo_runtime_disable_env_forces_false_without_probe(monkeypatch) -> None:
    """Disable override should bypass the cached subprocess probe."""
    _clear_libplacebo_env(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", "1")

    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return True

    assert libplacebo_runtime_usable(LibplaceboRuntimeState(), probe) is False
    assert calls == 0


def test_libplacebo_runtime_probe_env_forces_true_without_probe(monkeypatch) -> None:
    """Child probe processes should bypass the runtime probe recursion guard."""
    _clear_libplacebo_env(monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_LIBPLACEBO_PROBE", "1")

    calls = 0

    def probe() -> bool:
        nonlocal calls
        calls += 1
        return False

    assert libplacebo_runtime_usable(LibplaceboRuntimeState(), probe) is True
    assert calls == 0


def test_libplacebo_runtime_usable_caches_probe_result_for_state_lifetime(monkeypatch) -> None:
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


def test_libplacebo_runtime_override_does_not_mutate_cached_probe_result(monkeypatch) -> None:
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


def test_libplacebo_runtime_override_reads_current_environment(monkeypatch) -> None:
    """The override helper should reflect per-call environment changes."""
    _clear_libplacebo_env(monkeypatch)
    assert libplacebo_runtime_override() is None

    monkeypatch.setenv("FRAME_COMPARE_DISABLE_LIBPLACEBO", "1")
    assert libplacebo_runtime_override() is False

    monkeypatch.setenv("FRAME_COMPARE_REQUIRE_LIBPLACEBO", "1")
    assert libplacebo_runtime_override() is True
