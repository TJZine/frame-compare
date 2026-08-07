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
from typing import Final, Literal

from frame_compare.errors import JSONValue

type MediaRuntimeScope = Literal["analysis", "probe", "alignment", "index", "full"]
type MediaRuntimeProfile = Literal["windows-x64", "debian-trixie"]

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

LSMASH_SOURCE_COMMIT: Final = "84740c5d960ab622f4c08b971dc59192bc27ef74"
LSMASH_WORKS_RELEASE: Final = "1296.0.0.0"
LSMASH_WORKS_PYPI_RELEASE: Final = "1296.0.0.1"
LSMASH_WORKS_SOURCE_COMMIT: Final = "a83318210c183c8ebbe703d975ffc76fb499ef07"
LSMASH_WORKS_WINDOWS_FFMPEG_COMMIT: Final = "39c24f36247f370864ce86ebdf2aa936151f4bfc"

FFMS2_RELEASE: Final = "5.0"
FFMS2_RUNTIME_VERSION: Final = "5.0.0.0"
FFMS2_SOURCE_COMMIT: Final = "7ed5e4d039ca9a6236bd2ebdfdd656c4304fbe04"

VS_PLACEBO_RELEASE: Final = "2.0.4"
VS_PLACEBO_SOURCE_COMMIT: Final = "3cfd23f257ecb62b0cbd81eaaca092e18ae8e579"
LIBPLACEBO_SOURCE_COMMIT: Final = "a7a18af88ff0a17c04840dcb3246047bb6b46df3"
LIBDOVI_RELEASE: Final = "3.3.2"
LIBDOVI_SOURCE_COMMIT: Final = "4fd2b2235c9f93582dd4a00e65ee34a07800afd7"

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
    Windows bundled decoder lineage from the Debian-linked Linux lineage.
    """

    runtime_kind = os.environ.get("FRAME_COMPARE_RUNTIME_KIND", "").strip().casefold()
    if runtime_kind in {"windows", "windows-portable"}:
        return "windows-x64"
    if runtime_kind == "docker":
        return "debian-trixie"
    return "windows-x64" if sys.platform == "win32" else "debian-trixie"


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
    else:
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
    return identity


def _decoder_identity(profile: MediaRuntimeProfile) -> dict[str, JSONValue]:
    return {
        "vapoursynth": _vapoursynth_identity(),
        "l_smash": _lsmash_identity(),
        "l_smash_works": _lsmash_works_identity(profile),
    }


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
    return {
        "selection_kind": "debian-package",
        "distribution": "trixie",
        "package_version": DEBIAN_FFMPEG_PACKAGE_VERSION,
        "license_profile": "Debian-supported",
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
    return f"lsw1296-{fingerprint[:12]}"


def supported_media_runtime_report(
    *,
    profile: MediaRuntimeProfile | None = None,
) -> dict[str, JSONValue]:
    """Return the user-facing supported media-runtime matrix and fingerprints."""

    selected_profile = profile or media_runtime_profile()
    fingerprints: dict[str, JSONValue] = {}
    for scope in MEDIA_RUNTIME_SCOPES:
        fingerprints[scope] = media_runtime_fingerprint(scope, profile=selected_profile)
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


def runtime_environment_report() -> dict[str, JSONValue]:
    """Compare deployment-declared identity with the code-owned expectation."""

    expected = media_runtime_fingerprint("full")
    runtime_kind = os.environ.get("FRAME_COMPARE_RUNTIME_KIND", "").strip() or "unmanaged"
    declared_raw = os.environ.get("FRAME_COMPARE_MEDIA_RUNTIME_FINGERPRINT", "").strip()
    declared = declared_raw or None
    valid = declared is not None and _FINGERPRINT_RE.fullmatch(declared) is not None
    return {
        "runtime_kind": runtime_kind,
        "expected_full_fingerprint": expected,
        "declared_full_fingerprint": declared,
        "declared_full_fingerprint_valid": valid,
        "declared_full_fingerprint_match": valid and declared == expected,
        "ffms2_required": _env_flag("FRAME_COMPARE_RUNTIME_FFMS2_REQUIRED"),
    }


__all__ = [
    "DEBIAN_FFMPEG_PACKAGE_VERSION",
    "FFMS2_RELEASE",
    "FFMS2_RUNTIME_VERSION",
    "FFMS2_SOURCE_COMMIT",
    "LIBDOVI_RELEASE",
    "LIBDOVI_SOURCE_COMMIT",
    "LIBPLACEBO_SOURCE_COMMIT",
    "LSMASH_SOURCE_COMMIT",
    "LSMASH_WORKS_PYPI_RELEASE",
    "LSMASH_WORKS_RELEASE",
    "LSMASH_WORKS_SOURCE_COMMIT",
    "MEDIA_RUNTIME_CONTRACT_VERSION",
    "MEDIA_RUNTIME_SCOPES",
    "MediaRuntimeProfile",
    "MediaRuntimeScope",
    "VAPOURSYNTH_API_MAJOR",
    "VAPOURSYNTH_RELEASE",
    "VAPOURSYNTH_SOURCE_COMMIT",
    "VS_PLACEBO_RELEASE",
    "VS_PLACEBO_SOURCE_COMMIT",
    "WINDOWS_FFMPEG_ARTIFACT_ID",
    "WINDOWS_FFMPEG_BUILD_SOURCE_COMMIT",
    "WINDOWS_FFMPEG_RELEASE",
    "WINDOWS_FFMPEG_SOURCE_COMMIT",
    "index_cache_token",
    "media_runtime_fingerprint",
    "media_runtime_identity",
    "media_runtime_profile",
    "runtime_environment_report",
    "supported_media_runtime_report",
]
