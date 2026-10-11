from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

from tests.workflow_helpers import load_workflow
from tests.workflows._helpers import bash_executable_or_skip

# Deliberately tiny, public test-only RSA parameters; never use a real signing key here.
PARAMETERS = {
    "Modulus": 3233,
    "Exponent": 17,
    "P": 61,
    "Q": 53,
    "DP": 53,
    "DQ": 49,
    "InverseQ": 38,
    "D": 2753,
}


def key_xml(parameters: dict[str, int]) -> str:
    return (
        "<RSAKeyValue>"
        + "".join(
            f"<{name}>{base64.b64encode(value.to_bytes(4, 'big')).decode()}</{name}>"
            for name, value in parameters.items()
        )
        + "</RSAKeyValue>"
    )


@pytest.fixture
def migration(repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "migrate_signing_key", repo_root / "scripts/migrate_signing_key.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    public = tmp_path / "public.xml"
    public.write_text(
        key_xml({name: PARAMETERS[name] for name in ("Modulus", "Exponent")}), encoding="utf-8"
    )
    monkeypatch.setattr(module, "PUBLIC_KEY", public)
    monkeypatch.setenv("GITHUB_REPOSITORY", "TJZine/frame-compare")
    monkeypatch.setenv("GH_TOKEN", "test-only-migration-token")
    monkeypatch.setenv("SOURCE_SIGNING_KEY", key_xml(PARAMETERS))
    return module


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "invalid_key",
        "entity_xml",
        "oversized_xml",
        "public_mismatch",
        "missing_token",
        "wrong_repo",
        "unprotected_environment",
        "api_failure",
        "write_failure",
    ],
)
def test_migration_preserves_key_and_sanitizes_failures(
    migration: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: str | None,
) -> None:
    source = key_xml(PARAMETERS)
    calls: list[tuple[list[str], str | None]] = []
    if failure == "invalid_key":
        monkeypatch.setenv("SOURCE_SIGNING_KEY", key_xml(PARAMETERS | {"D": 1}))
    elif failure == "entity_xml":
        monkeypatch.setenv(
            "SOURCE_SIGNING_KEY",
            '<!DOCTYPE RSAKeyValue [<!ENTITY private "test-private-fragment">]>'
            "<RSAKeyValue>&private;</RSAKeyValue>",
        )
    elif failure == "oversized_xml":
        monkeypatch.setenv("SOURCE_SIGNING_KEY", "test-private-fragment" * 2000)
    elif failure == "public_mismatch":
        monkeypatch.setenv("SOURCE_SIGNING_KEY", key_xml(PARAMETERS | {"Modulus": 999}))
    elif failure == "missing_token":
        monkeypatch.delenv("GH_TOKEN")
    elif failure == "wrong_repo":
        monkeypatch.setenv("GITHUB_REPOSITORY", "other/repo")

    def fake_run(arguments: list[str], *, secret_input: str | None = None) -> str:
        calls.append((arguments, secret_input))
        if failure == "api_failure" or (failure == "write_failure" and arguments[0] == "secret"):
            raise migration.MigrationError(
                "GitHub rejected a migration operation; check token permissions."
            )
        if arguments[0] == "secret":
            assert secret_input == source
            assert source not in " ".join(arguments)
            assert "SOURCE_SIGNING_KEY" not in os.environ
            return ""
        if "/secrets/" in arguments[1]:
            return json.dumps({"name": "WINDOWS_UPDATE_SIGNING_KEY_XML"})
        protected = not (
            failure == "unprotected_environment" and arguments[1].endswith("release-candidate")
        )
        return json.dumps(
            {
                "protection_rules": [
                    {"type": "required_reviewers", "reviewers": [{"type": "User"}]}
                ]
                if protected
                else []
            }
        )

    monkeypatch.setattr(migration, "run_gh", fake_run)
    assert migration.main() == (0 if failure is None else 1)
    logs = capsys.readouterr()
    assert source not in logs.out + logs.err
    assert "test-private-fragment" not in logs.out + logs.err
    assert "test-only-migration-token" not in logs.out + logs.err
    if failure is None:
        writes = [args for args, _ in calls if args[0] == "secret"]
        assert [args[-1] for args in writes] == ["production", "release-candidate"]
        assert all(
            args[:3] == ["secret", "set", "WINDOWS_UPDATE_SIGNING_KEY_XML"] for args in writes
        )
        assert "Repository source secret retained" in logs.out
    elif failure != "write_failure":
        assert not any(args[0] == "secret" for args, _ in calls)


@pytest.mark.parametrize("result", ["success", "failure", "timeout"])
def test_cli_receives_secret_only_on_stdin_and_never_echoes_errors(
    migration: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    result: str,
) -> None:
    source = key_xml(PARAMETERS)
    monkeypatch.setenv("GH_DEBUG", "api")

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert source not in " ".join(command)
        assert kwargs["input"] == source
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        assert "GH_DEBUG" not in environment and "SOURCE_SIGNING_KEY" not in environment
        assert kwargs["capture_output"] is True
        if result == "timeout":
            raise subprocess.TimeoutExpired(command, 60, output=source, stderr=source)
        return subprocess.CompletedProcess(command, 0 if result == "success" else 1, source, source)

    monkeypatch.setattr(migration.subprocess, "run", fake_run)
    if result == "success":
        assert (
            migration.run_gh(
                ["secret", "set", "WINDOWS_UPDATE_SIGNING_KEY_XML"], secret_input=source
            )
            == ""
        )
    else:
        with pytest.raises(migration.MigrationError) as error:
            migration.run_gh(
                ["secret", "set", "WINDOWS_UPDATE_SIGNING_KEY_XML"], secret_input=source
            )
        assert source not in str(error.value)
    logs = capsys.readouterr()
    assert source not in logs.out + logs.err


def test_migration_dispatch_keeps_production_gate_and_explicit_source(repo_root: Path) -> None:
    dispatcher = load_workflow(repo_root / ".github/workflows/windows-portable.yml")
    caller = dispatcher["jobs"]["migrate_signing_key"]
    assert (
        "migrate-signing-key"
        in dispatcher["on"]["workflow_dispatch"]["inputs"]["operation"]["options"]
    )
    assert (
        caller["if"]
        == "github.event_name == 'workflow_dispatch' && inputs.operation == 'migrate-signing-key'"
    )
    assert caller["secrets"] == {
        "SOURCE_SIGNING_KEY": "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}",
        "SIGNING_KEY_MIGRATION_TOKEN": "${{ secrets.SIGNING_KEY_MIGRATION_TOKEN }}",
    }
    workflow = load_workflow(repo_root / ".github/workflows/migrate-signing-key.yml")
    assert set(workflow["on"]) == {"workflow_call"}
    assert workflow["permissions"] == {}
    assert workflow["on"]["workflow_call"]["secrets"] == {
        "SOURCE_SIGNING_KEY": {"required": "true"},
        "SIGNING_KEY_MIGRATION_TOKEN": {"required": "true"},
    }
    job = workflow["jobs"]["migrate"]
    assert job["needs"] == "preflight"
    assert job["environment"] == {"name": "production"}
    assert job["permissions"] == {"contents": "read"}
    assert job["steps"][-1]["env"] == {
        "SOURCE_SIGNING_KEY": "${{ secrets.SOURCE_SIGNING_KEY }}",
        "GH_TOKEN": "${{ secrets.SIGNING_KEY_MIGRATION_TOKEN }}",
    }
    assert not any("upload-artifact" in str(step.get("uses", "")) for step in job["steps"])


@pytest.mark.parametrize(
    "ref,sha,repo,accepted",
    [
        ("refs/heads/v0.7.0", "a" * 40, "TJZine/frame-compare", True),
        ("refs/heads/main", "a" * 40, "TJZine/frame-compare", False),
        ("refs/heads/v0.7.0", "b" * 40, "TJZine/frame-compare", False),
        ("refs/heads/v0.7.0", "a" * 40, "other/repo", False),
    ],
)
def test_migration_ref_and_sha_guard(
    repo_root: Path, ref: str, sha: str, repo: str, accepted: bool
) -> None:
    workflow = load_workflow(repo_root / ".github/workflows/migrate-signing-key.yml")
    command = workflow["jobs"]["preflight"]["steps"][0]["run"]
    completed = subprocess.run(
        [bash_executable_or_skip(), "-c", command],
        env=os.environ
        | {
            "EXPECTED_SHA": "a" * 40,
            "SOURCE_SHA": sha,
            "SOURCE_REF": ref,
            "SOURCE_REPOSITORY": repo,
        },
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert (completed.returncode == 0) is accepted
