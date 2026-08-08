"""Supported media-runtime component identity and cache fingerprints.

This module is the single source of truth for the coordinated decoder,
source-plugin, tone-mapping, and standalone FFmpeg stack.  Callers consume
scope-specific identities so a component change invalidates only the caches
whose outputs can actually change.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from typing import Final, Literal, TypedDict

from frame_compare.errors import JSONValue

type MediaRuntimeScope = Literal["analysis", "probe", "alignment", "index", "full"]
type MediaRuntimeProfile = Literal[
    "windows-x64", "debian-trixie", "unmanaged-linux", "native-macos"
]


class MediaRuntimeFingerprints(TypedDict):
    analysis: str
    probe: str
    alignment: str
    index: str
    full: str


class MediaRuntimeReport(TypedDict):
    contract_version: int
    profile: MediaRuntimeProfile
    components: dict[str, JSONValue]
    fingerprints: MediaRuntimeFingerprints
    index_cache_token: str


MEDIA_RUNTIME_CONTRACT_VERSION: Final = 1
MEDIA_RUNTIME_SCOPES: Final[tuple[MediaRuntimeScope, ...]] = (
    "analysis",
    "probe",
    "alignment",
    "index",
    "full",
)

VAPOURSYNTH_RELEASE: Final = "R78"
VAPOURSYNTH_API_MAJOR: Final = 4
VAPOURSYNTH_SOURCE_COMMIT: Final = "c2f5751a412347f306eb7f6a5985dd9a719f3896"
VAPOURSYNTH_SOURCE_TREE_SHA256: Final = (
    "cc0f2ec4127bd26f6dff074450ebe801368b6d4341b3ab9928c94073a682196f"
)

LSMASH_SOURCE_COMMIT: Final = "84740c5d960ab622f4c08b971dc59192bc27ef74"
LSMASH_SOURCE_TREE_SHA256: Final = (
    "b1553e40907e57240fd19a08642b3bc548dbdeda3750948ebbc1c5634af901b7"
)
OBUPARSE_SOURCE_COMMIT: Final = "a67fcab9cd9d56c866a7a860f8c4aeb91b8817e8"
OBUPARSE_SOURCE_TREE_SHA256: Final = (
    "f82de7a5f007a4e89441e7ff4b470a00eddc4dfedb22faa46f633acfeefde178"
)
LSMASH_WORKS_RELEASE: Final = "1296.0.0.0"
LSMASH_WORKS_PYPI_RELEASE: Final = "1296.0.0.1"
LSMASH_WORKS_SOURCE_COMMIT: Final = "a83318210c183c8ebbe703d975ffc76fb499ef07"
LSMASH_WORKS_SOURCE_TREE_SHA256: Final = (
    "7845a6a6d823046c6b0bbe617ae88e304ee117f466961aabceea931831d8f9e3"
)
LSMASH_WORKS_WINDOWS_FFMPEG_COMMIT: Final = "39c24f36247f370864ce86ebdf2aa936151f4bfc"

FFMS2_RELEASE: Final = "5.0"
FFMS2_RUNTIME_VERSION: Final = "5.0.0.0"
FFMS2_SOURCE_COMMIT: Final = "7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04"
FFMS2_SOURCE_TREE_SHA256: Final = "5be86d5f8f103f8e0b25aaed0b69b7afc06f1b6cd548a6c81160fcd14ea6e8d7"

VS_PLACEBO_RELEASE: Final = "2.0.4"
VS_PLACEBO_SOURCE_COMMIT: Final = "3cfd23f257ecb62b0cbd81eaaca092e18ae8e579"
VS_PLACEBO_SOURCE_TREE_SHA256: Final = (
    "beb830744f1fa1702eb64cfe8bdaf5780bb3501f9c48901df24ab112a406a30a"
)
LIBPLACEBO_SOURCE_COMMIT: Final = "a7a18af88ff0a17c04840dcb3246047bb6b46df3"
LIBPLACEBO_SOURCE_TREE_SHA256: Final = (
    "bdbe17582c081e107e1a66c44d5f01aa856a157aa124660d662221848e88eda7"
)
LIBDOVI_RELEASE: Final = "3.3.2"
LIBDOVI_SOURCE_COMMIT: Final = "4fd2b2235c9f93582dd4a00e65ee34a07800afd7"
LIBDOVI_SOURCE_TREE_SHA256: Final = (
    "e16dfb68270fc5b8610e2f1ae38b0b1051d8e7d03dd4b98a2f22f0e1fd09de26"
)

WINDOWS_FFMPEG_RELEASE: Final = "n8.1.2-34-g9b6c8969e0"
WINDOWS_FFMPEG_ARTIFACT_ID: Final = "ffmpeg-btbn-win64-lgpl-8.1-2026-07-31"
WINDOWS_FFMPEG_SOURCE_COMMIT: Final = "9b6c8969e05b4f0b29f0f85cd501be6b3e582e6b"
WINDOWS_FFMPEG_BUILD_SOURCE_COMMIT: Final = "a99e8230eae00d1cee38f23076a7a1f55cd984e2"
DEBIAN_FFMPEG_PACKAGE_VERSION: Final = "7:7.1.5-0+deb13u1"

_FINGERPRINT_RE: Final = re.compile(r"[0-9a-f]{64}")


def media_runtime_profile() -> MediaRuntimeProfile:
    """Return the supported component profile for the current process.

    The deployment kind selects the authoritative packaged profile.  Unmanaged
    hosts fall back by operating system so cache identities still separate the
    Windows bundled decoder lineage, managed Debian lineage, and unmanaged
    Linux and native macOS environments.
    """

    selected_runtime_kind = runtime_kind().casefold()
    if selected_runtime_kind in {"windows", "windows-portable"}:
        return "windows-x64"
    if selected_runtime_kind == "docker":
        return "debian-trixie"
    if sys.platform == "win32":
        return "windows-x64"
    if sys.platform == "darwin":
        return "native-macos"
    return "unmanaged-linux"


def _vapoursynth_identity() -> dict[str, JSONValue]:
    return {
        "release": VAPOURSYNTH_RELEASE,
        "api_major": VAPOURSYNTH_API_MAJOR,
        "source_commit": VAPOURSYNTH_SOURCE_COMMIT,
    }


def _lsmash_identity() -> dict[str, JSONValue]:
    return {
        "selection_kind": "commit",
        "source_commit": LSMASH_SOURCE_COMMIT,
        "formal_release": False,
    }


def _lsmash_works_identity(profile: MediaRuntimeProfile) -> dict[str, JSONValue]:
    identity: dict[str, JSONValue] = {
        "native_release": LSMASH_WORKS_RELEASE,
        "source_commit": LSMASH_WORKS_SOURCE_COMMIT,
        "vapoursynth_api_major": VAPOURSYNTH_API_MAJOR,
        "plugin_namespace": "lsmas",
        "required_functions": ["LibavSMASHSource", "LWLibavSource"],
        "l_smash_source_commit": LSMASH_SOURCE_COMMIT,
    }
    if profile == "windows-x64":
        identity.update(
            {
                "distribution": "vapoursynth-lsmas",
                "distribution_version": LSMASH_WORKS_PYPI_RELEASE,
                "decoder_ffmpeg": {
                    "selection_kind": "commit",
                    "source_commit": LSMASH_WORKS_WINDOWS_FFMPEG_COMMIT,
                },
            }
        )
    elif profile == "debian-trixie":
        identity.update(
            {
                "build": "source-meson-vapoursynth-only",
                "decoder_ffmpeg": {
                    "selection_kind": "debian-package",
                    "distribution": "trixie",
                    "package_version": DEBIAN_FFMPEG_PACKAGE_VERSION,
                },
            }
        )
    else:
        identity.update(
            {
                "build": "unmanaged-native",
                "platform": "linux" if profile == "unmanaged-linux" else "macos",
                "decoder_ffmpeg": {"selection_kind": "unmanaged-native"},
            }
        )
    return identity


def _decoder_identity(profile: MediaRuntimeProfile) -> dict[str, JSONValue]:
    identity: dict[str, JSONValue] = {
        "vapoursynth": _vapoursynth_identity(),
        "l_smash": _lsmash_identity(),
        "l_smash_works": _lsmash_works_identity(profile),
    }
    if profile == "debian-trixie":
        identity["obuparse"] = {
            "selection_kind": "commit",
            "source_commit": OBUPARSE_SOURCE_COMMIT,
            "linkage": "shared",
            "soname": "libobuparse.so.2",
        }
    return identity


def _standalone_ffmpeg_identity(profile: MediaRuntimeProfile) -> dict[str, JSONValue]:
    if profile == "windows-x64":
        return {
            "selection_kind": "retained-release-artifact",
            "release": WINDOWS_FFMPEG_RELEASE,
            "artifact_id": WINDOWS_FFMPEG_ARTIFACT_ID,
            "source_commit": WINDOWS_FFMPEG_SOURCE_COMMIT,
            "build_source_commit": WINDOWS_FFMPEG_BUILD_SOURCE_COMMIT,
            "branch": "8.1",
            "license_profile": "LGPL-only",
        }
    if profile == "debian-trixie":
        return {
            "selection_kind": "debian-package",
            "distribution": "trixie",
            "package_version": DEBIAN_FFMPEG_PACKAGE_VERSION,
            "license_profile": "Debian-supported",
        }
    return {
        "selection_kind": "unmanaged-native",
        "platform": "linux" if profile == "unmanaged-linux" else "macos",
    }


def _ffms2_identity(profile: MediaRuntimeProfile) -> dict[str, JSONValue]:
    return {
        "release": FFMS2_RELEASE,
        "runtime_version": FFMS2_RUNTIME_VERSION,
        "source_commit": FFMS2_SOURCE_COMMIT,
        "plugin_namespace": "ffms2",
        "required_functions": ["Source", "Version"],
        "included": profile == "debian-trixie",
        "windows_baseline": "excluded",
    }


def _tone_mapping_identity() -> dict[str, JSONValue]:
    return {
        "vs_placebo": {
            "release": VS_PLACEBO_RELEASE,
            "source_commit": VS_PLACEBO_SOURCE_COMMIT,
            "plugin_namespace": "placebo",
            "required_functions": ["Tonemap"],
        },
        "libplacebo": {
            "selection_kind": "commit",
            "source_commit": LIBPLACEBO_SOURCE_COMMIT,
        },
        "libdovi": {
            "release": LIBDOVI_RELEASE,
            "source_commit": LIBDOVI_SOURCE_COMMIT,
        },
    }


def _scope_components(
    scope: MediaRuntimeScope,
    profile: MediaRuntimeProfile,
) -> dict[str, JSONValue]:
    if scope in {"analysis", "probe"}:
        return {"decoder": _decoder_identity(profile)}
    if scope == "alignment":
        return {"standalone_ffmpeg": _standalone_ffmpeg_identity(profile)}
    if scope == "index":
        return {
            "decoder": _decoder_identity(profile),
            "index_contract": {
                "owner": "frame-compare",
                "format": "L-SMASH-Works-LWI",
                "rap_verification": 0,
                "token_version": 1,
            },
        }
    return {
        "decoder": _decoder_identity(profile),
        "standalone_ffmpeg": _standalone_ffmpeg_identity(profile),
        "ffms2": _ffms2_identity(profile),
        "tone_mapping": _tone_mapping_identity(),
        "plugin_layout": {
            "vapoursynth": "site-packages/vapoursynth/plugins",
            "extra": "VAPOURSYNTH_EXTRA_PLUGIN_PATH",
            "manifest": "VapourSynth Manifest V1",
        },
    }


def media_runtime_identity(
    scope: MediaRuntimeScope,
    *,
    profile: MediaRuntimeProfile | None = None,
) -> dict[str, JSONValue]:
    """Return the canonical component identity for one cache/deployment scope."""

    selected_profile = profile or media_runtime_profile()
    return {
        "contract_version": MEDIA_RUNTIME_CONTRACT_VERSION,
        "scope": scope,
        "profile": selected_profile,
        "components": _scope_components(scope, selected_profile),
    }


def _stable_json(payload: dict[str, JSONValue]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def media_runtime_fingerprint(
    scope: MediaRuntimeScope,
    *,
    profile: MediaRuntimeProfile | None = None,
) -> str:
    """Return the SHA-256 fingerprint for one supported runtime scope."""

    identity = media_runtime_identity(scope, profile=profile)
    return hashlib.sha256(_stable_json(identity).encode("utf-8")).hexdigest()


def index_cache_token(*, profile: MediaRuntimeProfile | None = None) -> str:
    """Return the compact owner token embedded in Frame Compare ``.lwi`` paths."""

    fingerprint = media_runtime_fingerprint("index", profile=profile)
    release_major = LSMASH_WORKS_RELEASE.partition(".")[0]
    return f"lsw{release_major}-{fingerprint[:12]}"


def supported_media_runtime_report(
    *,
    profile: MediaRuntimeProfile | None = None,
) -> MediaRuntimeReport:
    """Return the user-facing supported media-runtime matrix and fingerprints."""

    selected_profile = profile or media_runtime_profile()
    fingerprints = MediaRuntimeFingerprints(
        analysis=media_runtime_fingerprint("analysis", profile=selected_profile),
        probe=media_runtime_fingerprint("probe", profile=selected_profile),
        alignment=media_runtime_fingerprint("alignment", profile=selected_profile),
        index=media_runtime_fingerprint("index", profile=selected_profile),
        full=media_runtime_fingerprint("full", profile=selected_profile),
    )
    return {
        "contract_version": MEDIA_RUNTIME_CONTRACT_VERSION,
        "profile": selected_profile,
        "components": {
            "decoder": _decoder_identity(selected_profile),
            "standalone_ffmpeg": _standalone_ffmpeg_identity(selected_profile),
            "ffms2": _ffms2_identity(selected_profile),
            "tone_mapping": _tone_mapping_identity(),
        },
        "fingerprints": fingerprints,
        "index_cache_token": index_cache_token(profile=selected_profile),
    }


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def runtime_kind() -> str:
    """Return the deployment-declared runtime kind or ``unmanaged``."""

    return os.environ.get("FRAME_COMPARE_RUNTIME_KIND", "").strip() or "unmanaged"


def runtime_ffms2_required() -> bool:
    """Return whether deployment policy requires the FFMS2 runtime plugin."""

    return _env_flag("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED")


def runtime_environment_report() -> dict[str, JSONValue]:
    """Compare deployment-declared identity with the code-owned expectation."""

    expected = media_runtime_fingerprint("full")
    selected_runtime_kind = runtime_kind()
    declared_raw = os.environ.get("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", "").strip()
    declared = declared_raw or None
    valid = declared is not None and _FINGERPRINT_RE.fullmatch(declared) is not None
    return {
        "runtime_kind": selected_runtime_kind,
        "expected_full_fingerprint": expected,
        "declared_full_fingerprint": declared,
        "declared_full_fingerprint_valid": valid,
        "declared_full_fingerprint_match": valid and declared == expected,
        "ffms2_required": runtime_ffms2_required(),
    }


__all__ = [
    "DEBIAN_FFMPEG_PACKAGE_VERSION",
    "FFMS2_RELEASE",
    "FFMS2_RUNTIME_VERSION",
    "FFMS2_SOURCE_COMMIT",
    "FFMS2_SOURCE_TREE_SHA256",
    "LIBDOVI_RELEASE",
    "LIBDOVI_SOURCE_COMMIT",
    "LIBDOVI_SOURCE_TREE_SHA256",
    "LIBPLACEBO_SOURCE_COMMIT",
    "LIBPLACEBO_SOURCE_TREE_SHA256",
    "LSMASH_SOURCE_COMMIT",
    "LSMASH_SOURCE_TREE_SHA256",
    "LSMASH_WORKS_PYPI_RELEASE",
    "LSMASH_WORKS_RELEASE",
    "LSMASH_WORKS_SOURCE_COMMIT",
    "LSMASH_WORKS_SOURCE_TREE_SHA256",
    "MEDIA_RUNTIME_CONTRACT_VERSION",
    "MEDIA_RUNTIME_SCOPES",
    "MediaRuntimeFingerprints",
    "MediaRuntimeProfile",
    "MediaRuntimeReport",
    "MediaRuntimeScope",
    "OBUPARSE_SOURCE_COMMIT",
    "OBUPARSE_SOURCE_TREE_SHA256",
    "VAPOURSYNTH_API_MAJOR",
    "VAPOURSYNTH_RELEASE",
    "VAPOURSYNTH_SOURCE_COMMIT",
    "VAPOURSYNTH_SOURCE_TREE_SHA256",
    "VS_PLACEBO_RELEASE",
    "VS_PLACEBO_SOURCE_COMMIT",
    "VS_PLACEBO_SOURCE_TREE_SHA256",
    "WINDOWS_FFMPEG_ARTIFACT_ID",
    "WINDOWS_FFMPEG_BUILD_SOURCE_COMMIT",
    "WINDOWS_FFMPEG_RELEASE",
    "WINDOWS_FFMPEG_SOURCE_COMMIT",
    "index_cache_token",
    "media_runtime_fingerprint",
    "media_runtime_identity",
    "media_runtime_profile",
    "runtime_environment_report",
    "runtime_ffms2_required",
    "runtime_kind",
    "supported_media_runtime_report",
]
