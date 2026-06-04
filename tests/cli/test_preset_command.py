import tomllib
from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode
from frame_compare.config.errors import ConfigNotFoundError

from .cli_helpers import MINIMAL_CONFIG, _write_minimal_config, runner


def test_preset_apply_missing_preset_exits_with_error_code() -> None:
    with runner.isolated_filesystem():
        root = Path(".")
        config_path = _write_minimal_config(root)
        result = runner.invoke(
            app,
            [
                "preset",
                "apply",
                "missing",
                "--root",
                str(root),
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 2
        assert result.stdout == ""
        assert "FC-1004" in result.stderr


def test_preset_apply_invalid_name_exits_with_error_code() -> None:
    with runner.isolated_filesystem():
        root = Path(".")
        config_path = _write_minimal_config(root)
        result = runner.invoke(
            app,
            [
                "preset",
                "apply",
                "../escape",
                "--root",
                str(root),
                "--config",
                str(config_path),
            ],
        )
        assert result.exit_code == 2
        assert result.stdout == ""
        assert "FC-1006" in result.stderr


def test_preset_list_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Zebra.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Zebra"]
        assert result.stderr == ""


def test_preset_apply_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nframe_count = 12\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["preset", "apply", "boost", "--root", str(root), "--config", "config/config.toml"],
        )
        assert result.exit_code == 0
        assert result.stdout == ""
        assert f"Applied preset 'boost' to {config_path.resolve()}" in result.stderr
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 12


def test_preset_save_stub():
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "demo", "--root", str(root), "--config", "config/config.toml"],
        )
        assert result.exit_code == 0
        assert result.stdout == ""
        preset_path = root / "config" / "presets" / "demo.toml"
        assert preset_path.exists()
        assert f"Saved preset 'demo' to {preset_path.resolve()}" in result.stderr


def test_preset_list_prints_names_sorted_case_insensitive() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Bravo.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')
        (presets_dir / "charlie.toml").write_text('[paths]\ninput_dir = "c"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Bravo", "charlie"]
        assert result.stderr == ""


def test_preset_list_uses_root_presets_even_when_config_path_is_nondefault() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')

        result = runner.invoke(
            app,
            ["preset", "list", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha"]
        assert result.stderr == ""


def test_preset_list_error_does_not_suggest_unsupported_verbose(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.entry.list_presets",
        lambda *, presets_dir: (_ for _ in ()).throw(ConfigNotFoundError(Path("missing.toml"))),
    )

    result = runner.invoke(app, ["preset", "list"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert "--verbose" not in result.stderr
    assert "Details:" in result.stderr
    assert "path:" in result.stderr


def test_preset_save_respects_root_and_config_writes_preset_file() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "sample", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        preset_path = root / "config" / "presets" / "sample.toml"
        assert preset_path.exists()
        assert f"Saved preset 'sample' to {preset_path.resolve()}" in result.stderr


def test_preset_save_write_error_uses_cli_error_contract(
    monkeypatch: MonkeyPatch,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.config.presets.write_text_atomic", _write_text_atomic)

    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)

        result = runner.invoke(
            app,
            ["preset", "save", "demo", "--root", str(root), "--config", "config/config.toml"],
        )

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert result.stdout == ""
    assert "FC-1007" in result.stderr
    assert "Failed to write preset file" in result.stderr
    assert "Traceback" not in result.stderr


def test_preset_apply_respects_root_and_config_updates_config_file() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nframe_count = 22\n",
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            ["preset", "apply", "boost", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        assert result.stdout == ""
        assert f"Applied preset 'boost' to {config_path.resolve()}" in result.stderr
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["analysis"]["frame_count"] == 22
