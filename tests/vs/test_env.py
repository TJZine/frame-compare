"""Tests for VapourSynth environment detection."""

import runpy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import frame_compare.vs.env as env_module
from frame_compare.vs.env import (
    candidate_lsmas_plugin_path_details,
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
    app_site_packages = bundle_root / "app" / "site-packages"
    app_site_packages.mkdir(parents=True)
    vapoursynth_package = app_site_packages / "vapoursynth"
    vapoursynth_libs = app_site_packages / "vapoursynth.libs"
    vs_placebo_package = app_site_packages / "vs_placebo"
    vs_placebo_libs = app_site_packages / "vs_placebo.libs"
    lsmas_dir = bundle_root / "vs" / "extra-plugins" / "lsmas"
    qt_bin = app_site_packages / "PyQt6" / "Qt6" / "bin"
    for directory in (
        vapoursynth_package,
        vapoursynth_libs,
        vs_placebo_package,
        vs_placebo_libs,
        lsmas_dir,
        qt_bin,
    ):
        directory.mkdir(parents=True)
    ffmpeg_bin = bundle_root / "ffmpeg" / "bin"
    ffmpeg_bin.mkdir(parents=True)

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
        str(app_site_packages),
        str(vapoursynth_package),
        str(vapoursynth_libs),
        str(vs_placebo_package),
        str(vs_placebo_libs),
        str(lsmas_dir),
        str(qt_bin),
    ]
    assert calls == expected_calls
    assert str(ffmpeg_bin) not in calls


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
    monkeypatch.setattr(env_module, "import_vapoursynth_module", lambda: SimpleNamespace())
    monkeypatch.delenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", raising=False)
    monkeypatch.setenv(
        "VAPOURSYNTH_PLUGIN_PATH",
        os_pathsep_join([str(plugin_dir), str(plugin_dir), ""]),
    )

    result = candidate_lsmas_plugin_paths()

    assert result == [
        *_expected_lsmas_candidates(bundle_root / "vs" / "plugins"),
        *_expected_lsmas_candidates(plugin_dir),
    ]


def test_candidate_lsmas_plugin_paths_normalizes_relative_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setattr(env_module, "import_vapoursynth_module", lambda: SimpleNamespace())
    monkeypatch.delenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", raising=False)
    monkeypatch.setenv(
        "VAPOURSYNTH_PLUGIN_PATH",
        os_pathsep_join(["plugins", str(tmp_path / "plugins" / ".." / "plugins")]),
    )

    result = candidate_lsmas_plugin_paths()

    assert result[: len(_expected_lsmas_candidates(bundle_root / "vs" / "plugins"))] == (
        _expected_lsmas_candidates(bundle_root / "vs" / "plugins")
    )
    assert len(result) == len(_expected_lsmas_candidates(tmp_path / "plugins")) + len(
        _expected_lsmas_candidates(bundle_root / "vs" / "plugins")
    )


def os_pathsep_join(parts: list[str]) -> str:
    return env_module.os.pathsep.join(parts)


def _expected_lsmas_candidates(plugin_dir) -> list[str]:
    return [
        env_module.os.path.abspath(str(plugin_dir / filename))
        for filename in env_module._candidate_lsmas_filenames()
    ]


def _first_candidate_by_source(result) -> dict[str, str]:
    first_for_source: dict[str, str] = {}
    for candidate in result:
        first_for_source.setdefault(candidate.source, candidate.path)
    return first_for_source


def _paths_for_source(result, source: str) -> list[str]:
    return [candidate.path for candidate in result if candidate.source == source]


def test_candidate_lsmas_plugin_path_details_prefers_r74_discovery_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")
    canonical_dir = tmp_path / "canonical"
    extra_dir = tmp_path / "extra"
    legacy_dir = tmp_path / "legacy"

    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setattr(
        env_module,
        "import_vapoursynth_module",
        lambda: SimpleNamespace(get_plugin_dir=lambda: str(canonical_dir)),
    )
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_dir))
    monkeypatch.setenv("VAPOURSYNTH_PLUGIN_PATH", str(legacy_dir))

    result = candidate_lsmas_plugin_path_details()
    first_for_source = _first_candidate_by_source(result)

    assert (
        first_for_source["vapoursynth.get_plugin_dir"]
        == _expected_lsmas_candidates(canonical_dir)[0]
    )
    assert (
        first_for_source["VAPOURSYNTH_EXTRA_PLUGIN_PATH"]
        == _expected_lsmas_candidates(extra_dir)[0]
    )
    assert (
        first_for_source["bundle_vs_plugins"]
        == _expected_lsmas_candidates(bundle_root / "vs" / "plugins")[0]
    )
    assert first_for_source["VAPOURSYNTH_PLUGIN_PATH"] == _expected_lsmas_candidates(legacy_dir)[0]


def test_candidate_lsmas_plugin_path_details_expands_nested_extra_plugin_dirs_deterministically(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")
    extra_root = tmp_path / "extra"
    alpha_dir = extra_root / "alpha"
    lsmas_dir = extra_root / "lsmas"
    zebra_dir = extra_root / "zebra"
    alpha_dir.mkdir(parents=True)
    lsmas_dir.mkdir(parents=True)
    zebra_dir.mkdir()
    (alpha_dir / "libvslsmashsource.dll").write_text("")
    (lsmas_dir / "manifest.vs").write_text("libvslsmashsource")
    (zebra_dir / "manifest.vs").write_text("other-plugin")

    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setattr(env_module, "import_vapoursynth_module", lambda: SimpleNamespace())
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_root))
    monkeypatch.delenv("VAPOURSYNTH_PLUGIN_PATH", raising=False)

    result = candidate_lsmas_plugin_path_details()

    assert _paths_for_source(result, "VAPOURSYNTH_EXTRA_PLUGIN_PATH") == [
        *_expected_lsmas_candidates(extra_root),
        *_expected_lsmas_candidates(alpha_dir),
        *_expected_lsmas_candidates(lsmas_dir),
    ]


def test_candidate_lsmas_plugin_path_details_skips_non_utf8_nested_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")
    extra_root = tmp_path / "extra"
    alpha_dir = extra_root / "alpha"
    broken_dir = extra_root / "broken"
    lsmas_dir = extra_root / "lsmas"
    alpha_dir.mkdir(parents=True)
    broken_dir.mkdir()
    lsmas_dir.mkdir()
    (alpha_dir / "libvslsmashsource.dll").write_text("")
    (broken_dir / "manifest.vs").write_bytes(b"\xff\xfe\x00\x00")
    (lsmas_dir / "manifest.vs").write_text("libvslsmashsource")

    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setattr(env_module, "import_vapoursynth_module", lambda: SimpleNamespace())
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_root))
    monkeypatch.delenv("VAPOURSYNTH_PLUGIN_PATH", raising=False)

    result = candidate_lsmas_plugin_path_details()

    assert _paths_for_source(result, "VAPOURSYNTH_EXTRA_PLUGIN_PATH") == [
        *_expected_lsmas_candidates(extra_root),
        *_expected_lsmas_candidates(alpha_dir),
        *_expected_lsmas_candidates(lsmas_dir),
    ]


@pytest.mark.parametrize(
    "vs_module_factory",
    [
        pytest.param(
            lambda: SimpleNamespace(get_plugin_dir=lambda: (_ for _ in ()).throw(RuntimeError)),
            id="get-plugin-dir-raises",
        ),
        pytest.param(
            lambda: SimpleNamespace(get_plugin_dir=lambda: 42),
            id="get-plugin-dir-non-path",
        ),
    ],
)
def test_candidate_lsmas_plugin_path_details_continues_when_canonical_dir_unusable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    vs_module_factory,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")
    extra_dir = tmp_path / "extra"
    legacy_dir = tmp_path / "legacy"

    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setattr(env_module, "import_vapoursynth_module", vs_module_factory)
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_dir))
    monkeypatch.setenv("VAPOURSYNTH_PLUGIN_PATH", str(legacy_dir))

    result = candidate_lsmas_plugin_path_details()
    first_for_source = _first_candidate_by_source(result)

    assert "vapoursynth.get_plugin_dir" not in first_for_source
    assert (
        first_for_source["VAPOURSYNTH_EXTRA_PLUGIN_PATH"]
        == _expected_lsmas_candidates(extra_dir)[0]
    )
    assert (
        first_for_source["bundle_vs_plugins"]
        == _expected_lsmas_candidates(bundle_root / "vs" / "plugins")[0]
    )
    assert first_for_source["VAPOURSYNTH_PLUGIN_PATH"] == _expected_lsmas_candidates(legacy_dir)[0]


def test_candidate_lsmas_plugin_path_details_continues_when_vapoursynth_import_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    bundle_root = tmp_path / "bundle"
    python_dir = bundle_root / "python"
    python_dir.mkdir(parents=True)
    executable = python_dir / "python.exe"
    executable.write_text("")
    extra_dir = tmp_path / "extra"
    legacy_dir = tmp_path / "legacy"

    def _raise_import_error() -> object:
        raise ImportError("vapoursynth unavailable")

    monkeypatch.setattr(env_module.sys, "executable", str(executable))
    monkeypatch.setattr(env_module, "import_vapoursynth_module", _raise_import_error)
    monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_dir))
    monkeypatch.setenv("VAPOURSYNTH_PLUGIN_PATH", str(legacy_dir))

    result = candidate_lsmas_plugin_path_details()
    first_for_source = _first_candidate_by_source(result)

    assert "vapoursynth.get_plugin_dir" not in first_for_source
    assert (
        first_for_source["VAPOURSYNTH_EXTRA_PLUGIN_PATH"]
        == _expected_lsmas_candidates(extra_dir)[0]
    )
    assert (
        first_for_source["bundle_vs_plugins"]
        == _expected_lsmas_candidates(bundle_root / "vs" / "plugins")[0]
    )
    assert first_for_source["VAPOURSYNTH_PLUGIN_PATH"] == _expected_lsmas_candidates(legacy_dir)[0]


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


def test_try_load_lsmas_plugin_continues_after_load_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    first = tmp_path / "first" / "libvslsmashsource.dll"
    second = tmp_path / "second" / "libvslsmashsource.dll"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("")
    second.write_text("")
    load_calls: list[str] = []

    def _load_plugin(*, path: str) -> None:
        load_calls.append(path)
        if path == str(first):
            raise RuntimeError("bad plugin")

    core = SimpleNamespace(std=SimpleNamespace(LoadPlugin=_load_plugin))
    monkeypatch.setattr(
        env_module,
        "candidate_lsmas_plugin_paths",
        lambda: [str(first), str(second)],
    )

    assert try_load_lsmas_plugin(core) == str(second)
    assert load_calls == [str(first), str(second)]


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
