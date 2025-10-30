from __future__ import annotations

import json
from pathlib import Path

from src.analysis import SelectionDetail
from src.datatypes import ReportConfig
from src.report import generate_html_report


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def test_generate_html_report(tmp_path: Path) -> None:
    screens_dir = tmp_path / "screens"
    plan_a_file = screens_dir / "10 - Encode A.png"
    plan_b_file = screens_dir / "10 - Encode B.png"
    plan_a_second = screens_dir / "20 - Encode A.png"
    plan_b_second = screens_dir / "20 - Encode B.png"

    for file in (plan_a_file, plan_b_file, plan_a_second, plan_b_second):
        _touch(file)

    frames = [10, 20]
    selection_details = {
        10: SelectionDetail(
            frame_index=10,
            label="Bright",
            score=0.42,
            source="auto",
            timecode="00:00:10",
            clip_role=None,
            notes=None,
        ),
        20: SelectionDetail(
            frame_index=20,
            label="Motion",
            score=0.88,
            source="auto",
            timecode="00:00:20",
            clip_role=None,
            notes="High motion"
        ),
    }

    plans = [
        {
            "label": "Encode A",
            "metadata": {"resolution": "1920x1080", "codec": "h264"},
            "path": screens_dir / "encode-a.mkv",
        },
        {
            "label": "Encode B",
            "metadata": {"resolution": "1920x1080", "codec": "hevc"},
            "path": screens_dir / "encode-b.mkv",
        },
    ]

    cfg = ReportConfig(enable=True)
    report_dir = tmp_path / "report"

    index_path = generate_html_report(
        report_dir=report_dir,
        report_cfg=cfg,
        frames=frames,
        selection_details=selection_details,
        image_paths=[str(plan_a_file), str(plan_b_file), str(plan_a_second), str(plan_b_second)],
        plans=plans,
        metadata_title="Unit Test",
        include_metadata="full",
        slowpics_url="https://slow.pics/example",
    )

    assert index_path.exists()
    data_path = report_dir / "data.json"
    assert data_path.exists()

    with data_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["title"] == "Unit Test"
    assert payload["stats"] == {"frames": 2, "encodes": 2}
    assert payload["encodes"][0]["label"] == "Encode A"
    assert payload["frames"][0]["index"] == 10
    files_entry = payload["frames"][0]["files"]
    labels = {item["encode"] for item in files_entry}
    assert labels == {"Encode A", "Encode B"}
    assert payload["viewer_mode"] == "slider"
