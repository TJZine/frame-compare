"""Persisted probe facts require current, strong source and runtime authority."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import frame_compare.orchestration.probing.probe_cache as probe_cache
import frame_compare.vs.source_admission as admission
from frame_compare.analysis.errors import MetricsCalculationError
from frame_compare.orchestration import preparation
from frame_compare.orchestration.types import RunDependencies
from frame_compare.vs.errors import SourceLoadError
from frame_compare.vs.types import HDRMetadata, SourceInfo
from tests.orchestration.execute_run_helpers import FakeVSLoader
from tests.orchestration.preparation_test_support import (
    METRIC_CONFIG,
    create_config,
    create_video_files,
)
from tests.run_request_support import make_run_request


class RecordingLoader(FakeVSLoader):
    def __init__(self, *, hdr: bool = False) -> None:
        self.calls = 0
        self.hdr = hdr

    def load(self, path: Path) -> SourceInfo:
        self.calls += 1
        source = super().load(path)
        if not self.hdr:
            return replace(source, width=1280, height=720, frame_props={"_Transfer": 1})
        return replace(
            source,
            is_hdr=True,
            hdr_metadata=HDRMetadata(
                mastering_display="fixture",
                max_cll=1000,
                max_fall=400,
                color_primaries=9,
                transfer=16,
                matrix=9,
            ),
            frame_props={"_Transfer": 16, "DolbyVisionRPU": b"rpu"},
        )


def _run(root: Path, loader: FakeVSLoader):
    return asyncio.run(
        preparation.execute_prep(make_run_request(root=root), RunDependencies(vs_loader=loader))
    )


def _replace_same_stats(path: Path, *, in_place: bool) -> None:
    before = path.stat()
    if in_place:
        path.write_bytes(b"other")
    else:
        replacement = path.with_name("replacement")
        replacement.write_bytes(b"other")
        replacement.replace(path)
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size
    assert path.stat().st_mtime_ns == before.st_mtime_ns


@pytest.mark.parametrize("in_place", [False, True], ids=["replacement", "in-place"])
def test_same_size_and_mtime_replacement_invalidates_all_probe_facts(
    tmp_path: Path, in_place: bool
) -> None:
    create_config(tmp_path, METRIC_CONFIG)
    [path] = create_video_files(tmp_path / "comparison_videos", "source.mkv")
    hdr_loader = RecordingLoader(hdr=True)
    first = _run(tmp_path, hdr_loader).clips[0].probe
    unchanged = _run(tmp_path, hdr_loader).clips[0].probe
    assert hdr_loader.calls == 1
    assert unchanged == first
    assert first.fingerprint.source_token is not None
    assert first.is_hdr and first.hdr_metadata is not None
    assert "DolbyVisionRPU" in first.tonemap_prop_keys

    _replace_same_stats(path, in_place=in_place)
    sdr_loader = RecordingLoader()
    current = _run(tmp_path, sdr_loader).clips[0].probe

    assert sdr_loader.calls == 1
    assert current.fingerprint.source_token != first.fingerprint.source_token
    assert (current.width, current.height) == (1280, 720)
    assert not current.is_hdr
    assert current.hdr_metadata is None
    assert current.preserved_frame_props == {"_Transfer": 1}
    assert current.tonemap_prop_keys == ("_Transfer",)


@pytest.mark.parametrize("authority", ["stale", "private", "non-strict", "no-probe", "refused"])
def test_cache_only_refuses_invalid_probe_authority_before_metadata_and_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    create_config(tmp_path, METRIC_CONFIG)
    [path] = create_video_files(tmp_path / "comparison_videos", "source.mkv")
    _run(tmp_path, RecordingLoader())
    if authority == "stale":
        _replace_same_stats(path, in_place=True)
    elif authority == "non-strict":
        monkeypatch.setattr(probe_cache, "source_identity", MagicMock(side_effect=OSError))
    elif authority == "no-probe":
        monkeypatch.setattr(admission, "resolve_optional_executable", lambda _: None)
    else:
        original = admission.probe_admission_headers

        def headers(*args, **kwargs):
            streams, payload = original(*args, **kwargs)
            payload["format"] = {"format_name": "mpegvideo" if authority == "private" else "concat"}
            return streams, payload

        monkeypatch.setattr(admission, "probe_admission_headers", headers)
    reserve = MagicMock(side_effect=AssertionError("must validate before run metadata/reservation"))
    monkeypatch.setattr(preparation, "_resolve_run_directory", reserve)
    loader = RecordingLoader()
    with pytest.raises(MetricsCalculationError, match="Cached clip probe data is required"):
        asyncio.run(
            preparation.execute_prep(
                make_run_request(root=tmp_path, from_cache_only=True),
                RunDependencies(vs_loader=loader),
            )
        )
    assert loader.calls == 0
    reserve.assert_not_called()


@pytest.mark.parametrize(
    "authority", ["non-strict", "private", "no-probe-identity", "unknown-coded"]
)
def test_admitted_private_sources_work_in_memory_without_persisted_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, authority: str
) -> None:
    create_config(tmp_path, METRIC_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    if authority == "non-strict":
        monkeypatch.setattr(probe_cache, "source_identity", MagicMock(side_effect=OSError))
    elif authority == "no-probe-identity":
        monkeypatch.setattr(admission, "_probe_stamp", lambda _: None)
    else:
        original = admission.probe_admission_headers

        def headers(*args, **kwargs):
            streams, payload = original(*args, **kwargs)
            if authority == "private":
                payload["format"] = {"format_name": "mpegvideo"}
            else:
                streams[0].update(coded_width=0, coded_height=0)
            return streams, payload

        monkeypatch.setattr(admission, "probe_admission_headers", headers)
    loader = RecordingLoader()
    for _ in range(2):
        prep = _run(tmp_path, loader)
        assert prep.clips[0].probe.fingerprint.source_token is None
        assert prep.clips[0].probe.width == 1280
        assert (
            probe_cache.load_clip_probe_cache(prep.workspace.generated_dir / "clip_probe.toml")
            == {}
        )
    assert loader.calls == 2
    assert probe_cache.load_clip_probe_cache(tmp_path / "generated" / "clip_probe.toml") == {}


@pytest.mark.parametrize("private", [False, True], ids=["reusable", "private"])
def test_cold_native_probe_cannot_attach_changed_identity_to_old_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, private: bool
) -> None:
    create_config(tmp_path, METRIC_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    if private:
        monkeypatch.setattr(probe_cache, "source_identity", MagicMock(side_effect=OSError))

    class ReplacingLoader(RecordingLoader):
        def load(self, path: Path) -> SourceInfo:
            result = super().load(path)
            _replace_same_stats(path, in_place=True)
            return result

    with pytest.raises(SourceLoadError, match="Source video changed while probing"):
        _run(tmp_path, ReplacingLoader())
    assert not (tmp_path / "generated" / "clip_probe.toml").exists()


def test_live_probe_refuses_strict_identity_that_disagrees_with_admission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_config(tmp_path, METRIC_CONFIG)
    [path] = create_video_files(tmp_path / "comparison_videos", "source.mkv")
    wrong_identity = replace(admission.source_identity(path), inode=0)
    monkeypatch.setattr(probe_cache, "source_identity", lambda _: wrong_identity)
    loader = RecordingLoader()
    with pytest.raises(SourceLoadError, match="Source video changed during admission"):
        _run(tmp_path, loader)
    assert loader.calls == 0
    assert not (tmp_path / "generated" / "clip_probe.toml").exists()


@pytest.mark.parametrize("cache_only", [False, True], ids=["ordinary", "cache-only"])
@pytest.mark.parametrize("token", [None, "malformed"], ids=["legacy-missing-token", "bad-token"])
def test_untrusted_persisted_token_misses_at_both_preparation_entrypoints(
    tmp_path: Path, cache_only: bool, token: str | None
) -> None:
    import tomllib

    import tomli_w

    create_config(tmp_path, METRIC_CONFIG)
    create_video_files(tmp_path / "comparison_videos", "source.mkv")
    _run(tmp_path, RecordingLoader(hdr=True))
    cache_path = tmp_path / "generated" / "clip_probe.toml"
    payload = tomllib.loads(cache_path.read_text(encoding="utf-8"))
    for key, entry in payload.items():
        if key == "version":
            continue
        if token is None:
            entry.pop("source_token")
        else:
            entry["source_token"] = token
    cache_path.write_text(tomli_w.dumps(payload), encoding="utf-8")
    loader = RecordingLoader()
    if cache_only:
        with pytest.raises(MetricsCalculationError, match="Cached clip probe data is required"):
            asyncio.run(
                preparation.execute_prep(
                    make_run_request(root=tmp_path, from_cache_only=True),
                    RunDependencies(vs_loader=loader),
                )
            )
        assert loader.calls == 0
    else:
        probe = _run(tmp_path, loader).clips[0].probe
        assert loader.calls == 1
        assert not probe.is_hdr and probe.hdr_metadata is None
        assert probe.preserved_frame_props == {"_Transfer": 1}
