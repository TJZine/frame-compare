from __future__ import annotations

import re
from pathlib import Path


def read_text_or_fail(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


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
