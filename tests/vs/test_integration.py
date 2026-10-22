"""Integration tests for VapourSynth module."""

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Skip if VapourSynth is not installed
vs = pytest.importorskip("vapoursynth")

# Skip if VapourSynth is mocked (e.g. by test_exports.py running first in a no-VS env)
if isinstance(vs, MagicMock) or hasattr(vs, "_mock_methods"):
    pytest.skip("VapourSynth is mocked, skipping integration test", allow_module_level=True)

from frame_compare.vs import (  # noqa: E402
    detect_plugins,
    is_vapoursynth_available,
)
from frame_compare.vs.env import ensure_vs_environment  # noqa: E402
from frame_compare.vs.loader import DefaultVSLoader  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]


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
