"""Source acquisition failures follow the actual run command error contract."""

import json
from pathlib import Path

import pytest

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode

from .cli_helpers import isolated_cli_filesystem, runner


@pytest.mark.parametrize("json_mode", [False, True])
@pytest.mark.parametrize(
    ("failure", "code"),
    [
        ("missing", "FC-1001"),
        ("directory", "FC-1002"),
        ("utf8", "FC-1002"),
        ("toml", "FC-1002"),
        ("read_denied", "FC-1002"),
        ("section_json", "FC-1003"),
        ("list_json", "FC-1003"),
    ],
)
def test_run_config_acquisition_errors_are_typed_and_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    code: str,
    json_mode: bool,
) -> None:
    def unexpected_runtime(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("failed acquisition must not enter runtime")

    monkeypatch.setattr("frame_compare.cli.entry.runner.run", unexpected_runtime)
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = root / "config" / "selected.toml"
        config_path.parent.mkdir(parents=True)
        if failure == "directory":
            config_path.mkdir()
        elif failure == "utf8":
            config_path.write_bytes(b"\xff")
        elif failure == "toml":
            config_path.write_text("invalid = [")
        elif failure != "missing":
            config_path.write_text("[analysis]\nrandom_frame_count = 10\n")

        if failure == "read_denied":
            original = Path.read_bytes

            def denied(path: Path) -> bytes:
                if path.resolve() == config_path.resolve():
                    raise PermissionError("sentinel-sensitive-source-detail")
                return original(path)

            monkeypatch.setattr(Path, "read_bytes", denied)
        elif failure in {"section_json", "list_json"}:
            variable = (
                "FRAME_COMPARE_SLOWPICS"
                if failure == "section_json"
                else "FRAME_COMPARE_ANALYSIS__USER_FRAMES"
            )
            monkeypatch.setenv(variable, '{"webhook_url":"sentinel-sensitive-source-detail"')

        args = ["run", "--root", str(root), "--config", "config/selected.toml"]
        if json_mode:
            args.append("--json")
        result = runner.invoke(app, args)

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert "sentinel-sensitive-source-detail" not in result.stdout + result.stderr
    assert "Traceback" not in result.stdout + result.stderr
    if json_mode:
        assert result.stderr == ""
        payload = json.loads(result.stdout)
        assert payload["success"] is False
        assert payload["error"]["code"] == code
    else:
        assert result.stdout == ""
        assert code in result.stderr


@pytest.mark.parametrize("default_target", ["500", '"invalid-irrelevant-default"'])
def test_write_config_uses_selected_color_authority_despite_ambient_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    default_target: str,
) -> None:
    from frame_compare.config.loader import load_config
    from frame_compare.config.schema import TonemapPreset
    from frame_compare.render.prepare import resolve_tonemap_settings
    from frame_compare.vs.tonemap_presets import get_preset_settings

    with isolated_cli_filesystem(tmp_path, monkeypatch) as cwd:
        ambient = cwd / "config" / "config.toml"
        ambient.parent.mkdir()
        ambient.write_text(f"[color]\ntarget_nits = {default_target}\n")
        root = cwd / "workspace"
        selected = root / "configs" / "selected.toml"
        selected.parent.mkdir(parents=True)
        selected.write_text('[color]\npreset = "filmic"\n')
        presets = root / "config" / "presets"
        presets.mkdir(parents=True)
        (presets / "partial.toml").write_text("[analysis]\nrandom_frame_count = 23\n")

        applied = runner.invoke(
            app,
            [
                "preset",
                "apply",
                "partial",
                "--root",
                str(root),
                "--config",
                "configs/selected.toml",
            ],
        )
        assert applied.exit_code == 0, applied.stdout + applied.stderr
        expected = get_preset_settings(TonemapPreset.FILMIC)
        assert resolve_tonemap_settings(load_config(selected)) == expected

        written = runner.invoke(
            app,
            [
                "run",
                "--write-config",
                "--root",
                str(root),
                "--config",
                "configs/selected.toml",
                "--random-frame-count",
                "42",
                "--json",
            ],
        )
        assert written.exit_code == 0, written.stdout + written.stderr
        reloaded = load_config(selected)
        assert reloaded.analysis.random_frame_count == 42
        assert resolve_tonemap_settings(reloaded) == expected
