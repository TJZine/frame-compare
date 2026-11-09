"""Safely stage and policy-check final Windows portable security evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from portable_archive import checked_zip, copy_exact, digest_file

PREFIX = "frame-compare-portable-win-x64/"
MAX_RECEIPT = 16 * 1024
MAX_SCAN_DOCUMENT = 512 * 1024**2
MAX_DATABASE = 1024**3
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
ARTIFACT_ID = re.compile(r"[1-9][0-9]*")
ALLOWED_SEVERITIES = {"negligible", "low", "medium"}
BLOCKED_SEVERITIES = {"high", "critical", "unknown", ""}
SYFT_SCHEMA_VERSION = "16.1.12"
CYCLONEDX_SPEC_VERSION = "1.7"


def _read_json(path: Path, limit: int) -> dict[str, Any]:
    size = path.stat().st_size
    if not 0 < size <= limit:
        raise ValueError(f"Security evidence has an invalid size: {path.name}")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"Security evidence is not a JSON object: {path.name}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )


def _require_digest(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError(f"Invalid {label} digest")
    return value


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4096


def _validate_syft_inventory(report: dict[str, Any], scanner_version: str) -> int:
    artifacts = report.get("artifacts")
    descriptor = report.get("descriptor")
    schema = report.get("schema")
    source = report.get("source")
    if not isinstance(artifacts, list) or not artifacts:
        raise ValueError("Syft inventory is empty")
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("name") != "syft"
        or descriptor.get("version") != scanner_version
    ):
        raise ValueError("Syft inventory lacks verified scanner identity")
    if (
        not isinstance(schema, dict)
        or schema.get("version") != SYFT_SCHEMA_VERSION
        or not _text(schema.get("url"))
        or SYFT_SCHEMA_VERSION not in str(schema.get("url"))
    ):
        raise ValueError("Syft inventory does not identify the pinned JSON schema")
    if not isinstance(report.get("artifactRelationships"), list) or not isinstance(
        report.get("distro"), dict
    ):
        raise ValueError("Syft inventory is missing required document fields")
    if (
        not isinstance(source, dict)
        or source.get("type") != "directory"
        or not _text(source.get("id"))
        or not _text(source.get("name"))
        or not isinstance(source.get("metadata"), dict)
        or not _text(source["metadata"].get("path"))
    ):
        raise ValueError("Syft inventory lacks directory source provenance")
    for artifact in artifacts:
        if (
            not isinstance(artifact, dict)
            or any(not _text(artifact.get(field)) for field in ("id", "name", "version", "type"))
            or not isinstance(artifact.get("locations"), list)
            or not artifact["locations"]
        ):
            raise ValueError("Syft inventory contains a malformed package")
    return len(artifacts)


def _validate_cyclonedx_inventory(report: dict[str, Any], scanner_version: str) -> int:
    components = report.get("components")
    metadata = report.get("metadata")
    if (
        report.get("bomFormat") != "CycloneDX"
        or report.get("specVersion") != CYCLONEDX_SPEC_VERSION
        or report.get("version") != 1
        or report.get("$schema")
        not in {
            "http://cyclonedx.org/schema/bom-1.7.schema.json",
            "https://cyclonedx.org/schema/bom-1.7.schema.json",
        }
    ):
        raise ValueError("CycloneDX inventory does not identify the pinned schema")
    if not isinstance(components, list) or not components:
        raise ValueError("CycloneDX inventory is empty")
    tools = metadata.get("tools") if isinstance(metadata, dict) else None
    tool_components = tools.get("components") if isinstance(tools, dict) else None
    if not isinstance(tool_components, list) or not any(
        isinstance(tool, dict)
        and tool.get("name") == "syft"
        and tool.get("version") == scanner_version
        for tool in tool_components
    ):
        raise ValueError("CycloneDX inventory lacks verified scanner identity")
    for component in components:
        if (
            not isinstance(component, dict)
            or any(not _text(component.get(field)) for field in ("bom-ref", "type", "name"))
            or (component.get("type") != "file" and not _text(component.get("version")))
        ):
            raise ValueError("CycloneDX inventory contains a malformed component")
    return len(components)


def _validate_grype_source(report: dict[str, Any], scanner_version: str) -> None:
    descriptor = report.get("descriptor")
    source = report.get("source")
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("name") != "grype"
        or descriptor.get("version") != scanner_version
    ):
        raise ValueError("Grype report lacks verified scanner identity")
    if (
        not isinstance(source, dict)
        or source.get("type") != "directory"
        or not _text(source.get("target"))
    ):
        raise ValueError("Grype report lacks scanned-directory source provenance")


def _stage(args: argparse.Namespace) -> None:
    if COMMIT.fullmatch(args.expected_sha) is None:
        raise ValueError("Expected SHA must be a full lowercase commit SHA")
    if ARTIFACT_ID.fullmatch(args.expected_artifact_id) is None:
        raise ValueError("Portable artifact ID must be an immutable numeric ID")
    if args.output.exists():
        raise ValueError("Portable scan output directory must not already exist")

    receipt = _read_json(args.verification, MAX_RECEIPT)
    archive_digest = digest_file(args.archive)
    if (
        receipt.get("schema") != 2
        or receipt.get("commit") != args.expected_sha
        or receipt.get("portable_artifact_id") != args.expected_artifact_id
        or receipt.get("bundle_sha256") != archive_digest
    ):
        raise ValueError("Portable artifact does not match its verification receipt")
    catalog_digest = _require_digest(receipt.get("portable_catalog_sha256"), "catalog")
    _require_digest(receipt.get("requirements_sha256"), "requirements")
    _require_digest(receipt.get("manifest_sha256"), "manifest")

    args.output.mkdir(parents=True)
    file_count = directory_count = expanded_bytes = 0
    with checked_zip(args.archive) as archive:
        for entry in archive.infolist():
            name = entry.filename
            if not name.startswith(PREFIX):
                raise ValueError("Portable archive member is outside its canonical root")
            relative = name.removeprefix(PREFIX).removesuffix("/")
            if not relative:
                if not entry.is_dir():
                    raise ValueError("Portable canonical root must be a directory")
                continue
            target = args.output.joinpath(*relative.split("/"))
            if entry.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                directory_count += 1
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(entry) as source, target.open("xb") as destination:
                copy_exact(source, entry.file_size, destination)
            file_count += 1
            expanded_bytes += entry.file_size

    if file_count == 0:
        raise ValueError("Portable artifact contains no files to inventory")
    _write_json(
        args.scan_input,
        {
            "schema": 1,
            "commit": args.expected_sha,
            "tag": receipt.get("tag"),
            "portable_artifact_id": args.expected_artifact_id,
            "portable_sha256": archive_digest,
            "verification_sha256": digest_file(args.verification),
            "portable_catalog_sha256": catalog_digest,
            "files": file_count,
            "directories": directory_count,
            "expanded_bytes": expanded_bytes,
        },
    )


def _version(path: Path, expected: str, label: str) -> str:
    value = path.read_text(encoding="utf-8")
    if len(value) > 4096 or expected not in value:
        raise ValueError(f"Unexpected {label} version output")
    return expected


def _database_status(path: Path) -> dict[str, Any]:
    status = _read_json(path, MAX_RECEIPT)
    if status.get("valid") is not True:
        raise ValueError("Grype vulnerability database is not valid")
    built_value = status.get("built")
    if not isinstance(built_value, str):
        raise ValueError("Grype vulnerability database lacks a build time")
    built = datetime.fromisoformat(built_value.replace("Z", "+00:00")).astimezone(UTC)
    now = datetime.now(UTC)
    if built > now + timedelta(minutes=5) or now - built > timedelta(days=5):
        raise ValueError("Grype vulnerability database is outside the five-day age limit")

    source = status.get("from")
    if not isinstance(source, str):
        raise ValueError("Grype vulnerability database lacks source provenance")
    checksums = parse_qs(urlparse(source).query).get("checksum", [])
    if len(checksums) != 1 or not checksums[0].startswith("sha256:"):
        raise ValueError("Grype vulnerability database source lacks a SHA-256 checksum")
    archive_digest = checksums[0].removeprefix("sha256:")
    _require_digest(archive_digest, "database archive")

    database_path = Path(str(status.get("path", "")))
    if not database_path.is_file() or not 0 < database_path.stat().st_size <= MAX_DATABASE:
        raise ValueError("Grype vulnerability database file is missing or oversized")
    return {
        "schema_version": status.get("schemaVersion"),
        "built": built_value,
        "source": source,
        "archive_sha256": archive_digest,
        "database_sha256": digest_file(database_path),
    }


def _validate_findings(report: dict[str, Any]) -> tuple[Counter[str], int]:
    if report.get("ignoredMatches"):
        raise ValueError("Grype report contains suppressed findings")
    matches = report.get("matches")
    if not isinstance(matches, list):
        raise ValueError("Grype report lacks a findings list")
    counts: Counter[str] = Counter()
    known_exploited = 0
    blockers: list[str] = []
    for match in matches:
        if not isinstance(match, dict):
            raise ValueError("Grype report contains a malformed finding")
        artifact = match.get("artifact")
        primary = match.get("vulnerability")
        related = match.get("relatedVulnerabilities", [])
        if (
            not isinstance(artifact, dict)
            or not isinstance(primary, dict)
            or not isinstance(related, list)
        ):
            raise ValueError("Grype report contains an incomplete finding")
        package = f"{artifact.get('name', '<unknown>')}@{artifact.get('version', '<unknown>')}"
        vulnerabilities = [primary, *related]
        for vulnerability in vulnerabilities:
            if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get("id"), str):
                raise ValueError("Grype report contains malformed vulnerability metadata")
            severity = str(vulnerability.get("severity", "")).lower()
            counts[severity or "unknown"] += 1
            kev = vulnerability.get("knownExploited", [])
            if not isinstance(kev, list):
                raise ValueError("Grype report contains malformed KEV metadata")
            if kev:
                known_exploited += 1
                blockers.append(f"{vulnerability['id']} ({package}) is known exploited")
            if severity in BLOCKED_SEVERITIES or severity not in ALLOWED_SEVERITIES:
                blockers.append(
                    f"{vulnerability['id']} ({package}) has {severity or 'unknown'} severity"
                )
    if blockers:
        preview = "; ".join(blockers[:20])
        suffix = f"; plus {len(blockers) - 20} more" if len(blockers) > 20 else ""
        raise ValueError(f"Artifact advisory policy blocked release: {preview}{suffix}")
    return counts, known_exploited


def _policy(args: argparse.Namespace) -> None:
    scan_input = _read_json(args.scan_input, MAX_RECEIPT)
    if (
        scan_input.get("schema") != 1
        or COMMIT.fullmatch(str(scan_input.get("commit", ""))) is None
        or ARTIFACT_ID.fullmatch(str(scan_input.get("portable_artifact_id", ""))) is None
    ):
        raise ValueError("Scan input receipt is malformed")

    syft_version = _version(args.syft_version, args.expected_syft_version, "Syft")
    grype_version = _version(args.grype_version, args.expected_grype_version, "Grype")

    syft = _read_json(args.syft, MAX_SCAN_DOCUMENT)
    package_count = _validate_syft_inventory(syft, syft_version)
    cyclonedx = _read_json(args.cyclonedx, MAX_SCAN_DOCUMENT)
    component_count = _validate_cyclonedx_inventory(cyclonedx, syft_version)
    grype = _read_json(args.grype, MAX_SCAN_DOCUMENT)
    _validate_grype_source(grype, grype_version)
    counts, known_exploited = _validate_findings(grype)
    database = _database_status(args.db_status)

    _write_json(
        args.output,
        {
            "schema": 1,
            **scan_input,
            "syft_version": syft_version,
            "grype_version": grype_version,
            "database": database,
            "inventory_packages": package_count,
            "cyclonedx_components": component_count,
            "advisory_matches": sum(counts.values()),
            "advisory_severities": dict(sorted(counts.items())),
            "known_exploited_matches": known_exploited,
            "syft_sha256": digest_file(args.syft),
            "cyclonedx_sha256": digest_file(args.cyclonedx),
            "grype_sha256": digest_file(args.grype),
            "db_status_sha256": digest_file(args.db_status),
        },
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    stage = subparsers.add_parser("stage", help="validate and safely extract the portable ZIP")
    stage.add_argument("--archive", type=Path, required=True)
    stage.add_argument("--verification", type=Path, required=True)
    stage.add_argument("--expected-sha", required=True)
    stage.add_argument("--expected-artifact-id", required=True)
    stage.add_argument("--output", type=Path, required=True)
    stage.add_argument("--scan-input", type=Path, required=True)
    stage.set_defaults(handler=_stage)

    policy = subparsers.add_parser("policy", help="validate SBOM and advisory evidence")
    for name in ("scan-input", "syft", "cyclonedx", "grype", "db-status"):
        policy.add_argument(f"--{name}", type=Path, required=True)
    policy.add_argument("--syft-version", type=Path, required=True)
    policy.add_argument("--grype-version", type=Path, required=True)
    policy.add_argument("--expected-syft-version", required=True)
    policy.add_argument("--expected-grype-version", required=True)
    policy.add_argument("--output", type=Path, required=True)
    policy.set_defaults(handler=_policy)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
