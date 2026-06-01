from click import Group
from typer.main import get_command

from frame_compare.cli.entry import app

from .cli_helpers import _normalize_cli_output, runner

UNSUPPORTED_SLOWPICS_RUN_FLAGS = (
    "--slowpics-auto-upload",
    "--auto-upload",
    "--visibility",
    "--slowpics-visibility",
    "--delete-after-upload",
    "--confirm-upload",
    "--confirm-upload-after-report",
    "--remove-after",
    "--collection-name",
    "--collection-suffix",
    "--image-format",
    "--optimize-images",
    "--tags",
    "--hentai",
    "--copy-url",
    "--open-slowpics",
    "--create-shortcut",
    "--webhook",
    "--webhook-url",
)


def _declared_run_options() -> set[str]:
    command = get_command(app)
    assert isinstance(command, Group)
    run_command = command.commands["run"]
    return {
        opt
        for param in run_command.params
        for opt in (*getattr(param, "opts", ()), *getattr(param, "secondary_opts", ()))
    }


def test_run_declares_no_slowpics_flags_except_no_upload() -> None:
    declared_options = _declared_run_options()

    assert "--no-upload" in declared_options
    assert all(flag not in declared_options for flag in UNSUPPORTED_SLOWPICS_RUN_FLAGS)

    slowpics_related = {
        flag
        for flag in declared_options
        if (
            "slowpics" in flag
            or "slow-pics" in flag
            or "upload" in flag
            or "visibility" in flag
            or "remove" in flag
            or "delete" in flag
            or "webhook" in flag
        )
    }
    assert slowpics_related == {"--no-upload"}


def test_run_rejects_unsupported_slowpics_flags() -> None:
    for flag in UNSUPPORTED_SLOWPICS_RUN_FLAGS:
        result = runner.invoke(
            app,
            ["run", flag, "value"],
            color=False,
            terminal_width=200,
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )
        output = _normalize_cli_output(result.stderr or result.stdout)
        assert result.exit_code == 2, flag
        assert "No such option" in output, flag
