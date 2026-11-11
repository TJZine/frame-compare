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
# The observed Grype v6 database is about 3.2 GiB. Allow growth while bounding the hash read.
MAX_DATABASE = 8 * 1024**3
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
ARTIFACT_ID = re.compile(r"[1-9][0-9]*")
ALLOWED_SEVERITIES = {"negligible", "low", "medium"}


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


def _require_scanner(report: dict[str, Any], name: str, version: str) -> None:
    descriptor = report.get("descriptor")
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("name") != name
        or descriptor.get("version") != version
    ):
        raise ValueError(f"{name} report lacks verified scanner identity")


def _inventory_count(report: dict[str, Any], field: str, label: str) -> int:
    inventory = report.get(field)
    if not isinstance(inventory, list) or not any(
        isinstance(entry, dict) and entry.get("name") for entry in inventory
    ):
        raise ValueError(f"{label} inventory is empty")
    return len(inventory)


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
        or receipt.get("portable_reproduced") is not True
        or receipt.get("commit") != args.expected_sha
        or receipt.get("portable_artifact_id") != args.expected_artifact_id
        or receipt.get("bundle_sha256") != archive_digest
    ):
        raise ValueError("Portable artifact does not match its verification receipt")
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
            "portable_reproduced": True,
            "files": file_count,
            "directories": directory_count,
            "expanded_bytes": expanded_bytes,
        },
    )


def _database_status(path: Path) -> dict[str, Any]:
    status = _read_json(path, MAX_RECEIPT)
    if status.get("valid") is not True:
        raise ValueError("Grype vulnerability database is not valid")
    built_value = status.get("built")
    if not isinstance(built_value, str):
        raise ValueError("Grype vulnerability database lacks a build time")
    built = datetime.fromisoformat(built_value)
    if built.tzinfo is None:
        raise ValueError("Grype vulnerability database lacks a timezone for its build time")
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
    if not database_path.is_file():
        raise ValueError("Grype vulnerability database file is missing")
    with database_path.open("rb") as stream:
        size = stream.seek(0, 2)
        if not 0 < size <= MAX_DATABASE:
            raise ValueError("Grype vulnerability database file is empty or exceeds the size limit")
        stream.seek(0)
        database_digest = copy_exact(stream, size)
    return {
        "schema_version": status.get("schemaVersion"),
        "built": built_value,
        "source": source,
        "archive_sha256": archive_digest,
        "database_sha256": database_digest,
    }


def _validate_findings(report: dict[str, Any]) -> Counter[str]:
    if report.get("ignoredMatches", []) != []:
        raise ValueError("Grype report contains suppressed findings")
    matches = report.get("matches")
    if not isinstance(matches, list):
        raise ValueError("Grype report lacks a findings list")
    counts: Counter[str] = Counter()
    for match in matches:
        if not isinstance(match, dict) or not isinstance(
            match.get("relatedVulnerabilities", []), list
        ):
            raise ValueError("Grype report contains an incomplete finding")
        for vulnerability in [match.get("vulnerability"), *match.get("relatedVulnerabilities", [])]:
            if not isinstance(vulnerability, dict):
                raise ValueError("Grype report contains malformed vulnerability metadata")
            identifier = vulnerability.get("id", "<unknown>")
            severity = str(vulnerability.get("severity") or "unknown").lower()
            kev = vulnerability.get("knownExploited", [])
            if not isinstance(kev, list):
                raise ValueError("Grype report contains malformed KEV metadata")
            if kev:
                raise ValueError(
                    f"Artifact advisory policy blocked release: {identifier} is known exploited"
                )
            if severity not in ALLOWED_SEVERITIES:
                raise ValueError(
                    f"Artifact advisory policy blocked release: {identifier} has {severity} severity"
                )
            counts[severity] += 1
    return counts


def _policy(args: argparse.Namespace) -> None:
    scan_input = _read_json(args.scan_input, MAX_RECEIPT)
    if (
        scan_input.get("schema") != 1
        or scan_input.get("portable_reproduced") is not True
        or COMMIT.fullmatch(str(scan_input.get("commit", ""))) is None
        or ARTIFACT_ID.fullmatch(str(scan_input.get("portable_artifact_id", ""))) is None
    ):
        raise ValueError("Scan input receipt is malformed")

    _require_digest(scan_input.get("portable_sha256"), "portable")
    _require_digest(scan_input.get("verification_sha256"), "verification receipt")
    syft = _read_json(args.syft, MAX_SCAN_DOCUMENT)
    _require_scanner(syft, "syft", args.expected_syft_version)
    package_count = _inventory_count(syft, "artifacts", "Syft")
    cyclonedx = _read_json(args.cyclonedx, MAX_SCAN_DOCUMENT)
    if cyclonedx.get("bomFormat") != "CycloneDX":
        raise ValueError("Expected a CycloneDX inventory")
    component_count = _inventory_count(cyclonedx, "components", "CycloneDX")
    grype = _read_json(args.grype, MAX_SCAN_DOCUMENT)
    _require_scanner(grype, "grype", args.expected_grype_version)
    counts = _validate_findings(grype)
    database = _database_status(args.db_status)

    _write_json(
        args.output,
        {
            "schema": 1,
            **scan_input,
            "syft_version": args.expected_syft_version,
            "grype_version": args.expected_grype_version,
            "policy": "passed",
            "database": database,
            "inventory_packages": package_count,
            "cyclonedx_components": component_count,
            "advisory_matches": sum(counts.values()),
            "advisory_severities": dict(sorted(counts.items())),
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
    policy.add_argument("--expected-syft-version", required=True)
    policy.add_argument("--expected-grype-version", required=True)
    policy.add_argument("--output", type=Path, required=True)
    policy.set_defaults(handler=_policy)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        args.handler(args)
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
