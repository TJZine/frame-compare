from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml


def read_text_or_fail(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def load_workflow(path: Path) -> dict[str, Any]:
    parsed = yaml.load(read_text_or_fail(path), Loader=yaml.BaseLoader)
    assert isinstance(parsed, dict), f"Workflow must be a mapping: {path}"
    return cast(dict[str, Any], parsed)


def step_by_name(job: dict[str, Any], name: str) -> dict[str, Any]:
    matches = [step for step in job["steps"] if step["name"] == name]
    assert len(matches) == 1, f"Expected exactly one workflow step named {name!r}"
    return cast(dict[str, Any], matches[0])
