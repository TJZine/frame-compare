"""Integration tests for VapourSynth module."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# Required native proof must fail before optional-runtime collection skips.
try:
    import vapoursynth as vs
except ImportError as exc:
    if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
        pytest.fail(f"VapourSynth required for native proof: {exc}", pytrace=False)
    pytest.skip(f"VapourSynth unavailable: {exc}", allow_module_level=True)

# Skip if VapourSynth is mocked (e.g. by test_exports.py running first in a no-VS env)
if hasattr(vs, "_mock_methods"):
    if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
        pytest.fail("Real VapourSynth required for native proof; module is mocked", pytrace=False)
    pytest.skip("VapourSynth is mocked, skipping integration test", allow_module_level=True)

from frame_compare.vs import (
    detect_plugins,
    is_vapoursynth_available,
)
from frame_compare.vs.env import ensure_vs_environment
from frame_compare.vs.loader import DefaultVSLoader

_REPO_ROOT = Path(__file__).resolve().parents[2]

# Provenance: the complete HEVC UNSPEC62 sample published as “RANDOM RPU” in
# the MakeMKV Dolby Vision forum thread (post 96973, 2020-09-30).  The parsed
# sample reports CRC32 0x493cbbb2 and a non-zero Level 1 max_PQ.  Keeping the
# bytes here makes the native test independent of media files or dovi_tool.
# https://forum.makemkv.com/forum/viewtopic.php?p=96973
_RPU_VALID_HEVC_UNSPEC62 = bytes.fromhex(
    """
    7c 01 19 08 09 08 40 61 36 50 ef 00 3f f8 01 ff c0 0f ff d0
    00 00 08 00 00 06 80 00 00 40 00 00 34 00 00 03 02 00 00 03
    01 c9 59 80 00 0d 7a 89 59 be 7f 3a c7 09 59 91 32 80 00 00
    40 00 00 03 02 00 00 03 00 02 00 00 03 00 07 0d 88 90 c0 61
    82 97 8c 23 81 45 00 00 03 00 69 8f 96 bf ff c0 00 00 03 00
    00 03 00 00 03 00 18 08 1f 73 80 54 60 30 08 00 5d 21 99 80
    c0 28 21 80 47 fc 80 08 00 80 01 00 01 80 56 47 00 10 01 00
    10 01 00 0f ff 04 04 01 60 5e 12 0c 4e 20 00 64 4e 20 0d 18
    49 3c bb b2 80
    """
)
_RPU_MALFORMED = _RPU_VALID_HEVC_UNSPEC62[:-5] + b"\x00\x00\x00\x00\x80"


def _run_vs_script(script: str, *, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(script)],
        cwd=_REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _assert_vs_process_ok(result: subprocess.CompletedProcess[str]) -> None:
    if result.returncode == 0:
        stdout_lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert stdout_lines and stdout_lines[-1] == "OK"
        return

    output = []
    if result.stdout:
        output.append(f"stdout:\n{result.stdout.strip()}")
    if result.stderr:
        output.append(f"stderr:\n{result.stderr.strip()}")
    details = "\n\n".join(output)

    if result.returncode in (-11, 139):
        pytest.fail(f"VapourSynth subprocess segfaulted.\n\n{details}")
    pytest.fail(f"VapourSynth subprocess failed with exit {result.returncode}.\n\n{details}")


def _require_native_libplacebo_still_runtime() -> None:
    """Gate tests that require a real libplacebo/Vulkan child process."""
    require_libplacebo = os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1"
    if not bool(detect_plugins(vs.core).get("libplacebo")):
        if require_libplacebo:
            pytest.fail("libplacebo required for fast still native proof")
        pytest.skip("libplacebo unavailable for fast still native proof")

    from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime

    if not probe_libplacebo_runtime():
        if require_libplacebo:
            pytest.fail("libplacebo/Vulkan runtime required for fast still native proof")
        pytest.skip("libplacebo/Vulkan runtime unavailable for fast still native proof")


@pytest.mark.vs_required
def test_vs_integration_smoke():
    """Real VapourSynth test (not mocked)."""
    if not is_vapoursynth_available():
        pytest.skip("VapourSynth not available")

    result = _run_vs_script(
        """
        import vapoursynth as vs

        from frame_compare.vs import TonemapSettings, ensure_vs_environment, apply_tonemap

        core = ensure_vs_environment()
        clip = core.std.BlankClip(width=16, height=16, format=vs.RGBS, length=1)
        out = apply_tonemap(clip, TonemapSettings(enabled=True), hdr_metadata=None)
        assert out.applied is not None
        out = out.clip
        frame = out.get_frame(0)

        assert out.width == 16
        assert out.height == 16
        assert out.format.id == vs.RGBS
        assert frame.width == 16
        assert frame.height == 16
        print("OK")
        """
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_libplacebo_tonemap_succeeds_in_docker():
    """Exercise tonemap in Docker; require libplacebo only when configured.

    By default, Docker Desktop environments (macOS/Windows) may not have a usable
    Vulkan device. In that case, `apply_libplacebo` may return None and
    `apply_tonemap` must fall back without raising.

    Set `FRAME_COMPARE_REQUIRE_LIBPLACEBO=1` to require libplacebo to succeed.
    Local PyPI VapourSynth installs without bundled plugins skip this Docker
    runtime proof unless the require flag is set.
    """
    require_libplacebo = os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1"
    if not require_libplacebo and not bool(detect_plugins(vs.core).get("libplacebo")):
        pytest.skip(
            "libplacebo plugin unavailable in this local VapourSynth runtime; "
            "Docker gate treats this as a required runtime proof"
        )

    result = _run_vs_script(
        """
        import os

        import vapoursynth as vs

        from frame_compare.vs import HDRMetadata, TonemapSettings, apply_tonemap
        from frame_compare.vs.env import detect_plugins
        from frame_compare.vs.tonemap_libplacebo import apply_libplacebo
        from frame_compare.vs.types import TonemapResult, LibplaceboTonemap

        core = vs.core
        require_libplacebo = os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1"

        libplacebo_available = bool(detect_plugins(core).get("libplacebo"))
        if require_libplacebo:
            assert libplacebo_available, (
                "FRAME_COMPARE_REQUIRE_LIBPLACEBO=1 but libplacebo is unavailable"
            )
        else:
            assert libplacebo_available, "libplacebo plugin missing in Docker image (unexpected)"

        clip = core.std.BlankClip(
            width=16,
            height=16,
            format=vs.RGBS,
            length=1,
            color=[0.5, 0.5, 0.5],
        )
        settings = TonemapSettings(
            enabled=True,
            preset="reference",
            tone_curve="bt2390",
            target_nits=203,
        )
        hdr_metadata = HDRMetadata(
            mastering_display=None,
            max_cll=1000,
            max_fall=400,
            color_primaries=9,
            transfer=16,
            matrix=9,
        )

        if require_libplacebo:
            libplacebo_out = apply_libplacebo(clip, settings, core, hdr_metadata)
            assert isinstance(libplacebo_out, TonemapResult), (
                "apply_libplacebo returned None while FRAME_COMPARE_REQUIRE_LIBPLACEBO=1; "
                "Vulkan/libplacebo backend is not usable in this environment."
            )
            assert isinstance(libplacebo_out.applied.transform, LibplaceboTonemap)
            _ = libplacebo_out.clip.get_frame(0)

        out = apply_tonemap(clip, settings, hdr_metadata)
        assert out.applied is not None
        out = out.clip
        frame = out.get_frame(0)

        assert out.format.id == vs.RGBS
        assert frame.width == 16
        assert frame.height == 16
        print("OK")
        """
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_real_loader_sets_cache_and_unset_loader_preserves_it() -> None:
    core = ensure_vs_environment()
    original = core.max_cache_size
    try:
        assert DefaultVSLoader(memory_limit_mb=1024).ensure_core().max_cache_size == 1024
        core.max_cache_size = 1536
        assert DefaultVSLoader().ensure_core().max_cache_size == 1536
    finally:
        core.max_cache_size = original


@pytest.mark.vs_required
def test_native_srgb_encoding_patches_and_png(tmp_path: Path) -> None:
    """Independent goldens distinguish correct black, transfer and exactly-once conversion."""
    result = _run_vs_script(
        f"""
        import numpy as np
        import vapoursynth as vs
        from pathlib import Path
        from PIL import Image
        from frame_compare.vs.env import ensure_vs_environment
        from frame_compare.vs.tonemap_conversion import libplacebo_output_to_srgb
        from frame_compare.render.encoders import _render_vs_pillow
        from frame_compare.render.types import EncoderSettings

        core = ensure_vs_environment()
        patches = [(0,0,0), (16,16,16), (32,32,32), (64,64,64),
                   (128,128,128), (192,192,192), (255,255,255), (192,128,64)]
        goldens = [(0,0,0), (17,17,17), (35,35,35), (67,67,67),
                   (130,130,130), (193,193,193), (255,255,255), (193,130,67)]
        source = core.std.Splice([core.std.BlankClip(width=8,height=8,format=vs.RGBS,
            length=1,color=[v/255 for v in patch]) for patch in patches])
        source = source.std.SetFrameProps(_Matrix=0,_Range=1,_Transfer=16,_Primaries=9,
            DolbyVisionRPU=b'original-source-evidence',ContentLightLevelMax=448.0,
            MasteringDisplayMaxLuminance=1000.0,PLSceneMax=[285.0],PLSceneAvg=25.0)
        output = libplacebo_output_to_srgb(source,black_nits=.18,white_nits=100)
        for n,expected in enumerate(goldens):
            frame = output.get_frame(n)
            for plane,code in enumerate(expected):
                assert abs(float(frame[plane][0,0])*255-code) < .5
            assert frame.props['_Transfer'] == 13 and frame.props['_Primaries'] == 1
            assert frame.props['_Matrix'] == 0 and frame.props['_Range'] == 1
            assert frame.props.get('_FrameCompareExpandRange') == 0
            assert not any(k in frame.props for k in ['DolbyVisionRPU','ContentLightLevelMax',
                'MasteringDisplayMaxLuminance','PLSceneMax','PLSceneAvg'])
            path = Path({str(tmp_path)!r}) / (str(n)+'.png')
            _render_vs_pillow(output,n,path,settings=EncoderSettings(),overlay=None,
                frame_facts=None,geometry_plan=None)
            with Image.open(path) as image:
                assert image.info['srgb'] == 0
                assert np.all(np.asarray(image) == np.array(expected))
        # Conversion does not mutate original source facts or consume its RPU.
        assert source.get_frame(0).props['_Transfer'] == 16
        assert source.get_frame(0).props['DolbyVisionRPU'] == b'original-source-evidence'
        print('OK')
        """
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_native_still_tonemap_is_independent_of_request_history() -> None:
    if not bool(detect_plugins(vs.core).get("libplacebo")):
        if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
            pytest.fail("libplacebo required for still-image native proof")
        pytest.skip("libplacebo unavailable for still-image native proof")
    from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime

    if not probe_libplacebo_runtime():
        if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
            pytest.fail("libplacebo/Vulkan runtime required for still-image native proof")
        pytest.skip("libplacebo/Vulkan runtime unavailable for still-image native proof")
    result = _run_vs_script(
        """
        import gc
        import hashlib
        from dataclasses import asdict
        import numpy as np
        import vapoursynth as vs
        from frame_compare.vs.env import ensure_vs_environment
        from frame_compare.vs.tonemap_libplacebo import apply_libplacebo
        from frame_compare.vs.types import TonemapSettings, TonemapResult

        core=ensure_vs_environment();core.num_threads=4
        peaks=[180,260,225,210,245,200,230,190,250]
        source=core.std.BlankClip(width=64,height=32,format=vs.RGB48,length=len(peaks))
        def fill(n,f):
            f=f.copy()
            lum=np.linspace(.18,peaks[n],64)[None,:]
            for p,factor in enumerate([1.,.8,.6]):
                x=(lum*factor/10000)**(2610/16384)
                pq=((3424/4096+2413/128*x)/(1+2392/128*x))**(2523/32)
                np.copyto(np.asarray(f[p]),np.broadcast_to(np.rint(pq*65535).astype(np.uint16),(32,64)))
            return f
        source=source.std.ModifyFrame(clips=source,selector=fill).std.SetFrameProps(
            _Matrix=0,_Transfer=16,_Primaries=9,_Range=1,
            MasteringDisplayMinLuminance=.0001,MasteringDisplayMaxLuminance=1000.0,
            ContentLightLevelMax=1000.0,ContentLightLevelAverage=100.0)
        settings=TonemapSettings();unchanged=asdict(settings)
        histories=[[2],[0,2],list(range(9)),list(reversed(range(9))),[8,2,1,2,0,2]]
        results={}
        for history in histories:
            result=apply_libplacebo(source,settings,core,still_image=True)
            assert isinstance(result,TonemapResult)
            assert result.applied.transform.frame_policy == 'independent_frames'
            assert result.clip.num_frames == source.num_frames
            assert result.clip.fps == source.fps
            for n in history:
                f=result.clip.get_frame(n)
                h=hashlib.sha256(np.stack([np.asarray(f[i]) for i in range(3)]).tobytes()).hexdigest()
                assert n not in results or results[n] == h
                results[n]=h
            del result;gc.collect()
        result=apply_libplacebo(source,settings,core,still_image=True)
        futures=[result.clip.get_frame_async(n) for n in [8,2,1,2,0,2]]
        for n,future in zip([8,2,1,2,0,2],futures):
            f=future.result()
            assert hashlib.sha256(np.stack([np.asarray(f[i]) for i in range(3)]).tobytes()).hexdigest() == results[n]
        assert asdict(settings) == unchanged
        print('OK')
        """,
        timeout=90,
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_native_reference_knee_changes_libplacebo_output() -> None:
    """The reference knee differs from an explicit BT.2390 knee of 0.5."""
    _require_native_libplacebo_still_runtime()
    result = _run_vs_script(
        """
        from dataclasses import replace

        import numpy as np
        import vapoursynth as vs

        from frame_compare.config.loader import get_default_config
        from frame_compare.config.schema import TonemapPreset
        from frame_compare.render.prepare import resolve_tonemap_settings
        from frame_compare.vs.env import ensure_vs_environment
        from frame_compare.vs.tonemap_libplacebo import apply_libplacebo
        from frame_compare.vs.types import TonemapResult

        core = ensure_vs_environment()
        core.num_threads = 4
        config = get_default_config()

        def resolved_settings(preset):
            color = config.color.model_copy(update={"preset": preset})
            return resolve_tonemap_settings(config.model_copy(update={"color": color}))

        reference_settings = resolved_settings(TonemapPreset.REFERENCE)
        old_knee_settings = replace(reference_settings, knee_offset=0.5)
        assert reference_settings.knee_offset == 1.0
        assert old_knee_settings.knee_offset == 0.5

        width, height = 256, 16
        source = core.std.BlankClip(width=width, height=height, format=vs.RGB48, length=1)

        def fill(n, f):
            frame = f.copy()
            nits = np.linspace(100.0, 4000.0, width)
            encoded = (nits / 10000.0) ** (2610 / 16384)
            pq = ((3424 / 4096 + 2413 / 128 * encoded)
                  / (1 + 2392 / 128 * encoded)) ** (2523 / 32)
            codes = np.rint(pq * 65535).astype(np.uint16)
            ramp = np.broadcast_to(codes, (height, width))
            for plane in range(3):
                np.copyto(np.asarray(frame[plane]), ramp)
            return frame

        source = source.std.ModifyFrame(clips=source, selector=fill).std.SetFrameProps(
            _Range=1,
            _Matrix=0,
            _Primaries=9,
            _Transfer=16,
            ContentLightLevelMax=4000,
            ContentLightLevelAverage=2000,
            MasteringDisplayMinLuminance=0.005,
            MasteringDisplayMaxLuminance=4000.0,
        )

        reference = apply_libplacebo(
            source, reference_settings, core, still_image=True
        )
        old_knee = apply_libplacebo(
            source, old_knee_settings, core, still_image=True
        )
        assert isinstance(reference, TonemapResult)
        assert isinstance(old_knee, TonemapResult)

        def quantized_rgb(result):
            frame = result.clip.get_frame(0)
            planes = [np.asarray(frame[plane]) for plane in range(3)]
            return np.rint(np.clip(np.stack(planes, axis=-1), 0.0, 1.0) * 255).astype(
                np.uint8
            )

        reference_rgb = quantized_rgb(reference)
        old_knee_rgb = quantized_rgb(old_knee)
        assert not np.array_equal(reference_rgb, old_knee_rgb)
        reference_white = np.all(reference_rgb == 255, axis=-1).sum()
        old_knee_white = np.all(old_knee_rgb == 255, axis=-1).sum()
        assert reference_white < old_knee_white
        print("OK")
        """,
        timeout=90,
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_native_pq_patch_reaches_srgb_once() -> None:
    if not bool(detect_plugins(vs.core).get("libplacebo")):
        if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
            pytest.fail("libplacebo required for native sRGB patch proof")
        pytest.skip("libplacebo unavailable for native sRGB patch proof")
    from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime

    if not probe_libplacebo_runtime():
        if os.environ.get("FRAME_COMPARE_REQUIRE_LIBPLACEBO") == "1":
            pytest.fail("libplacebo/Vulkan runtime required for native sRGB patch proof")
        pytest.skip("libplacebo/Vulkan runtime unavailable for native sRGB patch proof")
    result = _run_vs_script(
        """
        import numpy as np
        import vapoursynth as vs
        from frame_compare.vs.env import ensure_vs_environment
        from frame_compare.vs.tonemap_libplacebo import apply_libplacebo
        from frame_compare.vs.types import TonemapSettings, TonemapResult

        core=ensure_vs_environment()
        patches=np.array([[0,0,0],[32,32,32],[64,64,64],[128,128,128],
                          [192,128,64],[64,192,128],[128,64,192],[255,255,255]])/255
        linear=np.where(patches<=.04045,patches/12.92,((patches+.055)/1.055)**2.4)
        # Independent D65 standard-primary matrices, not product conversion code.
        def matrix(prim):
            xyz=np.array([[x/y,1,(1-x-y)/y] for x,y in prim]).T
            white=np.array([.3127/.329,1,(1-.3127-.329)/.329])
            return xyz@np.diag(np.linalg.solve(xyz,white))
        m709=matrix([(.64,.33),(.30,.60),(.15,.06)])
        m2020=matrix([(.708,.292),(.170,.797),(.131,.046)])
        forward=np.linalg.solve(m2020,m709)
        nits=(.18+99.82*linear)@forward.T
        x=(nits/10000)**(2610/16384)
        codes=np.floor(((3424/4096+2413/128*x)/(1+2392/128*x))**(2523/32)*65535+.5).astype(np.uint16)
        source=core.std.BlankClip(width=8*len(patches),height=16,format=vs.RGB48,length=1)
        def fill(n,f):
            f=f.copy()
            for i in range(3):np.copyto(np.asarray(f[i]),np.tile(np.repeat(codes[:,i],8),(16,1)))
            return f
        source=source.std.ModifyFrame(clips=source,selector=fill).std.SetFrameProps(
            _Range=1,_Matrix=0,_Primaries=9,_Transfer=16,ContentLightLevelMax=100.0,
            MasteringDisplayMinLuminance=.18,MasteringDisplayMaxLuminance=100.0,
            MasteringDisplayPrimariesX=[.708,.170,.131],MasteringDisplayPrimariesY=[.292,.797,.046],
            MasteringDisplayWhitePointX=.3127,MasteringDisplayWhitePointY=.329)
        result=apply_libplacebo(source,TonemapSettings(source_peak=100,dynamic_peak_detection=False,
            metadata=2,use_dovi=False,gamut_mapping=0,contrast_recovery=0),core,still_image=True)
        assert isinstance(result,TonemapResult)
        # Return oracle starts from quantized PQ inputs to include input error.
        power=(codes.astype(float)/65535)**(32/2523)
        decoded=10000*(np.maximum(power-3424/4096,0)/(2413/128-2392/128*power))**(16384/2610)
        relative=np.clip((decoded@np.linalg.inv(forward).T-.18)/99.82,0,1)
        expected=np.where(relative<=.0031308,12.92*relative,1.055*relative**(1/2.4)-.055)
        f=result.clip.get_frame(0)
        actual=np.array([[float(f[i][8,j*8+4]) for i in range(3)] for j in range(len(patches))])
        assert np.max(np.abs(np.floor(actual*255+.5)-np.floor(expected*255+.5))) <= 1
        # A second correction would move the middle-gray/colored goldens by2–3 codes.
        assert f.props['_Transfer'] == 13 and f.props['_Primaries'] == 1
        assert source.get_frame(0).props['_Transfer'] == 16
        print('OK')
        """
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_native_fast_still_product_path_matches_fresh_reference_and_order_control() -> None:
    """Fast stills reuse one stateless node; detection-on remains order-sensitive."""
    _require_native_libplacebo_still_runtime()
    result = _run_vs_script(
        """
        import hashlib
        import numpy as np
        import vapoursynth as vs

        from frame_compare.config.schema_enums import TonemapSpeed
        from frame_compare.vs import TonemapSettings, apply_tonemap
        from frame_compare.vs.env import ensure_vs_environment
        from frame_compare.vs.tonemap_conversion import resolve_hdr_tonemap_inputs
        from frame_compare.vs.tonemap_libplacebo import apply_libplacebo
        from frame_compare.vs.tonemap_libplacebo import build_libplacebo_tonemap_kwargs

        core = ensure_vs_environment()
        core.num_threads = 4
        peaks = [180 + 18 * n for n in range(12)]
        source = core.std.BlankClip(
            width=64, height=32, format=vs.RGB48, length=len(peaks)
        )

        def fill(n, f):
            frame = f.copy()
            luminance = np.linspace(0.18, peaks[n], 64)[None, :]
            for plane, factor in enumerate((1.0, 0.8, 0.6)):
                encoded = (luminance * factor / 10000) ** (2610 / 16384)
                encoded = ((3424 / 4096 + 2413 / 128 * encoded)
                           / (1 + 2392 / 128 * encoded)) ** (2523 / 32)
                np.copyto(
                    np.asarray(frame[plane]),
                    np.broadcast_to(
                        np.rint(encoded * 65535).astype(np.uint16), (32, 64)
                    ),
                )
            return frame

        source = source.std.ModifyFrame(clips=source, selector=fill).std.SetFrameProps(
            _Matrix=0,
            _Transfer=16,
            _Primaries=9,
            _Range=1,
            MasteringDisplayMinLuminance=0.0001,
            MasteringDisplayMaxLuminance=1000.0,
            ContentLightLevelMax=1000.0,
            ContentLightLevelAverage=100.0,
        )
        settings = TonemapSettings(
            tonemap_speed=TonemapSpeed.FAST,
            dynamic_peak_detection=False,
            use_dovi=False,
        )

        def digest(frame):
            return hashlib.sha256(
                np.stack([np.asarray(frame[plane]) for plane in range(3)]).tobytes()
            ).hexdigest()

        # Each call creates a fresh native node.  Keep the kwargs comparison explicit so
        # equality is not accidentally established by different source-peak resolution.
        shared_kwargs = build_libplacebo_tonemap_kwargs(
            settings=settings,
            target_nits=settings.target_nits,
            inputs=resolve_hdr_tonemap_inputs(source, None),
        )
        reference = {}
        for n in range(len(peaks)):
            assert build_libplacebo_tonemap_kwargs(
                settings=settings,
                target_nits=settings.target_nits,
                inputs=resolve_hdr_tonemap_inputs(source[n : n + 1], None),
            ) == shared_kwargs
            fresh = apply_libplacebo(
                source[n : n + 1], settings, core, None, still_image=True
            )
            assert fresh.applied is not None
            assert fresh.applied.transform.frame_policy == "shared_stateless"
            reference[n] = digest(fresh.clip.get_frame(0))
        assert len(set(reference.values())) > 1

        orders = {
            "forward": list(range(len(peaks))),
            "reverse": list(reversed(range(len(peaks)))),
            "sparse": [0, 3, 6, 9, 11],
        }
        for order in orders.values():
            fast = apply_tonemap(source, settings, None, still_image=True)
            assert fast.applied is not None
            assert fast.applied.transform.frame_policy == "shared_stateless"
            observed = {n: digest(fast.clip.get_frame(n)) for n in order}
            assert observed == {n: reference[n] for n in order}

        # Negative control: a shared node with dynamic detection is expected to carry history.
        detected = TonemapSettings(dynamic_peak_detection=True, use_dovi=False)

        def render_detected(order):
            sequence = apply_tonemap(source, detected, None, still_image=False)
            assert sequence.applied is not None
            assert sequence.applied.transform.frame_policy == "sequence"
            return {n: digest(sequence.clip.get_frame(n)) for n in order}

        forward = render_detected(orders["forward"])
        reverse = render_detected(orders["reverse"])
        assert any(forward[n] != reverse[n] for n in range(len(peaks)))
        print("OK")
        """,
        timeout=180,
    )
    _assert_vs_process_ok(result)


@pytest.mark.vs_required
def test_native_fast_still_rpu_and_hdr_metadata_variation_is_order_independent() -> None:
    """Fast stills preserve independent per-frame RPU and HDR/scene metadata."""
    _require_native_libplacebo_still_runtime()
    result = _run_vs_script(
        f"""
        RPU_VALID = {_RPU_VALID_HEVC_UNSPEC62!r}
        RPU_MALFORMED = {_RPU_MALFORMED!r}

        import hashlib
        import numpy as np
        import vapoursynth as vs

        from frame_compare.config.schema_enums import TonemapSpeed
        from frame_compare.vs import TonemapSettings, apply_tonemap
        from frame_compare.vs.env import ensure_vs_environment
        from frame_compare.vs.tonemap_conversion import resolve_hdr_tonemap_inputs
        from frame_compare.vs.tonemap_libplacebo import apply_libplacebo
        from frame_compare.vs.tonemap_libplacebo import build_libplacebo_tonemap_kwargs

        core = ensure_vs_environment()
        core.num_threads = 4
        frame_count = 6
        base = core.std.BlankClip(
            width=64,
            height=32,
            format=vs.RGB48,
            length=frame_count,
            color=[30000, 30000, 30000],
        ).std.SetFrameProps(
            _Matrix=0,
            _Transfer=16,
            _Primaries=9,
            _Range=1,
            MasteringDisplayMinLuminance=0.0001,
            MasteringDisplayMaxLuminance=1000.0,
            ContentLightLevelAverage=100.0,
        )
        rpus = [RPU_VALID, None, RPU_MALFORMED, RPU_VALID, None, RPU_VALID]
        max_cll = [400.0, 800.0, 1600.0, 400.0, 800.0, 1600.0]
        frames = []
        for n, rpu in enumerate(rpus):
            frame = base[n : n + 1].std.SetFrameProps(
                ContentLightLevelMax=max_cll[n],
                PLSceneMax=[max_cll[n]],
                PLSceneAvg=[max_cll[n] / 2],
            )
            if rpu is not None:
                frame = frame.std.SetFrameProps(DolbyVisionRPU=rpu)
            frames.append(frame)
        source = core.std.Splice(frames)
        settings = TonemapSettings(
            source_peak=1000,
            tonemap_speed=TonemapSpeed.FAST,
            dynamic_peak_detection=False,
            use_dovi=True,
        )

        def digest(frame):
            return hashlib.sha256(
                np.stack([np.asarray(frame[plane]) for plane in range(3)]).tobytes()
            ).hexdigest()

        shared_kwargs = build_libplacebo_tonemap_kwargs(
            settings=settings,
            target_nits=settings.target_nits,
            inputs=resolve_hdr_tonemap_inputs(source, None),
        )
        reference = {{}}
        for n in range(frame_count):
            assert build_libplacebo_tonemap_kwargs(
                settings=settings,
                target_nits=settings.target_nits,
                inputs=resolve_hdr_tonemap_inputs(source[n : n + 1], None),
            ) == shared_kwargs
            fresh = apply_libplacebo(
                source[n : n + 1], settings, core, None, still_image=True
            )
            assert fresh.applied is not None
            assert fresh.applied.transform.frame_policy == "shared_stateless"
            reference[n] = digest(fresh.clip.get_frame(0))

        orders = {{
            "forward": list(range(frame_count)),
            "reverse": list(reversed(range(frame_count))),
            "sparse": [0, 2, 5],
        }}
        for order in orders.values():
            fast = apply_tonemap(source, settings, None, still_image=True)
            assert fast.applied is not None
            assert fast.applied.transform.frame_policy == "shared_stateless"
            observed = {{n: digest(fast.clip.get_frame(n)) for n in order}}
            assert observed == {{n: reference[n] for n in order}}

        # Non-vacuity: the valid RPU is consumed, while the no-RPU control uses the
        # same PQ pixels and static HDR props.
        with_rpu = apply_tonemap(source[0:1], settings, None, still_image=True)
        without_rpu = apply_tonemap(
            source[0:1].std.RemoveFrameProps(props=["DolbyVisionRPU"]),
            settings,
            None,
            still_image=True,
        )
        assert digest(with_rpu.clip.get_frame(0)) != digest(without_rpu.clip.get_frame(0))

        # Independent HDR10/scene metadata control: fixed src_max, differing per-frame
        # metadata still changes native output.
        metadata_frames = [
            base[0:1].std.SetFrameProps(
                ContentLightLevelMax=400.0,
                PLSceneMax=[400.0],
                PLSceneAvg=[200.0],
            ),
            base[0:1].std.SetFrameProps(
                ContentLightLevelMax=4000.0,
                PLSceneMax=[4000.0],
                PLSceneAvg=[2000.0],
            ),
        ]
        metadata_source = core.std.Splice(metadata_frames)
        metadata_settings = TonemapSettings(
            source_peak=1000,
            tonemap_speed=TonemapSpeed.FAST,
            dynamic_peak_detection=False,
            use_dovi=False,
        )
        metadata_result = apply_tonemap(
            metadata_source, metadata_settings, None, still_image=True
        )
        assert digest(metadata_result.clip.get_frame(0)) != digest(
            metadata_result.clip.get_frame(1)
        )
        print("OK")
        """,
        timeout=180,
    )
    _assert_vs_process_ok(result)
