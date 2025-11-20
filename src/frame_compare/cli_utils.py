"""Shared CLI helper utilities for frame-compare commands."""

from __future__ import annotations

from typing import Optional, TypeVar, cast

import click
from click.core import ParameterSource

T = TypeVar("T")


def _cli_override_value(ctx: click.Context, name: str, value: T | None) -> T | None:
    """
    Return ``value`` only when the corresponding CLI option originated from the command line.

    Click's ``default_map`` and other implicit sources should defer to config defaults so the
    runtime path mirrors ``frame_compare.run_cli`` unless the user explicitly passes a flag.
    """

    get_source = getattr(ctx, "get_parameter_source", None)
    if get_source is None or not callable(get_source):
        return value
    source = cast(Optional[ParameterSource], get_source(name))
    if source is ParameterSource.COMMANDLINE:
        return value
    return None


def _cli_flag_value(ctx: click.Context, name: str, value: bool, *, default: bool) -> bool:
    """
    Return the flag value only when the user explicitly passed the option.

    Click's ``default_map`` and env-provided values should not override config-driven defaults.
    """

    override = _cli_override_value(ctx, name, value)
    if override is None:
        return default
    return bool(override)


__all__ = ["_cli_override_value", "_cli_flag_value"]
