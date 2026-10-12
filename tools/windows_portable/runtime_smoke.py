from __future__ import annotations

import importlib.metadata
import json
import os
import subprocess
import sys
import types
from pathlib import Path


def assert_true(condition: object, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def proof(message: str) -> None:
    print(f"WINDOWS_BUNDLE_PROOF {message}", flush=True)


def prove_package_imports() -> None:
    import frame_compare  # noqa: F401, I001
    import rich  # noqa: F401
    import tomli_w  # noqa: F401
    import typer  # noqa: F401

    proof("package_imports=ok modules=frame_compare,rich,tomli_w,typer")


def prove_vsview_distribution_contract() -> None:
    expected = {
        "jetpytools": "3.1.2",
        "pyside6": "6.11.2",
        "pyside6-addons": "6.11.2",
        "pyside6-essentials": "6.11.2",
        "shiboken6": "6.11.2",
        "vapoursynth-bestsource": "22",
        "vapoursynth-lsmas": "1310.0.0.0",
        "vspackrgb": "2.0.0",
        "vsview": "0.12.1",
        "cyclopts": "5.2.0",
        "vsjetengine": "1.8.0",
    }
    observed = {name: importlib.metadata.version(name) for name in expected}
    assert_true(observed == expected, f"VSView distribution mismatch: {observed}")
    proof(
        "vsview_distributions=ok "
        + ",".join(f"{name}={version}" for name, version in observed.items())
    )


def prove_project_entrypoint_and_panel() -> None:
    from PySide6.QtWidgets import QApplication, QWidget

    import frame_compare

    bundle_root = Path(sys.executable).resolve().parent.parent
    source_root = (bundle_root / "app" / "src" / "frame_compare").resolve()
    package_path = Path(frame_compare.__file__).resolve()
    assert_true(
        package_path.is_relative_to(source_root),
        f"Frame Compare resolved outside app/src: {package_path}",
    )
    assert_true(
        not (bundle_root / "app" / "site-packages" / "frame_compare").exists(),
        "portable bundle contains a duplicate app/site-packages/frame_compare package",
    )

    entry_points = tuple(
        entry_point
        for entry_point in importlib.metadata.entry_points(group="vsview")
        if entry_point.name == "frame-compare-alignment-review"
        and entry_point.value == "frame_compare.vsview.alignment_review_panel"
    )
    assert_true(
        len(entry_points) == 1, f"Frame Compare VSView entry point mismatch: {entry_points}"
    )
    panel_type = getattr(entry_points[0].load(), "AlignmentReviewPanel", None)
    assert_true(
        panel_type is not None, "Frame Compare VSView entry point did not load AlignmentReviewPanel"
    )

    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    panel = panel_type(parent, types.SimpleNamespace(file_path=None))
    assert_true(
        "Inactive" in panel.progress_label.text(),
        "alignment panel is not inert outside a generated session",
    )
    panel.setParent(None)
    parent.deleteLater()
    app.processEvents()
    proof("project_entrypoint=ok source=app/src")
    proof("alignment_panel=ok state=inactive platform=offscreen")


def prove_qt_webengine_excluded() -> None:
    site_packages = Path(sys.executable).resolve().parent.parent / "app" / "site-packages"
    pyside_root = site_packages / "PySide6"
    chromium_runtime_names = {
        "icudtl.dat",
        "v8_context_snapshot.bin",
        "v8_context_snapshot.debug.bin",
    }
    forbidden = [
        path
        for path in pyside_root.rglob("*")
        if path.is_file()
        and (
            "webengine" in str(path.relative_to(pyside_root)).lower()
            or (path.parent.name == "resources" and path.name in chromium_runtime_names)
        )
    ]
    assert_true(not forbidden, f"Qt WebEngine deployment files remain: {forbidden}")
    proof("qt_webengine_runtime=absent deployment=excluded")


def prove_runtime_contract() -> None:
    from frame_compare.utils.subproc import resolve_executable
    from frame_compare.vs.runtime_contract import (
        VS_PLACEBO_RELEASE,
        WINDOWS_FFMPEG_EXECUTABLE_TOKEN,
        media_runtime_fingerprint,
        supported_media_runtime_report,
    )

    expected = media_runtime_fingerprint("full")
    observed = os.environ.get("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", "")
    assert_true(
        observed == expected,
        f"runtime fingerprint mismatch: expected={expected} observed={observed}",
    )
    assert_true(
        os.environ.get("FRAME_COMPARE_RUNTIME_KIND") == "windows-portable", "runtime kind mismatch"
    )
    assert_true(
        os.environ.get("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED") == "0",
        "Windows FFMS2 policy mismatch",
    )
    assert_true(
        importlib.metadata.version("vs-placebo") == VS_PLACEBO_RELEASE,
        "vs-placebo distribution mismatch",
    )

    bundle_root = Path(sys.executable).resolve().parent.parent
    bundled_ffmpeg_bin = os.path.normcase(os.path.normpath(str(bundle_root / "ffmpeg" / "bin")))
    path_entries = {
        os.path.normcase(os.path.normpath(entry))
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
    }
    assert_true(
        bundled_ffmpeg_bin not in path_entries, "standalone FFmpeg directory leaked onto PATH"
    )

    ffmpeg = Path(resolve_executable("ffmpeg")).resolve()
    ffprobe = Path(resolve_executable("ffprobe")).resolve()
    assert_true(
        ffmpeg == (bundle_root / "ffmpeg" / "bin" / "ffmpeg.exe").resolve(),
        f"unexpected FFmpeg path: {ffmpeg}",
    )
    assert_true(
        ffprobe == (bundle_root / "ffmpeg" / "bin" / "ffprobe.exe").resolve(),
        f"unexpected ffprobe path: {ffprobe}",
    )
    version_lines = {
        name: subprocess.check_output(
            [str(executable), "-version"], text=True, timeout=15
        ).splitlines()[0]
        for name, executable in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe))
    }
    for name, version_line in version_lines.items():
        assert_true(
            WINDOWS_FFMPEG_EXECUTABLE_TOKEN in version_line.split(),
            f"unexpected {name} version: {version_line}",
        )
    report = supported_media_runtime_report()
    assert_true(report["fingerprints"]["full"] == expected, "runtime report fingerprint mismatch")
    proof(
        f"runtime_contract=ok fingerprint={expected} "
        f"ffmpeg={version_lines['ffmpeg']} ffprobe={version_lines['ffprobe']}"
    )


def prove_vapoursynth_environment() -> None:
    import vapoursynth as vs

    core = vs.core
    version = getattr(vs, "__version__", None)
    api_version = getattr(vs, "__api_version__", None)
    version_major = getattr(version, "release_major", None)
    version_minor = getattr(version, "release_minor", None)
    api_major = getattr(api_version, "api_major", None)
    api_minor = getattr(api_version, "api_minor", None)
    plugin_dir = Path(vs.get_plugin_dir())
    plugins = list(core.plugins())
    plugin_namespaces = sorted(plugin.namespace for plugin in plugins)

    assert_true(
        version_major == 81 and version_minor == 0, f"expected VapourSynth R81, got {version!r}"
    )
    assert_true(api_major == 4, f"expected VapourSynth API 4, got {api_version!r}")
    assert_true(api_minor == 3, f"expected VapourSynth API minor 3, got {api_version!r}")
    assert_true(
        plugin_dir.is_dir(), f"vapoursynth.get_plugin_dir() is not a directory: {plugin_dir}"
    )
    assert_true(
        "vapoursynth" in str(plugin_dir).replace("\\", "/"), f"unexpected plugin dir: {plugin_dir}"
    )
    canonical_lsmas_plugin = plugin_dir / "LSMASHSource.dll"
    assert_true(
        canonical_lsmas_plugin.is_file(),
        f"canonical L-SMASH plugin missing: {canonical_lsmas_plugin}",
    )
    assert_true(
        "VAPOURSYNTH_EXTRA_PLUGIN_PATH" not in os.environ,
        "VAPOURSYNTH_EXTRA_PLUGIN_PATH should not be set",
    )
    assert_true(
        "VAPOURSYNTH_PLUGIN_PATH" not in os.environ,
        "legacy VAPOURSYNTH_PLUGIN_PATH should not be set",
    )
    assert_true("lsmas" in plugin_namespaces, f"lsmas plugin missing: {plugin_namespaces}")
    assert_true("placebo" in plugin_namespaces, f"placebo plugin missing: {plugin_namespaces}")
    assert_true(
        "ffms2" not in plugin_namespaces, "FFMS2 must remain excluded from the Windows baseline"
    )

    proof(f"vapoursynth_import=ok version=R{version_major} api={api_major}.{api_minor}")
    proof(f"plugin_dir={plugin_dir}")
    proof(f"canonical_lsmas_plugin=ok path={canonical_lsmas_plugin}")
    proof("extra_plugin_path=absent")
    proof(f"core_plugins={','.join(plugin_namespaces)}")


def prove_lwlibavsource(media_path: Path) -> None:
    import vapoursynth as vs

    from frame_compare.vs.env import candidate_lsmas_plugin_path_details, try_load_lsmas_plugin
    from frame_compare.vs.source import load_source, source_index_path

    core = vs.core
    lsmas_loaded_path = None
    if not (hasattr(core, "lsmas") and hasattr(core.lsmas, "LWLibavSource")):
        lsmas_loaded_path = try_load_lsmas_plugin(core)

    assert_true(hasattr(core, "lsmas"), "core.lsmas namespace missing")
    functions = {function.name for function in core.lsmas.functions()}
    assert_true("LWLibavSource" in functions, f"LWLibavSource missing: {sorted(functions)}")
    assert_true("LibavSMASHSource" in functions, f"LibavSMASHSource missing: {sorted(functions)}")

    if media_path.is_file():
        source = load_source(media_path, core=core)
        frame = source.clip.get_frame(0)
        assert_true(frame.width == 64 and frame.height == 64, "LWLibavSource frame render failed")
        assert_true(source.num_frames == 3, f"unexpected source frame count: {source.num_frames}")
        owned_index = source_index_path(media_path)
        assert_true(owned_index.is_file(), f"runtime-specific source index missing: {owned_index}")
        assert_true(
            not Path(f"{media_path}.lwi").exists(), "legacy unversioned source index was created"
        )
    else:
        candidates = [
            {"source": candidate.source, "path": candidate.path}
            for candidate in candidate_lsmas_plugin_path_details()
        ]
        raise AssertionError(f"tiny media proof missing: {media_path}; candidates={candidates}")

    proof(
        f"lwlibavsource=ok namespace=lsmas loaded_path={lsmas_loaded_path} functions={','.join(sorted(functions))}"
    )


def build_placebo_clip():
    import vapoursynth as vs

    core = vs.core
    assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
    assert_true(hasattr(core.placebo, "Tonemap"), "core.placebo.Tonemap missing")

    tonemap_clip = core.std.BlankClip(
        width=16, height=16, format=vs.RGB48, length=1, color=[32768, 32768, 32768]
    )
    tonemap_clip = tonemap_clip.std.SetFrameProps(_Matrix=0, _Range=1, _Transfer=16, _Primaries=9)
    return core.placebo.Tonemap(
        tonemap_clip,
        src_max=1000,
        dst_max=203,
        tone_mapping_function=2,
        dst_csp=0,
        dst_prim=1,
        src_csp=1,
    ), tonemap_clip


def prove_placebo_tonemap_api() -> None:
    import vapoursynth as vs

    core = vs.core
    assert_true(hasattr(core, "placebo"), "core.placebo namespace missing")
    functions = {function.name for function in core.placebo.functions()}
    assert_true("Tonemap" in functions, f"core.placebo.Tonemap missing: {sorted(functions)}")
    proof(f"placebo_tonemap_api=ok namespace=placebo functions={','.join(sorted(functions))}")


def prove_placebo_tonemap_frame() -> bool:
    from frame_compare.vs.tonemap_runtime import probe_libplacebo_runtime

    if not probe_libplacebo_runtime():
        proof("placebo_direct_frame=skipped reason=vulkan_runtime_unavailable")
        return False

    direct_out, _tonemap_clip = build_placebo_clip()
    direct_frame = direct_out.get_frame(0)
    assert_true(
        direct_frame.width == 16 and direct_frame.height == 16, "placebo direct frame render failed"
    )
    assert_true(
        direct_frame.format.bits_per_sample >= 10,
        "placebo unexpectedly reduced output below 10-bit",
    )
    proof(
        f"placebo_direct_frame=ok format={direct_frame.format.name} bits={direct_frame.format.bits_per_sample}"
    )
    return True


def prove_apply_tonemap_frame() -> None:
    import vapoursynth as vs

    from frame_compare.vs.tonemap import _libplacebo_runtime_usable, apply_tonemap
    from frame_compare.vs.types import TonemapSettings

    core = vs.core
    tonemap_clip = core.std.BlankClip(
        width=16, height=16, format=vs.RGB48, length=1, color=[32768, 32768, 32768]
    )
    tonemap_clip = tonemap_clip.std.SetFrameProps(_Matrix=0, _Range=1, _Transfer=16, _Primaries=9)

    libplacebo_runtime_usable = _libplacebo_runtime_usable()
    app_out = apply_tonemap(tonemap_clip, TonemapSettings(enabled=True))
    app_frame = app_out.get_frame(0)
    assert_true(
        app_frame.width == 16 and app_frame.height == 16, "apply_tonemap frame render failed"
    )
    assert_true(
        app_frame.format.bits_per_sample >= 10,
        "apply_tonemap unexpectedly reduced output below 10-bit",
    )

    proof(
        "apply_tonemap=ok "
        f"format={app_frame.format.name} bits={app_frame.format.bits_per_sample} "
        f"fallback_aware=true libplacebo_runtime_usable={str(libplacebo_runtime_usable).lower()}"
    )


def prove_bestsource_frame(media_path: Path) -> None:
    import vapoursynth as vs

    core = vs.core
    assert_true(hasattr(core, "bs"), "core.bs namespace missing")
    source = core.bs.VideoSource(source=str(media_path))
    frame = source.get_frame(0)
    assert_true(frame.width == 64 and frame.height == 64, "BestSource frame render failed")
    proof("bestsource_frame=ok namespace=bs")


def prove_generated_vsview_session(media_path: Path) -> None:
    import vapoursynth as vs  # noqa: I001

    from frame_compare.vsview.alignment_review_contract import (
        AlignmentReviewContractError,
        AlignmentReviewExpectedComparison,
        AlignmentReviewOutputCandidate,
        alignment_review_session_from_script,
        parse_alignment_review_workspace_metadata,
        read_alignment_review_result,
    )
    from frame_compare.vsview.alignment_review_panel import AlignmentReviewPanel
    from frame_compare.vsview.session_script import write_vsview_session_script
    from PySide6.QtWidgets import QApplication, QWidget
    from vsengine.loops import get_loop, set_loop
    from vsview.api import get_outputs
    from vsview.vsenv import QtEventLoop

    cache_dir = media_path.parent / "runtime-smoke-cache"
    comparison_one_media_path = media_path.with_name("runtime-smoke-comparison-1.mp4")
    comparison_two_media_path = media_path.with_name("runtime-smoke-comparison-2.mp4")
    assert_true(
        len({media_path, comparison_one_media_path, comparison_two_media_path}) == 3,
        "generated VSView fixture paths are not distinct",
    )
    script_path = write_vsview_session_script(
        reference=media_path,
        comparisons=[comparison_one_media_path, comparison_two_media_path],
        suggested_offsets_by_key={
            f"{media_path.stem}:{comparison_one_media_path.stem}": 0,
            f"{media_path.stem}:{comparison_two_media_path.stem}": 0,
        },
        audio_review_by_key={
            key: json.dumps(
                {
                    "current_authority": {
                        "origin": "shared_computed_offsets",
                        "frame_offset": 0,
                    },
                    "evidence_availability": "historical_details_unavailable",
                    "audio_attempt": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            for key in (
                f"{media_path.stem}:{comparison_one_media_path.stem}",
                f"{media_path.stem}:{comparison_two_media_path.stem}",
            )
        },
        cache_dir=cache_dir,
        frame_props_by_stem={
            media_path.stem: {"_Matrix": 2, "_Range": 2},
            comparison_one_media_path.stem: {"_Matrix": 2, "_Range": 2},
            comparison_two_media_path.stem: {"_Matrix": 2, "_Range": 2},
        },
    )
    script_text = script_path.read_text(encoding="utf-8")
    assert_true(
        "Color metadata incomplete; using standard display defaults (BT.709)" in script_text,
        "generated VSView session omitted BT.709 preview defaults",
    )
    script_module = types.ModuleType("__vsview__")
    script_module.__file__ = str(script_path)
    sys.modules["__vsview__"] = script_module
    try:
        exec(compile(script_text, str(script_path), "exec"), script_module.__dict__)
        outputs = get_outputs()
        names = [output.name for output in outputs.values()]
        assert_true(
            names == ["Reference", "Comparison 1", "Comparison 2"],
            f"unexpected VSView outputs: {names}",
        )
        assert_true(
            sorted(vs.get_outputs()) == [0, 1, 2],
            "generated session did not register outputs 0, 1, and 2",
        )
        for output in vs.get_outputs().values():
            frame = output.clip.get_frame(0)
            assert_true(frame.width == 64 and frame.height == 64, "generated VSView output failed")

        session = alignment_review_session_from_script(script_path, require_result_absent=True)
        candidates = tuple(
            AlignmentReviewOutputCandidate(
                output_id=output_id,
                source_frame_count=vs_output.clip.num_frames,
                metadata=outputs[output_id].kwargs,
            )
            for output_id, vs_output in sorted(vs.get_outputs().items())
        )
        workspace = parse_alignment_review_workspace_metadata(candidates)
        assert_true(
            workspace.session_id == session.session_id, "generated output/session identities differ"
        )
        expected = tuple(
            AlignmentReviewExpectedComparison(
                pair.comparison_key,
                workspace.reference.source_frame_count,
                pair.source_frame_count,
            )
            for pair in workspace.comparisons
        )

        class Timeline:
            def clear_notches(self, *_args, **_kwargs):
                return None

            def add_notch(self, *_args, **_kwargs):
                return None

        voutputs = [
            types.SimpleNamespace(
                vs_index=index,
                vs_output=output,
                kwargs=outputs[index].kwargs,
            )
            for index, output in sorted(vs.get_outputs().items())
        ]
        panel_api = types.SimpleNamespace(
            file_path=script_path,
            voutputs=voutputs,
            current_voutput=voutputs[0],
            current_frame=1,
            timeline=Timeline(),
        )
        app = QApplication.instance() or QApplication([])
        previous_loop = get_loop()
        set_loop(QtEventLoop(app))
        try:
            active_parent = QWidget()
            active_panel = AlignmentReviewPanel(active_parent, panel_api)
            active_panel.on_workspace_loaded()
            app.processEvents()
            assert_true(
                active_panel.progress_label.text() == "0/3 positions captured",
                "alignment panel did not start with an empty three-source lineup",
            )
            for output_index, frame in enumerate((1, 0, 2)):
                panel_api.current_voutput = voutputs[output_index]
                panel_api.current_frame = frame
                active_panel.on_current_voutput_changed(voutputs[output_index], output_index)
                app.processEvents()
            assert_true(
                active_panel.progress_label.text()
                == "3/3 positions captured \u2014 ready to confirm",
                "alignment panel did not record every source position",
            )
            assert_true(
                active_panel.use_positions_button.isEnabled(),
                "alignment positions action did not become ready for the whole set",
            )
            active_panel.use_positions_button.click()
            app.processEvents()
            observed_result = read_alignment_review_result(session, expected)
            assert_true(
                [decision.action for decision in observed_result.decisions]
                == ["confirmed", "confirmed"],
                "alignment positions action did not write complete confirmed decisions",
            )
            proof("alignment_positions=ok")

            session.result_path.unlink()
            keep_parent = QWidget()
            keep_panel = AlignmentReviewPanel(keep_parent, panel_api)
            keep_panel.on_workspace_loaded()
            app.processEvents()
            keep_panel.keep_button.click()
            app.processEvents()
            observed_result = read_alignment_review_result(session, expected)
            assert_true(
                [decision.action for decision in observed_result.decisions]
                == ["keep_current", "keep_current"],
                "keep-audio action did not write one decision per comparison",
            )
            proof("alignment_keep_current=ok")
        finally:
            set_loop(previous_loop)

        proof(
            "alignment_metadata=ok outputs=Reference,Comparison_1,Comparison_2 "
            "topology=one_reference_ordered_comparisons"
        )
        proof("alignment_result_roundtrip=ok")
        session.result_path.write_text("{}\n", encoding="utf-8")
        try:
            read_alignment_review_result(session, expected)
        except AlignmentReviewContractError:
            pass
        else:
            raise AssertionError("malformed alignment result was accepted")
        proof("alignment_result_validation=ok malformed=rejected")
    finally:
        sys.modules.pop("__vsview__", None)
        vs.clear_outputs()
        if "session" in locals():
            session.result_path.unlink(missing_ok=True)
    proof(
        "generated_vsview_session=ok outputs=Reference,Comparison_1,Comparison_2 color_defaults=BT709"
    )


def prove_vsview_runtime(media_path: Path) -> None:
    from frame_compare.vsview.launcher import preload_vapoursynth_runtime

    preload_vapoursynth_runtime()
    proof("vsview_runtime_preload=ok")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    QTimer.singleShot(0, app.quit)
    assert_true(app.exec() == 0, "controlled Qt event loop failed")
    proof("pyside6_event_loop=ok platform=offscreen")

    import vspackrgb.rust  # noqa: F401, I001
    import vsview  # noqa: F401
    import vsview.app.main  # noqa: F401
    import vsview.cli  # noqa: F401
    from vsview import set_output  # noqa: F401

    proof("vsview_deep_imports=ok modules=vsview.app.main,vsview.cli,vspackrgb.rust")
    site_packages = Path(sys.executable).resolve().parent.parent / "app" / "site-packages"
    qt_ffmpeg_dlls = [
        site_packages / "PySide6" / name
        for name in ("avcodec-61.dll", "avformat-61.dll", "avutil-59.dll")
    ]
    assert_true(
        all(path.is_file() for path in qt_ffmpeg_dlls),
        f"Qt FFmpeg DLL set incomplete: {qt_ffmpeg_dlls}",
    )
    proof("qt_ffmpeg_runtime=ok lineage=7.1.5 dlls=avcodec-61,avformat-61,avutil-59")
    prove_qt_webengine_excluded()
    prove_vsview_distribution_contract()
    prove_project_entrypoint_and_panel()
    prove_runtime_contract()
    prove_vapoursynth_environment()
    prove_bestsource_frame(media_path)
    prove_lwlibavsource(media_path)
    prove_generated_vsview_session(media_path)
    prove_placebo_tonemap_api()
    prove_apply_tonemap_frame()
    prove_placebo_tonemap_frame()
    proof("vsview_runtime=ok")


phase = sys.argv[1]
media_path = Path(sys.argv[2])
if phase == "package_imports":
    prove_package_imports()
elif phase == "runtime_contract":
    prove_runtime_contract()
elif phase == "vapoursynth_environment":
    prove_vapoursynth_environment()
elif phase == "lwlibavsource_frame":
    prove_lwlibavsource(media_path)
elif phase == "placebo_tonemap_api":
    prove_placebo_tonemap_api()
elif phase == "apply_tonemap_frame":
    prove_apply_tonemap_frame()
elif phase == "placebo_tonemap_frame":
    prove_placebo_tonemap_frame()
elif phase == "vsview_runtime":
    prove_vsview_runtime(media_path)
else:
    raise AssertionError(f"unknown runtime proof phase: {phase}")
