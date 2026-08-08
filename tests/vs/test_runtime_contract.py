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
    runtime_ffms2_required,
    runtime_kind,
    supported_media_runtime_report,
)


def test_runtime_profile_uses_explicit_deployment_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows-portable")
    assert media_runtime_profile() == "windows-x64"

    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "docker")
    assert media_runtime_profile() == "debian-trixie"


def test_unmanaged_macos_has_its_own_native_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
    monkeypatch.setattr("frame_compare.vs.runtime_contract.sys.platform", "darwin")

    assert media_runtime_profile() == "native-macos"
    identity = media_runtime_identity("full", profile="native-macos")
    components = identity["components"]
    assert components["decoder"]["l_smash_works"]["build"] == "unmanaged-native"
    assert components["standalone_ffmpeg"] == {
        "selection_kind": "unmanaged-native",
        "platform": "macos",
    }


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
        assert media_runtime_fingerprint(scope, profile="windows-x64") != media_runtime_fingerprint(
            scope, profile="debian-trixie"
        )

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


def test_authority_docs_use_tokens_calculated_by_runtime_contract(repo_root: Path) -> None:
    windows = index_cache_token(profile="windows-x64")
    linux = index_cache_token(profile="debian-trixie")

    for relative_path in (
        "docs/current-architecture.md",
        "docs/current-cli-contract.md",
        "docs/supported-media-runtime.md",
    ):
        content = (repo_root / relative_path).read_text(encoding="utf-8")
        assert windows in content
        assert linux in content


def test_windows_manifest_fingerprints_match_code_contract(repo_root: Path) -> None:
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    expected = {
        scope: media_runtime_fingerprint(scope, profile="windows-x64")
        for scope in MEDIA_RUNTIME_SCOPES
    }

    assert manifest["bundle"]["runtime_fingerprints"] == expected


def test_supported_report_contains_observable_component_contract() -> None:
    report = supported_media_runtime_report(profile="debian-trixie")

    assert report["components"]["decoder"]["vapoursynth"]["release"] == "R78"
    assert report["components"]["decoder"]["l_smash_works"]["native_release"] == ("1296.0.0.0")
    assert report["components"]["decoder"]["obuparse"]["soname"] == "libobuparse.so.2"
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


def test_runtime_environment_interpretation_is_centralized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", " windows-portable ")
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED", "yes")

    assert runtime_kind() == "windows-portable"
    assert runtime_ffms2_required() is True


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
        "https://github.com/vapoursynth/vapoursynth.git",
        "https://github.com/HomeOfAviSynthPlusEvolution/obuparse.git",
        "https://github.com/l-smash/l-smash.git",
        "https://github.com/HomeOfAviSynthPlusEvolution/L-SMASH-Works.git",
        "https://github.com/FFMS/ffms2.git",
        "https://github.com/Lypheo/vs-placebo.git",
        "https://github.com/haasn/libplacebo.git",
        "https://github.com/quietvoid/dovi_tool.git",
    ):
        assert source_url in dockerfile
    assert "codeload.github.com" not in dockerfile
    assert "checkout_source_commit.sh" in dockerfile


def test_docker_provenance_covers_every_distributed_media_component(
    repo_root: Path,
) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    for component in (
        '"name":"VapourSynth"',
        '"name":"OBUParse"',
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
        "OBUParse-LICENSE.txt",
        "L-SMASH-LICENSE.txt",
        "L-SMASH-Works-VapourSynth-LICENSE.txt",
        "FFMS2-COPYING.txt",
        "vs-placebo-LGPL-2.1.txt",
        "libplacebo-LGPL-2.1.txt",
        "libdovi-MIT.txt",
    ):
        assert license_name in dockerfile


def test_docker_uses_verified_tracked_source_tree_digests(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    expected = {
        "VAPOURSYNTH_SOURCE_TREE_SHA256": "cc0f2ec4127bd26f6dff074450ebe801368b6d4341b3ab9928c94073a682196f",
        "LSMASH_SOURCE_TREE_SHA256": "b1553e40907e57240fd19a08642b3bc548dbdeda3750948ebbc1c5634af901b7",
        "OBUPARSE_SOURCE_TREE_SHA256": "f82de7a5f007a4e89441e7ff4b470a00eddc4dfedb22faa46f633acfeefde178",
        "LSMASH_WORKS_SOURCE_TREE_SHA256": "7845a6a6d823046c6b0bbe617ae88e304ee117f466961aabceea931831d8f9e3",
        "FFMS2_SOURCE_TREE_SHA256": "5be86d5f8f103f8e0b25aaed0b69b7afc06f1b6cd548a6c81160fcd14ea6e8d7",
        "VS_PLACEBO_SOURCE_TREE_SHA256": "beb830744f1fa1702eb64cfe8bdaf5780bb3501f9c48901df24ab112a406a30a",
        "LIBPLACEBO_SOURCE_TREE_SHA256": "bdbe17582c081e107e1a66c44d5f01aa856a157aa124660d662221848e88eda7",
        "LIBDOVI_SOURCE_TREE_SHA256": "e16dfb68270fc5b8610e2f1ae38b0b1051d8e7d03dd4b98a2f22f0e1fd09de26",
    }
    for argument, digest in expected.items():
        assert f"ARG {argument}={digest}" in dockerfile
        assert f'"source_tree_sha256":"{digest}"' in dockerfile


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
    assert "props_indicate_limited_range" in script
    assert "invalid full-range fixture" in script
    assert '"color_transfer": "smpte2084"' in script
    assert '"color_primaries": "bt2020"' in script
    assert '"pix_fmt": "yuv420p10le"' in script
    assert 'get_optional_int_prop(interlaced_props, "_FieldBased") in {1, 2}' in script
