from __future__ import annotations

import re
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


def dockerfile_stages(dockerfile: str) -> list[tuple[str, str, str]]:
    matches = list(
        re.finditer(
            r"^FROM\s+(?P<base>\S+)\s+AS\s+(?P<name>\S+)\s*$",
            dockerfile,
            re.MULTILINE,
        )
    )
    return [
        (
            match.group("base"),
            match.group("name"),
            dockerfile[
                match.end() : matches[index + 1].start() if index + 1 < len(matches) else None
            ],
        )
        for index, match in enumerate(matches)
    ]
