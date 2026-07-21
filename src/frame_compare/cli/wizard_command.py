"""Implementation for the interactive goal-oriented configuration wizard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

import tomli_w
import typer

from frame_compare.cli.errors import ExitCode
from frame_compare.config.errors import ConfigWriteError
from frame_compare.config.loader import (
    TomlPayload,
    get_default_config,
    load_raw_config,
    validate_raw_config_payload,
)
from frame_compare.config.persistence import strip_nonpersistable_config_values
from frame_compare.config.schema import ConfigSchema
from frame_compare.error_categories import InputError
from frame_compare.error_context import ErrorContext
from frame_compare.errors import FrameCompareError
from frame_compare.orchestration.errors import NoVideosFoundError, SourceSelectionError
from frame_compare.orchestration.preflight import (
    discover_inputs,
    resolve_selected_config_path,
    validate_and_normalize_config_paths,
)
from frame_compare.orchestration.source_selection import (
    resolve_source_selection,
    resolve_source_selector,
)

from .cli_helpers import TextWriter
from .wizard_policy import (
    GOAL_MENU_LINES,
    GoalChoice,
    WizardGoal,
    copy_payload,
    coverage_goal,
    keep_goal,
    parse_specific_frames,
    random_goal,
    remove_table_key,
    set_table_values,
    specific_goal,
    table_key,
)

_CANCELED = "Canceled; configuration unchanged."
_STALE_REFERENCE_WARNING = (
    "Current reference does not match the discovered files; a run may fail until the files "
    "or selector change."
)


class ConfirmFn(Protocol):
    def __call__(self, text: str, *, default: bool) -> bool: ...


class PromptFn(Protocol):
    def __call__(self, text: str, *, default: str) -> str: ...


class PromptInputDirFn(Protocol):
    def __call__(self, default: str, *, base_dir: Path) -> str: ...


class WriteWizardPayloadFn(Protocol):
    def __call__(self, config_path: Path, data: TomlPayload) -> None: ...


class HandleErrorFn(Protocol):
    def __call__(
        self,
        error: Exception,
        *,
        no_color: bool,
        verbose: bool,
        verbose_hint: str | None = "--verbose",
    ) -> int: ...


class WizardTerminalRequiredError(InputError):
    """The wizard was started without interactive stdin and stdout (FC-3017)."""

    def __init__(self) -> None:
        super().__init__(
            ErrorContext(
                code="FC-3017",
                name="WIZARD_TERMINAL_REQUIRED",
                message="Wizard requires an interactive terminal.",
                hint=(
                    "Run frame-compare wizard from a terminal; edit the selected TOML file "
                    "directly for automation."
                ),
            )
        )


def handle_wizard(
    root: Path,
    config_path: Path,
    *,
    prompt_input_dir: PromptInputDirFn,
    prompt: PromptFn,
    confirm: ConfirmFn,
    write_payload: WriteWizardPayloadFn,
    handle_error: HandleErrorFn,
    stdin_is_tty: bool,
    stdout_is_tty: bool,
    no_color: bool,
) -> None:
    """Run the approved guided editor and persist only one confirmed candidate."""
    try:
        selected_path = resolve_selected_config_path(config_path, root)
        if not stdin_is_tty or not stdout_is_tty:
            raise WizardTerminalRequiredError

        existing = selected_path.exists()
        if existing:
            document = load_raw_config(selected_path)
            original = document.payload
            current_config = document.config
        else:
            original = {}
            current_config = get_default_config()
        validate_and_normalize_config_paths(current_config, root)

        candidate = copy_payload(original)
        input_value = prompt_input_dir(current_config.paths.input_dir, base_dir=root)
        input_changed = not existing or input_value != current_config.paths.input_dir
        if input_changed:
            set_table_values(candidate, "paths", {"input_dir": input_value})

        input_dir = _resolve_input_dir(input_value, root)
        discovered = _discover_for_wizard(input_dir)
        reference_change, stale_reference = _prompt_reference(
            prompt=prompt,
            input_dir=input_dir,
            discovered=discovered,
            current_config=current_config,
            candidate=candidate,
            existing=existing,
        )

        goal = _prompt_goal(prompt=prompt, current_config=current_config, existing=existing)
        before_goal = copy_payload(candidate)
        if goal.goal != WizardGoal.KEEP:
            set_table_values(candidate, "analysis", goal.analysis_patch)
        frame_changed = candidate != before_goal

        if not existing:
            set_table_values(candidate, "slowpics", {"auto_upload": False})

        if candidate == original:
            typer.echo(
                "No configuration changes. Configuration was not written.",
                err=True,
            )
            return

        strip_nonpersistable_config_values(candidate)
        validated_candidate = validate_raw_config_payload(candidate, redact_inputs=True)
        validate_and_normalize_config_paths(validated_candidate, root)
        _print_review(
            config_path=selected_path,
            existing=existing,
            original=original,
            old_config=current_config,
            new_config=validated_candidate,
            input_changed=input_changed,
            reference_change=reference_change,
            frame_changed=frame_changed,
            goal=goal,
            stale_reference=stale_reference,
        )
        if not confirm("Write these changes?", default=False):
            typer.echo(_CANCELED, err=True)
            return

        write_payload(selected_path, candidate)
        typer.echo(f"Configuration written: {selected_path}", err=True)
    except (KeyboardInterrupt, EOFError, typer.Abort):
        typer.echo(_CANCELED, err=True)
        raise typer.Exit(code=int(ExitCode.INTERRUPTED)) from None
    except FrameCompareError as error:
        raise typer.Exit(
            code=handle_error(
                error,
                no_color=no_color,
                verbose=False,
                verbose_hint=None,
            )
        ) from error


def prompt_input_dir(default: str, *, base_dir: Path) -> str:
    """Prompt for an existing input directory, resolving relative values from root."""
    while True:
        value = typer.prompt("Input directory", default=default)
        path = _resolve_input_dir(value, base_dir)
        if path.exists() and path.is_dir():
            return value
        typer.echo("Input directory does not exist or is not a directory.")


def _resolve_input_dir(value: str, root: Path) -> Path:
    path = Path(os.path.expandvars(value))
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _discover_for_wizard(input_dir: Path) -> list[Path]:
    try:
        discovered = discover_inputs(input_dir)
    except NoVideosFoundError:
        typer.echo("No supported video files found; reference selection is unchanged.")
        return []
    relative_names = [_relative_name(path, input_dir) for path in discovered]
    noun = "file" if len(relative_names) == 1 else "files"
    typer.echo(f"Found {len(relative_names)} video {noun}: {', '.join(relative_names)}")
    return discovered


def _prompt_reference(
    *,
    prompt: PromptFn,
    input_dir: Path,
    discovered: list[Path],
    current_config: ConfigSchema,
    candidate: TomlPayload,
    existing: bool,
) -> tuple[tuple[str, str] | None, bool]:
    if not discovered:
        return None, False

    automatic_sources = current_config.sources.model_copy(update={"reference": None})
    resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=discovered,
        config=automatic_sources,
    )

    current_selector = current_config.sources.reference
    stale_current = existing and _reference_is_stale(
        current_selector=current_selector,
        input_dir=input_dir,
        discovered=discovered,
    )

    names = [_relative_name(path, input_dir) for path in discovered]
    automatic_label = (
        "Automatic" if len(names) == 1 else f"Automatic (first discovered: {names[0]})"
    )
    options: list[tuple[str, str | None]] = []
    if existing:
        display = current_selector or "automatic"
        options.append((f"Keep current: {display}", "keep"))
    options.append((automatic_label, None))
    options.extend((name, name) for name in names)

    typer.echo("Reference:")
    for index, (label, _) in enumerate(options, start=1):
        typer.echo(f"  {index}. {label}")
    if stale_current:
        typer.echo(_STALE_REFERENCE_WARNING)

    selected = _prompt_menu_index(prompt, options_count=len(options), default=1)
    _, selector = options[selected - 1]
    old_display = current_selector or "automatic"
    if selector == "keep":
        return None, stale_current
    if selector is None:
        had_explicit_key = table_key(candidate, "sources", "reference") is not None
        remove_table_key(candidate, "sources", "reference")
        if not existing:
            return None, False
        if existing and not had_explicit_key:
            return None, False
        return (old_display, "automatic"), False

    explicit_sources = current_config.sources.model_copy(update={"reference": selector})
    resolve_source_selection(
        input_dir=input_dir,
        discovered_paths=discovered,
        config=explicit_sources,
    )
    set_table_values(candidate, "sources", {"reference": selector})
    if existing and selector == current_selector:
        return None, False
    return (old_display, selector), False


def _reference_is_stale(
    *,
    current_selector: str | None,
    input_dir: Path,
    discovered: list[Path],
) -> bool:
    if current_selector is None or current_selector == "auto":
        return False
    try:
        resolve_source_selector(
            selector=current_selector,
            input_dir=input_dir,
            paths=discovered,
            role="sources.reference",
        )
    except SourceSelectionError:
        return True
    return False


def _prompt_goal(
    *,
    prompt: PromptFn,
    current_config: ConfigSchema,
    existing: bool,
) -> GoalChoice:
    typer.echo("What do you want to compare?")
    if existing:
        typer.echo("  0. Keep current frame selection")
    for line in GOAL_MENU_LINES:
        typer.echo(f"  {line}")

    allowed = {0, 1, 2, 3} if existing else {1, 2, 3}
    default = "0" if existing else "1"
    while True:
        raw = prompt("Select", default=default).strip()
        try:
            selected = int(raw, 10)
        except ValueError:
            selected = -1
        if selected in allowed:
            break
        typer.echo("Invalid selection. Choose one of the listed numbers.")

    if selected == WizardGoal.KEEP:
        return keep_goal(current_config)
    if selected == WizardGoal.RANDOM:
        return random_goal()
    if selected == WizardGoal.COVERAGE:
        return coverage_goal()

    while True:
        raw_frames = prompt("Frame numbers (comma-separated)", default="").strip()
        try:
            frames = parse_specific_frames(raw_frames)
        except ValueError as error:
            typer.echo(str(error))
            continue
        typer.echo("Frame availability is checked when the comparison runs.")
        return specific_goal(frames)


def _prompt_menu_index(prompt: PromptFn, *, options_count: int, default: int) -> int:
    while True:
        raw = prompt("Select", default=str(default)).strip()
        try:
            selected = int(raw, 10)
        except ValueError:
            selected = 0
        if 1 <= selected <= options_count:
            return selected
        typer.echo("Invalid selection. Choose one of the listed numbers.")


def _print_review(
    *,
    config_path: Path,
    existing: bool,
    original: TomlPayload,
    old_config: ConfigSchema,
    new_config: ConfigSchema,
    input_changed: bool,
    reference_change: tuple[str, str] | None,
    frame_changed: bool,
    goal: GoalChoice,
    stale_reference: bool,
) -> None:
    typer.echo("Review configuration changes")
    typer.echo(f"  Config: {config_path}")
    if input_changed:
        old_input = old_config.paths.input_dir if existing else "<not configured>"
        typer.echo(f"  Input directory: {old_input} -> {new_config.paths.input_dir}")
    if reference_change is not None:
        typer.echo(f"  Reference: {reference_change[0]} -> {reference_change[1]}")
    if frame_changed:
        old_summary = keep_goal(old_config).summary if existing else "<default>"
        typer.echo(f"  Frame selection: {old_summary} -> {goal.summary}")
    typer.echo(f"  Metric scan: {goal.metric_scan}")
    webhook_removed = existing and table_key(original, "slowpics", "webhook_url") is not None
    publishing = (
        "preserved except webhook URL"
        if webhook_removed
        else ("preserved" if existing else "file default disabled")
    )
    typer.echo(f"  Publishing settings: {publishing}; environment may override at run time")
    typer.echo("  Other settings: preserved")
    if webhook_removed:
        typer.echo("  Webhook URL: removed from generated configuration")
    if existing and table_key(original, "tmdb", "api_key") is not None:
        typer.echo("  Other sensitive values: preserved and hidden")
    if stale_reference:
        typer.echo(f"  {_STALE_REFERENCE_WARNING}")


def _relative_name(path: Path, input_dir: Path) -> str:
    try:
        return path.relative_to(input_dir).as_posix()
    except ValueError:
        return path.name


def write_wizard_config_payload(
    config_path: Path,
    data: TomlPayload,
    *,
    text_writer: TextWriter,
) -> None:
    """Serialize one validated raw payload and write through the atomic owner."""
    persisted_data = copy_payload(data)
    strip_nonpersistable_config_values(persisted_data)
    try:
        toml_text = tomli_w.dumps(persisted_data)
    except (TypeError, ValueError) as exc:
        safe_error = OSError("TOML serialization failed")
        raise ConfigWriteError(
            config_path,
            label="configuration file",
            cause=safe_error,
        ) from exc
    try:
        text_writer(config_path, toml_text, encoding="utf-8")
    except OSError as exc:
        raise ConfigWriteError(config_path, label="configuration file", cause=exc) from exc
