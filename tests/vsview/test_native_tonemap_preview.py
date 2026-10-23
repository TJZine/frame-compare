"""Real native mapper proof at the generated-session preparation boundary.

Source loading and output registration are injected; no visible VSView GUI is
claimed. Each case owns a child process so native state cannot leak between cases.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_NATIVE_PREVIEW = r"""
import json
import sys
import types
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock

try:
    import vapoursynth as vs
except ImportError:
    print("VapourSynth unavailable")
    sys.exit(77)
if isinstance(vs, MagicMock) or hasattr(vs, "_mock_methods"):
    print("VapourSynth mocked")
    sys.exit(77)
from frame_compare.vs.env import ensure_vs_environment, detect_plugins
from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime
ensure_vs_environment()
if not detect_plugins(vs.core).get("libplacebo") or not probe_libplacebo_runtime():
    print("libplacebo/Vulkan unavailable")
    sys.exit(77)

from frame_compare.config.schema import ConfigSchema
from frame_compare.render.prepare import resolve_tonemap_settings
from frame_compare.vs.props import detect_hdr
from frame_compare.vs.tonemap import apply_tonemap
from frame_compare.vs.types import HDRMetadata, LibplaceboTonemap
from frame_compare.vsview import session_runtime as runtime
from frame_compare.vsview.session_script import write_vsview_session_script
from frame_compare.vsview.alignment_review_contract import (
    AlignmentReviewOutputCandidate, parse_alignment_review_workspace_metadata,
)

mode = sys.argv[1]
root = Path(sys.argv[2])
config = ConfigSchema.model_validate({"color": {"tonemap_speed": "fast" if mode == "fast" else "quality"}})
settings = resolve_tonemap_settings(config)
if mode in {"disabled", "legacy"}:
    settings = None
core = vs.core
# Unique luma by source position makes frame-address preservation observable.
source = core.std.Splice([
    core.std.BlankClip(width=64, height=32, length=1, format=vs.YUV420P16,
                       color=[12000 + n * 5000, 32768, 32768], fpsnum=24000, fpsden=1001)
    for n in range(3)
])
source = core.std.SetFrameProps(source, _Transfer=16, _Primaries=9, _Matrix=9,
                                _Range=1, ContentLightLevelMax=1000)
if mode == "sdr":
    source = core.std.SetFrameProps(source, _Transfer=1, _Primaries=1, _Matrix=2)
if mode == "probe":
    source = core.std.RemoveFrameProps(source, props=["_Transfer", "_Primaries", "_Matrix"])
    import frame_compare.vs.hdr_probe as hdr_probe
    probes = []
    def probe(path):
        probes.append(path)
        return HDRMetadata(None, 1000, None, 9, 16, 9)
    hdr_probe.probe_hdr_metadata = probe

ref = root / "ref.mkv"
comparisons = [root / "zeta.mkv", root / "alpha.mkv"]
for path in [ref, *comparisons]:
    path.touch()
clips = {"ref": source, "zeta": core.std.AssumeFPS(source, fpsnum=25, fpsden=1),
         "alpha": core.std.AssumeFPS(source, fpsnum=30, fpsden=1)}
class Loader:
    def LWLibavSource(self, path, **kwargs):
        return clips[Path(path).stem]
runtime.resolve_lwlibavsource = lambda core: Loader()
# Isolate preparation pixels from the independently covered display overlay.
models = []
def overlay(core, clip, model, *, warn):
    models.append(model)
    return clip
runtime.apply_alignment_overlay = overlay
# Observe the real product mapper result; never replace native processing.
import frame_compare.vs.tonemap as tonemap_module
applied = []
def observe_mapper(*args, **kwargs):
    result = apply_tonemap(*args, **kwargs)
    applied.append(result.applied)
    return result
tonemap_module.apply_tonemap = observe_mapper
outputs = []
def register(clip, index, name, *, hdr, **metadata):
    assert hdr is False
    outputs.append((clip, index, name, metadata))
viewer = types.ModuleType("vsview")
viewer.set_output = register
sys.modules["vsview"] = viewer
# Parent snapshots deliberately disagree with original HDR evidence. They may
# supply defaults only for clips that were not mapped.
snapshots = {path.stem: {"_Transfer": 2, "_Primaries": 2, "_Matrix": 2, "_Range": 1}
             for path in [ref, *comparisons]}
audio = {
    key: json.dumps({
        "current_authority": {"origin": "shared_computed_offsets" if offset is not None else "none",
                              "frame_offset": offset},
        "evidence_availability": "historical_details_unavailable" if offset is not None else "not_computed",
        "audio_attempt": None,
    }) for key, offset in {"ref:zeta": 1, "ref:alpha": None}.items()
}
script = write_vsview_session_script(
    reference=ref, comparisons=comparisons,
    suggested_offsets_by_key={"ref:zeta": 1, "ref:alpha": None},
    audio_review_by_key=audio, cache_dir=root,
    preview_tonemap=settings, frame_props_by_stem=snapshots,
)
text = script.read_text(encoding="utf-8")
if mode == "legacy":
    # Older generated payloads have no optional settings key.
    import ast
    module = ast.parse(text)
    assignment = next(n for n in module.body if isinstance(n, ast.Assign))
    payload = next(n.value for n in ast.walk(assignment)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str))
    data = json.loads(payload)
    data.pop("preview_tonemap")
    runtime.run_session(data, script)
else:
    exec(compile(text, str(script), "exec"), {"__file__": str(script)})
assert [output[1:3] for output in outputs] == [(0, "Reference"), (1, "Comparison 1"), (2, "Comparison 2")]
workspace = parse_alignment_review_workspace_metadata(tuple(
    AlignmentReviewOutputCandidate(index, clip.num_frames, metadata)
    for clip, index, name, metadata in outputs
))
assert len(models) == 3
if mode in {"quality", "fast", "probe"}:
    assert len(applied) == 3
    for facts in applied:
        assert isinstance(facts.transform, LibplaceboTonemap)
        assert facts.transform.frame_policy == "sequence"
        assert facts.requested == settings
        assert facts.requested.tonemap_speed is settings.tonemap_speed
        assert facts.requested.dynamic_peak_detection is (mode != "fast")
else:
    assert applied == []
assert outputs[1][3]["frame_compare_suggested_offset"] == 1
assert outputs[2][3]["frame_compare_suggested_offset"] is None
assert outputs[1][3]["frame_compare_alignment_key"] == "ref:zeta"
assert outputs[2][3]["frame_compare_alignment_key"] == "ref:alpha"
assert all(output[3]["frame_compare_contract_version"] == 5 for output in outputs)
for clip, index, name, metadata in outputs:
    assert clip.num_frames == 3
    assert clip.fps == Fraction(24000, 1001)
    with clip.get_frame(1) as frame:
        props = dict(frame.props)
    if mode in {"quality", "fast", "probe"}:
        assert props["_Transfer"] == 13, props
        assert props["_Primaries"] == 1, props
        assert clip.format.id == vs.RGBS
    else:
        assert props["_Transfer"] == 1
        assert props["_Primaries"] == 1
        assert props["_Matrix"] == 1
        assert clip.format.id == vs.YUV420P16
if mode == "probe":
    assert probes == [ref, *comparisons]
if mode in {"quality", "fast"}:
    with source.get_frame(0) as frame:
        _, metadata = detect_hdr(dict(frame.props))
    expected = apply_tonemap(source, settings, metadata, still_image=False)
    assert isinstance(expected.applied.transform, LibplaceboTonemap)
    assert expected.applied.transform.frame_policy == "sequence"
    assert expected.applied.requested.dynamic_peak_detection is (mode == "quality")
    def pixels(clip, n):
        with clip.get_frame(n) as frame:
            return tuple(bytes(frame[p]) for p in range(frame.format.num_planes))
    actual = [pixels(outputs[0][0], n) for n in range(3)]
    assert actual == [pixels(expected.clip, n) for n in range(3)]
    assert len(set(actual)) == 3
    if mode == "fast":
        stills = apply_tonemap(source, settings, metadata, still_image=True)
        assert isinstance(stills.applied.transform, LibplaceboTonemap)
        assert stills.applied.transform.frame_policy == "shared_stateless"
        assert actual == [pixels(stills.clip, n) for n in range(3)]
print("OK")
"""


@pytest.mark.vs_required
@pytest.mark.parametrize("mode", ["quality", "fast", "sdr", "disabled", "legacy", "probe"])
def test_generated_session_native_preview(mode: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", _NATIVE_PREVIEW, mode, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=90,
        check=False,
    )
    details = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    if result.returncode == 77:
        if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
            pytest.fail(f"Native preview runtime is required.\n{details}")
        pytest.skip(f"Native preview runtime unavailable.\n{details}")
    assert result.returncode == 0, details
    assert result.stdout.strip().endswith("OK"), details
