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
def test_powershell_shared_version_vectors(
    repo_root: Path, tmp_path: Path, interpreter: str
) -> None:
    exe = shutil.which(interpreter)
    if exe is None:
        pytest.skip(f"{interpreter} not available for shared version vectors")
    vectors = Path(__file__).with_name("version_vectors.json")
    cases = json.loads(vectors.read_text(encoding="utf-8"))
    (tmp_path / "src/frame_compare").mkdir(parents=True)
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
$source = Join-Path $env:FIXTURE 'src/frame_compare/__init__.py'
foreach ($case in $table.validity) {
  [IO.File]::WriteAllText($source, ('__version__ = "' + $case.value + '"'))
  try { $actual = Get-AppVersionFromSource -RepoRootPath $env:FIXTURE }
  catch {
    if ($case.valid) { throw }
    continue
  }
  if (!$case.valid -or $actual -cne $case.value) { throw "validity: $($case.value)" }
}
@{validity=$table.validity.Count} | ConvertTo-Json -Compress
""",
        ],
        env=os.environ
        | {
            "OWNER": str(repo_root / "tools/windows_portable/version_utils.ps1"),
            "VECTORS": str(vectors),
            "FIXTURE": str(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == {name: len(values) for name, values in cases.items()}
