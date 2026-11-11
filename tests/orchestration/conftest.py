"""Bounded header facts for orchestration's synthetic media fixtures."""

from pathlib import Path

import pytest

import frame_compare.vs.source_admission as admission


@pytest.fixture(autouse=True)
def synthetic_probe_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    if any(request.node.get_closest_marker(marker) for marker in ("integration", "vs_required")):
        return
    executable = tmp_path / "fixture-ffprobe"

    def resolve_probe(_name: str) -> str:
        if not executable.exists():
            executable.write_bytes(b"synthetic probe runtime")
        return str(executable)

    monkeypatch.setattr(admission, "resolve_optional_executable", resolve_probe)
    monkeypatch.setattr(
        admission,
        "probe_admission_headers",
        lambda *_args, **_kwargs: (
            [
                {
                    "index": 0,
                    "width": 1920,
                    "height": 1080,
                    "coded_width": 1920,
                    "coded_height": 1080,
                }
            ],
            {
                "format": {"format_name": "matroska,webm"},
                "program_version": {"version": "fixture"},
                "library_versions": [{"name": "fixture", "version": 1}],
            },
        ),
    )
