from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-B",
            "-I",
            "-S",
            str(repo_root / "tools/windows_portable/artifact_security.py"),
            *args,
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def _portable(path: Path, *, member: str = "app/example.txt") -> None:
    prefix = "frame-compare-portable-win-x64/"
    with ZipFile(path, "w", ZIP_DEFLATED, allowZip64=False) as archive:
        for directory in (prefix, f"{prefix}app/"):
            info = ZipInfo(directory)
            info.create_system = 3
            info.external_attr = stat.S_IFDIR << 16 | 0x10
            archive.writestr(info, b"")
        info = ZipInfo(f"{prefix}{member}")
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        info.compress_type = ZIP_DEFLATED
        archive.writestr(info, b"safe inventory input\n")


def _stage(
    repo_root: Path, tmp_path: Path, *, receipt_update: dict[str, object] | None = None
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    archive = tmp_path / "verified-portable.zip"
    _portable(archive)
    sha = "a" * 40
    receipt: dict[str, object] = {
        "schema": 2,
        "commit": sha,
        "tag": "v1.2.3",
        "bundle_sha256": _digest(archive),
        "portable_artifact_id": "123",
        "portable_catalog_sha256": "b" * 64,
        "requirements_sha256": "c" * 64,
        "manifest_sha256": "d" * 64,
    }
    receipt.update(receipt_update or {})
    verification = tmp_path / "verification.json"
    verification.write_text(json.dumps(receipt), encoding="utf-8")
    output = tmp_path / "portable-tree"
    scan_input = tmp_path / "scan-input.json"
    result = _run(
        repo_root,
        "stage",
        "--archive",
        str(archive),
        "--verification",
        str(verification),
        "--expected-sha",
        sha,
        "--expected-artifact-id",
        "123",
        "--output",
        str(output),
        "--scan-input",
        str(scan_input),
    )
    return result, output, scan_input


def test_artifact_security_stages_only_receipt_bound_portable(
    repo_root: Path, tmp_path: Path
) -> None:
    result, output, scan_input = _stage(repo_root, tmp_path)

    assert result.returncode == 0, result.stderr
    assert (output / "app/example.txt").read_bytes() == b"safe inventory input\n"
    evidence = json.loads(scan_input.read_bytes())
    assert evidence["portable_artifact_id"] == "123"
    assert evidence["files"] == 1
    assert evidence["directories"] == 1
    assert evidence["expanded_bytes"] == len(b"safe inventory input\n")


@pytest.mark.parametrize(
    "receipt_update, expected",
    [
        ({"bundle_sha256": "0" * 64}, "does not match"),
        ({"portable_artifact_id": "456"}, "does not match"),
        ({"portable_catalog_sha256": None}, "catalog"),
    ],
)
def test_artifact_security_rejects_unbound_inputs(
    repo_root: Path,
    tmp_path: Path,
    receipt_update: dict[str, object],
    expected: str,
) -> None:
    result, output, scan_input = _stage(repo_root, tmp_path, receipt_update=receipt_update)

    assert result.returncode != 0
    assert expected in result.stderr
    assert not scan_input.exists()
    if output.exists():
        assert not any(output.rglob("*"))


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _policy(
    repo_root: Path,
    tmp_path: Path,
    *,
    matches: list[dict[str, object]] | None = None,
    ignored: list[object] | None = None,
    built: str | None = None,
    syft_artifacts: list[object] | None = None,
    cyclonedx_components: list[object] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    database = tmp_path / "vulnerability.db"
    database.write_bytes(b"validated database")
    inputs = {
        "scan-input": {
            "schema": 1,
            "commit": "a" * 40,
            "portable_artifact_id": "123",
            "portable_sha256": "b" * 64,
        },
        "syft": {
            "artifacts": syft_artifacts
            if syft_artifacts is not None
            else [
                {
                    "id": "package-id",
                    "name": "demo",
                    "version": "1.0",
                    "type": "python",
                    "locations": [{"path": "app/demo.dist-info/METADATA"}],
                }
            ],
            "artifactRelationships": [],
            "source": {
                "id": "source-id",
                "name": "portable-security-tree",
                "type": "directory",
                "metadata": {"path": "/tmp/portable-security-tree"},
            },
            "distro": {},
            "descriptor": {"name": "syft", "version": "1.56.0"},
            "schema": {
                "version": "16.1.12",
                "url": "https://raw.githubusercontent.com/anchore/syft/v1.56.0/schema/json/schema-16.1.12.json",
            },
        },
        "cyclonedx": {
            "$schema": "http://cyclonedx.org/schema/bom-1.7.schema.json",
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "version": 1,
            "metadata": {
                "tools": {
                    "components": [{"type": "application", "name": "syft", "version": "1.56.0"}]
                }
            },
            "components": cyclonedx_components
            if cyclonedx_components is not None
            else [
                {
                    "bom-ref": "package-id",
                    "type": "library",
                    "name": "demo",
                    "version": "1.0",
                }
            ],
        },
        "grype": {
            "matches": matches or [],
            "ignoredMatches": ignored or [],
            "descriptor": {"name": "grype", "version": "0.121.0"},
            "source": {"type": "directory", "target": "portable-security-tree"},
        },
        "db-status": {
            "schemaVersion": "6.1.7",
            "from": "https://example.invalid/db.tar.zst?checksum=sha256%3A" + "e" * 64,
            "built": built or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "path": str(database),
            "valid": True,
        },
    }
    paths: dict[str, Path] = {}
    for name, value in inputs.items():
        paths[name] = tmp_path / f"{name}.json"
        _write_json(paths[name], value)
    syft_version = tmp_path / "syft-version.txt"
    grype_version = tmp_path / "grype-version.txt"
    syft_version.write_text("syft 1.56.0\n", encoding="utf-8")
    grype_version.write_text("grype 0.121.0\n", encoding="utf-8")
    output = tmp_path / "artifact-security.json"
    result = _run(
        repo_root,
        "policy",
        *(item for name, path in paths.items() for item in (f"--{name}", str(path))),
        "--syft-version",
        str(syft_version),
        "--grype-version",
        str(grype_version),
        "--expected-syft-version",
        "1.56.0",
        "--expected-grype-version",
        "0.121.0",
        "--output",
        str(output),
    )
    return result, output


def _match(*, severity: str, known_exploited: bool = False) -> dict[str, object]:
    return {
        "artifact": {"name": "demo", "version": "1.0", "type": "python"},
        "vulnerability": {
            "id": "CVE-2026-1234",
            "severity": severity,
            "knownExploited": ([{"cve": "CVE-2026-1234"}] if known_exploited else []),
        },
        "relatedVulnerabilities": [],
    }


def test_artifact_security_accepts_complete_lower_severity_evidence(
    repo_root: Path, tmp_path: Path
) -> None:
    result, output = _policy(repo_root, tmp_path, matches=[_match(severity="Medium")])

    assert result.returncode == 0, result.stderr
    receipt = json.loads(output.read_bytes())
    assert receipt["inventory_packages"] == 1
    assert receipt["advisory_severities"] == {"medium": 1}
    assert receipt["known_exploited_matches"] == 0
    assert receipt["database"]["database_sha256"] == _digest(tmp_path / "vulnerability.db")


@pytest.mark.parametrize(
    "matches, ignored, expected",
    [
        ([_match(severity="High")], None, "high severity"),
        ([_match(severity="Unknown")], None, "unknown severity"),
        ([_match(severity="Low", known_exploited=True)], None, "known exploited"),
        (None, [{"reason": "broad suppression"}], "suppressed findings"),
    ],
)
def test_artifact_security_blocks_unacceptable_or_suppressed_findings(
    repo_root: Path,
    tmp_path: Path,
    matches: list[dict[str, object]] | None,
    ignored: list[object] | None,
    expected: str,
) -> None:
    result, output = _policy(repo_root, tmp_path, matches=matches, ignored=ignored)

    assert result.returncode != 0
    assert expected in result.stderr
    assert not output.exists()


def test_artifact_security_rejects_stale_database(repo_root: Path, tmp_path: Path) -> None:
    result, output = _policy(repo_root, tmp_path, built="2020-01-01T00:00:00Z")

    assert result.returncode != 0
    assert "five-day age limit" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    ("syft_artifacts", "cyclonedx_components", "expected"),
    [
        ([None], None, "malformed package"),
        (None, [None], "malformed component"),
        ([], None, "Syft inventory is empty"),
        (None, [], "CycloneDX inventory is empty"),
    ],
)
def test_artifact_security_rejects_vacuous_or_malformed_inventory_entries(
    repo_root: Path,
    tmp_path: Path,
    syft_artifacts: list[object] | None,
    cyclonedx_components: list[object] | None,
    expected: str,
) -> None:
    result, output = _policy(
        repo_root,
        tmp_path,
        syft_artifacts=syft_artifacts,
        cyclonedx_components=cyclonedx_components,
    )

    assert result.returncode != 0
    assert expected in result.stderr
    assert not output.exists()
