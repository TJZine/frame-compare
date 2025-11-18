from __future__ import annotations

import json
from pathlib import Path

from src.datatypes import ReportConfig
from src.frame_compare.analysis import SelectionDetail
from src.frame_compare.render.naming import SAFE_LABEL_META_KEY
from src.frame_compare.report import generate_html_report


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
    assert payload["frames"][0]["thumbnail"] == "../screens/10 - Encode A.png"
    assert payload["frames"][0]["category"] == "Bright"
    assert payload["frames"][0]["category_key"] == "bright"
    assert payload["frames"][1]["category"] == "Motion"
    assert payload["frames"][1]["category_key"] == "motion"
    assert payload["categories"] == [
        {"key": "bright", "label": "Bright", "count": 1},
        {"key": "motion", "label": "Motion", "count": 1},
    ]
    assert payload["viewer_mode"] == "slider"


def test_generate_html_report_retains_duplicate_labels(tmp_path: Path) -> None:
    screens_dir = tmp_path / "screens"
    first = screens_dir / "5 - Dolby_Vision.png"
    second = screens_dir / "5 - Dolby_Vision_2.png"
    for file in (first, second):
        _touch(file)

    frames = [5]
    selection_details = {
        5: SelectionDetail(
            frame_index=5,
            label="Motion",
            score=0.3,
            source="auto",
            timecode=None,
            clip_role=None,
            notes=None,
        )
    }

    plans = [
        {
            "label": "Dolby Vision",
            "metadata": {SAFE_LABEL_META_KEY: "Dolby_Vision"},
            "path": screens_dir / "dolby-v.mkv",
        },
        {
            "label": "Dolby-Vision",
            "metadata": {SAFE_LABEL_META_KEY: "Dolby_Vision_2"},
            "path": screens_dir / "dolby-v2.mkv",
        },
    ]

    cfg = ReportConfig(enable=True)
    report_dir = tmp_path / "report"

    generate_html_report(
        report_dir=report_dir,
        report_cfg=cfg,
        frames=frames,
        selection_details=selection_details,
        image_paths=[str(first), str(second)],
        plans=plans,
        metadata_title=None,
        include_metadata="minimal",
        slowpics_url=None,
    )

    with (report_dir / "data.json").open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    labels = [encode["label"] for encode in payload["encodes"]]
    assert labels == ["Dolby Vision", "Dolby-Vision"]
    safe_labels = [encode["safe_label"] for encode in payload["encodes"]]
    assert safe_labels == ["Dolby_Vision", "Dolby_Vision_2"]
    frame_files = payload["frames"][0]["files"]
    assert {entry["safe_label"] for entry in frame_files} == set(safe_labels)
