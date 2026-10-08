"""Tests for libplacebo runtime probe policy."""

import os
import site
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import cast

import pytest
import structlog

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
        captured["script"] = argv[-1]
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(tonemap_runtime_module.subprocess, "run", fake_run)

    assert probe_libplacebo_runtime() is True
    assert "_Range=1" in captured["script"]
    assert "_ColorRange" not in captured["script"]


@pytest.mark.parametrize("source", ["cwd", "pythonpath", "cwd-and-pythonpath"])
def test_libplacebo_probe_does_not_import_hostile_vapoursynth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
) -> None:
    """The capability child must use the installed VapourSynth module."""
    hostile_dir = tmp_path / "hostile"
    hostile_dir.mkdir()
    safe_cwd = tmp_path / "safe-cwd"
    safe_cwd.mkdir()
    marker = tmp_path / "hostile-imported"
    (hostile_dir / "vapoursynth.py").write_text(
        "from pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('imported', encoding='utf-8')\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("PYTHONHOME", raising=False)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    monkeypatch.delenv("PYTHONUSERBASE", raising=False)
    clean_result = probe_libplacebo_runtime()

    monkeypatch.chdir(hostile_dir if source in {"cwd", "cwd-and-pythonpath"} else safe_cwd)
    if source == "cwd":
        monkeypatch.delenv("PYTHONPATH", raising=False)
    else:
        monkeypatch.setenv("PYTHONPATH", str(hostile_dir))

    assert probe_libplacebo_runtime() is clean_result
    assert not marker.exists()


def test_libplacebo_probe_launches_an_isolated_child_with_runtime_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        captured.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setenv("PYTHONPATH", "/caller/python-path")
    monkeypatch.setenv("PYTHONUSERBASE", "/caller/user-base")
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "/runtime/plugins")
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "docker")
    monkeypatch.setattr(tonemap_runtime_module.subprocess, "run", fake_run)

    assert probe_libplacebo_runtime() is True

    child_argv = cast(list[str], captured["argv"])
    assert child_argv[0] == sys.executable
    assert child_argv[1] == "-P"
    assert "-I" not in child_argv
    assert captured["cwd"] == Path(sys.executable).resolve().parent
    child_env = captured["env"]
    assert isinstance(child_env, dict)
    assert "PYTHONPATH" not in child_env
    assert child_env["PYTHONSAFEPATH"] == "1"
    assert child_env["VAPOURSYNTH_EXTRA_PLUGIN_PATH"] == "/runtime/plugins"
    assert child_env["FRAME_COMPARE_RUNTIME_KIND"] == "docker"
    if site.ENABLE_USER_SITE and not sys.flags.no_user_site:
        assert "-s" not in child_argv
        assert child_env["PYTHONUSERBASE"] == "/caller/user-base"
    else:
        assert "-s" in child_argv
        assert "PYTHONUSERBASE" not in child_env


def test_libplacebo_probe_preserves_parent_user_site_in_real_child(tmp_path: Path) -> None:
    """A parent with an enabled user site exposes that trusted site to its child."""
    base_executable = getattr(sys, "_base_executable", sys.executable)
    source_root = Path(__file__).parents[2] / "src"
    dependency_root = Path(structlog.__file__).resolve().parent.parent
    environment = os.environ.copy()
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONUSERBASE",
        "PYTHONNOUSERSITE",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "HOME": str(tmp_path / "home"),
            "PYTHONUSERBASE": str(tmp_path / "userbase"),
            "PYTHONPATH": os.pathsep.join((str(source_root), str(dependency_root))),
        }
    )
    script = textwrap.dedent(
        """
        import site
        from pathlib import Path

        user_site = Path(site.getusersitepackages())
        user_site.mkdir(parents=True, exist_ok=True)
        (user_site / "vapoursynth.py").write_text(
            "from types import SimpleNamespace\\n"
            "RGB48 = 1\\n"
            "class Clip:\\n"
            "    @property\\n"
            "    def std(self): return self\\n"
            "    def SetFrameProps(self, **kwargs): return self\\n"
            "    def get_frame(self, n): return None\\n"
            "core = SimpleNamespace(\\n"
            "    std=SimpleNamespace(BlankClip=lambda **kwargs: Clip()),\\n"
            "    placebo=SimpleNamespace(Tonemap=lambda clip, **kwargs: clip),\\n"
            ")\\n",
            encoding="utf-8",
        )

        from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime

        raise SystemExit(0 if probe_libplacebo_runtime() else 1)
        """
    )
    result = subprocess.run(
        [base_executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr


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
