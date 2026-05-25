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

    assert "FROM ghcr.io/astral-sh/uv:0.11.16 AS uv" in dockerfile
    assert "COPY --from=uv /uv /uvx /usr/local/bin/" in dockerfile
    assert re.search(
        r"COPY --chown=framecompare:framecompare pyproject\.toml uv\.lock\b", dockerfile
    )
    assert "uv export --frozen --no-dev --no-emit-project --format requirements.txt" in dockerfile
    assert "--output-file /tmp/requirements.lock.txt" in dockerfile
    assert (
        "python -m pip install --no-cache-dir --user --require-hashes -r /tmp/requirements.lock.txt"
    ) in dockerfile


def test_dockerfile_hash_verifies_docker_plugin_wheels(repo_root: Path) -> None:
    dockerfile_path = repo_root / "Dockerfile"
    dockerfile = _read_text_or_fail(dockerfile_path)

    assert (
        "ARG VAPOURSYNTH_X86_64_WHEEL_SHA256="
        "94986f4399b3ea8ab775abfbf5986dc58b93829fbf3db2a37e3b9e6454baf898"
    ) in dockerfile
    assert (
        "ARG VAPOURSYNTH_AARCH64_WHEEL_SHA256="
        "c516b04c9fde70b7075266a067b611f9d8409a20a5380ae425c21e1bada10997"
    ) in dockerfile
    assert (
        "ARG VS_PLACEBO_X86_64_WHEEL_SHA256="
        "cb44a42df2c7e78d614b4b0415e9b4d3c40659f9d57ac18d65076101f364fa8e"
    ) in dockerfile
    assert (
        "ARG VS_PLACEBO_AARCH64_WHEEL_SHA256="
        "25a94cde45bea9f2e2503040772a34a1355520a14b339a77009b233cf9457c2d"
    ) in dockerfile
    assert (
        '"vapoursynth==${VAPOURSYNTH_VERSION} '
        "--hash=sha256:${VAPOURSYNTH_X86_64_WHEEL_SHA256} "
        '--hash=sha256:${VAPOURSYNTH_AARCH64_WHEEL_SHA256}"' in dockerfile
    )
    assert (
        '"vs-placebo==${VS_PLACEBO_VERSION} '
        "--hash=sha256:${VS_PLACEBO_X86_64_WHEEL_SHA256} "
        '--hash=sha256:${VS_PLACEBO_AARCH64_WHEEL_SHA256}"' in dockerfile
    )
    assert "--require-hashes --only-binary=:all:" in dockerfile
    assert not re.search(
        r"python -m pip install[^\n]*--no-deps\s*\\\n"
        r"\s+\"vapoursynth==\$\{VAPOURSYNTH_VERSION\}\"",
        dockerfile,
    )


def test_dockerfile_uses_r76_wheel_plugin_layout(repo_root: Path) -> None:
    dockerfile_path = repo_root / "Dockerfile"
    dockerfile = _read_text_or_fail(dockerfile_path)

    assert "ARG VAPOURSYNTH_VERSION=76" in dockerfile
    assert "ARG VS_PLACEBO_VERSION=2.0.2" in dockerfile
    assert "VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins" in dockerfile
    assert "manifest.vs" in dockerfile
    assert "VAPOURSYNTH_PLUGIN_PATH" not in dockerfile


def test_docker_verify_script_asserts_runtime_proof_items(repo_root: Path) -> None:
    script_path = repo_root / "tools" / "verify_docker_integration.sh"
    script = _read_text_or_fail(script_path)

    assert re.search(r"cat <<'EOF'\nset -euo pipefail\n", script)
    assert "version_major == 76 and version_minor == 0" in script
    assert 'version_label = f"R{version_major}"' in script
    assert "required_proof_markers=(" in script
    assert 'grep -Fq "$proof_marker" "$tmp_log"' in script

    for proof_item in (
        "DOCKER_PROOF vapoursynth_import=ok version=R76",
        "vapoursynth.get_plugin_dir()",
        "core.plugins()",
        "LWLibavSource",
        "core.placebo.Tonemap",
        "DOCKER_PROOF plugin_dir=",
        "DOCKER_PROOF extra_plugin_path=/opt/vapoursynth-extra-plugins",
        "DOCKER_PROOF real_frame_render=ok frames=lwlibavsource,placebo",
        "zero skips",
    ):
        assert proof_item in script


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


def test_windows_portable_workflow_keeps_python_313_release_path(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert 'python-version: "3.13.13"' in workflow
    assert 'python-version: "3.14' not in workflow
    assert "tools/windows_portable/build_portable.ps1" in workflow
    assert "WINDOWS_WORKFLOW_PROOF" not in workflow


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
