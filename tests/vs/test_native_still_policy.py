"""Experimental native-still identity, routing and safety-cache boundaries."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import pytest
import vapoursynth as vs

from frame_compare.vs import tonemap_libplacebo, tonemap_runtime
from frame_compare.vs.errors import TonemapError


def _reviewed_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    binary = tmp_path / "libvs_placebo.dll"
    binary.write_bytes(b"reviewed-test-build")
    monkeypatch.setattr(
        tonemap_runtime,
        "EXPERIMENTAL_NATIVE_STILL_BUILD",
        replace(
            tonemap_runtime.EXPERIMENTAL_NATIVE_STILL_BUILD,
            sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        ),
    )
    plugin = SimpleNamespace(
        identifier="com.vs.placebo", namespace="placebo", plugin_path=str(binary)
    )
    function = Mock(return_value=SimpleNamespace(result="native"))
    function.plugin = plugin
    function.signature = "clip:vnode;independent:int:opt;"
    return SimpleNamespace(placebo=SimpleNamespace(Tonemap=function))


def _rgb48() -> SimpleNamespace:
    return SimpleNamespace(
        width=64,
        height=32,
        format=SimpleNamespace(
            id=vs.RGB48,
            color_family=vs.RGB,
            sample_type=vs.INTEGER,
            bits_per_sample=16,
            num_planes=3,
            subsampling_w=0,
            subsampling_h=0,
        ),
    )


@pytest.mark.parametrize("value", ["0", "true", "yes", " 1", "1 ", "secret-value"])
def test_invalid_native_still_opt_in_is_typed_and_does_not_echo_value(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS", value)
    with pytest.raises(TonemapError) as error:
        tonemap_runtime.experimental_native_stills_enabled()
    assert error.value.code == "FC-4003"
    assert error.value.hint and "Unset" in error.value.hint
    assert value not in error.value.context.message


def test_native_still_opt_in_is_default_off_and_rechecked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS", raising=False)
    assert not tonemap_runtime.experimental_native_stills_enabled()
    monkeypatch.setenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS", "1")
    assert tonemap_runtime.experimental_native_stills_enabled()
    monkeypatch.setenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS", "")
    assert not tonemap_runtime.experimental_native_stills_enabled()


@pytest.mark.parametrize(
    "violation",
    [
        "old_signature",
        "substring_signature",
        "forced_id",
        "forced_namespace",
        "unknown_binary",
        "missing_path",
        "relative_path",
        "missing_function_plugin",
    ],
)
def test_native_still_capability_requires_bound_identity_and_reviewed_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, violation: str
) -> None:
    core = _reviewed_plugin(tmp_path, monkeypatch)
    assert tonemap_runtime.experimental_native_still_plugin(core) is not None
    function = core.placebo.Tonemap
    if violation == "old_signature":
        function.signature = "clip:vnode;"
    elif violation == "substring_signature":
        function.signature = "clip:vnode;not_independent:int:opt;"
    elif violation == "forced_id":
        function.plugin.identifier = "experiment.followup"
    elif violation == "forced_namespace":
        function.plugin.namespace = "followup"
    elif violation == "unknown_binary":
        Path(function.plugin.plugin_path).write_bytes(b"unreviewed")
    elif violation == "missing_path":
        function.plugin.plugin_path = str(tmp_path / "absent.dll")
    elif violation == "relative_path":
        function.plugin.plugin_path = "libvs_placebo.dll"
    else:
        function.plugin = None
    assert tonemap_runtime.experimental_native_still_plugin(core) is None


@pytest.mark.parametrize(
    "case",
    [
        "off",
        "old_plugin",
        "hlg",
        "native_dovi",
        "unknown_csp",
        "hdr_destination",
        "el_none",
        "variable_format",
        "variable_size",
        "float",
        "subsampled",
        "admitted_rpu",
    ],
)
def test_still_routing_preserves_supported_fresh_path_and_native_kwargs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    core = _reviewed_plugin(tmp_path, monkeypatch)
    monkeypatch.setenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS", "1")
    clip = _rgb48()
    kwargs: dict[str, object] = {
        "src_csp": 1,
        "dst_csp": 0,
        "metadata": 0,
        "use_dovi": 1,
        "smoothing_period": 45.0,
        "contrast_recovery": 0.3,
    }
    unchanged = dict(kwargs)
    if case == "off":
        monkeypatch.delenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS")
    elif case == "old_plugin":
        core.placebo.Tonemap.signature = "clip:vnode;"
    elif case == "hlg":
        kwargs["src_csp"] = 2
    elif case == "native_dovi":
        kwargs["src_csp"] = 3
    elif case == "unknown_csp":
        kwargs.pop("src_csp")
    elif case == "hdr_destination":
        kwargs["dst_csp"] = 1
    elif case == "el_none":
        kwargs["dovi_el"] = None
    elif case == "variable_format":
        clip.format = None
    elif case == "variable_size":
        clip.width = 0
    elif case == "float":
        clip.format.sample_type = vs.FLOAT
    elif case == "subsampled":
        clip.format.subsampling_w = 1
    original_kwargs = dict(kwargs)
    legacy = Mock(return_value=SimpleNamespace(result="fresh"))
    monkeypatch.setattr(tonemap_libplacebo, "_independent_frame_tonemap", legacy)
    result = tonemap_libplacebo._still_frame_tonemap(
        cast("vs.VideoNode", clip), cast("vs.Core", core), kwargs
    )
    assert kwargs == original_kwargs
    if case == "admitted_rpu":
        assert result is core.placebo.Tonemap.return_value
        core.placebo.Tonemap.assert_called_once_with(clip, **unchanged, independent=1)
        legacy.assert_not_called()
    else:
        assert result is legacy.return_value
        legacy.assert_called_once_with(clip, core, original_kwargs)
        core.placebo.Tonemap.assert_not_called()


def test_native_constructor_failure_is_not_retried_as_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = _reviewed_plugin(tmp_path, monkeypatch)
    core.placebo.Tonemap.side_effect = RuntimeError("native constructor")
    monkeypatch.setenv("FRAME_COMPARE_EXPERIMENTAL_NATIVE_STILLS", "1")
    legacy = Mock()
    monkeypatch.setattr(tonemap_libplacebo, "_independent_frame_tonemap", legacy)
    with pytest.raises(RuntimeError, match="native constructor"):
        tonemap_libplacebo._still_frame_tonemap(
            cast("vs.VideoNode", _rgb48()), cast("vs.Core", core), {"src_csp": 1, "dst_csp": 0}
        )
    assert core.placebo.Tonemap.call_count == 1
    legacy.assert_not_called()


def test_safety_cache_does_not_authorize_a_different_loaded_plugin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in (
        "FRAME_COMPARE_REQUIRE_LIBPLACEBO",
        "FRAME_COMPARE_DISABLE_LIBPLACEBO",
        "FRAME_COMPARE_LIBPLACEBO_PROBE",
    ):
        monkeypatch.delenv(name, raising=False)
    state = tonemap_runtime.LibplaceboRuntimeState()
    first = tonemap_runtime.LibplaceboPluginIdentity("first.dll", "a" * 64)
    second = tonemap_runtime.LibplaceboPluginIdentity("second.dll", "a" * 64)
    probe = Mock(side_effect=[True, False, True])
    assert tonemap_runtime.libplacebo_runtime_usable(state, probe, plugin_identity=first)
    assert tonemap_runtime.libplacebo_runtime_usable(state, probe, plugin_identity=first)
    assert not tonemap_runtime.libplacebo_runtime_usable(state, probe, plugin_identity=second)
    assert tonemap_runtime.libplacebo_runtime_usable(state, probe)
    assert probe.call_count == 3


@pytest.mark.parametrize(
    "receipt_case", ["matching", "missing", "wrong_hash", "wrong_path", "nonobject"]
)
def test_experimental_safety_child_must_confirm_loaded_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, receipt_case: str
) -> None:
    identity = tonemap_runtime.LibplaceboPluginIdentity(str(tmp_path / "selected.dll"), "a" * 64)
    receipt: object = {"path": identity.path, "sha256": identity.sha256}
    if receipt_case == "wrong_hash":
        receipt = {"path": identity.path, "sha256": "b" * 64}
    elif receipt_case == "wrong_path":
        receipt = {"path": str(tmp_path / "stock.dll"), "sha256": identity.sha256}
    elif receipt_case == "nonobject":
        receipt = []
    stdout = "" if receipt_case == "missing" else json.dumps(receipt)
    child = Mock(return_value=subprocess.CompletedProcess([], 0, stdout, ""))
    monkeypatch.setattr(tonemap_runtime.subprocess, "run", child)
    assert tonemap_runtime.probe_libplacebo_runtime(plugin_identity=identity) is (
        receipt_case == "matching"
    )
    script = child.call_args.args[0][-1]
    assert "plugin.identifier" in script and "function.signature.split" in script
    compile(script, "probe", "exec")
