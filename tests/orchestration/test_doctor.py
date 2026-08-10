"""Unit tests for diagnostic checks."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import frame_compare.vs.env as env_module
from frame_compare.orchestration.doctor import (
    CheckResult,
    DoctorCheck,
    collect_checks,
    run_doctor,
)
from frame_compare.vs.env import PluginPathCandidate
from frame_compare.vs.runtime_contract import WINDOWS_FFMPEG_EXECUTABLE_TOKEN

pytestmark = pytest.mark.unit


def _completed_process(stdout: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess([], 0, stdout.encode(), b"")


def _clear_tmdb_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TMDB_API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__API_KEY", raising=False)
    monkeypatch.delenv("FRAME_COMPARE_TMDB__ENABLED", raising=False)


class TestCheckLsmas:
    """Tests for lsmas plugin check via run_doctor."""

    def test_check_lsmas_plugin_passes_when_available(self) -> None:
        """Mock vs core with lsmas namespace → check passes."""
        mock_core = MagicMock()
        mock_core.lsmas = MagicMock()
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch.dict(sys.modules, {"vapoursynth": mock_vs}):
            result = lsmas_check.check_fn()

        assert result.passed is True
        assert "L-SMASH-Works" in result.message
        assert "native version is not observable" in result.message
        assert result.details["runtime_identity_status"] == "unverifiable"

    @pytest.mark.parametrize("missing_function", ["LibavSMASHSource", "LWLibavSource"])
    def test_check_lsmas_plugin_requires_both_source_functions(self, missing_function: str) -> None:
        available_function = (
            "LWLibavSource" if missing_function == "LibavSMASHSource" else "LibavSMASHSource"
        )
        plugin = SimpleNamespace(
            **{available_function: lambda *_args, **_kwargs: object()},
            functions=lambda: [SimpleNamespace(name=available_function)],
        )
        mock_vs = SimpleNamespace(core=SimpleNamespace(lsmas=plugin))
        check = next(candidate for candidate in collect_checks() if candidate.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=mock_vs,
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert "missing required source functions" in result.message
        assert result.details["required_functions"] == [
            "LibavSMASHSource",
            "LWLibavSource",
        ]
        assert result.details["missing_functions"] == [missing_function]

    def test_check_lsmas_plugin_fails_when_missing(self) -> None:
        """Mock missing plugin → check fails."""
        mock_core = object()
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with (
            patch.dict(sys.modules, {"vapoursynth": mock_vs}),
            patch(
                "frame_compare.orchestration.doctor_checks.candidate_lsmas_plugin_path_details",
                return_value=[
                    PluginPathCandidate(
                        path="/opt/vs/plugins/libvslsmashsource.so",
                        source="vapoursynth.get_plugin_dir",
                    ),
                    PluginPathCandidate(
                        path="/bundle/vs/plugins/libvslsmashsource.so",
                        source="bundle_vs_plugins",
                    ),
                ],
            ),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.details["checked_plugin_paths"] == [
            {
                "source": "vapoursynth.get_plugin_dir",
                "path": "/opt/vs/plugins/libvslsmashsource.so",
            },
            {"source": "bundle_vs_plugins", "path": "/bundle/vs/plugins/libvslsmashsource.so"},
        ]
        assert result.hint == (
            "Make L-SMASH-Works available to VapourSynth; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        )
        assert "install" not in result.hint.lower()

    def test_check_lsmas_plugin_fallback_loads_from_nested_extra_plugin_root(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        """If autoload misses lsmas, fallback loading should recover from nested extra-plugin dirs."""

        bundle_root = tmp_path / "bundle"
        python_dir = bundle_root / "python"
        python_dir.mkdir(parents=True)
        executable = python_dir / "python.exe"
        executable.write_text("")
        extra_root = bundle_root / "vs" / "extra-plugins"
        plugin_dir = extra_root / "lsmas"
        plugin_dir.mkdir(parents=True)
        plugin_path = plugin_dir / "libvslsmashsource.dll"
        plugin_path.write_text("")
        (plugin_dir / "manifest.vs").write_text("libvslsmashsource")

        monkeypatch.setattr(env_module.sys, "executable", str(executable))
        monkeypatch.setattr(env_module, "import_vapoursynth_module", lambda: SimpleNamespace())
        monkeypatch.setenv("VAPOURSYNTH_EXTRA_PLUGIN_PATH", str(extra_root))
        monkeypatch.delenv("VAPOURSYNTH_PLUGIN_PATH", raising=False)

        load_calls: list[str] = []
        mock_core = SimpleNamespace()

        def _load_plugin(*, path: str) -> None:
            load_calls.append(path)
            mock_core.lsmas = MagicMock()

        mock_core.std = SimpleNamespace(LoadPlugin=_load_plugin)
        mock_vs = MagicMock()
        mock_vs.core = mock_core

        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=mock_vs,
        ):
            result = lsmas_check.check_fn()

        assert result.passed is True
        assert result.details.get("plugin_path") == str(plugin_path)
        assert load_calls == [str(plugin_path)]

    def test_check_lsmas_failure_uses_sanitized_exception_details(self) -> None:
        """Unexpected lsmas errors should not expose raw exception text."""
        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            side_effect=RuntimeError("secret path /Users/example/private"),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.message == "lsmas check failed"
        assert result.hint == (
            "Check the VapourSynth/plugin setup, then rerun doctor; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        )
        assert result.details == {"exception_type": "RuntimeError"}

    def test_check_lsmas_when_vapoursynth_is_unavailable_points_to_runtime_setup(
        self,
    ) -> None:
        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            side_effect=ImportError("missing runtime"),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.message == "Cannot check lsmas (VapourSynth not available)"
        assert result.hint == (
            "Make VapourSynth importable before checking L-SMASH-Works; see "
            "https://github.com/TJZine/frame-compare#quick-start"
        )

    def test_check_lsmas_import_error_after_runtime_import_is_setup_failure(self) -> None:
        checks = collect_checks()
        lsmas_check = next(c for c in checks if c.name == "lsmas")
        mock_vs = SimpleNamespace(core=object())

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
                return_value=mock_vs,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.try_load_lsmas_plugin",
                side_effect=ImportError("plugin setup import failed"),
            ),
        ):
            result = lsmas_check.check_fn()

        assert result.passed is False
        assert result.message == "lsmas check failed"
        assert result.details == {"exception_type": "ImportError"}
        assert "plugin setup import failed" not in str(result.details)

    def test_check_lsmas_failure_included_in_critical_failures(self) -> None:
        """Mock lsmas core failure → DoctorReport.critical_failures includes 'lsmas'."""
        lsmas_check = DoctorCheck(
            name="lsmas",
            category="core",
            check_fn=lambda: CheckResult(passed=False, message="L-SMASH-Works not found"),
        )

        report = run_doctor(checks=[lsmas_check])

        assert report.all_passed is False
        assert "lsmas" in report.critical_failures


class TestCheckPythonVersion:
    """Tests for python_version check via run_doctor."""

    def test_check_python_version_passes(self) -> None:
        """Mock sys.version_info to (3, 13, 0) → check passes."""
        checks = collect_checks()
        python_check = next(c for c in checks if c.name == "python_version")

        with patch.object(sys, "version_info", (3, 13, 0)):
            result = python_check.check_fn()

        assert result.passed is True
        assert "3.13" in result.message

    def test_check_python_version_fails(self) -> None:
        """Mock sys.version_info to (3, 12, 0) → check fails with hint."""
        checks = collect_checks()
        python_check = next(c for c in checks if c.name == "python_version")

        with patch.object(sys, "version_info", (3, 12, 0)):
            result = python_check.check_fn()

        assert result.passed is False
        assert "3.12" in result.message
        assert result.hint == (
            "Run Frame Compare with Python 3.13+; see "
            "https://github.com/TJZine/frame-compare#requirements"
        )


class TestCheckVapoursynth:
    """Tests for vapoursynth check via run_doctor."""

    def test_check_vapoursynth_reports_public_release_and_api(self) -> None:
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")
        version = SimpleNamespace(release_major=78, release_minor=0)
        api_version = SimpleNamespace(api_major=4, api_minor=2)
        mock_vs = SimpleNamespace(__version__=version, __api_version__=api_version)

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=mock_vs,
        ):
            result = vs_check.check_fn()

        assert result.passed is True
        assert result.details == {
            "expected_release": "R78",
            "expected_api_major": 4,
            "observed_version": str(version),
            "observed_api_version": str(api_version),
            "release_major": 78,
            "release_minor": 0,
            "api_major": 4,
            "api_minor": 2,
            "observed_release": "R78",
            "expected_release_match": True,
            "expected_api_match": True,
        }

    @pytest.mark.parametrize(
        ("release_major", "api_major"),
        [(76, 4), (78, 3)],
    )
    def test_check_vapoursynth_fails_on_runtime_identity_mismatch(
        self,
        release_major: int,
        api_major: int,
    ) -> None:
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")
        version = SimpleNamespace(release_major=release_major, release_minor=0)
        api_version = SimpleNamespace(api_major=api_major, api_minor=2)

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(
                __version__=version,
                __api_version__=api_version,
            ),
        ):
            result = vs_check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert result.details["expected_release_match"] is (release_major == 78)
        assert result.details["expected_api_match"] is (api_major == 4)
        assert "complete supported media runtime" in str(result.hint)

    def test_check_vapoursynth_fails_when_version_identity_is_unavailable(self) -> None:
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(),
        ):
            result = vs_check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert result.details["observed_version"] is None
        assert result.details["observed_release"] is None

    def test_check_vapoursynth_keeps_raw_partial_version_separate_from_release(self) -> None:
        check = next(candidate for candidate in collect_checks() if candidate.name == "vapoursynth")
        version = SimpleNamespace(release_major=78, release_minor=0)

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(__version__=version),
        ):
            result = check.check_fn()

        assert result.details["observed_version"] == str(version)
        assert result.details["observed_release"] is None

    def test_check_vapoursynth_fails_when_missing(self) -> None:
        """Mock ImportError on VS import → check fails."""
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            side_effect=ImportError("No module"),
        ):
            result = vs_check.check_fn()

        assert result.passed is False
        assert "not found" in result.message
        assert result.hint == (
            "Make VapourSynth importable; see https://github.com/TJZine/frame-compare#quick-start"
        )
        assert "pip install" not in result.hint

    def test_check_vapoursynth_registers_runtime_dirs_before_import(self) -> None:
        """Ensure runtime DLL path registration runs as an import fallback."""
        checks = collect_checks()
        vs_check = next(c for c in checks if c.name == "vapoursynth")

        original_import = __import__
        mock_vs = MagicMock()
        mock_vs.__version__ = SimpleNamespace(release_major=78, release_minor=0)
        mock_vs.__api_version__ = SimpleNamespace(api_major=4, api_minor=2)
        vs_attempts = {"count": 0}

        def _fake_import(name: str, *args: object, **kwargs: object) -> object:
            if name == "vapoursynth":
                vs_attempts["count"] += 1
                if vs_attempts["count"] == 1:
                    raise ImportError("missing runtime DLL")
                return mock_vs
            return original_import(name, *args, **kwargs)

        with (
            patch("frame_compare.vs.env.register_windows_dll_dirs") as register_dirs,
            patch("builtins.__import__", side_effect=_fake_import),
        ):
            result = vs_check.check_fn()

        register_dirs.assert_called_once()
        assert vs_attempts["count"] == 2
        assert result.passed is True


class TestCheckVsPlacebo:
    def test_check_vs_placebo_reports_distribution_and_filter(self) -> None:
        checks = collect_checks()
        check = next(candidate for candidate in checks if candidate.name == "vs_placebo")
        plugin = SimpleNamespace(
            Tonemap=object(),
            functions=lambda: [SimpleNamespace(name="Tonemap")],
        )
        mock_vs = SimpleNamespace(core=SimpleNamespace(placebo=plugin))

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
                return_value=mock_vs,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.importlib.metadata.version",
                return_value="2.0.4",
            ),
        ):
            result = check.check_fn()

        assert result.passed is True
        assert result.available is True
        assert result.details["observed_distribution_version"] == "2.0.4"
        assert result.details["expected_distribution_match"] is True
        assert result.details["functions"] == ["Tonemap"]
        assert result.message == "vs-placebo 2.0.4 available (placebo.Tonemap)"

    def test_check_vs_placebo_version_mismatch_is_reported(self) -> None:
        checks = collect_checks()
        check = next(candidate for candidate in checks if candidate.name == "vs_placebo")
        plugin = SimpleNamespace(Tonemap=lambda: object(), functions=lambda: [])
        mock_vs = SimpleNamespace(core=SimpleNamespace(placebo=plugin))

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
                return_value=mock_vs,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.importlib.metadata.version",
                return_value="2.0.2",
            ),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert result.details["expected_distribution_match"] is False
        assert "does not match 2.0.4" in result.message

    def test_check_vs_placebo_reports_missing_tonemap_function(self) -> None:
        check = next(candidate for candidate in collect_checks() if candidate.name == "vs_placebo")
        plugin = SimpleNamespace(functions=lambda: [])
        mock_vs = SimpleNamespace(core=SimpleNamespace(placebo=plugin))

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
                return_value=mock_vs,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.importlib.metadata.version",
                return_value="2.0.4",
            ),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is False
        assert result.details["missing_functions"] == ["Tonemap"]
        assert result.message == "vs-placebo plugin is missing placebo.Tonemap"

    def test_check_vs_placebo_missing_is_optional_failure(self) -> None:
        checks = collect_checks()
        check = next(candidate for candidate in checks if candidate.name == "vs_placebo")
        mock_vs = SimpleNamespace(core=SimpleNamespace())

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
                return_value=mock_vs,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.importlib.metadata.version",
                side_effect=PackageNotFoundError,
            ),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is False
        assert result.details["observed_available"] is False
        assert result.details["observed_distribution_version"] is None


class TestCheckFFMS2:
    @pytest.mark.parametrize(
        ("required", "expected_passed", "expected_hint"),
        [
            pytest.param(False, True, None, id="optional-windows-runtime"),
            pytest.param(
                True,
                False,
                "Repair the supported media runtime, then rerun doctor",
                id="required-docker-runtime",
            ),
        ],
    )
    def test_check_ffms2_exception_honors_runtime_policy(
        self,
        monkeypatch: pytest.MonkeyPatch,
        required: bool,
        expected_passed: bool,
        expected_hint: str | None,
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1" if required else "0")
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            side_effect=RuntimeError("runtime failure"),
        ):
            result = check.check_fn()

        assert result.passed is expected_passed
        assert result.available is False
        assert result.hint == expected_hint
        assert result.details["exception_type"] == "RuntimeError"

    def test_check_ffms2_missing_is_expected_for_windows_baseline(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows-portable")
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "0")
        checks = collect_checks()
        check = next(candidate for candidate in checks if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace()),
        ):
            result = check.check_fn()

        assert result.passed is True
        assert result.available is False
        assert result.details["windows_baseline"] == "excluded"
        assert result.details["required_in_current_runtime"] is False

    @pytest.mark.parametrize(
        "required_value",
        [
            pytest.param(None, id="requirement-missing"),
            pytest.param("0", id="requirement-false"),
            pytest.param("not-a-flag", id="requirement-malformed"),
        ],
    )
    def test_check_ffms2_missing_fails_closed_for_docker_policy(
        self, monkeypatch: pytest.MonkeyPatch, required_value: str | None
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", " Docker ")
        if required_value is None:
            monkeypatch.delenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", raising=False)
        else:
            monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", required_value)
        checks = collect_checks()
        check = next(candidate for candidate in checks if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace()),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is False
        assert "required by this Docker runtime" in result.message
        assert result.hint == "Repair the complete Docker media runtime, then rerun doctor"
        assert result.details["current_runtime_kind"] == "docker"
        assert result.details["required_in_current_runtime"] is True

    def test_check_ffms2_reports_registered_source_function(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1")
        plugin = SimpleNamespace(
            Source=lambda *_args, **_kwargs: object(),
            Version=lambda: {"version": "5.0.0.0"},
            functions=lambda: [
                SimpleNamespace(name="Source"),
                SimpleNamespace(name="Version"),
            ],
        )
        checks = collect_checks()
        check = next(candidate for candidate in checks if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace(ffms2=plugin)),
        ):
            result = check.check_fn()

        assert result.passed is True
        assert result.available is True
        assert result.details["functions"] == ["Source", "Version"]
        assert result.details["observed_runtime_version"] == "5.0.0.0"
        assert result.details["expected_runtime_version_match"] is True

    def test_check_ffms2_rejects_wrong_runtime_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1")
        plugin = SimpleNamespace(
            Source=lambda *_args, **_kwargs: object(),
            Version=lambda: {"version": "4.0.0.0"},
            functions=lambda: [
                SimpleNamespace(name="Source"),
                SimpleNamespace(name="Version"),
            ],
        )
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace(ffms2=plugin)),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert result.details["observed_runtime_version"] == "4.0.0.0"
        assert result.details["expected_runtime_version_match"] is False

    def test_check_ffms2_allows_optional_runtime_version_mismatch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "0")
        plugin = SimpleNamespace(
            Source=lambda *_args, **_kwargs: object(),
            Version=lambda: {"version": "4.0.0.0"},
        )
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace(ffms2=plugin)),
        ):
            result = check.check_fn()

        assert result.passed is True
        assert result.available is True
        assert result.hint is None
        assert result.details["expected_runtime_version_match"] is False

    def test_check_ffms2_rejects_loaded_plugin_in_windows_portable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "WINDOWS-PORTABLE")
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "0")
        plugin = SimpleNamespace(
            Source=lambda *_args, **_kwargs: object(),
            Version=lambda: {"version": "5.0.0.0"},
            functions=lambda: [SimpleNamespace(name="Source"), SimpleNamespace(name="Version")],
        )
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace(ffms2=plugin)),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert "Windows portable baseline excludes it" in result.message
        assert result.details["current_runtime_kind"] == "windows-portable"

    def test_check_ffms2_rejects_partial_plugin_in_windows_portable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows-portable")
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "0")
        plugin = SimpleNamespace(
            Source=lambda *_args, **_kwargs: object(),
            functions=lambda: [SimpleNamespace(name="Source")],
        )
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffms2")

        with patch(
            "frame_compare.orchestration.doctor_checks.import_vapoursynth_module",
            return_value=SimpleNamespace(core=SimpleNamespace(ffms2=plugin)),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is False
        assert result.details["observed_available"] is False
        assert result.details["functions"] == ["Source"]
        assert "Windows portable baseline excludes it" in result.message


class TestCheckFFmpeg:
    """Tests for FFmpeg/ffprobe diagnostics."""

    def test_check_ffmpeg_reports_both_executable_versions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
        checks = collect_checks()
        ffmpeg_check = next(c for c in checks if c.name == "ffmpeg")

        def _resolve(name: str) -> str:
            return f"/runtime/{name}"

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.resolve_executable",
                side_effect=_resolve,
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.run_subprocess",
                side_effect=[
                    _completed_process("ffmpeg version n8.1.2-34-g9b6c8969e0\n"),
                    _completed_process("ffprobe version n8.1.2-34-g9b6c8969e0\n"),
                ],
            ),
        ):
            result = ffmpeg_check.check_fn()

        assert result.passed is True
        assert result.message == "ffmpeg version n8.1.2-34-g9b6c8969e0"
        assert result.details["ffmpeg_path"] == "/runtime/ffmpeg"
        assert result.details["ffprobe_path"] == "/runtime/ffprobe"
        assert result.details["ffprobe_version_line"] == ("ffprobe version n8.1.2-34-g9b6c8969e0")
        assert result.details["windows_license_profile"] == "LGPL-only"
        assert result.details["expected_version_fragment"] is None

    @pytest.mark.parametrize(
        ("runtime_kind_value", "version_fragment"),
        [
            ("windows-portable", WINDOWS_FFMPEG_EXECUTABLE_TOKEN),
            ("docker", "7.1.5-0+deb13u1"),
        ],
    )
    def test_check_ffmpeg_enforces_managed_runtime_identity(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runtime_kind_value: str,
        version_fragment: str,
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", runtime_kind_value)
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffmpeg")

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.resolve_executable",
                side_effect=lambda name: f"/runtime/{name}",
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.run_subprocess",
                side_effect=[
                    _completed_process(f"ffmpeg version {version_fragment}\n"),
                    _completed_process(f"ffprobe version {version_fragment}\n"),
                ],
            ),
        ):
            result = check.check_fn()

        assert result.passed is True
        assert result.details["expected_version_fragment"] == version_fragment
        assert result.details["expected_version_match"] is True

    def test_check_ffmpeg_accepts_epoch_free_debian_version_constant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        version = "7.1.5-0+deb13u1"
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "docker")
        monkeypatch.setattr(
            "frame_compare.orchestration.doctor_checks.DEBIAN_FFMPEG_PACKAGE_VERSION",
            version,
        )
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffmpeg")

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.resolve_executable",
                side_effect=lambda name: f"/runtime/{name}",
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.run_subprocess",
                side_effect=[
                    _completed_process(f"ffmpeg version {version}\n"),
                    _completed_process(f"ffprobe version {version}\n"),
                ],
            ),
        ):
            result = check.check_fn()

        assert result.passed is True
        assert result.details["expected_version_fragment"] == version
        assert result.details["expected_version_match"] is True

    @pytest.mark.parametrize(
        ("runtime_kind_value", "observed_version"),
        [
            ("windows-portable", "stale"),
            ("docker", "7.1.5-0+deb13u10"),
        ],
    )
    def test_check_ffmpeg_rejects_managed_runtime_identity_mismatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        runtime_kind_value: str,
        observed_version: str,
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", runtime_kind_value)
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffmpeg")

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.resolve_executable",
                side_effect=lambda name: f"/runtime/{name}",
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.run_subprocess",
                side_effect=[
                    _completed_process(f"ffmpeg version {observed_version}\n"),
                    _completed_process(f"ffprobe version {observed_version}\n"),
                ],
            ),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert result.details["expected_version_match"] is False
        assert "selected managed runtime version" in result.message

    @pytest.mark.parametrize("mismatched_executable", ["ffmpeg", "ffprobe"])
    def test_check_ffmpeg_rejects_windows_executable_token_near_match(
        self,
        monkeypatch: pytest.MonkeyPatch,
        mismatched_executable: str,
    ) -> None:
        monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows-portable")
        check = next(candidate for candidate in collect_checks() if candidate.name == "ffmpeg")
        versions: dict[str, str] = dict.fromkeys(
            ("ffmpeg", "ffprobe"), WINDOWS_FFMPEG_EXECUTABLE_TOKEN
        )
        versions[mismatched_executable] = f"{WINDOWS_FFMPEG_EXECUTABLE_TOKEN}0"

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.resolve_executable",
                side_effect=lambda name: f"/runtime/{name}",
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.run_subprocess",
                side_effect=[
                    _completed_process(f"ffmpeg version {versions['ffmpeg']}\n"),
                    _completed_process(f"ffprobe version {versions['ffprobe']}\n"),
                ],
            ),
        ):
            result = check.check_fn()

        assert result.passed is False
        assert result.available is True
        assert result.details["expected_version_fragment"] == WINDOWS_FFMPEG_EXECUTABLE_TOKEN
        assert result.details["expected_version_match"] is False

    @pytest.mark.parametrize("missing_executable", ["ffmpeg", "ffprobe"])
    def test_check_ffmpeg_fails_when_required_executable_is_missing(
        self, missing_executable: str
    ) -> None:
        checks = collect_checks()
        ffmpeg_check = next(c for c in checks if c.name == "ffmpeg")

        def _resolve(name: str) -> str:
            if name == missing_executable:
                raise FileNotFoundError(name)
            return f"/runtime/{name}"

        with patch(
            "frame_compare.orchestration.doctor_checks.resolve_executable",
            side_effect=_resolve,
        ):
            result = ffmpeg_check.check_fn()

        assert result.passed is False
        assert f"{missing_executable} not found" in result.message
        assert result.hint == (
            "Provide FFmpeg and ffprobe executables; see "
            "https://github.com/TJZine/frame-compare#requirements"
        )
        assert all(
            command not in result.hint.lower()
            for command in ("apt ", "brew ", "choco ", "pip ", "winget ")
        )

    def test_check_ffmpeg_sanitizes_version_probe_failure(self) -> None:
        checks = collect_checks()
        ffmpeg_check = next(c for c in checks if c.name == "ffmpeg")

        with (
            patch(
                "frame_compare.orchestration.doctor_checks.resolve_executable",
                side_effect=lambda name: f"/runtime/{name}",
            ),
            patch(
                "frame_compare.orchestration.doctor_checks.run_subprocess",
                side_effect=OSError("secret path"),
            ),
        ):
            result = ffmpeg_check.check_fn()

        assert result.passed is False
        assert result.details["exception_type"] == "OSError"
        assert "secret path" not in str(result.details)


def test_collect_checks_has_canonical_media_runtime_order() -> None:
    assert [check.name for check in collect_checks()] == [
        "python_version",
        "vapoursynth",
        "lsmas",
        "vs_placebo",
        "ffms2",
        "ffmpeg",
        "vspreview",
        "slowpics",
        "tmdb_api_key",
    ]
