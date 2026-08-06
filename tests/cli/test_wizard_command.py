# pyright: reportUnusedFunction=false

from __future__ import annotations

import tomllib
from datetime import UTC, date, datetime, time
from pathlib import Path

import pytest
import typer
from pytest import MonkeyPatch

from frame_compare.cli.entry import app
from frame_compare.cli.errors import ExitCode
from frame_compare.cli.wizard_command import write_wizard_config_payload
from frame_compare.config.errors import ConfigWriteError
from frame_compare.config.loader import TomlPayload, load_config
from frame_compare.orchestration.errors import InputDiscoveryError
from frame_compare.orchestration.preflight import resolve_paths

from .cli_helpers import isolated_cli_filesystem, runner


@pytest.fixture(autouse=True)
def _interactive_terminal(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("frame_compare.cli.entry._sys_stream_isatty", lambda _name: True)


def _workspace() -> tuple[Path, Path]:
    root = Path("workspace")
    input_dir = root / "comparison_videos"
    input_dir.mkdir(parents=True)
    return root, root / "config" / "config.toml"


def _invoke(root: Path, input_text: str, *extra: str, env: dict[str, str] | None = None):
    return runner.invoke(
        app,
        ["wizard", "--root", str(root), *extra],
        input=input_text,
        env=env,
    )


def test_first_use_writes_random_goal_minimal_payload_and_honest_privacy_copy(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        monkeypatch.setenv("FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD", "true")

        result = _invoke(root, "\n\n\ny\n")

        assert result.exit_code == 0
        assert (
            result.stdout.index("Input directory")
            < result.stdout.index("Generated data location")
            < result.stdout.index("What do you want to compare?")
        )
        assert "durable comparison folders and reusable caches" in result.stdout
        assert "10 deterministic random frames using the configured seed" in result.stdout
        assert "file default disabled; environment may override at run time" in result.stdout
        assert "Configuration written" in result.stderr
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload == {
            "paths": {"input_dir": "comparison_videos", "generated_dir": "generated"},
            "analysis": {
                "user_frames": [],
                "random_frame_count": 10,
                "dark_frame_count": 0,
                "bright_frame_count": 0,
                "motion_frame_count": 0,
            },
            "slowpics": {"auto_upload": False},
        }
        assert load_config(config_path=config_path).slowpics.auto_upload is True


def test_first_use_one_file_retries_menus_without_reporting_automatic_as_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        (root / "comparison_videos" / "Only.mkv").touch()

        result = _invoke(root, "\n\n0\n1\n9\n1\ny\n")

        assert result.exit_code == 0
        assert "Found 1 video file: Only.mkv" in result.stdout
        assert result.stdout.count("Invalid selection. Choose one of the listed numbers.") == 2
        assert "Reference: automatic -> automatic" not in result.stdout
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert "sources" not in payload


@pytest.mark.parametrize("generated_value", ["persistent-generated", "../review-output"])
def test_first_use_persists_authored_relative_generated_directory(
    generated_value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()

        result = _invoke(root, f"\n{generated_value}\n\ny\n")

        assert result.exit_code == 0
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["paths"]["generated_dir"] == generated_value
        assert "Generated data location:" in result.stdout


def test_wizard_persists_authored_absolute_generated_directory_without_creating_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        external = (Path("outside") / "persistent-generated").resolve()

        result = _invoke(root, f"\n{external}\n\ny\n")

        assert result.exit_code == 0
        assert not external.exists()
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["paths"]["generated_dir"] == str(external)
        assert resolve_paths(load_config(config_path=config_path), root).generated_root == external


def test_existing_config_edit_persists_authored_generated_directory_and_reviews_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        config_path.write_text(
            '[paths]\ninput_dir = "comparison_videos"\ngenerated_dir = "generated"\n',
            encoding="utf-8",
        )

        result = _invoke(root, "\nexternal-review\n\ny\n")

        assert result.exit_code == 0
        assert "Generated data location: generated -> external-review" in result.stdout
        assert (
            tomllib.loads(config_path.read_text(encoding="utf-8"))["paths"]["generated_dir"]
            == "external-review"
        )


def test_missing_generated_directory_is_not_probed_or_created(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        external = (Path("missing") / "generated").resolve()
        original_exists = Path.exists
        probed: list[Path] = []

        def _exists(path: Path) -> bool:
            if path == external:
                probed.append(path)
            return original_exists(path)

        monkeypatch.setattr(Path, "exists", _exists)
        result = _invoke(root, f"\n{external}\n\ny\n")

        assert result.exit_code == 0
        assert probed == []
        assert not original_exists(external)
        assert tomllib.loads(config_path.read_text(encoding="utf-8"))["paths"][
            "generated_dir"
        ] == str(external)


def test_wizard_accepts_environment_expanded_generated_value_and_preserves_authored_text(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        external = (Path("outside") / "env-generated").resolve()
        monkeypatch.setenv("GENERATED_SENTINEL", str(external))

        result = _invoke(root, "\n$GENERATED_SENTINEL\n\ny\n")

        assert result.exit_code == 0
        assert not external.exists()
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["paths"]["generated_dir"] == "$GENERATED_SENTINEL"


def test_eof_at_generated_location_prompt_preserves_existing_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        original = b'[paths]\ninput_dir = "comparison_videos"\ngenerated_dir = "generated"\n'
        config_path.write_bytes(original)

        result = _invoke(root, "\n")

        assert result.exit_code == int(ExitCode.INTERRUPTED)
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert config_path.read_bytes() == original


def test_first_use_multiple_files_uses_canonical_order_and_coverage_patch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        input_dir = root / "comparison_videos"
        for name in ("b.MKV", "A.mkv", "c.MKV"):
            (input_dir / name).touch()

        result = _invoke(root, "\n\n4\n2\ny\n")

        assert result.exit_code == 0
        assert "Found 3 video files: A.mkv, b.MKV, c.MKV" in result.stdout
        assert "Automatic (first discovered: A.mkv)" in result.stdout
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["sources"]["reference"] == "c.MKV"
        assert payload["analysis"] == {
            "user_frames": [],
            "random_frame_count": 4,
            "dark_frame_count": 2,
            "bright_frame_count": 2,
            "motion_frame_count": 2,
            "performance_mode": "quality",
        }
        assert "scans full-resolution luma" in result.stdout
        assert "Metric scan: quality" in result.stdout


def test_existing_config_preserves_raw_values_but_strips_generated_secrets(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        config_path.write_text(
            """\
title = "unknown root"
day = 2026-07-14
clock = 01:02:03
stamp = 2026-07-14T01:02:03Z

[paths]
input_dir = "comparison_videos"

[analysis]
random_frame_count = 7
random_seed = 99
performance_mode = "performance"

[slowpics]
title = ""
webhook_url = "https://secret.invalid/token"

[tmdb]
api_key = "sentinel-secret"

[unknown.nested]
empty = ""

[[unknown.items]]
name = "first"
""",
            encoding="utf-8",
        )
        monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "environment-only-secret")

        result = _invoke(root, "\n\n1\ny\n")

        assert result.exit_code == 0
        combined = result.stdout + result.stderr
        for secret in ("sentinel-secret", "secret.invalid", "environment-only-secret"):
            assert secret not in combined
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["title"] == "unknown root"
        assert payload["day"] == date(2026, 7, 14)
        assert payload["clock"] == time(1, 2, 3)
        assert payload["stamp"] == datetime(2026, 7, 14, 1, 2, 3, tzinfo=UTC)
        assert payload["unknown"] == {"nested": {"empty": ""}, "items": [{"name": "first"}]}
        assert "api_key" not in payload["tmdb"]
        assert "webhook_url" not in payload["slowpics"]
        assert "environment-only-secret" not in config_path.read_text(encoding="utf-8")
        assert payload["analysis"]["random_seed"] == 99
        assert payload["analysis"]["performance_mode"] == "performance"
        assert "Publishing settings: preserved except webhook URL" in result.stdout
        assert "Webhook URL: removed from generated configuration" in result.stdout
        assert "TMDB API key: removed from generated configuration" in result.stdout


def test_existing_config_ignores_environment_only_values_during_review(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        config_path.write_text(
            '[paths]\ninput_dir = "comparison_videos"\n',
            encoding="utf-8",
        )
        monkeypatch.setenv("FRAME_COMPARE_ANALYSIS__RANDOM_FRAME_COUNT", "77")
        monkeypatch.setenv("FRAME_COMPARE_TMDB__API_KEY", "environment-only-secret")
        monkeypatch.setenv("FRAME_COMPARE_SLOWPICS__AUTO_UPLOAD", "true")

        result = _invoke(root, "\n\n3\n0\ny\n")

        assert result.exit_code == 0
        combined = result.stdout + result.stderr
        assert "Frame selection: 10 random -> frames 0" in result.stdout
        assert "77 random" not in combined
        assert "environment-only-secret" not in combined
        persisted = config_path.read_text(encoding="utf-8")
        assert "environment-only-secret" not in persisted
        assert "auto_upload" not in persisted


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ("", "empty entries"),
        ("1,,2", "empty entries"),
        ("-1", "non-negative"),
        ("1.5", "base-10"),
        ("1,1", "duplicates"),
        (",".join(str(value) for value in range(101)), "between 1 and 100"),
    ],
)
def test_specific_frames_retry_then_sort_without_probing(
    invalid: str, message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()

        result = _invoke(root, f"\n\n3\n{invalid}\n+24, 0,120\ny\n")

        assert result.exit_code == 0
        assert message in result.stdout
        assert "Frame availability is checked when the comparison runs." in result.stdout
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["analysis"]["user_frames"] == [0, 24, 120]
        assert payload["analysis"]["random_frame_count"] == 0
        assert payload["analysis"]["dark_frame_count"] == 0
        assert payload["analysis"]["bright_frame_count"] == 0
        assert payload["analysis"]["motion_frame_count"] == 0


def test_specific_frames_accepts_100_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        frames = ",".join(str(value) for value in reversed(range(100)))

        result = _invoke(root, f"\n\n3\n{frames}\ny\n")

        assert result.exit_code == 0
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert payload["analysis"]["user_frames"] == list(range(100))


def test_existing_keep_is_true_noop_without_confirmation_or_write(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        original = (
            b'[paths]\ninput_dir = "comparison_videos"\n\n[analysis]\nrandom_frame_count = 9\n'
            b'\n[slowpics]\nwebhook_url = "https://secret.invalid/token"\n'
        )
        config_path.write_bytes(original)
        monkeypatch.setattr(
            "frame_compare.cli.entry._write_wizard_config_payload",
            lambda *_args, **_kwargs: pytest.fail("no-op must not write"),
        )

        result = _invoke(root, "\n\n\n")

        assert result.exit_code == 0
        assert "Write these changes?" not in result.stdout
        assert "No configuration changes. Configuration was not written." in result.stderr
        assert config_path.read_bytes() == original


def test_final_no_preserves_existing_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        original = b'[paths]\ninput_dir = "comparison_videos"\n'
        config_path.write_bytes(original)

        result = _invoke(root, "\n\n1\nn\n")

        assert result.exit_code == 0
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert config_path.read_bytes() == original


def test_atomic_config_write_failure_preserves_existing_bytes(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        original = b'[paths]\ninput_dir = "comparison_videos"\ngenerated_dir = "generated"\n'
        config_path.write_bytes(original)

        def _failure(path: Path, _data: TomlPayload) -> None:
            raise ConfigWriteError(
                path, label="configuration file", cause=PermissionError("denied")
            )

        monkeypatch.setattr("frame_compare.cli.entry._write_wizard_config_payload", _failure)
        result = _invoke(root, "\nnew-generated\n\ny\n")

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert "FC-1007" in result.stderr
        assert config_path.read_bytes() == original


@pytest.mark.parametrize("input_text", ["", "\n", "\n\n", "\n\n3\n", "\n\n3\n0,1\n"])
def test_eof_at_each_prompt_boundary_exits_130_without_write(
    input_text: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()

        result = _invoke(root, input_text)

        assert result.exit_code == int(ExitCode.INTERRUPTED)
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert not config_path.exists()


def test_typer_abort_uses_exact_cancellation_contract(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.entry._prompt_input_dir",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(typer.Abort()),
    )
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()

        result = _invoke(root, "")

        assert result.exit_code == int(ExitCode.INTERRUPTED)
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert not config_path.exists()


def test_typer_abort_at_generated_location_uses_exact_cancellation_contract(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.entry._prompt_generated_dir",
        lambda *_args: (_ for _ in ()).throw(typer.Abort()),
    )
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()

        result = _invoke(root, "\n")

        assert result.exit_code == int(ExitCode.INTERRUPTED)
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert not config_path.exists()


def test_keyboard_interrupt_uses_exact_cancellation_contract(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    def _interrupt(*_args: object, **_kwargs: object) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("frame_compare.cli.entry._prompt_input_dir", _interrupt)
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()

        result = _invoke(root, "")

        assert result.exit_code == int(ExitCode.INTERRUPTED)
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert not config_path.exists()


def test_eof_at_reference_prompt_exits_130_without_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        (root / "comparison_videos" / "clip.mkv").touch()

        result = _invoke(root, "\n\n")

        assert result.exit_code == int(ExitCode.INTERRUPTED)
        assert result.stderr == "Canceled; configuration unchanged.\n"
        assert not config_path.exists()


@pytest.mark.parametrize(
    ("stdin_tty", "stdout_tty"), [(False, False), (False, True), (True, False)]
)
def test_noninteractive_matrix_fails_before_config_read_or_prompt(
    monkeypatch: MonkeyPatch,
    stdin_tty: bool,
    stdout_tty: bool,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "frame_compare.cli.entry._sys_stream_isatty",
        lambda name: stdin_tty if name == "stdin" else stdout_tty,
    )
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        config_path.write_text("secret = [", encoding="utf-8")

        result = _invoke(root, "", env={"NO_COLOR": "1"})

        assert result.exit_code == int(ExitCode.INPUT_ERROR)
        assert result.stdout == ""
        assert "[FC-3017]" in result.stderr
        assert "Wizard requires an interactive terminal." in result.stderr
        assert "edit the selected TOML file directly" in " ".join(result.stderr.split())
        assert "--verbose" not in result.stderr
        assert "secret" not in result.stderr
        assert "\x1b" not in result.stderr


def test_external_config_is_rejected_before_tty_check_or_prompt(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("frame_compare.cli.entry._sys_stream_isatty", lambda _name: False)
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, _ = _workspace()
        external_config = (Path("outside") / "config.toml").resolve()

        result = _invoke(root, "", "--config", str(external_config))

        assert result.exit_code == int(ExitCode.INPUT_ERROR)
        assert result.stdout == ""
        assert "FC-3009" in result.stderr
        assert "FC-3017" not in result.stderr


def test_invalid_existing_secret_is_redacted_before_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        config_path.write_text(
            '[slowpics]\ntitle_template = "${do-not-leak-this}"\n',
            encoding="utf-8",
        )

        result = _invoke(root, "")

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert result.stdout == ""
        assert "FC-1003" in result.stderr
        assert "<redacted>" in result.stderr
        assert "do-not-leak-this" not in result.stderr


def test_invalid_utf8_existing_config_uses_typed_parse_error_and_preserves_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        original = b'[paths]\ninput_dir = "comparison_videos"\n\xff'
        config_path.write_bytes(original)

        result = _invoke(root, "")

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert result.stdout == ""
        assert "FC-1002" in result.stderr
        assert "not valid UTF-8" in result.stderr
        assert config_path.read_bytes() == original


def test_existing_environment_expanded_input_is_validated_without_rewriting(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        external = Path("external-media").resolve()
        external.mkdir()
        monkeypatch.setenv("MEDIA_SENTINEL", str(external))
        config_path.parent.mkdir()
        original = b'[paths]\ninput_dir = "$MEDIA_SENTINEL"\n'
        config_path.write_bytes(original)

        result = _invoke(root, "\n\n\n")

        assert result.exit_code == 0
        assert "does not exist or is not a directory" not in result.stdout
        assert "No configuration changes. Configuration was not written." in result.stderr
        assert config_path.read_bytes() == original


def test_invalid_existing_contained_path_fails_before_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        config_path.write_text(
            '[paths]\ninput_dir = "comparison_videos"\nconfig_dir = "../escape"\n',
            encoding="utf-8",
        )

        result = _invoke(root, "")

        assert result.exit_code == int(ExitCode.INPUT_ERROR)
        assert result.stdout == ""
        assert "FC-3009" in result.stderr


@pytest.mark.parametrize("generated_value", ["/", "C:\\", "\\\\server\\share"])
def test_generated_filesystem_roots_are_rejected_without_replacing_existing_config(
    generated_value: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        config_path.parent.mkdir()
        original = b'[paths]\ninput_dir = "comparison_videos"\ngenerated_dir = "generated"\n'
        config_path.write_bytes(original)

        result = _invoke(root, f"\n{generated_value}\n\n")

        assert result.exit_code == int(ExitCode.CONFIG_ERROR)
        assert "FC-1003" in result.stderr
        assert "dedicated directory" in result.stderr
        assert config_path.read_bytes() == original


def test_automatic_reference_removes_existing_explicit_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        (root / "comparison_videos" / "clip.mkv").touch()
        config_path.parent.mkdir()
        config_path.write_text(
            '[paths]\ninput_dir = "comparison_videos"\n[sources]\nreference = "clip.mkv"\n',
            encoding="utf-8",
        )

        result = _invoke(root, "\n\n2\n\ny\n")

        assert result.exit_code == 0
        payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
        assert "reference" not in payload["sources"]
        assert "Reference: clip.mkv -> automatic" in result.stdout


def test_exact_windows_portable_config_exception_is_preserved(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, _ = _workspace()
        portable_config = (Path("portable-state") / "config.toml").resolve()
        monkeypatch.setattr(
            "frame_compare.orchestration.preflight._windows_portable_state_config_path",
            lambda: portable_config,
        )

        result = _invoke(root, "\n\n\ny\n", "--config", str(portable_config))

        assert result.exit_code == 0
        assert portable_config.exists()
        assert "Configuration written" in result.stderr


def test_duplicate_stems_fail_before_reference_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        (root / "comparison_videos" / "clip.mkv").touch()
        (root / "comparison_videos" / "clip.mp4").touch()

        result = _invoke(root, "\n\n")

        assert result.exit_code == int(ExitCode.INPUT_ERROR)
        assert "FC-3013" in result.stderr
        assert "Reference:" not in result.stdout
        assert not config_path.exists()


def test_stale_reference_keep_warns_in_menu_and_review(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        (root / "comparison_videos" / "present.mkv").touch()
        config_path.parent.mkdir()
        config_path.write_text(
            '[paths]\ninput_dir = "comparison_videos"\n[sources]\nreference = "gone.mkv"\n',
            encoding="utf-8",
        )

        result = _invoke(root, "\n\n\n1\nn\n")

        assert result.exit_code == 0
        assert result.stdout.count("Current reference does not match the discovered files") == 2
        assert config_path.read_text(encoding="utf-8").endswith('reference = "gone.mkv"\n')


def test_external_input_is_allowed_and_discovery_error_is_typed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    with isolated_cli_filesystem(tmp_path, monkeypatch):
        root, config_path = _workspace()
        external = Path("external").resolve()
        external.mkdir()

        result = _invoke(root, f"{external}\n\n\ny\n")
        assert result.exit_code == 0
        assert tomllib.loads(config_path.read_text(encoding="utf-8"))["paths"]["input_dir"] == str(
            external
        )

        monkeypatch.setattr(
            "frame_compare.cli.wizard_command.discover_inputs",
            lambda _path: (_ for _ in ()).throw(InputDiscoveryError(external, OSError("denied"))),
        )
        config_path.unlink()
        failed = _invoke(root, f"{external}\n\n")
        assert failed.exit_code == int(ExitCode.INPUT_ERROR)
        assert "FC-3010" in failed.stderr
        assert not config_path.exists()


def test_writer_serializes_raw_toml_once_and_maps_failure(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    destination = tmp_path / "config.toml"
    calls: list[str] = []
    payload: TomlPayload = {
        "unknown": {"empty": ""},
        "slowpics": {"webhook_url": "https://secret.invalid/token"},
        "tmdb": {"api_key": "sentinel-secret"},
    }

    def _writer(path: Path, content: str, *, encoding: str) -> None:
        assert path == destination
        assert encoding == "utf-8"
        calls.append(content)

    write_wizard_config_payload(destination, payload, text_writer=_writer)
    assert len(calls) == 1
    assert tomllib.loads(calls[0]) == {
        "unknown": {"empty": ""},
        "slowpics": {},
        "tmdb": {},
    }
    assert payload["slowpics"] == {"webhook_url": "https://secret.invalid/token"}
    assert payload["tmdb"] == {"api_key": "sentinel-secret"}
    assert "sentinel-secret" not in calls[0]

    def _failure(path: Path, content: str, *, encoding: str) -> None:
        del path, content, encoding
        raise PermissionError("denied")

    with pytest.raises(ConfigWriteError, match="Failed to write configuration file"):
        write_wizard_config_payload(destination, payload, text_writer=_failure)

    def _serialization_failure(_payload: TomlPayload) -> str:
        raise TypeError("sentinel serialization detail")

    monkeypatch.setattr("frame_compare.cli.wizard_command.tomli_w.dumps", _serialization_failure)
    with pytest.raises(ConfigWriteError, match="Failed to write configuration file") as exc_info:
        write_wizard_config_payload(destination, payload, text_writer=_writer)
    safe_error = str(exc_info.value.context.to_dict())
    assert "sentinel serialization detail" not in safe_error
    assert "sentinel-secret" not in safe_error
    assert len(calls) == 1
