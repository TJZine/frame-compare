from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import vapoursynth as vs

from frame_compare.config.schema import ToneCurve
from frame_compare.vs.props import get_optional_int_prop, props_indicate_limited_range
from frame_compare.vs.runtime_contract import (
    DEBIAN_FFMPEG_PACKAGE_VERSION,
    FFMS2_RELEASE,
    FFMS2_RUNTIME_VERSION,
    FFMS2_SOURCE_COMMIT,
    FFMS2_SOURCE_TREE_SHA256,
    LIBDOVI_SOURCE_COMMIT,
    LIBDOVI_SOURCE_TREE_SHA256,
    LIBPLACEBO_SOURCE_COMMIT,
    LIBPLACEBO_SOURCE_TREE_SHA256,
    LSMASH_SOURCE_COMMIT,
    LSMASH_SOURCE_TREE_SHA256,
    LSMASH_WORKS_RELEASE,
    LSMASH_WORKS_SOURCE_COMMIT,
    LSMASH_WORKS_SOURCE_TREE_SHA256,
    OBUPARSE_SOURCE_COMMIT,
    OBUPARSE_SOURCE_TREE_SHA256,
    VAPOURSYNTH_RELEASE,
    VAPOURSYNTH_SOURCE_COMMIT,
    VAPOURSYNTH_SOURCE_TREE_SHA256,
    VS_PLACEBO_RELEASE,
    VS_PLACEBO_SOURCE_COMMIT,
    VS_PLACEBO_SOURCE_TREE_SHA256,
    index_cache_token,
    media_runtime_fingerprint,
)
from frame_compare.vs.source import load_source, source_index_path
from frame_compare.vs.tonemap import apply_tonemap
from frame_compare.vs.types import TonemapSettings


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


media_path = Path(sys.argv[1])
doctor_path = Path(sys.argv[2])
ffindex_path = Path(sys.argv[3])
assert_true(media_path.is_file(), f"proof media missing: {media_path}")
assert_true(os.geteuid() != 0, "Docker runtime proof unexpectedly runs as root")

expected_fingerprint = media_runtime_fingerprint("full")
assert_true(
    os.environ.get("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT") == expected_fingerprint,
    "declared Docker media-runtime fingerprint does not match the application contract",
)
assert_true(os.environ.get("FRAME_COMPARE_RUNTIME_KIND") == "docker", "runtime kind mismatch")
assert_true(
    os.environ.get("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED") == "1",
    "Docker FFMS2 requirement is not declared",
)
assert_true(
    os.environ.get("FRAME_COMPARE_FFMPEG_EXECUTABLE") == "/usr/bin/ffmpeg",
    "Docker FFmpeg executable override mismatch",
)
assert_true(
    os.environ.get("FRAME_COMPARE_FFPROBE_EXECUTABLE") == "/usr/bin/ffprobe",
    "Docker ffprobe executable override mismatch",
)
loader_paths = os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
assert_true(
    "/home/framecompare/.local/lib/python3.13/site-packages/vapoursynth" in loader_paths,
    "VapourSynth R81 wheel native-library path missing from LD_LIBRARY_PATH",
)
assert_true("/usr/local/lib" in loader_paths, "/usr/local/lib missing from LD_LIBRARY_PATH")

provenance_path = Path("/usr/local/share/frame-compare/media-runtime/SOURCES.json")
provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
assert_true(provenance.get("schema_version") == 2, "runtime provenance schema mismatch")
components = {component["name"]: component for component in provenance["components"]}
expected_source_trees = {
    "VapourSynth": (VAPOURSYNTH_SOURCE_COMMIT, VAPOURSYNTH_SOURCE_TREE_SHA256),
    "OBUParse": (OBUPARSE_SOURCE_COMMIT, OBUPARSE_SOURCE_TREE_SHA256),
    "L-SMASH": (LSMASH_SOURCE_COMMIT, LSMASH_SOURCE_TREE_SHA256),
    "L-SMASH-Works": (LSMASH_WORKS_SOURCE_COMMIT, LSMASH_WORKS_SOURCE_TREE_SHA256),
    "FFMS2": (FFMS2_SOURCE_COMMIT, FFMS2_SOURCE_TREE_SHA256),
    "vs-placebo": (VS_PLACEBO_SOURCE_COMMIT, VS_PLACEBO_SOURCE_TREE_SHA256),
    "libplacebo": (LIBPLACEBO_SOURCE_COMMIT, LIBPLACEBO_SOURCE_TREE_SHA256),
    "libdovi": (LIBDOVI_SOURCE_COMMIT, LIBDOVI_SOURCE_TREE_SHA256),
}
for name, (commit, tree_sha256) in expected_source_trees.items():
    component = components.get(name, {})
    assert_true(component.get("source_commit") == commit, f"{name} source commit mismatch")
    assert_true(
        component.get("source_tree_sha256") == tree_sha256,
        f"{name} source-tree digest mismatch",
    )
assert_true(components["OBUParse"].get("linkage") == "shared", "OBUParse linkage mismatch")
assert_true(components["OBUParse"].get("soname") == "libobuparse.so.2", "OBUParse SONAME mismatch")
assert_true(
    components["Debian FFmpeg"].get("license") == "GPL-2.0-or-later",
    "Debian FFmpeg license profile mismatch",
)
license_root = Path("/usr/local/share/licenses/frame-compare-media-runtime")
for license_name in (
    "Debian-FFmpeg-copyright",
    "VapourSynth-LGPL-2.1.txt",
    "OBUParse-LICENSE.txt",
    "L-SMASH-LICENSE.txt",
    "L-SMASH-Works-VapourSynth-LICENSE.txt",
    "FFMS2-COPYING.txt",
    "vs-placebo-LGPL-2.1.txt",
    "libplacebo-LGPL-2.1.txt",
    "libdovi-MIT.txt",
):
    assert_true((license_root / license_name).is_file(), f"runtime license missing: {license_name}")

core = vs.core
version = getattr(vs, "__version__", None)
api_version = getattr(vs, "__api_version__", None)
release_major = getattr(version, "release_major", None)
release_minor = getattr(version, "release_minor", None)
api_major = getattr(api_version, "api_major", None)
api_minor = getattr(api_version, "api_minor", None)
version_label = f"R{release_major}" if release_major is not None else str(version)
plugin_dir = Path(vs.get_plugin_dir())
extra_plugin_path = os.environ.get("VAPOURSYNTH_EXTRA_PLUGIN_PATH", "")
plugin_namespaces = sorted(plugin.namespace for plugin in core.plugins())

assert_true(VAPOURSYNTH_RELEASE == "R81", "application runtime contract is not R81")
assert_true(
    release_major == 81 and release_minor == 0,
    f"expected VapourSynth R81, got {version!r}",
)
assert_true(api_major == 4, f"expected VapourSynth API 4, got {api_major!r}")
assert_true(api_minor == 3, f"expected VapourSynth API minor 3, got {api_minor!r}")
assert_true(plugin_dir.is_dir(), f"VapourSynth plugin directory missing: {plugin_dir}")
assert_true(extra_plugin_path == "/opt/vapoursynth-extra-plugins", "extra plugin path mismatch")
assert_true(plugin_namespaces, "core.plugins() returned no plugins")
assert_true(hasattr(core, "lsmas"), "core.lsmas namespace missing")
lsmas_functions = sorted(function.name for function in core.lsmas.functions())
assert_true("LWLibavSource" in lsmas_functions, "lsmas.LWLibavSource missing")
assert_true("LibavSMASHSource" in lsmas_functions, "lsmas.LibavSMASHSource missing")
source = load_source(media_path, core=core)
source_frame = source.clip.get_frame(0)
expected_index = source_index_path(media_path)
assert_true(expected_index.is_file(), f"versioned L-SMASH-Works index missing: {expected_index}")
assert_true(index_cache_token() in expected_index.name, "source index lacks runtime token")
assert_true(source.num_frames == 12, f"unexpected L-SMASH-Works frame count: {source.num_frames}")
assert_true(
    source_frame.width == 64 and source_frame.height == 48,
    "L-SMASH-Works frame dimensions mismatch",
)

assert_true(hasattr(core, "ffms2"), "core.ffms2 namespace missing")
ffms2_functions = sorted(function.name for function in core.ffms2.functions())
assert_true("Source" in ffms2_functions, "ffms2.Source missing")
assert_true("Version" in ffms2_functions, "ffms2.Version missing")
ffms2_version_result = core.ffms2.Version()
if isinstance(ffms2_version_result, dict):
    ffms2_version_value = ffms2_version_result.get("version")
elif hasattr(ffms2_version_result, "version"):
    ffms2_version_value = ffms2_version_result.version
else:
    ffms2_version_value = ffms2_version_result
if isinstance(ffms2_version_value, bytes):
    ffms2_version_value = ffms2_version_value.decode("utf-8")
assert_true(
    ffms2_version_value == FFMS2_RUNTIME_VERSION,
    f"unexpected FFMS2 runtime version: {ffms2_version_value!r}",
)
ffms2_clip = core.ffms2.Source(str(media_path), cachefile=str(ffindex_path))
ffms2_frame = ffms2_clip.get_frame(0)
assert_true(ffindex_path.is_file(), f"FFMS2 index missing: {ffindex_path}")
assert_true(ffms2_clip.num_frames == 12, f"unexpected FFMS2 frame count: {ffms2_clip.num_frames}")
assert_true(
    ffms2_frame.width == 64 and ffms2_frame.height == 48,
    "FFMS2 frame dimensions mismatch",
)


def run_ffmpeg(*arguments: str) -> None:
    subprocess.run(
        ["/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", *arguments],
        check=True,
        text=True,
        timeout=90,
    )


def ffmpeg_has_encoder(name: str) -> bool:
    output = subprocess.check_output(
        ["/usr/bin/ffmpeg", "-hide_banner", "-encoders"],
        text=True,
        timeout=15,
    )
    return any(line.split()[1:2] == [name] for line in output.splitlines())


def probe_stream_color(path: Path) -> dict[str, str]:
    payload = json.loads(
        subprocess.check_output(
            [
                "/usr/bin/ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=pix_fmt,color_range,color_space,color_transfer,color_primaries",
                "-of",
                "json",
                str(path),
            ],
            text=True,
            timeout=15,
        )
    )
    streams = payload.get("streams", [])
    assert_true(len(streams) == 1, f"expected one video stream in {path}: {payload!r}")
    return streams[0]


def open_with_source_loaders(
    path: Path,
) -> tuple[object, object, dict[str, object], dict[str, object]]:
    lsw_source = load_source(path, core=core)
    lsw_frame = lsw_source.clip.get_frame(0)
    ffms_clip = core.ffms2.Source(str(path), cache=0)
    ffms_frame = ffms_clip.get_frame(0)
    assert_true(
        lsw_source.num_frames == ffms_clip.num_frames, f"loader frame-count mismatch: {path}"
    )
    assert_true(
        lsw_frame.width == ffms_frame.width and lsw_frame.height == ffms_frame.height,
        f"loader dimension mismatch: {path}",
    )
    return lsw_source, ffms_clip, dict(lsw_frame.props), dict(ffms_frame.props)


fixture_results: list[str] = []
with tempfile.TemporaryDirectory(prefix="frame-compare-media-fixtures-") as fixture_root_raw:
    fixture_root = Path(fixture_root_raw)

    limited_source, limited_ffms, limited_props, limited_ffms_props = open_with_source_loaders(
        media_path
    )
    assert_true(
        probe_stream_color(media_path).get("color_range") == "tv",
        "invalid limited-range fixture",
    )
    assert_true(
        props_indicate_limited_range(limited_props) is True,
        f"LWLibavSource lost limited-range metadata: {limited_props!r}",
    )
    assert_true(
        props_indicate_limited_range(limited_ffms_props) is True,
        f"FFMS2 lost limited-range metadata: {limited_ffms_props!r}",
    )
    fixture_results.append(f"h264_limited:{limited_source.num_frames}:{limited_ffms.num_frames}")

    full_range = fixture_root / "full-range.mkv"
    run_ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=4:duration=1",
        "-vf",
        "scale=in_range=tv:out_range=pc",
        "-frames:v",
        "4",
        "-c:v",
        "libx264",
        "-x264-params",
        "range=pc",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "pc",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-y",
        str(full_range),
    )
    _full_lsw, _full_ffms, full_props, full_ffms_props = open_with_source_loaders(full_range)
    assert_true(
        probe_stream_color(full_range).get("color_range") == "pc",
        "invalid full-range fixture",
    )
    assert_true(
        props_indicate_limited_range(full_props) is False,
        f"LWLibavSource lost full-range metadata: {full_props!r}",
    )
    assert_true(
        props_indicate_limited_range(full_ffms_props) is False,
        f"FFMS2 lost full-range metadata: {full_ffms_props!r}",
    )
    fixture_results.append("h264_full_range")

    vfr_path = fixture_root / "vfr.mkv"
    run_ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=4:duration=2",
        "-vf",
        "setpts='if(eq(N,0),0,PREV_OUTPTS+if(eq(mod(N,2),0),2,1)/(4*TB))'",
        "-fps_mode",
        "vfr",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(vfr_path),
    )
    probe_payload = json.loads(
        subprocess.check_output(
            [
                "/usr/bin/ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "frame=best_effort_timestamp_time",
                "-of",
                "json",
                str(vfr_path),
            ],
            text=True,
            timeout=15,
        )
    )
    timestamps = [
        float(frame["best_effort_timestamp_time"])
        for frame in probe_payload.get("frames", [])
        if "best_effort_timestamp_time" in frame
    ]
    intervals = {
        round(right - left, 6) for left, right in zip(timestamps, timestamps[1:], strict=False)
    }
    assert_true(len(intervals) > 1, f"generated VFR fixture is not variable: {intervals}")
    vfr_lsw, vfr_ffms, _vfr_props, _vfr_ffms_props = open_with_source_loaders(vfr_path)
    assert_true(vfr_lsw.num_frames == len(timestamps), "LWLibavSource VFR frame count mismatch")
    assert_true(vfr_ffms.num_frames == len(timestamps), "FFMS2 VFR frame count mismatch")
    fixture_results.append(f"vfr:{','.join(str(value) for value in sorted(intervals))}")

    interlaced_path = fixture_root / "interlaced.mkv"
    run_ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=64x48:rate=25:duration=0.4",
        "-vf",
        "tinterlace=interleave_top",
        "-flags",
        "+ilme+ildct",
        "-top",
        "1",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-y",
        str(interlaced_path),
    )
    _int_lsw, _int_ffms, interlaced_props, interlaced_ffms_props = open_with_source_loaders(
        interlaced_path
    )
    assert_true(
        get_optional_int_prop(interlaced_props, "_FieldBased") in {1, 2},
        f"LWLibavSource lost field order: {interlaced_props!r}",
    )
    assert_true(
        get_optional_int_prop(interlaced_ffms_props, "_FieldBased") in {1, 2},
        f"FFMS2 lost field order: {interlaced_ffms_props!r}",
    )
    fixture_results.append("h264_interlaced")

    if ffmpeg_has_encoder("libx265"):
        hdr_path = fixture_root / "hdr10.mkv"
        run_ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x48:rate=4:duration=1",
            "-vf",
            "format=yuv420p10le",
            "-frames:v",
            "4",
            "-c:v",
            "libx265",
            "-preset",
            "ultrafast",
            "-x265-params",
            "repeat-headers=1:hdr10=1:master-display=G(13250,34500)B(7500,3000)"
            "R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400:range=limited:"
            "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc",
            "-pix_fmt",
            "yuv420p10le",
            "-color_primaries",
            "bt2020",
            "-color_trc",
            "smpte2084",
            "-colorspace",
            "bt2020nc",
            "-color_range",
            "tv",
            "-y",
            str(hdr_path),
        )
        hdr_lsw, hdr_ffms, hdr_props, hdr_ffms_props = open_with_source_loaders(hdr_path)
        hdr_stream = probe_stream_color(hdr_path)
        assert_true(
            hdr_stream
            == {
                "pix_fmt": "yuv420p10le",
                "color_range": "tv",
                "color_space": "bt2020nc",
                "color_transfer": "smpte2084",
                "color_primaries": "bt2020",
            },
            f"invalid HDR fixture signal metadata: {hdr_stream!r}",
        )
        assert_true(hdr_lsw.clip.format.bits_per_sample >= 10, "LWLibavSource lost HDR precision")
        assert_true(hdr_ffms.format.bits_per_sample >= 10, "FFMS2 lost HDR precision")
        assert_true(hdr_lsw.is_hdr is True, "production source loader did not classify HDR")
        assert_true(hdr_lsw.hdr_metadata is not None, "production source loader lost HDR metadata")
        assert_true(hdr_lsw.hdr_metadata.transfer == 16, "production source loader lost PQ")
        assert_true(
            hdr_lsw.hdr_metadata.color_primaries == 9,
            "production source loader lost BT.2020 primaries",
        )
        untagged_hdr_clip = hdr_lsw.clip.std.RemoveFrameProps(
            props=["_Matrix", "_Transfer", "_Primaries"]
        )
        tonemapped_hdr = apply_tonemap(
            untagged_hdr_clip,
            TonemapSettings(tone_curve=ToneCurve.BT2390, target_nits=203),
            hdr_lsw.hdr_metadata,
        )
        spline_hdr = apply_tonemap(
            untagged_hdr_clip,
            TonemapSettings(tone_curve=ToneCurve.SPLINE, target_nits=203),
            hdr_lsw.hdr_metadata,
        )
        tonemapped_hdr_frame = tonemapped_hdr.get_frame(0)
        assert_true(
            tonemapped_hdr_frame.props.get("_Tonemapped") == 1,
            "production tonemap did not render the classified untagged HDR source",
        )
        curve_diff_clips = [
            core.std.PlaneStats(tonemapped_hdr, spline_hdr, plane=plane) for plane in range(3)
        ]
        curve_diffs = [
            float(diff_clip.get_frame(frame_index).props["PlaneStatsDiff"])
            for diff_clip in curve_diff_clips
            for frame_index in range(tonemapped_hdr.num_frames)
        ]
        assert_true(
            any(difference > 0 for difference in curve_diffs),
            "BT2390 output matched spline across the HDR fixture",
        )
        for props, loader_name in ((hdr_props, "LWLibavSource"), (hdr_ffms_props, "FFMS2")):
            assert_true(
                props_indicate_limited_range(props) is True,
                f"{loader_name} lost limited range: {props!r}",
            )
        fixture_results.append("hevc10_hdr10_tonemap")
    else:
        raise SystemExit("required libx265 encoder is unavailable")

    if ffmpeg_has_encoder("libaom-av1"):
        av1_path = fixture_root / "av1.mkv"
        run_ffmpeg(
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=64x48:rate=4:duration=1",
            "-frames:v",
            "4",
            "-c:v",
            "libaom-av1",
            "-cpu-used",
            "8",
            "-crf",
            "45",
            "-b:v",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(av1_path),
        )
        av1_lsw, av1_ffms, _av1_props, _av1_ffms_props = open_with_source_loaders(av1_path)
        assert_true(av1_lsw.num_frames == 4, "LWLibavSource AV1 frame count mismatch")
        assert_true(av1_ffms.num_frames == 4, "FFMS2 AV1 frame count mismatch")
        fixture_results.append("av1")
    else:
        raise SystemExit("required libaom-av1 encoder is unavailable")

assert_true(importlib.metadata.version("vs-placebo") == VS_PLACEBO_RELEASE, "vs-placebo mismatch")
assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
placebo_functions = sorted(function.name for function in core.placebo.functions())
assert_true("Tonemap" in placebo_functions, "core.placebo.Tonemap missing")
tonemap_input = core.std.BlankClip(
    width=16,
    height=16,
    format=vs.RGB48,
    length=1,
    color=[32768, 32768, 32768],
).std.SetFrameProps(_Matrix=0, _Range=1, _Transfer=16, _Primaries=9)
tonemap_output = core.placebo.Tonemap(
    tonemap_input,
    src_max=1000,
    dst_max=203,
    tone_mapping_function=2,
    dst_csp=0,
    dst_prim=1,
    src_csp=1,
)
tonemap_frame = tonemap_output.get_frame(0)
assert_true(tonemap_frame.width == 16 and tonemap_frame.height == 16, "placebo render failed")
assert_true(
    tonemap_frame.format.bits_per_sample >= 16,
    f"placebo output unexpectedly lost precision: {tonemap_frame.format.name}",
)

ffmpeg_version_line = subprocess.check_output(
    ["/usr/bin/ffmpeg", "-version"], text=True, timeout=10
).splitlines()[0]
ffprobe_version_line = subprocess.check_output(
    ["/usr/bin/ffprobe", "-version"], text=True, timeout=10
).splitlines()[0]
debian_ffmpeg_package = subprocess.check_output(
    ["dpkg-query", "-W", "-f=${Version}", "ffmpeg"], text=True, timeout=10
).strip()
assert_true(
    debian_ffmpeg_package == DEBIAN_FFMPEG_PACKAGE_VERSION,
    f"unexpected Debian FFmpeg package: {debian_ffmpeg_package}",
)

payload = json.loads(doctor_path.read_text(encoding="utf-8"))
assert_true(payload.get("success") is True, f"doctor failed: {payload}")
doctor = payload["doctor"]
assert_true(doctor["baseline_version"] == VAPOURSYNTH_RELEASE, "doctor R81 baseline mismatch")
assert_true(
    doctor["media_runtime"]["fingerprints"]["full"] == expected_fingerprint,
    "doctor runtime fingerprint mismatch",
)
runtime_environment = doctor["runtime_environment"]
assert_true(runtime_environment["runtime_kind"] == "docker", "doctor runtime kind mismatch")
assert_true(
    runtime_environment["declared_full_fingerprint_match"] is True, "doctor fingerprint mismatch"
)
assert_true(runtime_environment["ffms2_required"] is True, "doctor FFMS2 policy mismatch")
checks = {
    entry.get("id"): entry
    for entry in doctor["checks"]
    if isinstance(entry, dict) and isinstance(entry.get("id"), str)
}
for required_check in ("vapoursynth", "lsmas", "vs_placebo", "ffms2", "ffmpeg"):
    assert_true(required_check in checks, f"doctor required check missing: {required_check}")
    assert_true(
        checks[required_check]["status"] == "pass",
        f"doctor check failed: {required_check}",
    )
assert_true(checks["vapoursynth"]["details"]["observed_release"] == "R81", "doctor VS release")
assert_true(checks["vapoursynth"]["details"]["api_major"] == 4, "doctor VS API")
assert_true(
    checks["lsmas"]["details"]["expected_native_release"] == LSMASH_WORKS_RELEASE,
    "doctor L-SMASH-Works release mismatch",
)
assert_true(
    checks["ffms2"]["details"]["observed_runtime_version"] == FFMS2_RUNTIME_VERSION,
    "doctor FFMS2 runtime version mismatch",
)
assert_true(
    checks["vs_placebo"]["details"]["observed_distribution_version"] == VS_PLACEBO_RELEASE,
    "doctor vs-placebo distribution mismatch",
)

version_output = Path("/tmp/frame-compare-version.txt").read_text(encoding="utf-8").strip()
print(f"DOCKER_PROOF cli=ok version_output={version_output}")
print(f"DOCKER_PROOF non_root=ok uid={os.geteuid()}")
print(f"DOCKER_PROOF vapoursynth_import=ok version={version_label} api={api_major}.{api_minor}")
print(f"DOCKER_PROOF plugin_dir={plugin_dir}")
print(f"DOCKER_PROOF extra_plugin_path={extra_plugin_path}")
print(f"DOCKER_PROOF core_plugins={','.join(plugin_namespaces)}")
print(
    "DOCKER_PROOF lsmash_works=ok "
    f"release={LSMASH_WORKS_RELEASE} functions={','.join(lsmas_functions)} index={expected_index.name}"
)
print(
    "DOCKER_PROOF ffms2=ok "
    f"release={FFMS2_RELEASE} runtime={ffms2_version_value} "
    f"functions={','.join(ffms2_functions)} index={ffindex_path.name}"
)
print(
    "DOCKER_PROOF vs_placebo=ok "
    f"version={VS_PLACEBO_RELEASE} functions={','.join(placebo_functions)} "
    f"output={tonemap_frame.format.name}"
)
print(f"DOCKER_PROOF debian_ffmpeg={debian_ffmpeg_package}")
print(f"DOCKER_PROOF ffmpeg_version={ffmpeg_version_line}")
print(f"DOCKER_PROOF ffprobe_version={ffprobe_version_line}")
print("DOCKER_PROOF software_vulkan=ok")
print("DOCKER_PROOF native_shared_libraries=ok")
print("DOCKER_PROOF obuparse=ok linkage=shared soname=libobuparse.so.2 provenance=verified")
print("DOCKER_PROOF source_provenance=ok strategy=git-commit-tracked-tree-sha256")
print("DOCKER_PROOF doctor_json=ok")
print(f"DOCKER_PROOF generated_fixture_matrix=ok fixtures={';'.join(fixture_results)}")
print("DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,ffms2,placebo")
