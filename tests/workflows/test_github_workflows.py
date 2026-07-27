import ast
import json
import re
import tomllib
from pathlib import Path

from tests.workflow_helpers import (
    assert_release_asset_name_hardening as _assert_release_asset_name_hardening,
)
from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail


def test_release_please_owns_python_version_sources(repo_root: Path) -> None:
    release_config = json.loads(_read_text_or_fail(repo_root / "release-please-config.json"))
    release_manifest = json.loads(_read_text_or_fail(repo_root / ".release-please-manifest.json"))

    with (repo_root / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    package_name = project["name"].replace("-", "_")
    package_source = _read_text_or_fail(repo_root / "src" / package_name / "__init__.py")
    package_module = ast.parse(package_source)
    package_version = next(
        ast.literal_eval(statement.value)
        for statement in package_module.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in statement.targets
        )
    )

    assert release_config["release-type"] == "python"
    assert release_config["packages"]["."]["release-type"] == "python"
    assert release_manifest["."] == project["version"] == package_version


def test_release_please_workflow_requires_human_review(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "release-please.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "gh pr merge" not in workflow
    assert "--auto" not in workflow


def test_ci_requires_clean_distribution_build_and_install(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "uv build --out-dir dist" in workflow
    assert ".dist-venv/bin/python scripts/verify_distribution.py dist" in workflow
    assert "uv pip install --python .dist-venv/bin/python dist/*.whl" in workflow
    assert ".dist-venv/bin/frame-compare version" in workflow
    assert ".dist-venv/bin/frame-compare --help" in workflow
    assert "needs: [lint, security, typecheck, test, import-lints, package]" in workflow
    assert '[[ "${{ needs.package.result }}" != "success" ]]' in workflow


def test_docker_integration_workflow_covers_supported_pull_request_bases(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docker-integration.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert re.search(r"pull_request:\s*\n\s+branches:\s*\[main,\s*cleanup\]", workflow)


def test_docker_integration_workflow_watches_lockfile(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docker-integration.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert re.search(r"paths:\s*(?:\n\s+- .*)*\n\s+- uv\.lock\b", workflow)


def test_docker_integration_workflow_watches_docker_overrides_and_verify_scripts(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docker-integration.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "- docker-compose*.yml" in workflow
    assert "- tools/verify_docker_*.sh" in workflow
    assert "- tests/workflows/**" in workflow


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
    assert "git clone --depth 1 --branch" not in dockerfile
    assert re.search(
        r"ARG VAPOURSYNTH_SOURCE_COMMIT=[a-f0-9]{40}",
        dockerfile,
    )
    assert re.search(
        r"ARG LSMASH_WORKS_COMMIT=[a-f0-9]{40}",
        dockerfile,
    )
    assert re.search(
        r"ARG FFMS2_COMMIT=[a-f0-9]{40}",
        dockerfile,
    )
    assert 'git fetch --depth 1 origin "$commit"' in dockerfile
    assert 'test "$(git rev-parse HEAD)" = "$commit"' in dockerfile


def test_dockerfile_uses_r76_wheel_plugin_layout(repo_root: Path) -> None:
    dockerfile_path = repo_root / "Dockerfile"
    dockerfile = _read_text_or_fail(dockerfile_path)

    assert "ARG VAPOURSYNTH_VERSION=76" in dockerfile
    assert "ARG VS_PLACEBO_VERSION=2.0.2" in dockerfile
    assert "VAPOURSYNTH_EXTRA_PLUGIN_PATH=/opt/vapoursynth-extra-plugins" in dockerfile
    assert "manifest.vs" in dockerfile
    assert "VAPOURSYNTH_PLUGIN_PATH" not in dockerfile
    assert "git remote add origin" in dockerfile


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


def test_readme_docker_examples_do_not_use_removed_frame_count_flags(repo_root: Path) -> None:
    readme_path = repo_root / "README.md"
    readme = _read_text_or_fail(readme_path)

    assert "single `docker compose up`" not in readme

    docker_sections = [
        match.group(0)
        for match in re.finditer(r"```bash\n.*?\n```", readme, re.DOTALL)
        if "docker" in match.group(0)
    ]

    assert docker_sections, "Expected README to include Docker command examples."
    assert all("--frame-count" not in section for section in docker_sections)
    assert all(
        not re.search(r"(?<![A-Za-z0-9_-])-n(?![A-Za-z0-9_-])", section)
        for section in docker_sections
    )


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
    assert "Resolve release asset names" in workflow
    assert "Prepare versioned release asset" in workflow
    _assert_release_asset_name_hardening(workflow)
    assert "steps.release_names.outputs.asset_tag" in workflow
    assert 'hash="$(sha256sum "$zip" | cut -d \' \' -f 1)"' in workflow
    assert 'printf \'%s  %s\\n\' "$hash" "$(basename "$zip")" > "$zip.sha256"' in workflow
    assert (
        "dist/release-assets/frame-compare-portable-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip"
    ) in workflow
    assert (
        "dist/release-assets/frame-compare-portable-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip.sha256"
    ) in workflow


def test_windows_portable_workflow_smokes_installed_shim(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Smoke: extracted install shim" in workflow
    assert '& "$bundle/install.cmd"' in workflow
    assert "Programs/FrameCompare/bin/frame-compare.cmd" in workflow
    assert "& $shim version" in workflow
    assert "& $shim --help" in workflow


def test_windows_portable_workflow_proves_code_only_update_without_pr_secrets(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert workflow.index("Build portable bundle") < workflow.index("Build code-only update zip")
    assert "tools/windows_portable/build_update.ps1" in workflow
    assert "frame-compare-update-win-x64-$version.zip" in workflow
    assert "UPDATE_ZIP=$updateZip" in workflow
    assert "Pull requests prove unsigned update zip creation without signing secrets." in workflow
    assert "Upload code-only update artifact" in workflow
    assert "name: frame-compare-update-win-x64" in workflow
    assert "dist/frame-compare-update-win-x64-*.zip" in workflow


def test_windows_portable_workflow_requires_signed_update_release_assets(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert (
        "WINDOWS_UPDATE_SIGNING_KEY_XML: ${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}" in workflow
    )
    assert "WINDOWS_UPDATE_SIGNING_KEY_XML is required for release and manual runs." in workflow
    assert "tools/windows_portable/sign_update.ps1" in workflow
    assert "update_signed" not in workflow
    assert "Download signed update artifact" in workflow
    assert "Prepare versioned signed update asset" in workflow
    assert "Verify required release asset set" in workflow
    assert "Upload required release assets" in workflow
    assert "Missing required release asset: $asset" in workflow
    assert "fail_on_unmatched_files: true" in workflow
    assert "mapfile -t update_zips" in workflow
    assert "Expected exactly one signed update zip artifact, found ${#update_zips[@]}." in workflow
    assert "frame-compare-update-win-x64-${ASSET_TAG}.zip" in workflow
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip"
    ) in workflow
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "steps.release_names.outputs.asset_tag }}.zip.sha256"
    ) in workflow
