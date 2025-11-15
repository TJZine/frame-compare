from __future__ import annotations

import types
from pathlib import Path

import pytest

from src.datatypes import RuntimeConfig
from src.frame_compare import selection as selection_module
from src.frame_compare.cli_runtime import ClipPlan


def _make_plan(path: Path, *, reference: bool = False, fps_override: tuple[int, int] | None = None) -> ClipPlan:
    return ClipPlan(path=path, metadata={"label": path.stem}, use_as_reference=reference, fps_override=fps_override)


def test_probe_clip_metadata_populates_fps_and_props(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plans = [
        _make_plan(tmp_path / "Reference.mkv", reference=True),
        _make_plan(tmp_path / "TargetA.mkv"),
        _make_plan(tmp_path / "TargetB.mkv", fps_override=(30000, 1001)),
    ]

    props_by_name = {
        "Reference.mkv": {"_Matrix": 9, "_Transfer": 16},
        "TargetA.mkv": {"_Matrix": 1},
        "TargetB.mkv": {"_Matrix": 2},
    }

    clip_specs = {
        "Reference.mkv": dict(width=1920, height=1080, fps_num=24000, fps_den=1001, num_frames=2400),
        "TargetA.mkv": dict(width=1280, height=720, fps_num=60000, fps_den=1001, num_frames=3600),
        "TargetB.mkv": dict(width=1280, height=720, fps_num=24000, fps_den=1001, num_frames=1800),
    }

    ram_limits: list[int] = []
    monkeypatch.setattr(selection_module.vs_core, "set_ram_limit", lambda limit: ram_limits.append(int(limit)))

    init_calls: list[tuple[str, tuple[int, int] | None]] = []

    def fake_init_clip(
        path: str,
        *,
        trim_start: int = 0,
        trim_end: int | None = None,
        fps_map: tuple[int, int] | None = None,
        cache_dir: str | None = None,
        frame_props_sink=None,
        **_kwargs: object,
    ) -> types.SimpleNamespace:
        name = Path(path).name
        init_calls.append((name, fps_map))
        spec = clip_specs[name]
        clip = types.SimpleNamespace(**spec)
        if frame_props_sink is not None:
            frame_props_sink(dict(props_by_name[name]))
        return clip

    monkeypatch.setattr(selection_module.vs_core, "init_clip", fake_init_clip)

    runtime = RuntimeConfig(ram_limit_mb=1024)
    cache_dir = tmp_path / "cache"

    selection_module.probe_clip_metadata(plans, runtime, cache_dir)

    assert ram_limits == [runtime.ram_limit_mb]
    assert len(init_calls) == len(plans)

    reference_plan = plans[0]
    assert reference_plan.effective_fps == (24000, 1001)
    assert reference_plan.source_fps == (24000, 1001)
    assert reference_plan.source_num_frames == 2400
    assert reference_plan.source_width == 1920
    assert reference_plan.source_height == 1080
    assert reference_plan.source_frame_props == props_by_name["Reference.mkv"]

    target_plan = plans[1]
    assert target_plan.applied_fps == reference_plan.effective_fps
    assert target_plan.effective_fps == (60000, 1001)
    assert target_plan.source_fps == (60000, 1001)
    assert target_plan.source_num_frames == 3600
    assert target_plan.source_frame_props == props_by_name["TargetA.mkv"]

    override_plan = plans[2]
    assert override_plan.applied_fps == (30000, 1001)
    assert override_plan.effective_fps == (24000, 1001)
    assert override_plan.source_frame_props == props_by_name["TargetB.mkv"]
    ref_props = reference_plan.source_frame_props
    assert ref_props is not None
    assert target_plan.source_frame_props is not None
    assert override_plan.source_frame_props is not None

    # Mutate the stored props to confirm the capture helper honours existing dictionaries.
    ref_props["sentinel"] = True
    props_by_name["Reference.mkv"] = {"_Matrix": 1}

    selection_module.probe_clip_metadata(plans, runtime, cache_dir)

    assert ram_limits == [runtime.ram_limit_mb, runtime.ram_limit_mb]
    assert len(init_calls) == len(plans) * 2
    assert ref_props["sentinel"] is True
    assert ref_props["_Matrix"] == 9
