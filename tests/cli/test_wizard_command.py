import tomllib
from pathlib import Path

import typer
from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode

from .cli_helpers import runner


def _run_wizard_and_assert_config() -> None:
    with runner.isolated_filesystem():
        Path("inputs").mkdir()
        result = runner.invoke(
            app,
            ["wizard"],
            input="inputs\ny\npublic\ny\nabc123\n",
        )
        assert result.exit_code == 0
        assert "slow.pics visibility (public|unlisted)" in result.stdout
        assert "private" not in result.stdout

        config_path = Path("config") / "config.toml"
        assert config_path.exists()

        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert set(data.keys()) == {"paths", "slowpics", "tmdb"}
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["auto_upload"] is True
        assert data["slowpics"]["visibility"] == "public"
        assert data["slowpics"]["delete_after_upload"] is True
        assert data["tmdb"]["api_key"] == "abc123"


def test_wizard_writer_uses_atomic_write(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from frame_compare.cli.entry import _write_wizard_config_payload

    calls: list[Path] = []

    def _fake_write(path: Path, content: str, *, encoding: str = "utf-8") -> None:
        calls.append(path)
        path.write_text(content, encoding=encoding)

    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _fake_write)

    destination = tmp_path / "config" / "config.toml"
    _write_wizard_config_payload(destination, {"paths": {}, "slowpics": {}})

    assert calls == [destination]


def test_wizard_defaults_slowpics_upload_to_disabled() -> None:
    with runner.isolated_filesystem():
        Path("inputs").mkdir()
        result = runner.invoke(
            app,
            ["wizard"],
            input="inputs\n\nunlisted\n\n\n",
        )
        assert result.exit_code == 0

        config_path = Path("config") / "config.toml"
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["slowpics"]["auto_upload"] is False


def test_wizard_writes_valid_config_toml():
    _run_wizard_and_assert_config()


def test_wizard_writer_writes_to_explicit_config_path(tmp_path: Path) -> None:
    from frame_compare.cli.entry import _write_wizard_config_payload

    destination = tmp_path / "custom" / "config.toml"
    payload: dict[str, object] = {
        "paths": {"input_dir": "comparison_videos"},
        "slowpics": {"auto_upload": False},
        "tmdb": {"api_key": None},
    }

    _write_wizard_config_payload(destination, payload)

    assert destination.exists()
    text = destination.read_text(encoding="utf-8")
    assert "[paths]" in text
    assert 'input_dir = "comparison_videos"' in text
    data = tomllib.loads(text)
    assert "tmdb" not in data


def test_wizard_cancel_exits_130_and_writes_nothing(monkeypatch: MonkeyPatch) -> None:
    def _abort(*_args: object, **_kwargs: object) -> None:
        raise typer.Abort()

    monkeypatch.setattr("frame_compare.cli.entry.typer.prompt", _abort)

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["wizard"])
        assert result.exit_code == 130
        assert not (Path("config") / "config.toml").exists()


def test_wizard_write_error_uses_cli_error_contract(monkeypatch: MonkeyPatch) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr(
        "frame_compare.cli.entry._prompt_input_dir",
        lambda *_args, **_kwargs: "inputs",
    )
    monkeypatch.setattr("frame_compare.cli.entry.typer.confirm", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        "frame_compare.cli.entry._prompt_visibility",
        lambda _default: "unlisted",
    )
    monkeypatch.setattr("frame_compare.cli.entry.typer.prompt", lambda *_args, **_kwargs: "")
    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(app, ["wizard", "--root", str(root)])

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert result.stdout == ""
        assert "FC-1007" in result.stderr
        assert "Failed to write configuration file" in result.stderr
        assert "Traceback" not in result.stderr
        assert not (root / "config" / "config.toml").exists()


def test_wizard_root_validates_relative_input_dir_against_root() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["wizard", "--root", str(root)],
            input="inputs\ny\nunlisted\ny\nabc123\n",
        )
        assert result.exit_code == 0

        config_path = root / "config" / "config.toml"
        assert config_path.exists()
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["visibility"] == "unlisted"


def test_wizard_root_reprompts_on_missing_input_dir() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        root.mkdir()
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(
            app,
            ["wizard", "--root", str(root)],
            input="missing\ninputs\ny\nprivate\nunlisted\ny\nabc123\n",
        )
        assert result.exit_code == 0
        assert "Invalid visibility. Choose public or unlisted." in result.stdout

        config_path = root / "config" / "config.toml"
        assert config_path.exists()
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["visibility"] == "unlisted"


def test_prepare_toml_payload_copies_paths_and_slowpics_sections() -> None:
    from frame_compare.cli.entry import _prepare_toml_payload

    paths = {"input_dir": "inputs"}
    slowpics = {"auto_upload": True}
    payload: dict[str, object] = {
        "paths": paths,
        "slowpics": slowpics,
        "tmdb": {"api_key": ""},
    }

    prepared = _prepare_toml_payload(payload)
    assert prepared["paths"] == paths
    assert prepared["slowpics"] == slowpics
    assert prepared["paths"] is not paths
    assert prepared["slowpics"] is not slowpics
    assert "tmdb" not in prepared
