"""Unit tests for the diagnostics helper utilities."""

from __future__ import annotations

import pytest

from src.frame_compare import diagnostics as diag


def test_extract_dovi_metadata_handles_common_props() -> None:
    props = {
        "DolbyVision_Block_Index": 2,
        "DolbyVision_Block_Total": "8",
        "DolbyVision_Target_Nits": "550",
        "DolbyVision_L1_Average": "0.12",
        "DolbyVision_L1_Maximum": 0.5,
    }
    metadata = diag.extract_dovi_metadata(props)
    assert metadata["block_index"] == 2
    assert metadata["block_total"] == 8
    assert metadata["target_nits"] == pytest.approx(550.0)
    assert metadata["l1_average"] == pytest.approx(0.12)
    assert metadata["l1_maximum"] == pytest.approx(0.5)


def test_extract_hdr_metadata_merges_mdl_and_cll() -> None:
    props = {
        "MasteringDisplayLuminance": "0.002 1000",
        "ContentLightLevelMax": 900,
        "ContentLightLevelFall": 300,
    }
    metadata = diag.extract_hdr_metadata(props)
    assert metadata["min_luminance"] == pytest.approx(0.002)
    assert metadata["max_luminance"] == pytest.approx(1000.0)
    assert metadata["max_cll"] == pytest.approx(900.0)
    assert metadata["max_fall"] == pytest.approx(300.0)


def test_format_frame_metrics_line_includes_category() -> None:
    entry = {
        "avg_nits": 120.0,
        "max_nits": 160.0,
        "category": "bright",
    }
    line = diag.format_frame_metrics_line(entry)
    assert line == "Measurement MAX/AVG: 160nits / 120nits (bright)"


def test_build_frame_metric_entry_clamps_scores() -> None:
    entry = diag.build_frame_metric_entry(5, 1.25, "Auto", target_nits=500.0)
    assert entry is not None
    assert entry["frame"] == 5
    assert entry["avg_nits"] == pytest.approx(500.0)
    assert entry["max_nits"] == pytest.approx(500.0)


def test_format_dovi_l1_line_renders_stats() -> None:
    metadata = {
        "l1_average": 23.4,
        "l1_maximum": 715,
    }
    line = diag.format_dovi_l1_line(metadata)
    assert line == "DV RPU Level 1 MAX/AVG: 715nits / 23.4nits"


def test_format_dovi_line_marks_missing_metadata() -> None:
    line = diag.format_dovi_line("auto", {})
    assert line == "DoVi: auto (no DV metadata)"
