from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pytest import MonkeyPatch
from typer.testing import Result

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode

from .cli_helpers import MINIMAL_CONFIG, isolated_cli_filesystem, runner


def _write_workspace(root: Path, *, config_suffix: str = "") -> Path:
    config_dir = root / "config"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(MINIMAL_CONFIG + config_suffix, encoding="utf-8")
    return config_path


def _invoke(root: Path, config_path: Path, *args: str) -> Result:
    return runner.invoke(
        app,
        [
            "run",
            "--root",
            str(root),
            "--config",
            str(config_path.relative_to(root)),
            "--dry-run",
            *args,
        ],
    )


def _unexpected(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("runtime boundary must not be reached by --dry-run")


def test_run_dry_run_json_has_exact_allowlisted_shape_and_no_secrets(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.run_command.build_run_request_from_cli",
        _unexpected,
    )
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _unexpected)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(
            root,
            config_suffix="""
[sources]
reference = "Zulu.mp4"

[analysis]
user_frames = [7, 9]
random_frame_count = 3
dark_frame_count = 1
bright_frame_count = 0
motion_frame_count = 2
random_seed = 99
performance_mode = "performance"

[slowpics]
auto_upload = true
visibility = "unlisted"
webhook_url = "https://secret.invalid/sentinel-token"

[tmdb]
api_key = "sentinel-api-key"
""",
        )
        input_dir = root / "comparison_videos"
        input_dir.mkdir()
        for name in ("Zulu.mp4", "alpha.MKV", "ignored.txt"):
            (input_dir / name).write_bytes(b"")
        resolved_input = input_dir.resolve()

        result = _invoke(root, config_path, "--json")

    assert result.exit_code == 0
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload == {
        "checks_not_performed": [
            "doctor",
            "ffprobe_or_ffmpeg",
            "media_probe",
            "analysis",
            "alignment",
            "cache_reads_or_writes",
            "run_folder_reservation_or_metadata_writes",
            "render_or_report_generation",
            "network_publishing_or_metadata",
            "browser_clipboard_or_vspreview",
        ],
        "dry_run": True,
        "input": {
            "resolved_directory": str(resolved_input),
            "source_filenames": ["alpha.MKV", "Zulu.mp4"],
        },
        "outputs": {
            "report": True,
            "report_auto_open_configured": True,
            "run_folders": True,
            "screenshots": True,
        },
        "publishing": {
            "copy_url_to_clipboard_configured": True,
            "create_url_shortcut_configured": True,
            "open_in_browser_configured": True,
            "slowpics_upload": True,
            "slowpics_visibility": "unlisted",
            "webhook_configured": True,
        },
        "reference": {
            "configured_selector": "Zulu.mp4",
            "resolved_filename": "Zulu.mp4",
        },
        "runtime_facts": {
            "clip_metadata": {
                "reason": "requires media probing",
                "status": "unknown",
                "value": None,
            },
            "final_selected_frames": {
                "reason": "requires media probing and runtime frame selection",
                "status": "unknown",
                "value": None,
            },
            "output_dimensions": {
                "reason": "requires media probing and render planning",
                "status": "unknown",
                "value": None,
            },
            "run_folder_name": {
                "reason": "resolved during run-folder reservation",
                "status": "unknown",
                "value": None,
            },
        },
        "selection": {
            "analysis_metrics_required": True,
            "analysis_performance_mode": "performance",
            "bright_frame_count": 0,
            "dark_frame_count": 1,
            "motion_frame_count": 2,
            "random_frame_count": 3,
            "random_seed": 99,
            "requested_user_frames": [7, 9],
            "strategy": ["user", "random", "dark", "motion"],
        },
    }
    assert "sentinel-api-key" not in result.stdout
    assert "sentinel-token" not in result.stdout
    assert "secret.invalid" not in result.stdout


def test_run_dry_run_human_and_quiet_follow_current_quiet_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)
        input_dir = root / "comparison_videos"
        input_dir.mkdir()
        (input_dir / "source.mkv").write_bytes(b"")

        normal = _invoke(root, config_path)
        quiet = _invoke(root, config_path, "--quiet")

    assert normal.exit_code == 0
    assert "Dry-run plan" in normal.stdout
    assert "source.mkv" in normal.stdout
    assert "checks not performed" in normal.stdout
    assert normal.stderr == ""
    assert quiet.exit_code == 0
    assert "Dry run: 1 source files; no side effects performed." in quiet.stdout
    assert "checks not performed" not in quiet.stdout
    assert quiet.stderr == ""


def test_run_dry_run_always_reserves_a_run_folder_when_execution_proceeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)
        input_dir = root / "comparison_videos"
        input_dir.mkdir()
        (input_dir / "source.mkv").write_bytes(b"")

        result = _invoke(root, config_path, "--json")

    assert result.exit_code == 0
    assert json.loads(result.stdout)["runtime_facts"]["run_folder_name"] == {
        "reason": "resolved during run-folder reservation",
        "status": "unknown",
        "value": None,
    }


def test_run_dry_run_accepts_external_input_override_and_reports_only_that_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)
        external_input = Path("external-media").resolve()
        external_input.mkdir()
        (external_input / "external.ts").write_bytes(b"")

        result = _invoke(root, config_path, "--input", str(external_input), "--json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["input"] == {
        "resolved_directory": str(external_input),
        "source_filenames": ["external.ts"],
    }


@pytest.mark.parametrize(
    ("setup_input", "expected_code"),
    [
        (False, "FC-3006"),
        (True, "FC-3001"),
    ],
)
def test_run_dry_run_rejects_missing_or_empty_input(
    setup_input: bool,
    expected_code: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)
        if setup_input:
            input_dir = root / "comparison_videos"
            input_dir.mkdir()
            (input_dir / "not-video.txt").write_text("ignored", encoding="utf-8")

        result = _invoke(root, config_path, "--json")

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"]["code"] == expected_code


def test_run_dry_run_validates_reference_selector_without_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(
            root,
            config_suffix='\n[sources]\nreference = "missing-source"\n',
        )
        input_dir = root / "comparison_videos"
        input_dir.mkdir()
        (input_dir / "source.mkv").write_bytes(b"")

        result = _invoke(root, config_path, "--json")

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "FC-3012"
    assert payload["error"]["details"]["role"] == "sources.reference"


@pytest.mark.parametrize("early_mode", ["--write-config", "--diagnose-paths"])
def test_run_dry_run_rejects_other_early_exit_modes(
    early_mode: str,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _unexpected)
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)

        result = _invoke(root, config_path, early_mode, "--json")

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["message"] == ("--dry-run is incompatible with another early-exit mode")


def test_run_dry_run_validates_existing_cache_and_interactive_contracts(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _unexpected)
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)

        cache_result = _invoke(
            root,
            config_path,
            "--no-cache",
            "--from-cache-only",
            "--json",
        )
        interactive_result = _invoke(
            root,
            config_path,
            "--force-interactive-alignment",
            "--json",
        )

    assert cache_result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert json.loads(cache_result.stdout)["error"]["message"] == (
        "Cache mode flags are mutually exclusive"
    )
    assert interactive_result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert json.loads(interactive_result.stdout)["error"]["message"] == (
        "Interactive alignment is not supported with --json"
    )


def test_run_dry_run_preserves_fastest_analysis_cache_only_conflict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(
            root,
            config_suffix="""
[sources]
analysis_source = "fastest"

[analysis]
random_frame_count = 0
dark_frame_count = 1
""",
        )
        input_dir = root / "comparison_videos"
        input_dir.mkdir()
        (input_dir / "source.mkv").write_bytes(b"")

        result = _invoke(root, config_path, "--from-cache-only", "--json")

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stderr == ""
    assert json.loads(result.stdout)["error"]["code"] == "FC-3014"


def test_run_dry_run_invalid_choice_uses_standard_json_error_and_skips_request(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.run_command.build_run_request_from_cli",
        _unexpected,
    )
    monkeypatch.setattr("frame_compare.cli.entry.runner.run", _unexpected)
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root)

        result = _invoke(root, config_path, "--tm-preset", "invalid", "--json")

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == [
        "color",
        "preset",
    ]


@pytest.mark.parametrize(
    ("config_suffix", "extra_args", "expected_loc"),
    [
        ("\n[analysis]\nunknown_selector = 1\n", (), ["analysis", "unknown_selector"]),
        ("", ("--frames", "1,,2"), ["analysis", "user_frames"]),
    ],
)
def test_run_dry_run_rejects_invalid_config_and_frame_selectors(
    config_suffix: str,
    extra_args: tuple[str, ...],
    expected_loc: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_workspace(root, config_suffix=config_suffix)

        result = _invoke(root, config_path, *extra_args, "--json")

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "FC-1003"
    assert payload["error"]["details"]["validation_errors"][0]["loc"] == expected_loc


def test_run_dry_run_does_not_import_or_call_runtime_side_effect_owners(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    config_path = _write_workspace(root)
    input_dir = root / "comparison_videos"
    input_dir.mkdir()
    (input_dir / "source.mkv").write_bytes(b"")
    script = r"""
import importlib.abc
import json
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

blocked = (
    "frame_compare.orchestration.coordinator",
    "frame_compare.runner",
    "frame_compare.vs",
    "frame_compare.vspreview",
    "frame_compare.services.report",
    "frame_compare.services.metadata",
    "frame_compare.services.publishers",
    "frame_compare.services.run_info",
    "frame_compare.services.slowpics",
    "frame_compare.analysis.cache_io",
    "frame_compare.services.alignment_reuse_cache",
    "frame_compare.orchestration.preparation",
)

class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in blocked):
            raise AssertionError(f"forbidden import: {fullname}")
        return None

def unexpected(*args, **kwargs):
    raise AssertionError("forbidden side effect")

sys.meta_path.insert(0, Blocker())

from typer.testing import CliRunner
from frame_compare.cli.entry import app
import frame_compare.cli.entry as entry
import frame_compare.cli.run_command as run_command

def snapshot_tree(root):
    snapshot = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot.append((relative, "directory", None))
        else:
            snapshot.append((relative, "file", path.read_bytes()))
    return snapshot

root = Path(sys.argv[1])
config = Path(sys.argv[2])
before = snapshot_tree(root)
subprocess.run = unexpected
subprocess.Popen = unexpected
webbrowser.open = unexpected
socket.create_connection = unexpected
socket.socket = unexpected
entry._copy_text_to_clipboard = unexpected
entry._open_url_in_browser = unexpected
entry._maybe_open_report = unexpected
entry.configure_logging = unexpected
entry.runner.run = unexpected
run_command.build_run_request_from_cli = unexpected
result = CliRunner().invoke(
    app,
    ["run", "--root", str(root), "--config", str(config.relative_to(root)), "--dry-run", "--json"],
)
assert result.exit_code == 0, result.output
assert json.loads(result.stdout)["dry_run"] is True
assert result.stderr == ""
assert snapshot_tree(root) == before
"""

    result = subprocess.run(
        [sys.executable, "-c", script, str(root), str(config_path)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
