"""Tests for coordinated media-runtime identity and fingerprints."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from frame_compare.vs.runtime_contract import (
    DEBIAN_FFMPEG_PACKAGE_VERSION,
    FFMS2_SOURCE_TREE_SHA256,
    LIBDOVI_SOURCE_TREE_SHA256,
    LIBPLACEBO_SOURCE_TREE_SHA256,
    LSMASH_SOURCE_TREE_SHA256,
    LSMASH_WORKS_RELEASE,
    LSMASH_WORKS_SOURCE_TREE_SHA256,
    MEDIA_RUNTIME_SCOPES,
    OBUPARSE_SOURCE_TREE_SHA256,
    VAPOURSYNTH_SOURCE_TREE_SHA256,
    VS_PLACEBO_SOURCE_TREE_SHA256,
    WINDOWS_FFMPEG_ARTIFACT_ID,
    WINDOWS_FFMPEG_EXECUTABLE_TOKEN,
    WINDOWS_FFMPEG_RELEASE,
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

    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "DOCKER")
    assert media_runtime_profile() == "debian-trixie"

    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "windows")
    monkeypatch.setattr("frame_compare.vs.runtime_contract.sys.platform", "win32")
    assert media_runtime_profile() == "unmanaged-windows"


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


def test_unmanaged_windows_does_not_inherit_portable_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
    monkeypatch.setattr("frame_compare.vs.runtime_contract.sys.platform", "win32")

    assert media_runtime_profile() == "unmanaged-windows"
    identity = media_runtime_identity("full", profile="unmanaged-windows")
    components = identity["components"]
    assert components["decoder"]["l_smash_works"]["build"] == "unmanaged-native"
    assert components["standalone_ffmpeg"] == {
        "selection_kind": "unmanaged-native",
        "platform": "windows",
    }
    for scope in MEDIA_RUNTIME_SCOPES:
        assert media_runtime_fingerprint(
            scope, profile="unmanaged-windows"
        ) != media_runtime_fingerprint(scope, profile="windows-x64")
    assert index_cache_token(profile="unmanaged-windows") != index_cache_token(
        profile="windows-x64"
    )


def test_unmanaged_linux_does_not_inherit_debian_package_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FRAME_COMPARE_RUNTIME_KIND", raising=False)
    monkeypatch.setattr("frame_compare.vs.runtime_contract.sys.platform", "linux")

    assert media_runtime_profile() == "unmanaged-linux"
    identity = media_runtime_identity("full", profile="unmanaged-linux")
    components = identity["components"]
    assert components["decoder"]["l_smash_works"]["build"] == "unmanaged-native"
    assert components["standalone_ffmpeg"] == {
        "selection_kind": "unmanaged-native",
        "platform": "linux",
    }
    for scope in MEDIA_RUNTIME_SCOPES:
        assert media_runtime_fingerprint(
            scope, profile="unmanaged-linux"
        ) != media_runtime_fingerprint(scope, profile="debian-trixie")


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


def test_debian_ffmpeg_identity_records_gpl_enabled_license_profile() -> None:
    identity = media_runtime_identity("alignment", profile="debian-trixie")

    assert identity["components"]["standalone_ffmpeg"]["license_profile"] == ("GPL-2.0-or-later")


def test_index_token_is_profile_scoped() -> None:
    windows = index_cache_token(profile="windows-x64")
    linux = index_cache_token(profile="debian-trixie")

    release_major = LSMASH_WORKS_RELEASE.partition(".")[0]
    token_pattern = rf"lsw{release_major}-[0-9a-f]{{12}}"
    assert re.fullmatch(token_pattern, windows)
    assert re.fullmatch(token_pattern, linux)
    assert windows != linux


def test_authority_docs_use_tokens_calculated_by_runtime_contract(repo_root: Path) -> None:
    windows = index_cache_token(profile="windows-x64")
    unmanaged_windows = index_cache_token(profile="unmanaged-windows")
    linux = index_cache_token(profile="debian-trixie")

    for relative_path in (
        "docs/current-architecture.md",
        "docs/current-cli-contract.md",
        "docs/supported-media-runtime.md",
    ):
        content = (repo_root / relative_path).read_text(encoding="utf-8")
        assert windows in content
        assert unmanaged_windows in content
        assert linux in content

    analysis_validation = (repo_root / "docs/analysis-performance-validation.md").read_text(
        encoding="utf-8"
    )
    assert windows in analysis_validation

    validation = (repo_root / "docs/media-runtime-windows-validation.md").read_text(
        encoding="utf-8"
    )
    assert media_runtime_fingerprint("full", profile="windows-x64") in validation


def test_windows_manifest_fingerprints_match_code_contract(repo_root: Path) -> None:
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    expected = {
        scope: media_runtime_fingerprint(scope, profile="windows-x64")
        for scope in MEDIA_RUNTIME_SCOPES
    }

    assert manifest["bundle"]["runtime_fingerprints"] == expected


def test_windows_ffmpeg_executable_token_matches_selected_artifact(repo_root: Path) -> None:
    manifest = json.loads(
        (repo_root / "tools/windows_portable/manifest.windows-x64.json").read_text(encoding="utf-8")
    )
    ffmpeg = next(
        artifact
        for artifact in manifest["artifacts"]
        if artifact["id"] == WINDOWS_FFMPEG_ARTIFACT_ID
    )

    assert ffmpeg["version"].startswith(WINDOWS_FFMPEG_RELEASE)
    assert (
        f"{WINDOWS_FFMPEG_RELEASE}-{ffmpeg['release_date'].replace('-', '')}"
    ) == WINDOWS_FFMPEG_EXECUTABLE_TOKEN


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
    monkeypatch.setenv("FRAME_COMPARE_RUNTIME_KIND", "DOCKER")
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
        assert component in dockerfile or component.replace('"', '\\"') in dockerfile
    assert '\\"version\\":\\"${DEBIAN_FFMPEG_PACKAGE_VERSION}\\"' in dockerfile
    assert '\\"license\\":\\"GPL-2.0-or-later\\"' in dockerfile
    assert "Debian-FFmpeg-copyright" in dockerfile
    assert '"version":"7:7.1.5-0+deb13u1"' not in dockerfile
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
        assert license_name in dockerfile


def test_docker_provenance_derives_vapoursynth_release_from_build_arg(
    repo_root: Path,
) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG VAPOURSYNTH_VERSION=78" in dockerfile
    assert '\\"version\\":\\"R${VAPOURSYNTH_VERSION}\\"' in dockerfile
    assert '\\"version\\":\\"R78\\"' not in dockerfile


def test_docker_lsmash_works_meson_rewrite_fails_closed(repo_root: Path, tmp_path: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")

    perl = shutil.which("perl")
    if perl is None:
        pytest.skip("Perl is required to execute the Dockerfile Meson rewrite proof")

    rewrite_match = re.search(
        r"perl -0pi -e '(?P<program>.*?)' meson\.build", dockerfile, re.DOTALL
    )
    assert rewrite_match is not None, "Dockerfile must own the L-SMASH-Works rewrite"
    # Dockerfile line continuations are removed before /bin/sh receives this
    # program. Normalize those continuations so the exact owned Perl program
    # can be exercised without building an image.
    perl_program = rewrite_match.group("program").replace("\\\n", "")
    meson_block = (
        "  install: true,\n"
        "  install_dir: join_paths(vapoursynth_dep.get_pkgconfig_variable('libdir'), 'vapoursynth'),\n"
    )

    def run_rewrite(content: str) -> subprocess.CompletedProcess[str]:
        meson_path = tmp_path / "meson.build"
        meson_path.write_text(content, encoding="utf-8")
        return subprocess.run(
            [perl, "-0pi", "-e", perl_program, str(meson_path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )

    matched = run_rewrite(meson_block)
    assert matched.returncode == 0, matched.stderr
    assert (tmp_path / "meson.build").read_text(encoding="utf-8") == "  install: false,\n"

    missing = run_rewrite("project('unrelated')\n")
    assert missing.returncode != 0
    assert "exactly once" in missing.stderr

    duplicate = run_rewrite(meson_block + meson_block)
    assert duplicate.returncode != 0
    assert "exactly once" in duplicate.stderr


def test_docker_uses_verified_tracked_source_tree_digests(repo_root: Path) -> None:
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    expected = {
        "VAPOURSYNTH_SOURCE_TREE_SHA256": VAPOURSYNTH_SOURCE_TREE_SHA256,
        "LSMASH_SOURCE_TREE_SHA256": LSMASH_SOURCE_TREE_SHA256,
        "OBUPARSE_SOURCE_TREE_SHA256": OBUPARSE_SOURCE_TREE_SHA256,
        "LSMASH_WORKS_SOURCE_TREE_SHA256": LSMASH_WORKS_SOURCE_TREE_SHA256,
        "FFMS2_SOURCE_TREE_SHA256": FFMS2_SOURCE_TREE_SHA256,
        "VS_PLACEBO_SOURCE_TREE_SHA256": VS_PLACEBO_SOURCE_TREE_SHA256,
        "LIBPLACEBO_SOURCE_TREE_SHA256": LIBPLACEBO_SOURCE_TREE_SHA256,
        "LIBDOVI_SOURCE_TREE_SHA256": LIBDOVI_SOURCE_TREE_SHA256,
    }
    for argument, digest in expected.items():
        assert f"ARG {argument}={digest}" in dockerfile
        assert f'\\"source_tree_sha256\\":\\"${{{argument}}}\\"' in dockerfile


def test_docker_runtime_reads_release_and_api_identities_separately(repo_root: Path) -> None:
    script = (repo_root / "tools/verify_docker_integration.sh").read_text(encoding="utf-8")

    assert "DOCKER_PROOF vapoursynth_import=ok version=R78 api=4" in script


def test_docker_doctor_gate_preserves_missing_check_diagnostic_and_proof_marker(
    repo_root: Path,
) -> None:
    script = (repo_root / "tools/verify_docker_integration.sh").read_text(encoding="utf-8")

    assert "doctor required check missing: {required_check}" in script
    assert script.count("DOCKER_PROOF doctor_json=ok") == 2


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
    assert "hdr_lsw.is_hdr is True" in script
    assert "hdr_lsw.hdr_metadata.transfer == 16" in script
    assert "hdr_lsw.hdr_metadata.color_primaries == 9" in script
    assert "RemoveFrameProps" in script
    assert 'tonemapped_hdr_frame.props.get("_Tonemapped") == 1' in script
