"""Tests for VapourSynth environment detection."""

import runpy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import frame_compare.vs.env as env_module
from frame_compare.vs.env import (
    candidate_lsmas_plugin_paths,
    detect_plugins,
    ensure_vs_environment,
    import_vapoursynth_module,
    is_vapoursynth_available,
    require_plugin,
    try_load_lsmas_plugin,
)
from frame_compare.vs.errors import PluginNotFoundError, VapourSynthError, VapourSynthNotFoundError


def test_env_module_annotations_do_not_require_runtime_vapoursynth(repo_root) -> None:
    """Import-time annotations must not require the optional VS runtime."""
    env_path = repo_root / "src" / "frame_compare" / "vs" / "env.py"
    namespace = runpy.run_path(str(env_path))

    assert namespace["ensure_vs_environment"].__annotations__["return"] == "vs.Core"


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


def test_register_windows_dll_dirs_is_idempotent_per_process(monkeypatch, tmp_path) -> None:
    """Windows DLL registration should be once-per-directory for the process lifetime."""
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")

    env_home = tmp_path / "vapoursynth-home"
    env_home.mkdir()
    vs_core = bundle_root / "vs" / "core"
    vs_core.mkdir(parents=True)
    plugin_dir = vs_core / "plugins"
    plugin_dir.mkdir()
    app_site_packages = bundle_root / "app" / "site-packages"
    app_site_packages.mkdir(parents=True)
    nested_site_packages = app_site_packages / "Lib" / "site-packages"
    nested_site_packages.mkdir(parents=True)

    monkeypatch.setattr(env_module.os, "name", "nt", raising=False)
    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setenv("VAPOURSYNTH_HOME", str(env_home))
    monkeypatch.setattr(
        env_module,
        "_WINDOWS_DLL_REGISTRATION",
        env_module._WindowsDllRegistrationState(),
    )

    calls: list[str] = []

    def fake_add_dll_directory(path: str) -> object:
        calls.append(path)
        return object()

    monkeypatch.setattr(env_module.os, "add_dll_directory", fake_add_dll_directory, raising=False)

    env_module.register_windows_dll_dirs()
    env_module.register_windows_dll_dirs()

    expected_calls = [
        str(env_home),
        str(vs_core),
        str(plugin_dir),
        str(app_site_packages),
        str(nested_site_packages),
    ]
    assert calls == expected_calls


def test_import_vapoursynth_module_registers_runtime_dirs_before_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_import = __import__
    mock_vs = MagicMock()
    vs_attempts = {"count": 0}

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "vapoursynth":
            vs_attempts["count"] += 1
            if vs_attempts["count"] == 1:
                raise ImportError("missing runtime DLL")
            return mock_vs
        return original_import(name, *args, **kwargs)

    register_dirs = MagicMock()
    monkeypatch.setattr(env_module, "register_windows_dll_dirs", register_dirs)
    monkeypatch.setattr("builtins.__import__", _fake_import)

    result = import_vapoursynth_module()

    assert result is mock_vs
    register_dirs.assert_called_once()
    assert vs_attempts["count"] == 2


def test_candidate_lsmas_plugin_paths_preserves_order_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()

    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setenv(
        "VAPOURSYNTH_PLUGIN_PATH",
        os_pathsep_join([str(plugin_dir), str(plugin_dir), ""]),
    )

    result = candidate_lsmas_plugin_paths()

    assert result == [
        str(plugin_dir / "libvslsmashsource.dll"),
        str(bundle_root / "vs" / "plugins" / "libvslsmashsource.dll"),
    ]


def os_pathsep_join(parts: list[str]) -> str:
    return env_module.os.pathsep.join(parts)


def test_try_load_lsmas_plugin_loads_first_existing_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    first = tmp_path / "missing" / "libvslsmashsource.dll"
    second = tmp_path / "present" / "libvslsmashsource.dll"
    second.parent.mkdir()
    second.write_text("")
    load_calls: list[str] = []
    core = SimpleNamespace(std=SimpleNamespace(LoadPlugin=lambda *, path: load_calls.append(path)))

    monkeypatch.setattr(
        env_module,
        "candidate_lsmas_plugin_paths",
        lambda: [str(first), str(second)],
    )

    assert try_load_lsmas_plugin(core) == str(second)
    assert load_calls == [str(second)]


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
