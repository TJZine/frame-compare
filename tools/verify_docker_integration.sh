#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash tools/verify_docker_integration.sh [--service NAME] [--no-build] [--no-cache] [--pytest-path PATH]

Runs integration tests inside the Docker image where VapourSynth + FFmpeg are installed.
Fails if any tests are skipped (the “real deps work” gate).

Defaults:
  --service frame-compare-test
  Runs: pytest -v tests/integration/ tests/vs/

Environment:
  FRAME_COMPARE_REQUIRE_LIBPLACEBO=1  Require app-level libplacebo tonemap to succeed.

Options:
  --service NAME   Docker Compose service to run (default: frame-compare-test)
  --no-build       Do not run "docker compose build" before tests
  --no-cache       Add "--no-cache" to "docker compose build"
  --pytest-path    Repeat to override default pytest paths with a focused subset
EOF
}

service="frame-compare-test"
run_build="1"
no_cache="0"
use_custom_pytest_paths="0"
pytest_paths=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --service)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "ERROR: --service requires a value" >&2
        usage >&2
        exit 2
      fi
      service="${2:-}"
      shift 2
      ;;
    --no-build)
      run_build="0"
      shift
      ;;
    --no-cache)
      no_cache="1"
      shift
      ;;
    --pytest-path)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "ERROR: --pytest-path requires a value" >&2
        usage >&2
        exit 2
      fi
      if [[ "$use_custom_pytest_paths" == "0" ]]; then
        pytest_paths=()
        use_custom_pytest_paths="1"
      fi
      pytest_paths+=("${2:-}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown arg: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."; then
  echo "ERROR: unable to change to the Frame Compare repository root" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not on PATH" >&2
  exit 127
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose is not available (need Docker Desktop or compose plugin)" >&2
  exit 127
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: docker daemon is not running; start Docker Desktop or your Docker daemon and retry" >&2
  exit 127
fi

# Ensure the host bind-mount source exists before Compose creates any container.
# This keeps the generated-data proof writable by the invoking host user on
# Linux daemons that otherwise create a missing bind source as root.
mkdir -p generated

build_args=()
if [[ "$no_cache" == "1" ]]; then
  build_args+=(--no-cache)
fi
build_services=("$service")
if [[ "$service" != "frame-compare-run" ]]; then
  build_services+=("frame-compare-run")
fi

if [[ "$run_build" == "1" ]]; then
  # bash 3.2 + `set -u` can treat empty `${array[@]}` expansions as unbound.
  if [[ "${#build_args[@]}" -gt 0 ]]; then
    docker compose build "${build_args[@]}" "${build_services[@]}"
  else
    docker compose build "${build_services[@]}"
  fi
fi

tmp_log="$(mktemp)"
production_log="$(mktemp)"
proof_dir=""
cleanup() {
  rm -f "$tmp_log" "$production_log"
  if [[ "$proof_dir" == generated/.docker-integration-proof.* && -d "$proof_dir" ]]; then
    rm -rf -- "$proof_dir"
  fi
}
trap cleanup EXIT

docker_cmd=(
  docker compose run
  --rm
)

docker_env_args=()
if [[ "${FRAME_COMPARE_REQUIRE_LIBPLACEBO:-}" == "1" ]]; then
  docker_env_args+=(-e FRAME_COMPARE_REQUIRE_LIBPLACEBO=1)
fi

if [[ "${#docker_env_args[@]}" -gt 0 ]]; then
  docker_cmd+=("${docker_env_args[@]}")
fi

if [[ "${#pytest_paths[@]}" -eq 0 ]]; then
  pytest_paths=(tests/integration/ tests/vs/)
fi

printf -v pytest_args ' %q' "${pytest_paths[@]}"

docker_cmd+=(
  "$service"
  -c
)

# Note: keep this robust even if the image doesn't include pytest yet.
container_cmd=$(
  cat <<'EOF'
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
export PATH="/home/framecompare/.local/bin:${PATH}"
icd="/usr/share/vulkan/icd.d/lvp_icd.json"
if [[ -f "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
pytest_cache_dir=""
media_path="$(mktemp /tmp/frame-compare-docker-proof.XXXXXX.mp4)"
doctor_path="$(mktemp /tmp/frame-compare-doctor.XXXXXX.json)"
ffindex_path="$(mktemp -u /tmp/frame-compare-docker-proof.XXXXXX.ffindex)"
cleanup_runtime_proof() {
  rm -f "$media_path" "$doctor_path" "$ffindex_path"
  rm -f "${media_path}.frame-compare-"*.lwi
  if [[ -n "${pytest_cache_dir:-}" ]]; then
    rm -rf "$pytest_cache_dir"
  fi
}
trap cleanup_runtime_proof EXIT

frame-compare --help >/tmp/frame-compare-help.txt
frame-compare version >/tmp/frame-compare-version.txt
frame-compare doctor --json >"$doctor_path"
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=64x48:rate=24000/1001 \
  -frames:v 12 -pix_fmt yuv420p -c:v libx264 -x264-params range=tv \
  -color_range tv -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -y "$media_path"

if [[ -f "$icd" ]]; then
  vulkaninfo --summary >/tmp/frame-compare-vulkan-summary.txt
else
  echo "ERROR: Mesa software Vulkan ICD is missing from the Docker runtime" >&2
  exit 10
fi

native_ldd_log="$(mktemp /tmp/frame-compare-native-ldd.XXXXXX.txt)"
for library in \
  /opt/vapoursynth-extra-plugins/lsmas/libvslsmashsource.so \
  /opt/vapoursynth-extra-plugins/ffms2/libffms2.so \
  /usr/local/lib/libobuparse.so.2 \
  /usr/local/lib/liblsmash.so \
  /usr/local/lib/libffms2.so; do
  test -e "$library"
  echo "### $library" >>"$native_ldd_log"
  ldd "$library" >>"$native_ldd_log"
done
if grep -Fq 'not found' "$native_ldd_log"; then
  cat "$native_ldd_log" >&2
  echo "ERROR: native media runtime has unresolved shared-library dependencies" >&2
  exit 11
fi
if ! grep -Eq 'libobuparse\.so\.2 => /usr/local/lib/libobuparse\.so\.2' "$native_ldd_log"; then
  cat "$native_ldd_log" >&2
  echo "ERROR: selected L-SMASH runtime is not linked to staged OBUParse SONAME" >&2
  exit 12
fi

python - "$media_path" "$doctor_path" "$ffindex_path" <<'PY'
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
    "VapourSynth R79 wheel native-library path missing from LD_LIBRARY_PATH",
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

assert_true(VAPOURSYNTH_RELEASE == "R79", "application runtime contract is not R79")
assert_true(
    release_major == 79 and release_minor == 0,
    f"expected VapourSynth R79, got {version!r}",
)
assert_true(api_major == 4, f"expected VapourSynth API 4, got {api_major!r}")
assert_true(api_minor == 2, f"expected VapourSynth API minor 2, got {api_minor!r}")
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
                "/usr/bin/ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries",
                "stream=pix_fmt,color_range,color_space,color_transfer,color_primaries",
                "-of", "json", str(path),
            ],
            text=True,
            timeout=15,
        )
    )
    streams = payload.get("streams", [])
    assert_true(len(streams) == 1, f"expected one video stream in {path}: {payload!r}")
    return streams[0]


def open_with_source_loaders(path: Path) -> tuple[object, object, dict[str, object], dict[str, object]]:
    lsw_source = load_source(path, core=core)
    lsw_frame = lsw_source.clip.get_frame(0)
    ffms_clip = core.ffms2.Source(str(path), cache=0)
    ffms_frame = ffms_clip.get_frame(0)
    assert_true(lsw_source.num_frames == ffms_clip.num_frames, f"loader frame-count mismatch: {path}")
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
    fixture_results.append(
        f"h264_limited:{limited_source.num_frames}:{limited_ffms.num_frames}"
    )

    full_range = fixture_root / "full-range.mkv"
    run_ffmpeg(
        "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=4:duration=1",
        "-vf", "scale=in_range=tv:out_range=pc",
        "-frames:v", "4", "-c:v", "libx264", "-x264-params", "range=pc",
        "-pix_fmt", "yuv420p",
        "-color_range", "pc", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-colorspace", "bt709", "-y", str(full_range),
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
        "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=4:duration=2",
        "-vf", "setpts='if(eq(N,0),0,PREV_OUTPTS+if(eq(mod(N,2),0),2,1)/(4*TB))'",
        "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-y", str(vfr_path),
    )
    probe_payload = json.loads(
        subprocess.check_output(
            [
                "/usr/bin/ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "frame=best_effort_timestamp_time", "-of", "json",
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
    intervals = {round(right - left, 6) for left, right in zip(timestamps, timestamps[1:])}
    assert_true(len(intervals) > 1, f"generated VFR fixture is not variable: {intervals}")
    vfr_lsw, vfr_ffms, _vfr_props, _vfr_ffms_props = open_with_source_loaders(vfr_path)
    assert_true(vfr_lsw.num_frames == len(timestamps), "LWLibavSource VFR frame count mismatch")
    assert_true(vfr_ffms.num_frames == len(timestamps), "FFMS2 VFR frame count mismatch")
    fixture_results.append(f"vfr:{','.join(str(value) for value in sorted(intervals))}")

    interlaced_path = fixture_root / "interlaced.mkv"
    run_ffmpeg(
        "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=25:duration=0.4",
        "-vf", "tinterlace=interleave_top", "-flags", "+ilme+ildct", "-top", "1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(interlaced_path),
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
            "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=4:duration=1",
            "-vf", "format=yuv420p10le", "-frames:v", "4", "-c:v", "libx265",
            "-preset", "ultrafast",
            "-x265-params",
            "repeat-headers=1:hdr10=1:master-display=G(13250,34500)B(7500,3000)"
            "R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400:range=limited:"
            "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc",
            "-pix_fmt", "yuv420p10le", "-color_primaries", "bt2020",
            "-color_trc", "smpte2084", "-colorspace", "bt2020nc",
            "-color_range", "tv", "-y", str(hdr_path),
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
            "-f", "lavfi", "-i", "testsrc2=size=64x48:rate=4:duration=1",
            "-frames:v", "4", "-c:v", "libaom-av1", "-cpu-used", "8",
            "-crf", "45", "-b:v", "0", "-pix_fmt", "yuv420p", "-y", str(av1_path),
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
assert_true(doctor["baseline_version"] == VAPOURSYNTH_RELEASE, "doctor R79 baseline mismatch")
assert_true(
    doctor["media_runtime"]["fingerprints"]["full"] == expected_fingerprint,
    "doctor runtime fingerprint mismatch",
)
runtime_environment = doctor["runtime_environment"]
assert_true(runtime_environment["runtime_kind"] == "docker", "doctor runtime kind mismatch")
assert_true(runtime_environment["declared_full_fingerprint_match"] is True, "doctor fingerprint mismatch")
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
assert_true(checks["vapoursynth"]["details"]["observed_release"] == "R79", "doctor VS release")
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
PY
python -c "import pytest, pytest_mock" >/dev/null 2>&1 || {
  echo "ERROR: pytest and pytest-mock are missing from the Docker runtime image" >&2
  exit 13
}
pytest_cache_dir="$(mktemp -d /tmp/frame-compare-pytest-cache.XXXXXX)"
EOF
)
container_cmd+=$'\n'"python -m pytest -v -o cache_dir=\"\$pytest_cache_dir\"${pytest_args}"

set +e
"${docker_cmd[@]}" "$container_cmd" 2>&1 | tee "$tmp_log"
exit_code="${PIPESTATUS[0]}"
set -e

if [[ "$exit_code" != "0" ]]; then
  echo "ERROR: docker integration tests failed (exit $exit_code)" >&2
  exit "$exit_code"
fi

if grep -Eq '([1-9][0-9]* skipped|skipped=[1-9][0-9]*)' "$tmp_log"; then
  echo "ERROR: docker integration tests reported skipped tests; this gate requires zero skips" >&2
  exit 3
fi

required_proof_markers=(
  "DOCKER_PROOF cli=ok"
  "DOCKER_PROOF non_root=ok"
  "DOCKER_PROOF vapoursynth_import=ok version=R79 api=4.2"
  "DOCKER_PROOF plugin_dir="
  "DOCKER_PROOF extra_plugin_path=/opt/vapoursynth-extra-plugins"
  "DOCKER_PROOF core_plugins="
  "DOCKER_PROOF lsmash_works=ok release=1310.0.0.0"
  "DOCKER_PROOF ffms2=ok release=5.0"
  "DOCKER_PROOF vs_placebo=ok version=2.0.4"
  "DOCKER_PROOF debian_ffmpeg="
  "DOCKER_PROOF ffmpeg_version="
  "DOCKER_PROOF ffprobe_version="
  "DOCKER_PROOF software_vulkan=ok"
  "DOCKER_PROOF native_shared_libraries=ok"
  "DOCKER_PROOF obuparse=ok linkage=shared soname=libobuparse.so.2 provenance=verified"
  "DOCKER_PROOF source_provenance=ok strategy=git-commit-tracked-tree-sha256"
  "DOCKER_PROOF doctor_json=ok"
  "DOCKER_PROOF generated_fixture_matrix=ok fixtures=h264_limited"
  "DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,ffms2,placebo"
)

for proof_marker in "${required_proof_markers[@]}"; do
  if ! grep -Fq "$proof_marker" "$tmp_log"; then
    echo "ERROR: docker runtime proof marker missing: $proof_marker" >&2
    exit 4
  fi
done

# Prove the default generated-data bind mount survives container removal.  The
# unique host directory is created under the same generated root used by the
# default Compose services, then removed by the EXIT trap after all assertions.
# The container runs the real CLI against two tiny FFmpeg-generated clips; no
# handcrafted report, screenshot, or run-record files are accepted as proof.
proof_dir="$(mktemp -d generated/.docker-integration-proof.XXXXXX)"
if ! host_uid="$(id -u)" || ! host_gid="$(id -g)"; then
  echo "ERROR: unable to determine the invoking user's UID/GID for the Docker proof" >&2
  exit 2
fi
readonly host_uid host_gid
proof_name="$(basename "$proof_dir")"
container_proof_cmd=$(cat <<'EOF'
set -euo pipefail
export LIBGL_ALWAYS_SOFTWARE=1
export PATH="/home/framecompare/.local/bin:${PATH}"
if command -v uv >/dev/null 2>&1 || command -v uvx >/dev/null 2>&1; then
  echo "ERROR: uv build tooling leaked into the production image" >&2
  exit 6
fi
if python -c 'import pytest' >/dev/null 2>&1; then
  echo "ERROR: pytest test tooling leaked into the production image" >&2
  exit 6
fi
echo "DOCKER_PROOF production_tooling_absent=ok"
icd="/usr/share/vulkan/icd.d/lvp_icd.json"
if [[ -f "$icd" ]]; then
  export VK_ICD_FILENAMES="$icd"
fi
generated_root="/workspace/generated/PROOF_NAME"
workspace_dir="$(mktemp -d /tmp/frame-compare-docker-proof.XXXXXX)"
cleanup_workspace() {
  rm -rf -- "$workspace_dir"
}
trap cleanup_workspace EXIT

media_dir="$workspace_dir/comparison_videos"
config_dir="$workspace_dir/config"
mkdir -p "$media_dir" "$config_dir"
cat > "$config_dir/config.toml" <<CONFIG
[paths]
input_dir = "comparison_videos"
generated_dir = "$generated_root"
config_dir = "config"

[sources]
reference = "reference.mp4"

[analysis]
user_frames = []
random_frame_count = 0
dark_frame_count = 1
bright_frame_count = 0
motion_frame_count = 0
min_window_seconds = 0.0

[audio_alignment]
enable = false

[screenshots]
use_ffmpeg = true

[color]
enable_tonemap = false

[slowpics]
auto_upload = false

[tmdb]
enabled = false

[report]
enable = true
auto_open = false
CONFIG

ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=32x32:rate=2:duration=2 \
  -frames:v 4 -c:v mpeg4 -pix_fmt yuv420p -y "$media_dir/reference.mp4"
ffmpeg -hide_banner -loglevel error \
  -f lavfi -i testsrc2=size=32x32:rate=2:duration=2 \
  -vf hue=h=20 -frames:v 4 -c:v mpeg4 -pix_fmt yuv420p -y "$media_dir/comparison.mp4"

frame-compare run \
  --root "$workspace_dir" \
  --config "$config_dir/config.toml" \
  --input "$media_dir" \
  --skip-metadata \
  --no-upload \
  --quiet

# The application must not leave core output artifacts beside the ephemeral
# fixture workspace. Any match here means generated_dir containment failed.
unexpected_outputs="$(find "$workspace_dir" -type f \( \
  -name 'report.html' -o -name 'run_info.toml' -o -name 'run_result.toml' -o -name '*.png' \
\) -print)"
if [[ -n "$unexpected_outputs" ]]; then
  echo "ERROR: Frame Compare emitted core artifacts outside /workspace/generated:" >&2
  printf '%s\n' "$unexpected_outputs" >&2
  exit 7
fi

run_dirs=()
while IFS= read -r -d '' run_dir; do
  run_dirs+=("$run_dir")
done < <(find "$generated_root" -mindepth 1 -maxdepth 1 -type d ! -name cache -print0)
if [[ "${#run_dirs[@]}" != "1" ]]; then
  echo "ERROR: expected one application-created run folder under $generated_root" >&2
  exit 8
fi
run_root="${run_dirs[0]}"
require_nonempty_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" || ! -s "$path" ]]; then
    echo "ERROR: missing or empty $label: $path" >&2
    exit 9
  fi
}

require_nonempty_file "$run_root/report.html" "HTML report"
require_nonempty_file "$run_root/run_info.toml" "run_info.toml"
require_nonempty_file "$run_root/run_result.toml" "run_result.toml"
require_nonempty_file "$generated_root/clip_probe.toml" "shared probe cache"
require_nonempty_file "$run_root/generated/clip_probe.toml" "run-local probe state"

if ! screenshot_path="$(
  find "$run_root/screenshots" -type f -name '*.png' -size +0c -print -quit 2>/dev/null
)" || [[ -z "$screenshot_path" ]]; then
  echo "ERROR: no non-empty PNG screenshots found under $run_root/screenshots" >&2
  exit 9
fi
if ! analysis_cache_path="$(
  find "$generated_root/cache/analysis" -type f -name '*.compframes' -size +0c -print -quit 2>/dev/null
)" || [[ -z "$analysis_cache_path" ]]; then
  echo "ERROR: no non-empty shared analysis cache found under $generated_root/cache/analysis" >&2
  exit 9
fi
echo "DOCKER_PROOF application_run=ok"
EOF
)
container_proof_cmd="${container_proof_cmd//PROOF_NAME/$proof_name}"

if ! env \
  FRAME_COMPARE_HOST_UID="$host_uid" \
  FRAME_COMPARE_HOST_GID="$host_gid" \
  docker compose run --rm --entrypoint /bin/bash frame-compare-run -lc "$container_proof_cmd" \
    | tee "$production_log"; then
  echo "ERROR: generated-data bind-mount proof failed" >&2
  exit 5
fi
if ! grep -Fq "DOCKER_PROOF production_tooling_absent=ok" "$production_log"; then
  echo "ERROR: production-image tooling proof marker missing" >&2
  exit 6
fi

host_python=""
if command -v python3 >/dev/null 2>&1; then
  host_python="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  host_python="$(command -v python)"
fi
if [[ -z "$host_python" ]]; then
  echo "ERROR: host Python is required to parse Docker-generated TOML and PNG proof files" >&2
  exit 127
fi

export PYTHONPATH="${PWD}/src${PYTHONPATH:+:${PYTHONPATH}}"
if ! "$host_python" - "$proof_dir" <<'PY'
from __future__ import annotations

import struct
import sys
import tomllib
from pathlib import Path

from frame_compare.vs.runtime_contract import media_runtime_fingerprint


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


proof_dir = Path(sys.argv[1]).resolve()
run_dirs = sorted(
    path
    for path in proof_dir.iterdir()
    if path.is_dir() and not path.is_symlink() and path.name != "cache"
)
if len(run_dirs) != 1:
    fail(f"expected one host run folder after container removal under {proof_dir}, found {run_dirs}")
run_dir = run_dirs[0]
generated_root = proof_dir


def require_file(path: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        fail(f"generated-data bind-mount artifact missing after container removal: {label}: {path}")
    return path


report_path = require_file(run_dir / "report.html", "report.html")
if "<html" not in report_path.read_text(encoding="utf-8").lower():
    fail(f"application report is not HTML: {report_path}")

run_info_path = require_file(run_dir / "run_info.toml", "run_info.toml")
with run_info_path.open("rb") as handle:
    run_info = tomllib.load(handle)
if run_info.get("version") != 2:
    fail(f"run_info.toml is not a parseable V2 record: {run_info_path}")
media_runtime = run_info.get("media_runtime")
if not isinstance(media_runtime, dict):
    fail(f"run_info.toml has no media_runtime table: {run_info_path}")
fingerprints = media_runtime.get("fingerprints")
if not isinstance(fingerprints, dict):
    fail(f"run_info.toml has no media runtime fingerprints: {run_info_path}")
if fingerprints.get("full") != media_runtime_fingerprint("full", profile="debian-trixie"):
    fail(f"run_info.toml media runtime fingerprint mismatch: {run_info_path}")

run_result_path = require_file(run_dir / "run_result.toml", "run_result.toml")
with run_result_path.open("rb") as handle:
    run_result = tomllib.load(handle)
if run_result.get("version") != 1 or run_result.get("status") not in {
    "completed",
    "completed_with_warnings",
}:
    fail(f"run_result.toml is not a completed parseable V1 record: {run_result_path}")
if run_result.get("report_path") != "report.html":
    fail(f"run_result.toml report_path is not canonical: {run_result_path}")
if run_result.get("screenshot_dir") != "screenshots":
    fail(f"run_result.toml screenshot_dir is not canonical: {run_result_path}")

screenshot_dir = run_dir / "screenshots"
screenshots = sorted(screenshot_dir.glob("*.png"))
if not screenshots:
    fail(f"application produced no PNG screenshots: {screenshot_dir}")
for screenshot in screenshots:
    payload = require_file(screenshot, "screenshots/*.png").read_bytes()
    if payload[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"application screenshot is not a PNG: {screenshot}")
    if len(payload) < 24 or payload[12:16] != b"IHDR":
        fail(f"application screenshot has no PNG IHDR: {screenshot}")
    width, height = struct.unpack(">II", payload[16:24])
    if width == 0 or height == 0:
        fail(f"application screenshot has invalid dimensions: {screenshot}")

root_probe_path = require_file(generated_root / "clip_probe.toml", "shared probe cache")
with root_probe_path.open("rb") as handle:
    root_probe = tomllib.load(handle)
if root_probe.get("version") != "1":
    fail(f"shared probe cache is not parseable: {root_probe_path}")

run_probe_path = require_file(run_dir / "generated" / "clip_probe.toml", "run-local probe state")
with run_probe_path.open("rb") as handle:
    run_probe = tomllib.load(handle)
if run_probe.get("version") != "1":
    fail(f"run-local probe state is not parseable: {run_probe_path}")

analysis_cache_dir = generated_root / "cache" / "analysis"
analysis_caches = sorted(analysis_cache_dir.glob("*.compframes"))
if not analysis_caches:
    fail(f"application produced no shared analysis cache: {analysis_cache_dir}")
for cache_path in analysis_caches:
    require_file(cache_path, "shared analysis cache")

print(
    "DOCKER_PROOF generated_mount=ok "
    "artifacts=report,screenshots,run_info,run_result,run_generated,analysis_cache,probe_cache"
)
PY
then
  exit 6
fi

echo "OK: docker runtime proof and integration tests passed with zero skips"
