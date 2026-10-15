from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from scripts.validate_release_contract import RC_VERSION_RE, STABLE_VERSION_RE


def test_release_contract_shared_validity_vectors() -> None:
    vectors = json.loads(
        Path(__file__).with_name("version_vectors.json").read_text(encoding="utf-8")
    )
    for case in vectors["validity"]:
        valid = bool(
            STABLE_VERSION_RE.fullmatch(case["value"]) or RC_VERSION_RE.fullmatch(case["value"])
        )
        assert valid == case["valid"], case


@pytest.mark.parametrize("interpreter", ["powershell", "pwsh"])
def test_powershell_shared_version_vectors(repo_root: Path, interpreter: str) -> None:
    exe = shutil.which(interpreter)
    if exe is None:
        pytest.skip(f"{interpreter} not available for shared version vectors")
    vectors = Path(__file__).with_name("version_vectors.json")
    cases = json.loads(vectors.read_text(encoding="utf-8"))
    result = subprocess.run(
        [
            exe,
            "-NoProfile",
            "-Command",
            r"""
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. $env:OWNER
$table = Get-Content -LiteralPath $env:VECTORS -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($case in $table.validity) {
  $expected = $case.valid
  if ($null -ne $case.PSObject.Properties['powershell_valid']) { $expected = $case.powershell_valid }
  if (($null -ne (ConvertTo-FrameCompareVersion $case.value)) -ne $expected) { throw "validity: $($case.value)" }
}
foreach ($case in $table.ordering) {
  if ((Compare-FrameCompareVersion $case.left $case.right) -ne $case.order) { throw "ordering: $($case.left), $($case.right)" }
}
foreach ($case in $table.ranges) {
  if ((Test-FrameCompareVersionInRange $case.value $case.min $case.max) -ne $case.allowed) { throw "range: $($case.value)" }
}
@{validity=$table.validity.Count; ordering=$table.ordering.Count; ranges=$table.ranges.Count} | ConvertTo-Json -Compress
""",
        ],
        env=os.environ
        | {
            "OWNER": str(repo_root / "tools/windows_portable/shim/frame-compare-version.ps1"),
            "VECTORS": str(vectors),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {name: len(values) for name, values in cases.items()}
