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


def assert_release_asset_name_hardening(workflow: str) -> None:
    assert re.search(
        r"- name: Resolve release asset names[\s\S]*?env:\s*\n\s+RELEASE_TAG:\s+\$\{\{\s*github\.event\.release\.tag_name\s*\}\}"
        r"[\s\S]*?asset_tag=\"\$\{RELEASE_TAG//\\//-\}\"",
        workflow,
    )
    assert re.search(
        r"- name: Prepare versioned release asset[\s\S]*?env:\s*\n\s+ASSET_TAG:\s+\$\{\{\s*steps\.release_names\.outputs\.asset_tag\s*\}\}"
        r"[\s\S]*?frame-compare-portable-win-x64-\$\{ASSET_TAG\}\.zip",
        workflow,
    )
    assert re.search(
        r"- name: Prepare versioned signed update asset[\s\S]*?env:\s*\n\s+ASSET_TAG:\s+\$\{\{\s*steps\.release_names\.outputs\.asset_tag\s*\}\}"
        r"[\s\S]*?frame-compare-update-win-x64-\$\{ASSET_TAG\}\.zip",
        workflow,
    )
    assert 'tag="${{ github.event.release.tag_name }}"' not in workflow
    assert 'asset_tag="${{ steps.release_names.outputs.asset_tag }}"' not in workflow
