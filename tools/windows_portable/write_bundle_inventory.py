from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

JsonObject = dict[str, object]

REQUIRED_DISTRIBUTIONS = {
    "jetpytools",
    "pyside6",
    "pyside6-addons",
    "pyside6-essentials",
    "shiboken6",
    "vapoursynth",
    "vapoursynth-bestsource",
    "vs-placebo",
    "vsjetengine",
    "vspackrgb",
    "vsview",
    "vsview-cli",
}
SOURCE_SCRIPTS = (
    ".github/workflows/windows-portable-build.yml",
    ".github/workflows/windows-portable.yml",
    "tools/windows_portable/build_portable.ps1",
    "tools/windows_portable/build_update.ps1",
    "tools/windows_portable/bundle_info.schema.json",
    "tools/windows_portable/generate_update_keypair.ps1",
    "tools/windows_portable/install-from-source.cmd",
    "tools/windows_portable/install-from-source.ps1",
    "tools/windows_portable/install.cmd",
    "tools/windows_portable/install.ps1",
    "tools/windows_portable/manifest.windows-x64.json",
    "tools/windows_portable/manifest.schema.json",
    "tools/windows_portable/sign_update.ps1",
    "tools/windows_portable/update_manifest.schema.json",
    "tools/windows_portable/shim/frame-compare-update.ps1",
    "tools/windows_portable/validate_update_public_key.ps1",
    "tools/windows_portable/write_bundle_inventory.py",
)
PRIVATE_RSA_FIELDS = ("P", "Q", "DP", "DQ", "InverseQ", "D")
PROHIBITED_BUNDLE_FILENAMES = frozenset({".env", "config.toml", "report.html"})
_INTER_VERSION = "4.1"
_INTER_LICENSE_SPDX = "OFL-1.1"
_INTER_SOURCE_URL = "https://github.com/rsms/inter/releases/tag/v4.1"
_INTER_LICENSE_SOURCE = Path("app/src/frame_compare/assets/fonts/Inter-OFL.txt")
_INTER_LICENSE_DESTINATION = Path("licenses/Inter-OFL.txt")
_INTER_LICENSE_SHA256 = "262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the Windows bundle inventory.")
    parser.add_argument("--bundle-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-clean-repo", action="store_true")
    return parser.parse_args()


def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30.0,
    )
    return result.stdout.strip()


def _require_dict(value: object, context: str) -> JsonObject:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be an object")
    return cast(JsonObject, value)


def _require_list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    return value


def _require_str(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context} must be a non-empty string")
    return value


def _require_sha256(value: object, context: str) -> str:
    digest = _require_str(value, context)
    if re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError(f"{context} must be a lowercase SHA-256 digest")
    return digest


def _require_int(value: object, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{context} must be an integer")
    if value < 0:
        raise ValueError(f"{context} must be non-negative")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional metadata value must be a string")
    stripped = value.strip()
    return stripped or None


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _metadata_values(
    metadata: importlib.metadata.PackageMetadata,
    key: str,
) -> list[str]:
    return sorted(
        {
            value.strip()
            for value in (metadata.get_all(key) or [])
            if value is not None and value.strip()
        }
    )


def _python_distributions(site_packages: Path) -> list[JsonObject]:
    records: list[JsonObject] = []
    found: set[str] = set()
    for distribution in importlib.metadata.distributions(path=[str(site_packages)]):
        metadata = distribution.metadata
        name = _require_str(metadata.get("Name"), "Python distribution Name")
        version = _require_str(distribution.version, f"Python distribution {name} version")
        normalized = _normalized_name(name)
        if normalized in found:
            raise ValueError(f"duplicate Python distribution metadata: {name}")
        found.add(normalized)

        project_urls: list[JsonObject] = []
        for value in _metadata_values(metadata, "Project-URL"):
            label, separator, url = value.partition(",")
            project_urls.append(
                {
                    "label": label.strip() if separator else "unspecified",
                    "url": url.strip() if separator else value,
                }
            )
        project_urls.sort(key=lambda item: (str(item["label"]).lower(), str(item["url"])))

        records.append(
            {
                "declared_license": _optional_str(metadata.get("License")),
                "license_classifiers": sorted(
                    value
                    for value in _metadata_values(metadata, "Classifier")
                    if value.startswith("License ::")
                ),
                "license_expression": _metadata_values(metadata, "License-Expression"),
                "name": name,
                "project_urls": project_urls,
                "source_url": f"https://pypi.org/project/{normalized}/{version}/",
                "version": version,
            }
        )

    missing = sorted(REQUIRED_DISTRIBUTIONS - found)
    if missing:
        raise ValueError(f"required Python distributions missing from bundle: {', '.join(missing)}")

    records.sort(key=lambda item: (str(item["name"]).lower(), str(item["version"])))
    return records


def _manifest_inventory(manifest: JsonObject) -> tuple[list[JsonObject], list[JsonObject]]:
    artifacts: list[JsonObject] = []
    for index, raw_artifact in enumerate(
        _require_list(manifest.get("artifacts"), "manifest.artifacts")
    ):
        artifact = _require_dict(raw_artifact, f"manifest.artifacts[{index}]")
        artifact_id = _require_str(artifact.get("id"), f"manifest.artifacts[{index}].id")
        license_info = _require_dict(
            artifact.get("license"),
            f"manifest artifact {artifact_id} license",
        )
        record: JsonObject = {
            "binary_bytes": _require_int(artifact.get("bytes"), f"{artifact_id}.bytes"),
            "binary_sha256": _require_sha256(artifact.get("sha256"), f"{artifact_id}.sha256"),
            "binary_url": _require_str(artifact.get("url"), f"{artifact_id}.url"),
            "id": artifact_id,
            "license_spdx": _require_str(license_info.get("spdx"), f"{artifact_id}.license.spdx"),
            "license_url": _require_str(license_info.get("url"), f"{artifact_id}.license.url"),
            "name": _require_str(artifact.get("name"), f"{artifact_id}.name"),
            "source_url": _require_str(artifact.get("source_url"), f"{artifact_id}.source_url"),
            "version": _require_str(artifact.get("version"), f"{artifact_id}.version"),
        }
        for field in (
            "release_date",
            "source_kind",
            "source_ref",
            "source_commit",
            "build_source_url",
            "build_source_commit",
        ):
            value = _optional_str(artifact.get(field))
            if value is not None:
                record[field] = value
        for field in ("source_sha256", "build_source_sha256"):
            value = artifact.get(field)
            if value is not None:
                record[field] = _require_sha256(value, f"{artifact_id}.{field}")
        for field in ("source_bytes", "build_source_bytes"):
            value = artifact.get(field)
            if value is not None:
                record[field] = _require_int(value, f"{artifact_id}.{field}")
        artifacts.append(record)
    artifacts.sort(key=lambda item: str(item["id"]))

    corresponding_sources: list[JsonObject] = []
    for index, raw_source in enumerate(
        _require_list(
            manifest.get("corresponding_sources"),
            "manifest.corresponding_sources",
        )
    ):
        source = _require_dict(raw_source, f"manifest.corresponding_sources[{index}]")
        source_record: JsonObject = {
            "license": _require_str(source.get("license"), f"source[{index}].license"),
            "name": _require_str(source.get("name"), f"source[{index}].name"),
            "source_url": _require_str(source.get("source_url"), f"source[{index}].source_url"),
            "version": _require_str(source.get("version"), f"source[{index}].version"),
        }
        for field in (
            "selection_kind",
            "source_ref",
            "source_commit",
            "release_date",
            "notes",
        ):
            value = _optional_str(source.get(field))
            if value is not None:
                source_record[field] = value
        source_record["sha256"] = _require_sha256(source.get("sha256"), f"source[{index}].sha256")
        source_record["bytes"] = _require_int(source.get("bytes"), f"source[{index}].bytes")
        corresponding_sources.append(source_record)
    corresponding_sources.sort(key=lambda item: (str(item["name"]), str(item["version"])))
    return artifacts, corresponding_sources


def _license_inventory(bundle_root: Path) -> list[JsonObject]:
    licenses_root = bundle_root / "licenses"
    if not licenses_root.is_dir():
        raise ValueError("bundle licenses directory is missing")
    records = [
        {
            "path": path.relative_to(bundle_root).as_posix(),
            "sha256": _sha256(path),
        }
        for path in licenses_root.rglob("*")
        if path.is_file()
    ]
    records.sort(key=lambda item: str(item["path"]))
    return records


def _promote_bundled_inter_license(bundle_root: Path) -> None:
    source = bundle_root / _INTER_LICENSE_SOURCE
    if not source.is_file():
        raise ValueError(f"bundled Inter OFL notice is missing: {_INTER_LICENSE_SOURCE.as_posix()}")
    if _sha256(source) != _INTER_LICENSE_SHA256:
        raise ValueError("bundled Inter OFL notice SHA-256 mismatch")

    destination = bundle_root / _INTER_LICENSE_DESTINATION
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _assert_safe_bundle(bundle_root: Path) -> None:
    prohibited: list[str] = []
    for path in bundle_root.rglob("*"):
        if not path.is_file():
            continue
        relative_path = path.relative_to(bundle_root)
        relative = relative_path.as_posix()
        lowered_parts = tuple(part.casefold() for part in relative_path.parts)
        lowered = "/".join(lowered_parts)
        if (
            lowered_parts[0] in {"config", "comparison_videos"}
            or lowered.startswith("runtime-smoke")
            or "__pycache__" in lowered_parts
            or lowered.endswith((".pyc", ".pyo", ".private.xml"))
            or lowered_parts[-1] in PROHIBITED_BUNDLE_FILENAMES
            or "private_key" in lowered
            or "private-key" in lowered
        ):
            prohibited.append(relative)
    if prohibited:
        raise ValueError(
            "prohibited local/generated files found in bundle: "
            + ", ".join(sorted(set(prohibited)))
        )

    public_key = bundle_root / "shim" / "update_public_key.xml"
    public_text = public_key.read_text(encoding="utf-8")
    for field in PRIVATE_RSA_FIELDS:
        if f"<{field}>" in public_text:
            raise ValueError(f"bundle public key contains private RSA field: {field}")


def _write_source_urls(
    *,
    bundle_root: Path,
    app_version: str,
    commit_sha: str,
    artifacts: list[JsonObject],
    corresponding_sources: list[JsonObject],
    distributions: list[JsonObject],
) -> None:
    source_archive = f"https://github.com/TJZine/frame-compare/archive/{commit_sha}.tar.gz"
    lines = [
        f"Frame Compare {app_version} source ({commit_sha}): {source_archive}",
        "",
        "Bundled application assets:",
        f"- Inter {_INTER_VERSION}: {_INTER_SOURCE_URL}",
        "",
        "Manifest-provided runtime sources:",
    ]
    for artifact in artifacts:
        lines.append(f"- {artifact['name']} {artifact['version']}: {artifact['source_url']}")
        build_source_url = artifact.get("build_source_url")
        if build_source_url is not None:
            lines.append(
                f"- {artifact['name']} build source {artifact['version']}: {build_source_url}"
            )
    lines.extend(("", "Additional corresponding sources:"))
    for source in corresponding_sources:
        lines.append(f"- {source['name']} {source['version']}: {source['source_url']}")
    lines.extend(("", "Installed Python distribution version pages:"))
    for distribution in distributions:
        lines.append(
            f"- {distribution['name']} {distribution['version']}: {distribution['source_url']}"
        )
    (bundle_root / "licenses" / "SOURCE_URLS.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_notices(
    *,
    bundle_root: Path,
    artifacts: list[JsonObject],
    corresponding_sources: list[JsonObject],
    distributions: list[JsonObject],
) -> None:
    lines = [
        "Frame Compare Windows portable third-party inventory",
        "",
        "License texts are under licenses/. Exact versions and declared license metadata are",
        "listed here; hashes are recorded in bundle_inventory.json and source pointers in",
        "SOURCE_URLS.txt.",
        "",
        "Bundled application assets:",
        f"- Inter {_INTER_VERSION} ({_INTER_LICENSE_SPDX})",
        "",
        "Manifest-provided runtimes:",
    ]
    lines.extend(
        f"- {item['name']} {item['version']} ({item['license_spdx']})" for item in artifacts
    )
    lines.extend(("", "Additional corresponding sources:"))
    lines.extend(
        f"- {item['name']} {item['version']} ({item['license']})" for item in corresponding_sources
    )
    lines.extend(("", "Installed Python distributions:"))
    lines.extend(f"- {item['name']} {item['version']}" for item in distributions)
    (bundle_root / "licenses" / "THIRD_PARTY_NOTICES.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    args = _parse_args()
    bundle_root = args.bundle_root.resolve(strict=True)
    manifest_path = args.manifest.resolve(strict=True)
    repo_root = args.repo_root.resolve(strict=True)
    output_path = args.output.resolve(strict=False)
    packaged_src = (bundle_root / "app" / "src").resolve(strict=True)
    if not packaged_src.is_dir():
        raise NotADirectoryError(packaged_src)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(packaged_src))
    from frame_compare.vs.runtime_contract import (  # noqa: PLC0415
        MEDIA_RUNTIME_SCOPES,
    )
    from frame_compare.vs.runtime_contract import (
        media_runtime_fingerprint as canonical_media_runtime_fingerprint,
    )

    commit_sha = _run_git(repo_root, "rev-parse", "HEAD")
    if not re.fullmatch(r"[a-f0-9]{40}", commit_sha):
        raise ValueError("git HEAD is not a full commit SHA")
    if args.require_clean_repo and _run_git(
        repo_root, "status", "--porcelain", "--untracked-files=all"
    ):
        raise ValueError("release bundle inventory requires a clean repository")
    for source_path in SOURCE_SCRIPTS:
        _run_git(repo_root, "cat-file", "-e", f"{commit_sha}:{source_path}")

    manifest = _require_dict(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        "manifest",
    )
    bundle_info = _require_dict(
        json.loads((bundle_root / "bundle_info.json").read_text(encoding="utf-8")),
        "bundle_info",
    )
    schema_version = _require_int(bundle_info.get("schema_version"), "bundle_info.schema_version")
    if schema_version != 2:
        raise ValueError(f"unsupported bundle_info schema_version: {schema_version}")
    app_version = _require_str(bundle_info.get("app_version"), "bundle_info.app_version")
    requirements_sha = _require_sha256(
        bundle_info.get("requirements_lock_sha256"),
        "bundle_info.requirements_lock_sha256",
    )
    media_runtime_fingerprint = _require_sha256(
        bundle_info.get("media_runtime_fingerprint"),
        "bundle_info.media_runtime_fingerprint",
    )
    media_runtime_fingerprints = _require_dict(
        bundle_info.get("media_runtime_fingerprints"),
        "bundle_info.media_runtime_fingerprints",
    )
    expected_scopes = set(MEDIA_RUNTIME_SCOPES)
    if set(media_runtime_fingerprints) != expected_scopes:
        raise ValueError(
            "bundle_info.media_runtime_fingerprints must contain the exact supported scopes"
        )
    validated_media_runtime_fingerprints = {
        scope: _require_sha256(
            media_runtime_fingerprints[scope],
            f"bundle_info.media_runtime_fingerprints.{scope}",
        )
        for scope in sorted(expected_scopes)
    }
    if validated_media_runtime_fingerprints["full"] != media_runtime_fingerprint:
        raise ValueError(
            "bundle_info full media-runtime fingerprint does not match the primary fingerprint"
        )
    manifest_bundle = _require_dict(manifest.get("bundle"), "manifest.bundle")
    manifest_fingerprints = _require_dict(
        manifest_bundle.get("runtime_fingerprints"), "manifest.bundle.runtime_fingerprints"
    )
    if set(manifest_fingerprints) != expected_scopes:
        raise ValueError("manifest runtime fingerprints must contain the exact supported scopes")
    validated_manifest_fingerprints = {
        scope: _require_sha256(
            manifest_fingerprints.get(scope),
            f"manifest.bundle.runtime_fingerprints.{scope}",
        )
        for scope in sorted(expected_scopes)
    }
    if validated_manifest_fingerprints != validated_media_runtime_fingerprints:
        raise ValueError("bundle_info media-runtime fingerprints do not match manifest.json")
    canonical_fingerprints = {
        scope: canonical_media_runtime_fingerprint(scope, profile="windows-x64")
        for scope in MEDIA_RUNTIME_SCOPES
    }
    if validated_manifest_fingerprints != canonical_fingerprints:
        raise ValueError(
            "portable media-runtime fingerprints do not match the canonical windows-x64 contract"
        )

    _assert_safe_bundle(bundle_root)
    _promote_bundled_inter_license(bundle_root)
    distributions = _python_distributions(bundle_root / "app" / "site-packages")
    artifacts, corresponding_sources = _manifest_inventory(manifest)
    _write_source_urls(
        bundle_root=bundle_root,
        app_version=app_version,
        commit_sha=commit_sha,
        artifacts=artifacts,
        corresponding_sources=corresponding_sources,
        distributions=distributions,
    )
    _write_notices(
        bundle_root=bundle_root,
        artifacts=artifacts,
        corresponding_sources=corresponding_sources,
        distributions=distributions,
    )
    licenses = _license_inventory(bundle_root)

    inventory: JsonObject = {
        "bundle": {
            "commit_sha": commit_sha,
            "frame_compare_license": "GPL-3.0-only",
            "name": "Frame Compare",
            "platform": "windows-x64",
            "requirements_lock_sha256": requirements_sha,
            "media_runtime_fingerprint": media_runtime_fingerprint,
            "media_runtime_fingerprints": validated_media_runtime_fingerprints,
            "source_archive_url": (
                f"https://github.com/TJZine/frame-compare/archive/{commit_sha}.tar.gz"
            ),
            "version": app_version,
        },
        "corresponding_sources": corresponding_sources,
        "licenses": licenses,
        "manifest_artifacts": artifacts,
        "python_distributions": distributions,
        "schema_version": 2,
        "source_build_install_scripts": sorted(SOURCE_SCRIPTS),
    }
    output_path.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
