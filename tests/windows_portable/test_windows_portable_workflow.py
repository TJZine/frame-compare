from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import step_by_name as _step_by_name
from tests.workflows._helpers import bash_executable_or_skip as _bash_executable_or_skip
from tests.workflows._helpers import bash_path_or_skip as _bash_path_or_skip

_SCRIPT_TIMEOUT_SECONDS = 10.0


def _build_action(repo_root: Path) -> dict[str, Any]:
    return _load_workflow(repo_root / ".github/actions/windows-portable-build/action.yml")["runs"]


def test_windows_portable_workflow_delegates_extracted_bundle_verification(
    repo_root: Path,
) -> None:
    verify_step = _step_by_name(_build_action(repo_root), "Verify extracted portable bundle")
    assert "tools/windows_portable/verify_extracted_bundle.ps1" in verify_step["run"]
    assert "-ZipPath dist/frame-compare-portable-win-x64.zip" in verify_step["run"]
    assert "-ExtractRoot dist/zip_extract_check" in verify_step["run"]
    assert verify_step["env"] == {"EXPECTED_SHA": "${{ inputs.expected_sha }}"}
    assert '-ExpectedCommitSha "$env:EXPECTED_SHA"' in verify_step["run"]
    assert "WINDOWS_EXTRACTED_PROOF license_inventory=ok" in verify_step["run"]
    assert "WINDOWS_EXTRACTED_PROOF vsview_distributions=ok" in verify_step["run"]
    assert (
        "WINDOWS_EXTRACTED_PROOF qt_webengine_runtime=absent deployment=excluded"
        in verify_step["run"]
    )
    assert "WINDOWS_EXTRACTED_PROOF result=ok" in verify_step["run"]
    assert "inputs.expected_sha" not in verify_step["run"]
    assert "-CommandTimeoutSeconds 300" in verify_step["run"]


def test_windows_portable_workflow_installs_native_vsview_extra(repo_root: Path) -> None:
    install_step = _step_by_name(_build_action(repo_root), "Install dev dependencies (frozen)")

    assert (
        "uv sync --all-groups --extra vsview --frozen --no-build --no-install-package anitopy"
        in (install_step["run"])
    )
    assert "portable_runtime.py anitopy-wheel" in install_step["run"]
    assert (
        "uv --offline --no-config pip install --no-index --no-deps --no-build"
        in (install_step["run"])
    )


def test_windows_portable_workflow_requires_native_alignment_package_proof(
    repo_root: Path,
) -> None:
    build_step = _step_by_name(_build_action(repo_root), "Build portable bundle")
    for marker in (
        "project_entrypoint=ok source=app/src",
        "alignment_panel=ok state=inactive platform=offscreen",
        "alignment_metadata=ok outputs=Reference,Comparison_1",
        "alignment_result_roundtrip=ok",
        "alignment_result_validation=ok malformed=rejected",
    ):
        assert marker in build_step["run"]


def test_windows_portable_manual_verify_binds_exact_sha_to_selected_ref(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _load_workflow(workflow_path)
    validate = workflow["jobs"]["validate_manual"]
    verify = workflow["jobs"]["verify_manual"]
    step = validate["steps"][0]

    assert validate["permissions"] == {}
    assert "secrets" not in validate
    assert validate["outputs"] == {"expected_sha": "${{ steps.validate.outputs.expected_sha }}"}
    assert step["env"] == {
        "DISPATCH_REF_NAME": "${{ github.ref_name }}",
        "DISPATCH_REF_PROTECTED": "${{ github.ref_protected }}",
        "DISPATCH_REF_TYPE": "${{ github.ref_type }}",
        "VERIFY_CHANNEL": "${{ inputs.channel }}",
        "DISPATCH_SHA": "${{ github.sha }}",
        "EXPECTED_SHA": "${{ inputs.expected_sha || github.sha }}",
    }
    assert verify["needs"] == "validate_manual"
    assert verify["with"]["expected_sha"] == ("${{ needs.validate_manual.outputs.expected_sha }}")
    assert verify["with"]["environment_name"] == (
        "${{ inputs.channel == 'stable' && 'production' || 'release-candidate' }}"
    )
    assert verify["secrets"] == {
        "WINDOWS_UPDATE_SIGNING_KEY_XML": "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    }


@pytest.mark.parametrize(
    ("expected_sha", "dispatch_sha", "ref_type", "ref_name", "protected", "channel", "succeeds"),
    [
        ("a" * 40, "a" * 40, "branch", "main", "true", "stable", True),
        ("a" * 40, "a" * 40, "branch", "pre-release", "true", "rc", True),
        ("a" * 40, "a" * 40, "branch", "main", "true", "rc", False),
        ("a" * 40, "a" * 40, "branch", "pre-release", "true", "stable", False),
        ("b" * 40, "b" * 40, "tag", "v0.5.0", "true", "stable", False),
        ("c" * 40, "c" * 40, "tag", "v0.6.0-rc.1", "true", "rc", False),
        ("A" * 40, "A" * 40, "branch", "main", "true", "stable", False),
        ("a" * 40, "b" * 40, "branch", "main", "true", "stable", False),
        ("a" * 40, "a" * 40, "branch", "pre-release", "false", "rc", False),
        ("a" * 40, "a" * 40, "branch", "topic", "false", "rc", False),
        ("a" * 40, "a" * 40, "pull_request", "1/merge", "false", "rc", False),
    ],
)
def test_windows_portable_manual_sha_validation_fails_closed(
    repo_root: Path,
    tmp_path: Path,
    expected_sha: str,
    dispatch_sha: str,
    ref_type: str,
    ref_name: str,
    protected: str,
    channel: str,
    succeeds: bool,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "windows-portable.yml")
    script = workflow["jobs"]["validate_manual"]["steps"][0]["run"]
    output = tmp_path / "github-output"
    bash = _bash_executable_or_skip()

    completed = subprocess.run(
        [bash, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        timeout=_SCRIPT_TIMEOUT_SECONDS,
        env=os.environ
        | {
            "DISPATCH_REF_NAME": ref_name,
            "DISPATCH_REF_PROTECTED": protected,
            "DISPATCH_REF_TYPE": ref_type,
            "DISPATCH_SHA": dispatch_sha,
            "VERIFY_CHANNEL": channel,
            "EXPECTED_SHA": expected_sha,
            "GITHUB_OUTPUT": _bash_path_or_skip(bash, output),
        },
    )

    assert (completed.returncode == 0) is succeeds, completed.stderr
    assert output.exists() is succeeds
    if succeeds:
        assert output.read_text(encoding="utf-8") == f"expected_sha={expected_sha}\n"


def test_windows_portable_jobs_enforce_distinct_trust_boundaries(repo_root: Path) -> None:
    path = repo_root / ".github/workflows/windows-portable-build.yml"
    workflow = _load_workflow(path)
    jobs = workflow["jobs"]
    assert set(jobs) == {
        "build_test",
        "verify_unsigned",
        "artifact_security",
        "sign_manifest",
        "package_attest",
    }
    assert workflow["permissions"] == {}
    assert "needs" not in jobs["build_test"]
    assert jobs["verify_unsigned"]["needs"] == "build_test"
    verify = _step_by_name(jobs["verify_unsigned"], "Verify unsigned inputs on a fresh runner")
    assert verify["with"]["require_portable_authority"] == "true"
    assert jobs["artifact_security"]["needs"] == "verify_unsigned"
    assert jobs["sign_manifest"]["needs"] == ["verify_unsigned", "artifact_security"]
    assert jobs["package_attest"]["needs"] == [
        "verify_unsigned",
        "artifact_security",
        "sign_manifest",
    ]
    secret_inputs = workflow["on"]["workflow_call"]["secrets"]
    assert set(secret_inputs) == {"WINDOWS_UPDATE_SIGNING_KEY_XML"}
    assert secret_inputs["WINDOWS_UPDATE_SIGNING_KEY_XML"]["required"] == "true"
    for name, job in jobs.items():
        assert job["runs-on"] == (
            "ubuntu-24.04" if name == "artifact_security" else "windows-latest"
        )
        permissions = {"contents": "read"}
        if name == "package_attest":
            permissions |= {"id-token": "write", "attestations": "write"}
        assert job["permissions"] == permissions
        if name == "sign_manifest":
            assert job["environment"] == {"name": "${{ inputs.environment_name }}"}
        else:
            assert "environment" not in job
        checkout = _step_by_name(job, "Checkout exact source")
        assert checkout["with"] == {
            "ref": "${{ inputs.expected_sha }}",
            "fetch-depth": "1",
            "persist-credentials": "false",
        }
        guard = _step_by_name(job, "Verify exact checkout")
        assert guard["env"] == {"EXPECTED_SHA": "${{ inputs.expected_sha }}"}
        if name == "artifact_security":
            assert '"$(git rev-parse HEAD)" != "$EXPECTED_SHA"' in guard["run"]
        else:
            assert "(git rev-parse HEAD).Trim() -cne $env:EXPECTED_SHA" in guard["run"]

    secret_ref = "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    assert path.read_text(encoding="utf-8").count(secret_ref) == 1
    signer = jobs["sign_manifest"]
    sign = _step_by_name(signer, "Sign approved manifest bytes")
    assert sign["env"]["WINDOWS_UPDATE_SIGNING_KEY_XML"] == secret_ref
    prepare = _step_by_name(signer, "Regenerate and compare manifest from the exact checkout")
    assert "release_update.ps1 -Stage PrepareSigning" in prepare["run"]
    assert signer["steps"].index(prepare) < signer["steps"].index(sign)
    assert "sign_verified_manifest.ps1" in sign["run"]
    assert not any(
        "secrets: inherit" in item.read_text(encoding="utf-8")
        for item in (repo_root / ".github/workflows").glob("*.yml")
    )


def test_windows_portable_privileged_jobs_use_allowlisted_steps_and_handoffs(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github/workflows/windows-portable-build.yml")
    jobs = workflow["jobs"]
    downloads = {
        "sign_manifest": [
            "needs.verify_unsigned.outputs.manifest_id",
            "needs.verify_unsigned.outputs.receipt_id",
        ],
        "package_attest": [
            "needs.verify_unsigned.outputs.verified_bundle_id",
            "needs.verify_unsigned.outputs.verified_update_id",
            "needs.verify_unsigned.outputs.manifest_id",
            "needs.verify_unsigned.outputs.receipt_id",
            "needs.sign_manifest.outputs.signature_id",
        ],
    }
    for name, ids in downloads.items():
        steps = jobs[name]["steps"]
        assert {step["uses"].split("@")[0] for step in steps if "uses" in step} == (
            {"actions/checkout", "actions/download-artifact", "actions/upload-artifact"}
            | ({"actions/attest"} if name == "package_attest" else set())
        )
        assert [
            step["with"]
            for step in steps
            if step.get("uses", "").startswith("actions/download-artifact@")
        ] == [
            {
                "artifact-ids": "${{ " + reference + " }}",
                "path": "${{ runner.temp }}/portable-inputs",
                "skip-decompress": "true",
                "digest-mismatch": "error",
            }
            for reference in ids
        ]
        guard = _step_by_name(jobs[name], "Require immutable input artifact IDs")
        assert steps.index(guard) < next(
            i for i, s in enumerate(steps) if "Download exact" in s["name"]
        )
        expected_ids = {"${{ " + reference + " }}" for reference in ids}
        assert expected_ids <= set(guard["env"].values())
        if name == "sign_manifest":
            assert guard["env"]["SECURITY_EVIDENCE_ID"] == (
                "${{ needs.artifact_security.outputs.evidence_id }}"
            )
            assert guard["env"]["SECURITY_EVIDENCE_DIGEST"] == (
                "${{ needs.artifact_security.outputs.evidence_digest }}"
            )
        commands = "\n".join(step.get("run", "") for step in steps)
        for forbidden in (
            "uv ",
            "pytest",
            "python ",
            "build_portable.ps1",
            "verify_extracted_bundle.ps1",
        ):
            assert forbidden not in commands
    package = _step_by_name(
        jobs["package_attest"], "Package and independently verify signed assets"
    )
    assert (
        package["env"]["MANIFEST_DIGEST"] == "${{ needs.verify_unsigned.outputs.manifest_digest }}"
    )
    assert (
        package["env"]["VERIFICATION_DIGEST"]
        == "${{ needs.verify_unsigned.outputs.receipt_digest }}"
    )
    assert (
        package["env"]["SIGNATURE_DIGEST"] == "${{ needs.sign_manifest.outputs.signature_digest }}"
    )
    assert "release_update.ps1 -Stage Package" in package["run"]
    sign = _step_by_name(jobs["sign_manifest"], "Sign approved manifest bytes")
    assert sign["env"]["MANIFEST_DIGEST"] == package["env"]["MANIFEST_DIGEST"]
    assert sign["env"]["VERIFICATION_DIGEST"] == package["env"]["VERIFICATION_DIGEST"]


def test_windows_portable_security_gate_scans_exact_verified_artifact(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github/workflows/windows-portable-build.yml")
    job = workflow["jobs"]["artifact_security"]
    steps = job["steps"]
    source = (repo_root / ".github/workflows/windows-portable-build.yml").read_text(
        encoding="utf-8"
    )

    assert "environment" not in job
    assert "secrets" not in job
    assert job["permissions"] == {"contents": "read"}
    assert job["outputs"] == {
        "evidence_id": "${{ steps.evidence.outputs.artifact-id }}",
        "evidence_digest": "${{ steps.evidence.outputs.artifact-digest }}",
    }
    downloads = [
        step for step in steps if step.get("uses", "").startswith("actions/download-artifact@")
    ]
    assert [step["with"]["artifact-ids"] for step in downloads] == [
        "${{ needs.verify_unsigned.outputs.verified_bundle_id }}",
        "${{ needs.verify_unsigned.outputs.receipt_id }}",
    ]
    assert all(step["with"]["skip-decompress"] == "true" for step in downloads)
    assert all(step["with"]["digest-mismatch"] == "error" for step in downloads)
    stage = _step_by_name(job, "Safely stage the receipt-bound portable tree")
    assert "artifact_security.py stage" in stage["run"]
    assert '--expected-artifact-id "$VERIFIED_BUNDLE_ID"' in stage["run"]
    install = _step_by_name(job, "Install checksum-pinned scanners")["run"]
    for digest in (
        "bf52519eb57f675d47c07d43213cb6dff6449f3d6d1147ff6701ed91f44eef0c",
        "e9da18cc1429e786722e32161288103600efffd8e483c90761f90485bd1bec85",
    ):
        assert digest in install
    scan = _step_by_name(job, "Generate SBOMs and unsuppressed advisory evidence")
    assert "syft-json=" in scan["run"] and "cyclonedx-json=" in scan["run"]
    assert (
        '"$GRYPE_BIN" --config "$config" "sbom:$evidence/windows-portable.syft.json"'
        in (scan["run"])
    )
    assert "artifact_security.py policy" in scan["run"]
    assert scan["env"]["GRYPE_DB_REQUIRE_UPDATE_CHECK"] == "true"
    assert scan["env"]["GRYPE_DB_VALIDATE_AGE"] == "true"
    assert "--fail-on" not in source
    assert "--ignore" not in scan["run"]
    evidence = _step_by_name(job, "Retain final-artifact security evidence")
    assert evidence["if"] == "always()"
    assert evidence["with"]["retention-days"] == "90"
    assert evidence["with"]["if-no-files-found"] == "error"


def test_windows_portable_attests_and_uploads_exact_release_assets(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github/workflows/windows-portable-build.yml")
    package = workflow["jobs"]["package_attest"]
    attest = _step_by_name(package, "Attest release ZIP provenance")
    upload = _step_by_name(package, "Upload exact orchestrated release assets")
    assert attest["if"] == upload["if"] == "inputs.prepare_release_assets"
    assert attest["uses"] == "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6"
    zips = [
        "dist/release-assets/frame-compare-portable-win-x64-${{ inputs.release_tag }}.zip",
        "dist/release-assets/frame-compare-update-win-x64-${{ inputs.release_tag }}.zip",
    ]
    assert attest["with"]["subject-path"].splitlines() == zips
    assert upload["with"]["path"].splitlines() == [
        filename for path in zips for filename in (path, f"{path}.sha256")
    ]
    assert upload["with"]["if-no-files-found"] == "error"
    assert package["steps"].index(attest) < package["steps"].index(upload)
    assert workflow["on"]["workflow_call"]["outputs"]["release_assets_id"]["value"] == (
        "${{ jobs.package_attest.outputs.release_assets_id }}"
    )
    release = _load_workflow(repo_root / ".github/workflows/release.yml")
    download = _step_by_name(release["jobs"]["publish"], "Download exact release assets")
    assert download["with"]["artifact-ids"] == "${{ needs.windows.outputs.release_assets_id }}"
    assert download["with"]["digest-mismatch"] == "error"


def test_windows_portable_workflow_runs_full_suite_once_including_updater_proof(
    repo_root: Path,
) -> None:
    steps = _build_action(repo_root)["steps"]
    pytest_runs = [step["run"] for step in steps if "pytest" in step.get("run", "")]
    assert pytest_runs == ["uv run --no-sync pytest -q"]


def test_windows_portable_composite_actions_pin_and_bind_unsigned_artifacts(
    repo_root: Path,
) -> None:
    actions = repo_root / ".github/actions"
    build = _load_workflow(actions / "windows-portable-build/action.yml")
    verify = _load_workflow(actions / "windows-portable-verify/action.yml")
    for action in (build, verify):
        assert action["runs"]["using"] == "composite"
        for step in action["runs"]["steps"]:
            if "uses" in step:
                assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", step["uses"])
            else:
                assert step["shell"] == "pwsh"

    for purpose, filename, producer, consumer in (
        ("bundle", "portable.zip", "Upload portable input", "Download exact portable input"),
        (
            "update",
            "unsigned-update.zip",
            "Upload unsigned update input",
            "Download exact unsigned update input",
        ),
    ):
        upload = _step_by_name(build["runs"], producer)
        assert upload["id"] == purpose
        assert upload["with"]["name"] == filename
        assert Path(upload["with"]["path"]).name == filename
        assert upload["with"]["archive"] == "false"
        assert upload["with"]["if-no-files-found"] == "error"
        assert build["outputs"][f"{purpose}_id"]["value"] == (
            "${{ steps." + purpose + ".outputs.artifact-id }}"
        )
        assert build["outputs"][f"{purpose}_digest"]["value"] == (
            "${{ steps." + purpose + ".outputs.artifact-digest }}"
        )
        download = _step_by_name(verify["runs"], consumer)
        assert download["with"]["artifact-ids"] == "${{ inputs." + purpose + "_id }}"
        assert download["with"]["digest-mismatch"] == "error"
        assert download["with"]["skip-decompress"] == "true"

    check = _step_by_name(verify["runs"], "Verify archive, exact source and compatibility")
    assert check["env"]["BUNDLE_DIGEST"] == "${{ inputs.bundle_digest }}"
    assert check["env"]["UPDATE_DIGEST"] == "${{ inputs.update_digest }}"
    assert "portable_runtime.py export --output" in check["run"]
    assert "release_update.ps1 -Stage Verify" in check["run"]
