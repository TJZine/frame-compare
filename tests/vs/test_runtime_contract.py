"""Tests for coordinated media-runtime identity and fingerprints."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from frame_compare.vs.runtime_contract import (
    DEBIAN_FFMPEG_PACKAGE_VERSION,
    MEDIA_RUNTIME_SCOPES,
    index_cache_token,
    media_runtime_fingerprint,
    media_runtime_identity,
    media_runtime_profile,
    runtime_environment_report,
    supported_media_runtime_report,
)


def test_runtime_profile_uses_explicit_deployment_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows-portable")
    assert media_runtime_profile() == "windows-x64"

    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "docker")
    assert media_runtime_profile() == "debian-trixie"


def test_all_scope_fingerprints_are_deterministic_and_distinct() -> None:
    first = {
        scope: media_runtime_fingerprint(scope, profile="windows-x64")
        for scope in MEDIA_RUNTIME_SCOPES
    }
    second = {
        scope: media_runtime_fingerprint(scope, profile="windows-x64")
        for scope in MEDIA_RUNTIME_SCOPES
    }

    assert first == second
    assert len(set(first.values())) == len(MEDIA_RUNTIME_SCOPES)
    assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in first.values())


def test_windows_and_debian_decoder_profiles_do_not_share_cache_identity() -> None:
    for scope in ("analysis", "probe", "index", "full"):
        assert media_runtime_fingerprint(
            scope, profile="windows-x64"
        ) != media_runtime_fingerprint(scope, profile="debian-trixie")

    windows = media_runtime_identity("analysis", profile="windows-x64")
    linux = media_runtime_identity("analysis", profile="debian-trixie")
    windows_lsw = windows["components"]["decoder"]["l_smash_works"]
    linux_lsw = linux["components"]["decoder"]["l_smash_works"]
    assert windows_lsw["distribution_version"] == "1296.0.0.1"
    assert linux_lsw["decoder_ffmpeg"]["package_version"] == DEBIAN_FFMPEG_PACKAGE_VERSION


def test_analysis_identity_excludes_tone_mapping_components() -> None:
    identity = media_runtime_identity("analysis", profile="windows-x64")
    serialized = json.dumps(identity, sort_keys=True)

    assert "vs_placebo" not in serialized
    assert "libplacebo" not in serialized
    assert "libdovi" not in serialized
    assert "l_smash_works" in serialized


def test_alignment_identity_is_owned_by_standalone_ffmpeg() -> None:
    identity = media_runtime_identity("alignment", profile="windows-x64")

    assert set(identity["components"]) == {"standalone_ffmpeg"}
    assert identity["components"]["standalone_ffmpeg"]["license_profile"] == "LGPL-only"


def test_index_token_is_profile_scoped() -> None:
    windows = index_cache_token(profile="windows-x64")
    linux = index_cache_token(profile="debian-trixie")

    assert re.fullmatch(r"lsw1296-[0-9a-f]{12}", windows)
    assert re.fullmatch(r"lsw1296-[0-9a-f]{12}", linux)
    assert windows != linux


def test_windows_manifest_fingerprints_match_code_contract(repo_root: Path) -> None:
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        scope: media_runtime_fingerprint(scope, profile="windows-x64")
        for scope in MEDIA_RUNTIME_SCOPES
    }

    assert manifest["bundle"]["runtime_fingerprints"] == expected


def test_supported_report_contains_observable_component_contract() -> None:
    report = supported_media_runtime_report(profile="debian-trixie")

    assert report["components"]["decoder"]["vapoursynth"]["release"] == "R78"
    assert report["components"]["decoder"]["l_smash_works"]["native_release"] == (
        "1296.0.0.0"
    )
    assert report["components"]["ffms2"]["included"] is True
    assert report["components"]["tone_mapping"]["vs_placebo"]["release"] == "2.0.4"
    assert report["fingerprints"]["full"] == media_runtime_fingerprint(
        "full", profile="debian-trixie"
    )


def test_runtime_environment_report_fails_closed_on_invalid_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "docker")
    monkeypatch.setenv("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", "not-a-fingerprint")
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "1")

    report = runtime_environment_report()

    assert report["runtime_kind"] == "docker"
    assert report["declared_full_fingerprint"] == "not-a-fingerprint"
    assert report["declared_full_fingerprint_valid"] is False
    assert report["declared_full_fingerprint_match"] is False
    assert report["ffms2_required"] is True


def test_docker_contract_matches_debian_profile(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    assert (
        "FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT="
        + media_runtime_fingerprint("full", profile="debian-trixie")
    ) in dockerfile
    assert f"ARG DEBIAN_FFMPEG_PACKAGE_VERSION={DEBIAN_FFMPEG_PACKAGE_VERSION}" in dockerfile
    for package in (
        "libavcodec-dev",
        "libavformat-dev",
        "libavutil-dev",
        "libswscale-dev",
        "libswresample-dev",
    ):
        assert package in dockerfile
    assert "dpkg-query -W -f='${Version}'" in dockerfile
    for source_url in (
        "https://codeload.github.com/vapoursynth/vapoursynth/tar.gz/",
        "https://codeload.github.com/l-smash/l-smash/tar.gz/",
        "https://codeload.github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works/tar.gz/",
        "https://codeload.github.com/FFMS/ffms2/tar.gz/",
        "https://codeload.github.com/Lypheo/vs-placebo/tar.gz/",
        "https://codeload.github.com/haasn/libplacebo/tar.gz/",
        "https://codeload.github.com/quietvoid/dovi_tool/tar.gz/",
    ):
        assert source_url in dockerfile
    assert "https://github.com/vapoursynth/vapoursynth/archive/" not in dockerfile


def test_docker_provenance_covers_every_distributed_media_component(
    repo_root: Path,
) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    for component in (
        '"name":"VapourSynth"',
        '"name":"L-SMASH"',
        '"name":"L-SMASH-Works"',
        '"name":"FFMS2"',
        '"name":"Debian FFmpeg"',
        '"name":"vs-placebo"',
        '"name":"libplacebo"',
        '"name":"libdovi"',
    ):
        assert component in dockerfile
    for license_name in (
        "VapourSynth-LGPL-2.1.txt",
        "L-SMASH-LICENSE.txt",
        "L-SMASH-Works-VapourSynth-LICENSE.txt",
        "FFMS2-COPYING.txt",
        "vs-placebo-LGPL-2.1.txt",
        "libplacebo-LGPL-2.1.txt",
        "libdovi-MIT.txt",
    ):
        assert license_name in dockerfile


def test_verified_immutable_source_hashes_are_consistent(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(
            encoding="utf-8"
        )
    )
    corresponding = {entry["name"]: entry for entry in manifest["corresponding_sources"]}

    expected = {
        "libplacebo": (
            "ba0c8c011c19cb74bcee26646d2d6070447151da89a9abdd01c9034e768de8b2",
            873993,
        ),
        "libdovi": (
            "8ccb1922d7dbb57bc4f2c15c10b90c462f7a5f292efe317c116db923728dd3f1",
            489628,
        ),
    }
    for component, (sha256, size) in expected.items():
        entry = corresponding[component]
        assert entry["sha256"] == sha256
        assert entry["bytes"] == size
        assert sha256 in dockerfile
        assert str(size) in dockerfile


def test_docker_runtime_reads_release_and_api_identities_separately(repo_root: Path) -> None:
    script = (repo_root / "tools/verify_docker_integration.sh").read_text(encoding="utf-8")

    assert 'api_version = getattr(vs, "__api_version__", None)' in script
    assert 'api_major = getattr(api_version, "api_major", None)' in script
    assert 'api_major = getattr(version, "api_major", None)' not in script


def test_docker_runtime_generates_metadata_sensitive_fixture_matrix(repo_root: Path) -> None:
    script = (repo_root / "tools/verify_docker_integration.sh").read_text(encoding="utf-8")

    for marker in (
        "h264_full_range",
        "generated VFR fixture is not variable",
        "h264_interlaced",
        "hevc10_hdr10",
        "libaom-av1",
        "generated_fixture_matrix=ok",
    ):
        assert marker in script
    assert 'props.get("_ColorRange") == 0' in script
    assert 'props.get("_Transfer") == 16' in script
    assert 'props.get("_FieldBased") in {1, 2}' in script
