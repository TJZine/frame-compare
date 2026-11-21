from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _validate(repo_root: Path, report: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", "tools/validate_pip_audit.py", str(report)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


def test_pip_audit_evidence_requires_real_dependency_coverage(
    repo_root: Path, tmp_path: Path
) -> None:
    report = tmp_path / "audit.json"
    report.write_text(json.dumps({"dependencies": [], "fixes": []}), encoding="utf-8")

    result = _validate(repo_root, report)

    assert result.returncode == 1
    assert "collected no dependencies" in result.stderr


def test_pip_audit_evidence_accepts_nonempty_well_formed_inventory(
    repo_root: Path, tmp_path: Path
) -> None:
    report = tmp_path / "audit.json"
    report.write_text(
        json.dumps(
            {
                "dependencies": [{"name": "example", "version": "1.2.3", "vulns": []}],
                "fixes": [],
            }
        ),
        encoding="utf-8",
    )

    result = _validate(repo_root, report)

    assert result.returncode == 0, result.stderr
    assert "1 dependencies" in result.stdout
