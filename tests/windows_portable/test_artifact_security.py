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
from tools.windows_portable import artifact_security


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
    repo_root: Path,
    tmp_path: Path,
    *,
    expected_sha: str = "a" * 40,
    artifact_id: str = "123",
    digest: str | None = None,
    member: str = "app/example.txt",
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    archive = tmp_path / "portable.zip"
    _portable(archive, member=member)
    output = tmp_path / "portable-tree"
    scan_input = tmp_path / "scan-input.json"
    result = _run(
        repo_root,
        "stage",
        "--archive",
        str(archive),
        "--expected-digest",
        _digest(archive) if digest is None else digest,
        "--expected-sha",
        expected_sha,
        "--expected-artifact-id",
        artifact_id,
        "--output",
        str(output),
        "--scan-input",
        str(scan_input),
    )
    return result, output, scan_input


def test_artifact_security_stages_only_producer_bound_portable(
    repo_root: Path, tmp_path: Path
) -> None:
    result, output, scan_input = _stage(repo_root, tmp_path)

    assert result.returncode == 0, result.stderr
    assert (output / "app/example.txt").read_bytes() == b"safe inventory input\n"
    evidence = json.loads(scan_input.read_bytes())
    assert evidence["portable_artifact_id"] == "123"
    assert evidence["commit"] == "a" * 40
    assert evidence["portable_sha256"] == _digest(tmp_path / "portable.zip")
    assert evidence["files"] == 1
    assert evidence["directories"] == 1
    assert evidence["expanded_bytes"] == len(b"safe inventory input\n")


@pytest.mark.parametrize(
    "expected_sha, artifact_id, digest, expected",
    [
        ("a" * 40, "123", "0" * 64, "does not match the producer ZIP digest"),
        ("a" * 40, "123", "invalid", "producer ZIP"),
        ("a" * 40, "invalid", None, "immutable numeric ID"),
        ("invalid", "123", None, "full lowercase commit SHA"),
    ],
)
def test_artifact_security_rejects_unbound_inputs(
    repo_root: Path,
    tmp_path: Path,
    expected_sha: str,
    artifact_id: str,
    digest: str | None,
    expected: str,
) -> None:
    result, output, scan_input = _stage(
        repo_root, tmp_path, expected_sha=expected_sha, artifact_id=artifact_id, digest=digest
    )

    assert result.returncode != 0
    assert expected in result.stderr
    assert not scan_input.exists()
    if output.exists():
        assert not any(output.rglob("*"))


def test_artifact_security_refuses_unsafe_zip_even_with_the_expected_digest(
    repo_root: Path, tmp_path: Path
) -> None:
    result, staged, receipt = _stage(repo_root, tmp_path, member="app/../outside.txt")
    assert result.returncode != 0
    assert "Unsafe portable member path" in result.stderr
    assert not receipt.exists()
    assert not any(staged.iterdir())


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _db_status(database: Path) -> dict[str, object]:
    return {
        "schemaVersion": "6.1.7",
        "from": "https://example.invalid/db.tar.zst?checksum=sha256%3A" + "e" * 64,
        "built": datetime.now(UTC).isoformat(),
        "path": str(database),
        "valid": True,
    }


def _policy(
    repo_root: Path,
    tmp_path: Path,
    *,
    matches: list[dict[str, object]] | None = None,
    ignored: list[object] | None = None,
    db_update: dict[str, object] | None = None,
    scanner_version: str = "0.121.0",
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
            "artifacts": [{"name": "demo"}] if syft_artifacts is None else syft_artifacts,
            "descriptor": {"name": "syft", "version": "1.56.0"},
        },
        "cyclonedx": {
            "bomFormat": "CycloneDX",
            "components": [{"name": "demo"}]
            if cyclonedx_components is None
            else cyclonedx_components,
        },
        "grype": {
            "matches": matches or [],
            "ignoredMatches": ignored or [],
            "descriptor": {"name": "grype", "version": scanner_version},
        },
        "db-status": _db_status(database) | (db_update or {}),
    }
    paths: dict[str, Path] = {}
    for name, value in inputs.items():
        paths[name] = tmp_path / f"{name}.json"
        _write_json(paths[name], value)
    output = tmp_path / "artifact-security.json"
    result = _run(
        repo_root,
        "policy",
        *(item for name, path in paths.items() for item in (f"--{name}", str(path))),
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
    assert receipt["policy"] == "passed"
    assert receipt["portable_artifact_id"] == "123"
    assert receipt["portable_sha256"] == "b" * 64
    assert receipt["commit"] == "a" * 40
    assert receipt["database"]["database_sha256"] == _digest(tmp_path / "vulnerability.db")


@pytest.mark.parametrize(
    "matches, ignored, expected",
    [
        ([_match(severity="High")], None, "high severity"),
        ([_match(severity="Critical")], None, "critical severity"),
        ([_match(severity="Unknown")], None, "unknown severity"),
        ([_match(severity="Low", known_exploited=True)], None, "known exploited"),
        (
            [
                _match(severity="Low")
                | {"relatedVulnerabilities": [{"id": "CVE-2026-3456", "severity": "High"}]}
            ],
            None,
            "high severity",
        ),
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


@pytest.mark.parametrize(
    ("db_update", "expected"),
    [
        ({"built": "2020-01-01T00:00:00Z"}, "five-day age limit"),
        ({"valid": False}, "database is not valid"),
        ({"path": ""}, "database file is missing"),
    ],
)
def test_artifact_security_rejects_unusable_database(
    repo_root: Path, tmp_path: Path, db_update: dict[str, object], expected: str
) -> None:
    result, output = _policy(repo_root, tmp_path, db_update=db_update)
    assert result.returncode != 0
    assert expected in result.stderr
    assert not output.exists()


@pytest.mark.parametrize("size", [0, 16, 17])
def test_artifact_security_bounds_database_hash_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    monkeypatch.setattr(artifact_security, "MAX_DATABASE", 16)
    database = tmp_path / "vulnerability.db"
    database.write_bytes(b"x" * size)
    status = tmp_path / "db-status.json"
    _write_json(status, _db_status(database))

    if size == 16:
        assert artifact_security._database_status(status)["database_sha256"] == _digest(database)
    else:
        with pytest.raises(ValueError, match="database file is empty or exceeds the size limit"):
            artifact_security._database_status(status)


def test_artifact_security_rejects_unpinned_scanner(repo_root: Path, tmp_path: Path) -> None:
    result, output = _policy(repo_root, tmp_path, scanner_version="0.121.0-dev")
    assert result.returncode != 0
    assert "verified scanner identity" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    ("syft_artifacts", "cyclonedx_components", "expected"),
    [
        ([], None, "Syft inventory is empty"),
        ([None], None, "Syft inventory is empty"),
        (None, [], "CycloneDX inventory is empty"),
    ],
)
def test_artifact_security_rejects_empty_inventory(
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
