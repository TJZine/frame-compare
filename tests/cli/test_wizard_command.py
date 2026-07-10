import tomllib
from pathlib import Path

import typer
from pytest import MonkeyPatch

from frame_compare.cli.cli_helpers import prepare_toml_payload
from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode
from frame_compare.cli.wizard_command import handle_wizard, write_wizard_config_payload

from .cli_helpers import runner


def _write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.write_text(content, encoding=encoding)


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
        assert f"Configuration written: {config_path.resolve()}" in result.stderr


def test_wizard_writes_explicit_config_path_via_public_cli() -> None:
    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)
        config_path = root / "custom" / "config.toml"

        result = runner.invoke(
            app,
            ["wizard", "--root", str(root), "--config", "custom/config.toml"],
            input="inputs\ny\npublic\ny\nabc123\n",
        )

        assert result.exit_code == 0
        assert result.stdout
        assert f"Configuration written: {config_path.resolve()}" in result.stderr
        assert config_path.exists()
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["paths"]["input_dir"] == "inputs"
        assert data["slowpics"]["auto_upload"] is True
        assert data["slowpics"]["visibility"] == "public"
        assert data["slowpics"]["delete_after_upload"] is True
        assert data["tmdb"]["api_key"] == "abc123"


def test_wizard_rejects_external_config_before_prompts_or_write(
    monkeypatch: MonkeyPatch,
) -> None:
    def _unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external config must be rejected before prompting or writing")

    monkeypatch.setattr("frame_compare.cli.entry._prompt_input_dir", _unexpected)
    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _unexpected)

    with runner.isolated_filesystem():
        root = Path("workspace")
        root.mkdir()
        external_config = (Path("outside") / "config.toml").resolve()

        result = runner.invoke(
            app,
            ["wizard", "--root", str(root), "--config", str(external_config)],
        )

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stdout == ""
    assert "FC-3009" in result.stderr
    assert "Traceback" not in result.stderr


def test_handle_wizard_allows_exact_windows_portable_state_config(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    portable_config = tmp_path / "portable-state" / "config.toml"
    monkeypatch.setattr(
        "frame_compare.orchestration.preflight._windows_portable_state_config_path",
        lambda: portable_config,
    )
    writes: list[Path] = []

    handle_wizard(
        root,
        portable_config,
        prompt_input_dir=lambda _default, *, base_dir: str(tmp_path / "external-media"),
        prompt_visibility=lambda _default: "unlisted",
        confirm=lambda _text, *, default: default,
        prompt_secret=lambda _text, *, default, hide_input: "",
        write_payload=lambda path, _data: writes.append(path),
        handle_error=lambda *_args, **_kwargs: int(ExitCode.GENERAL_ERROR),
        stdin_is_tty=False,
        no_color=True,
    )

    assert writes == [portable_config]


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
        assert f"Configuration written: {config_path.resolve()}" in result.stderr
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["slowpics"]["auto_upload"] is False


def test_wizard_defaults_slowpics_visibility_to_public() -> None:
    with runner.isolated_filesystem():
        Path("inputs").mkdir()
        result = runner.invoke(
            app,
            ["wizard"],
            input="inputs\n\n\n\n\n",
        )

        assert result.exit_code == 0
        config_path = Path("config") / "config.toml"
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert data["slowpics"]["visibility"] == "public"


def test_wizard_writes_valid_config_toml():
    _run_wizard_and_assert_config()


def test_wizard_writer_writes_to_explicit_config_path(tmp_path: Path) -> None:
    destination = tmp_path / "custom" / "config.toml"
    payload: dict[str, object] = {
        "paths": {"input_dir": "comparison_videos"},
        "slowpics": {"auto_upload": False},
        "tmdb": {"api_key": None},
    }

    write_wizard_config_payload(destination, payload, text_writer=_write_text)

    assert destination.exists()
    text = destination.read_text(encoding="utf-8")
    assert "[paths]" in text
    assert 'input_dir = "comparison_videos"' in text
    data = tomllib.loads(text)
    assert "tmdb" not in data


def test_wizard_writer_preserves_unrelated_sections_and_strips_nested_none(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "custom" / "config.toml"
    payload: dict[str, object] = {
        "paths": {"input_dir": "comparison_videos"},
        "report": {"output_dir": None, "auto_open": False},
        "diagnostics": {"nested": {"drop": None, "keep": "value"}},
        "tmdb": {"api_key": "", "enabled": True, "timeout_seconds": None},
    }

    write_wizard_config_payload(destination, payload, text_writer=_write_text)

    data = tomllib.loads(destination.read_text(encoding="utf-8"))
    assert data["report"] == {"auto_open": False}
    assert data["diagnostics"] == {"nested": {"keep": "value"}}
    assert data["tmdb"] == {"enabled": True}


def test_wizard_writer_omits_unsupported_preserved_values(tmp_path: Path) -> None:
    destination = tmp_path / "custom" / "config.toml"
    unsupported = object()
    payload: dict[str, object] = {
        "paths": {"input_dir": "comparison_videos"},
        "report": {
            "auto_open": True,
            "unsupported": unsupported,
            "nested": {"drop": unsupported, "keep": "value"},
            "list_values": ["keep", None, unsupported],
        },
        "top_level_unsupported": unsupported,
    }

    write_wizard_config_payload(destination, payload, text_writer=_write_text)

    data = tomllib.loads(destination.read_text(encoding="utf-8"))
    assert "top_level_unsupported" not in data
    assert data["report"] == {
        "auto_open": True,
        "nested": {"keep": "value"},
        "list_values": ["keep"],
    }


def test_wizard_cancel_exits_130_and_writes_nothing(monkeypatch: MonkeyPatch) -> None:
    def _abort(*_args: object, **_kwargs: object) -> None:
        raise typer.Abort()

    monkeypatch.setattr("frame_compare.cli.entry.typer.prompt", _abort)

    with runner.isolated_filesystem():
        result = runner.invoke(app, ["wizard"])
        assert result.exit_code == 130
        assert not (Path("config") / "config.toml").exists()


def test_wizard_eof_exits_130_and_writes_nothing() -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["wizard"], input="")

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
        assert "--verbose" not in result.stderr
        assert "Details:" in result.stderr
        assert "Traceback" not in result.stderr
        assert not (root / "config" / "config.toml").exists()


def test_wizard_error_uses_default_terminal_color_policy(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.delenv("NO_COLOR", raising=False)

    def _handle_error(
        _error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int:
        captured["no_color"] = no_color
        captured["verbose"] = verbose
        captured["verbose_hint"] = verbose_hint
        return int(ExitCode.CONFIG_ERROR)

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
    monkeypatch.setattr("frame_compare.cli.entry.handle_error", _handle_error)
    monkeypatch.setattr("frame_compare.cli.entry.write_text_atomic", _write_text_atomic)

    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(app, ["wizard", "--root", str(root)])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert captured == {
        "no_color": False,
        "verbose": False,
        "verbose_hint": None,
    }


def test_wizard_validation_error_uses_cli_error_contract(monkeypatch: MonkeyPatch) -> None:
    from frame_compare.config.schema import ConfigSchema

    def _raise_validation_error(_data: dict[str, object]) -> None:
        ConfigSchema.model_validate({"analysis": {"frame_count": 0}})

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
    monkeypatch.setattr("frame_compare.cli.wizard_command.validate_config", _raise_validation_error)

    with runner.isolated_filesystem():
        root = Path("workspace")
        (root / "inputs").mkdir(parents=True)

        result = runner.invoke(app, ["wizard", "--root", str(root)])

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert result.stdout == ""
        assert "FC-1003" in result.stderr
        assert "Invalid configuration: frame_count" in result.stderr
        assert "--verbose" not in result.stderr
        assert "Details:" in result.stderr
        assert "Traceback" not in result.stderr
        assert not (root / "config" / "config.toml").exists()


def test_handle_wizard_uses_visible_secret_prompt_when_stdin_is_not_tty(tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    written_payloads: list[tuple[Path, dict[str, object]]] = []

    def _prompt_secret(text: str, *, default: str, hide_input: bool) -> str:
        captured["text"] = text
        captured["default"] = default
        captured["hide_input"] = hide_input
        return ""

    handle_wizard(
        tmp_path,
        tmp_path / "config" / "config.toml",
        prompt_input_dir=lambda _default, *, base_dir: "inputs",
        prompt_visibility=lambda _default: "unlisted",
        confirm=lambda _text, *, default: default,
        prompt_secret=_prompt_secret,
        write_payload=lambda config_path, data: written_payloads.append((config_path, data)),
        handle_error=lambda _error, *, no_color, verbose, verbose_hint="--verbose": 1,
        stdin_is_tty=False,
        no_color=False,
    )

    assert captured == {
        "text": "TMDB API key (optional)",
        "default": "",
        "hide_input": False,
    }
    assert written_payloads


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


def test_prepare_toml_payload_preserves_sections_strips_none_and_copies() -> None:
    paths = {"input_dir": "inputs"}
    slowpics = {"auto_upload": True}
    report = {"output_dir": None, "auto_open": True}
    payload: dict[str, object] = {
        "paths": paths,
        "slowpics": slowpics,
        "report": report,
        "diagnostics": {"nested": {"drop": None, "keep": "value"}},
        "tmdb": {"api_key": ""},
    }

    prepared = prepare_toml_payload(payload)
    assert prepared["paths"] == paths
    assert prepared["slowpics"] == slowpics
    assert prepared["report"] == {"auto_open": True}
    assert prepared["diagnostics"] == {"nested": {"keep": "value"}}
    assert prepared["paths"] is not paths
    assert prepared["slowpics"] is not slowpics
    assert "tmdb" not in prepared


def test_prepare_toml_payload_omits_tmdb_when_api_key_is_none() -> None:
    prepared = prepare_toml_payload({"tmdb": {"api_key": None}})

    assert "tmdb" not in prepared
