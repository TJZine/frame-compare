"""Keep local collection names out of the published example inputs."""

import re
from pathlib import Path, PureWindowsPath

import pytest

from tests.public_media_examples import EGRET, EPISODE, HERON, OWL

_MEDIA_EXTENSION = r"(?:mkv|mp4|avi|m2ts|ts)"


def test_first_comparison_uses_public_capture_names(repo_root: Path) -> None:
    guide = (repo_root / "docs/getting-started/first-comparison.md").read_text(encoding="utf-8")
    output = "\n".join(re.findall(r"^```[^\n]*\.fc-output\b[^\n]*\n(.*?)^```", guide, re.M | re.S))
    filenames = set(re.findall(rf"[^\s,]+\.{_MEDIA_EXTENSION}\b", output, re.IGNORECASE))
    if filenames != {OWL, HERON, EGRET}:
        pytest.fail(
            "Capture the CLI examples using the releases in tests/public_media_examples.py.",
            pytrace=False,
        )

    folders = set(re.findall(r"\bgenerated[/\\]([^/\\\n]+)[/\\]", output))
    if folders != {f"{EPISODE.replace('.', ' ')} - OwL, HERON, EGRET"}:
        pytest.fail("Capture generated paths using the same fictional releases.", pytrace=False)


def test_benchmark_preparation_uses_role_named_inputs(repo_root: Path) -> None:
    guide = (repo_root / "docs/analysis-performance-validation.md").read_text(encoding="utf-8")
    commands = "\n".join(re.findall(r"^```powershell\b[^\n]*\n(.*?)^```", guide, re.M | re.S))
    inputs = {
        PureWindowsPath(path)
        for _, path in re.findall(rf"""(['"])([^'"\n]+\.{_MEDIA_EXTENSION})\1""", commands, re.I)
    }
    expected = {
        PureWindowsPath("comparison_videos", f"{case}-{role}.mkv")
        for case in ("hdr-film", "animation")
        for role in ("reference", "comparison")
    }
    if inputs != expected:
        pytest.fail(
            "Use the hdr-film and animation reference/comparison input aliases in benchmark commands.",
            pytrace=False,
        )
