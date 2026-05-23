import re
from pathlib import Path


def _read_text_or_fail(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def test_docker_integration_workflow_covers_supported_pull_request_bases(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docker-integration.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert re.search(r"pull_request:\s*\n\s+branches:\s*\[main,\s*cleanup\]", workflow)


def test_docker_integration_workflow_watches_lockfile(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docker-integration.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert re.search(r"paths:\s*(?:\n\s+- .*)*\n\s+- uv\.lock\b", workflow)


def test_dockerfile_installs_lock_export_with_hashes(repo_root: Path) -> None:
    dockerfile_path = repo_root / "Dockerfile"
    dockerfile = _read_text_or_fail(dockerfile_path)

    assert "FROM ghcr.io/astral-sh/uv:0.8.22 AS uv" in dockerfile
    assert "COPY --from=uv /uv /uvx /usr/local/bin/" in dockerfile
    assert re.search(
        r"COPY --chown=framecompare:framecompare pyproject\.toml uv\.lock\b", dockerfile
    )
    assert "uv export --frozen --no-dev --no-emit-project --format requirements.txt" in dockerfile
    assert "--output-file /tmp/requirements.lock.txt" in dockerfile
    assert (
        "python -m pip install --no-cache-dir --user --require-hashes -r /tmp/requirements.lock.txt"
    ) in dockerfile


def test_dockerfile_installs_project_without_dependency_resolution(repo_root: Path) -> None:
    dockerfile_path = repo_root / "Dockerfile"
    dockerfile = _read_text_or_fail(dockerfile_path)

    assert "python -m pip install --no-cache-dir --user --no-deps -e ." in dockerfile
    assert not re.search(r"(?<!python -m )pip install[^\n]* -e \.", dockerfile)
    assert not re.search(r"python -m pip install(?![^\n]*--no-deps)[^\n]* -e \.", dockerfile)


def test_windows_portable_workflow_disables_uv_cache_for_pull_requests(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "enable-cache: ${{ github.event_name != 'pull_request' }}" in workflow


def test_windows_portable_workflow_limits_release_write_permissions(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert re.search(r"permissions:\s*\n\s+contents:\s+read", workflow)
    assert re.search(r"jobs:\s*\n\s+build:\s*\n\s+permissions:\s*\n\s+contents:\s+read", workflow)
    assert re.search(
        r"release-assets:\s*\n\s+if:\s+github\.event_name == 'release'\s*\n\s+needs:\s+build\s*\n\s+permissions:\s*\n\s+contents:\s+write",
        workflow,
    )
    assert "Download bundle artifact" in workflow
    assert "path: dist/release-assets" in workflow
    assert "dist/release-assets/frame-compare-portable-win-x64.zip" in workflow
    assert "dist/release-assets/frame-compare-portable-win-x64.zip.sha256" in workflow
