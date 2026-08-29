import tomllib
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode
from frame_compare.config.errors import ConfigNotFoundError

from .cli_helpers import MINIMAL_CONFIG, _write_minimal_config, isolated_cli_filesystem, runner


def test_preset_apply_missing_preset_exits_with_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
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


def test_preset_apply_invalid_name_exits_with_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
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


def test_preset_list_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "Zebra.toml").write_text('[paths]\ninput_dir = "a"')
        (presets_dir / "alpha.toml").write_text('[paths]\ninput_dir = "b"')

        result = runner.invoke(app, ["preset", "list", "--root", str(root)])
        assert result.exit_code == 0
        assert result.stdout.splitlines() == ["alpha", "Zebra"]
        assert result.stderr == ""


def test_preset_apply_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(MINIMAL_CONFIG)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nrandom_frame_count = 12\n",
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
        assert data["analysis"]["random_frame_count"] == 12


def test_preset_save_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    with isolated_cli_filesystem(tmp_path, monkeypatch):
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


@pytest.mark.parametrize("operation", ["apply", "save"])
def test_preset_config_writes_reject_external_config_before_load_or_write(
    operation: str,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("external config must be rejected before load or write")

    monkeypatch.setattr("frame_compare.cli.entry.load_config", _unexpected)
    monkeypatch.setattr("frame_compare.cli.entry.write_config_to", _unexpected)
    monkeypatch.setattr("frame_compare.cli.entry.apply_preset", _unexpected)
    monkeypatch.setattr("frame_compare.cli.entry.save_preset", _unexpected)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        root.mkdir()
        external_config = (Path("outside") / "config.toml").resolve()
        result = runner.invoke(
            app,
            [
                "preset",
                operation,
                "demo",
                "--root",
                str(root),
                "--config",
                str(external_config),
            ],
        )

    assert result.exit_code == int(ExitCode.INPUT_ERROR)
    assert result.stdout == ""
    assert "FC-3009" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("operation", ["apply", "save"])
def test_preset_config_writes_allow_exact_windows_portable_state_config(
    operation: str,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        root.mkdir()
        portable_config = Path("portable-state") / "config.toml"
        portable_config.parent.mkdir()
        portable_config.write_text(MINIMAL_CONFIG, encoding="utf-8")
        resolved_portable_config = portable_config.resolve()
        monkeypatch.setattr(
            "frame_compare.orchestration.preflight._windows_portable_state_config_path",
            lambda: resolved_portable_config,
        )
        if operation == "apply":
            presets_dir = root / "config" / "presets"
            presets_dir.mkdir(parents=True)
            (presets_dir / "demo.toml").write_text(
                "[analysis]\nrandom_frame_count = 12\n",
                encoding="utf-8",
            )

        result = runner.invoke(
            app,
            [
                "preset",
                operation,
                "demo",
                "--root",
                str(root),
                "--config",
                str(resolved_portable_config),
            ],
        )

        assert result.exit_code == 0
        if operation == "apply":
            persisted = tomllib.loads(portable_config.read_text(encoding="utf-8"))
            assert persisted["analysis"]["random_frame_count"] == 12
        else:
            assert (root / "config" / "presets" / "demo.toml").exists()


@pytest.mark.parametrize("operation", ["apply", "save"])
def test_preset_config_rejects_removed_report_output_directory(
    operation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            MINIMAL_CONFIG + '\n[report]\noutput_dir = "reports/custom"\n', encoding="utf-8"
        )
        if operation == "apply":
            presets_dir = root / "config" / "presets"
            presets_dir.mkdir(parents=True, exist_ok=True)
            (presets_dir / "demo.toml").write_text(
                "[analysis]\nrandom_frame_count = 12\n",
                encoding="utf-8",
            )

        result = runner.invoke(
            app,
            [
                "preset",
                operation,
                "demo",
                "--root",
                str(root),
                "--config",
                "config/config.toml",
            ],
        )

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert result.stdout == ""
        assert "Extra inputs are not permitted" in result.stderr


@pytest.mark.parametrize("operation", ["apply", "save"])
def test_preset_config_writes_preserve_external_generated_root(
    operation: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = root / "config" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            MINIMAL_CONFIG.replace('generated_dir = "generated"', 'generated_dir = "../../out"'),
            encoding="utf-8",
        )
        if operation == "apply":
            (root / "config" / "presets").mkdir(parents=True, exist_ok=True)
            (root / "config" / "presets" / "demo.toml").write_text(
                "[analysis]\nrandom_frame_count = 10\n",
                encoding="utf-8",
            )
        result = runner.invoke(
            app,
            [
                "preset",
                operation,
                "demo",
                "--root",
                str(root),
                "--config",
                "config/config.toml",
            ],
        )

        assert result.exit_code == 0
        persisted_path = (
            config_path if operation == "apply" else root / "config" / "presets" / "demo.toml"
        )
        persisted = tomllib.loads(persisted_path.read_text(encoding="utf-8"))
        assert persisted["paths"]["generated_dir"] == "../../out"


def test_preset_apply_preserves_external_generated_root_added_by_preset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = _write_minimal_config(root)
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "escape.toml").write_text(
            '[paths]\ngenerated_dir = "../../out"\n',
            encoding="utf-8",
        )

        result = runner.invoke(
            app,
            [
                "preset",
                "apply",
                "escape",
                "--root",
                str(root),
                "--config",
                "config/config.toml",
            ],
        )

        assert result.exit_code == 0
        persisted = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert persisted["paths"]["generated_dir"] == "../../out"


def test_preset_list_prints_names_sorted_case_insensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
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


def test_preset_list_uses_root_presets_even_when_config_path_is_nondefault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
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


def test_preset_list_error_uses_default_terminal_color_policy(
    monkeypatch: MonkeyPatch,
) -> None:
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

    monkeypatch.setattr(
        "frame_compare.cli.entry.list_presets",
        lambda *, presets_dir: (_ for _ in ()).throw(ConfigNotFoundError(Path("missing.toml"))),
    )
    monkeypatch.setattr("frame_compare.cli.entry.handle_error", _handle_error)

    result = runner.invoke(app, ["preset", "list"])

    assert result.exit_code == int(ExitCode.CONFIG_ERROR)
    assert captured == {
        "no_color": False,
        "verbose": False,
        "verbose_hint": None,
    }


def test_preset_save_respects_root_and_config_writes_secret_safe_preset(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "FRAME_COMPARE_SLOWPICS__WEBHOOK_URL",
        "https://discord.com/api/webhooks/env-id/env-secret",
    )
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "sentinel-tmdb-api-key")
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            MINIMAL_CONFIG
            + '\n[slowpics]\nwebhook_url = "https://discord.com/api/webhooks/id/file-secret"\n'
            + '\n[tmdb]\napi_key = "sentinel-tmdb-api-key"\n'
        )

        result = runner.invoke(
            app,
            ["preset", "save", "sample", "--root", str(root), "--config", "configs/config.toml"],
        )
        assert result.exit_code == 0
        preset_path = root / "config" / "presets" / "sample.toml"
        assert preset_path.exists()
        assert f"Saved preset 'sample' to {preset_path.resolve()}" in result.stderr
        preset_text = preset_path.read_text(encoding="utf-8")
        assert "webhook_url" not in preset_text
        assert "env-secret" not in preset_text
        assert "file-secret" not in preset_text
        assert "sentinel-tmdb-api-key" not in preset_text
        assert "sentinel-tmdb-api-key" not in result.stdout + result.stderr


def test_preset_save_write_error_uses_cli_error_contract(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    def _write_text_atomic(_path: Path, _content: str, *, encoding: str = "utf-8") -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr("frame_compare.config.presets.write_text_atomic", _write_text_atomic)

    with isolated_cli_filesystem(tmp_path, monkeypatch):
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


def test_preset_apply_updates_config_and_strips_webhook_secret(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(
        "FRAME_COMPARE_SLOWPICS__WEBHOOK_URL",
        "https://discord.com/api/webhooks/env-id/env-secret",
    )
    monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "sentinel-tmdb-api-key")
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root = Path("workspace")
        config_path = root / "configs" / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            MINIMAL_CONFIG
            + '\n[slowpics]\nwebhook_url = "https://discord.com/api/webhooks/id/file-secret"\n'
            + '\n[tmdb]\napi_key = "sentinel-tmdb-api-key"\n'
        )
        presets_dir = root / "config" / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / "boost.toml").write_text(
            "[analysis]\nrandom_frame_count = 22\n",
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
        assert data["analysis"]["random_frame_count"] == 22
        assert "webhook_url" not in data["slowpics"]
        assert "api_key" not in data["tmdb"]
        config_text = config_path.read_text(encoding="utf-8")
        assert "env-secret" not in config_text
        assert "file-secret" not in config_text
        assert "sentinel-tmdb-api-key" not in config_text
        assert "sentinel-tmdb-api-key" not in result.stdout + result.stderr
