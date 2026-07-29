import ast
import json
import re
import tomllib
from pathlib import Path

from tests.workflow_helpers import load_workflow as _load_workflow
from tests.workflow_helpers import read_text_or_fail as _read_text_or_fail
from tests.workflow_helpers import step_by_name as _step_by_name


def test_release_please_owns_python_version_sources(repo_root: Path) -> None:
    release_config = json.loads(_read_text_or_fail(repo_root / "release-please-config.json"))
    release_manifest = json.loads(_read_text_or_fail(repo_root / ".release-please-manifest.json"))

    with (repo_root / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]
    with (repo_root / "uv.lock").open("rb") as lock_file:
        locked_project = next(
            package
            for package in tomllib.load(lock_file)["package"]
            if package["name"] == project["name"]
        )

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
    assert (
        release_manifest["."]
        == project["version"]
        == package_version
        == locked_project["version"]
    )


def test_initial_release_remains_at_temporary_prerelease_state(repo_root: Path) -> None:
    release_config = json.loads(_read_text_or_fail(repo_root / "release-please-config.json"))
    release_manifest = json.loads(_read_text_or_fail(repo_root / ".release-please-manifest.json"))

    assert release_manifest["."] == "0.0.0"
    assert release_config["release-as"] == "0.1.0"
    assert (
        release_config["bootstrap-sha"]
        == "f212c475b584ac97d309736abd268df41c96d876"
    )
    assert release_config["packages"]["."]["extra-files"] == [
        {
            "type": "toml",
            "path": "uv.lock",
            "jsonpath": "$.package[?(@.name.value == 'frame-compare')].version",
        }
    ]
    assert "prerelease" not in release_config
    assert "prerelease-type" not in release_config


def test_release_please_workflow_requires_human_review(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "release-please.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "gh pr merge" not in workflow
    assert "--auto" not in workflow


def test_release_please_is_dormant_until_published_stable_v010(repo_root: Path) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "release-please.yml")
    source = _read_text_or_fail(repo_root / ".github" / "workflows" / "release-please.yml")
    guard = workflow["jobs"]["initial_release_guard"]
    release = workflow["jobs"]["release_please"]

    assert workflow["concurrency"] == {
        "group": "release-please-main",
        "cancel-in-progress": "false",
    }
    assert guard["permissions"] == {"contents": "read"}
    assert guard["timeout-minutes"] == "5"
    assert release["needs"] == "initial_release_guard"
    assert release["if"] == "needs.initial_release_guard.outputs.enabled == 'true'"
    assert release["permissions"] == {
        "contents": "write",
        "pull-requests": "write",
    }
    assert "releases/tags/v0.1.0" in source
    assert "git/ref/tags/v0.1.0" in source
    assert 'draft" != "false"' in source
    assert 'prerelease" != "false"' in source
    assert "enabled=true" in source
    assert release["steps"][0]["with"]["skip-github-release"] == "true"


def test_guarded_release_workflow_has_explicit_immutable_inputs(repo_root: Path) -> None:
    entry_path = repo_root / ".github" / "workflows" / "windows-portable.yml"
    entry = _load_workflow(entry_path)
    dispatch = entry["on"]["workflow_dispatch"]["inputs"]
    release_job = entry["jobs"]["release"]
    pull_request_job = entry["jobs"]["verify_pull_request"]
    manual_job = entry["jobs"]["verify_manual"]

    workflow_path = repo_root / ".github" / "workflows" / "release.yml"
    workflow = _load_workflow(workflow_path)
    source = _read_text_or_fail(workflow_path)
    call = workflow["on"]["workflow_call"]["inputs"]

    assert set(entry["on"]) == {"pull_request", "workflow_dispatch"}
    assert set(dispatch) == {"operation", "channel", "version", "tag", "expected_sha"}
    assert dispatch["operation"]["options"] == ["verify", "release"]
    assert dispatch["channel"]["options"] == ["rc", "stable"]
    assert set(call) == {"channel", "version", "tag", "expected_sha"}
    assert all(value["required"] == "true" for value in call.values())
    assert release_job["uses"] == "./.github/workflows/release.yml"
    assert release_job["permissions"] == {"contents": "write"}
    assert release_job["concurrency"] == {
        "group": "frame-compare-release-${{ inputs.tag }}",
        "cancel-in-progress": "false",
    }
    assert "secrets" not in pull_request_job
    assert pull_request_job["with"]["require_signing"] == "false"
    assert manual_job["with"]["require_signing"] == "true"
    assert manual_job["secrets"]["WINDOWS_UPDATE_SIGNING_KEY_XML"] == (
        "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    )
    assert workflow["permissions"] == {}
    assert "workflow_dispatch" not in workflow["on"]
    assert "ref: ${{ inputs.expected_sha }}" in source
    assert "The selected workflow ref head must equal expected_sha." in source
    assert "Stable publication must be dispatched from the main branch." in source
    assert "--expected-sha \"$EXPECTED_SHA\"" in source
    assert "--main-sha \"$MAIN_SHA\"" in source


def test_guarded_release_workflow_fails_closed_on_collisions_and_permissions(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "release.yml"
    workflow = _load_workflow(workflow_path)
    source = _read_text_or_fail(workflow_path)

    assert workflow["jobs"]["preflight"]["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["windows"]["permissions"] == {"contents": "read"}
    assert workflow["jobs"]["publish"]["permissions"] == {"contents": "write"}
    assert source.count("Reject existing tag or release") == 1
    assert source.count("check_absent()") == 2
    assert source.count("HTTP 404") == 3
    assert "Unable to prove that $label is absent." in source
    assert "Unable to prove that $label remains absent." in source
    assert source.index("Reject existing tag or release") < source.index(
        "Build, sign, and verify Windows assets"
    )
    assert "Main advanced after preflight; refusing stable publication." in source
    assert "Enforce initial stable release identity" in source
    assert "Unable to determine whether the initial stable release exists." in source
    assert (
        "The first published stable release must be exactly version 0.1.0 and tag v0.1.0."
        in source
    )
    assert source.index("Recheck main, collisions, and create exact tag") < source.index(
        "Create a new draft release"
    )


def test_guarded_release_workflow_builds_before_draft_and_publishes_last(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "release.yml"
    workflow = _load_workflow(workflow_path)
    source = _read_text_or_fail(workflow_path)
    windows = workflow["jobs"]["windows"]
    publish = workflow["jobs"]["publish"]

    assert windows["uses"] == "./.github/workflows/windows-portable-build.yml"
    assert windows["with"] == {
        "expected_sha": "${{ inputs.expected_sha }}",
        "release_tag": "${{ inputs.tag }}",
        "require_signing": "true",
        "prepare_release_assets": "true",
    }
    assert windows["secrets"]["WINDOWS_UPDATE_SIGNING_KEY_XML"] == (
        "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    )
    assert publish["needs"] == ["preflight", "windows"]
    assert publish["environment"]["name"] == (
        "${{ inputs.channel == 'stable' && 'production' || 'release-candidate' }}"
    )
    assert '-F "draft=true"' in source
    assert 'gh api --method POST "repos/${GITHUB_REPOSITORY}/releases"' in source
    assert source.index("Verify complete local asset set") < source.index(
        "Create a new draft release"
    )
    assert source.index("Create a new draft release") < source.index(
        "Attach every mandatory asset to the new draft"
    )
    assert source.index("Attach every mandatory asset to the new draft") < source.index(
        "Verify draft target and exact remote asset bytes"
    )
    assert source.index("Verify draft target and exact remote asset bytes") < source.index(
        "Publish verified release"
    )
    assert source.index("Publish verified release") < source.index(
        "Verify final publication state"
    )
    named_steps = {step["name"]: step for step in publish["steps"] if "name" in step}
    final_publish = named_steps["Publish verified release"]["run"]
    assert "Main advanced before publication; refusing stable publication." in final_publish
    assert "Release, tag, or draft target changed before publication." in final_publish
    assert "Remote asset set changed before publication." in final_publish
    assert "Remote asset changed before publication: $name" in final_publish
    assert final_publish.index('release_json="$(gh api "$release_endpoint")"') < (
        final_publish.index('gh api --method PATCH "$release_endpoint"')
    )
    final_proof = named_steps["Verify final publication state"]["run"]
    assert "Main no longer points to the published stable commit." in final_proof
    assert '"$target" != "$EXPECTED_SHA"' in final_proof
    assert "Published release does not contain the exact mandatory asset set." in final_proof
    assert "Published release asset digest mismatch: $name" in final_proof


def test_guarded_release_workflow_requires_exact_four_signed_assets(repo_root: Path) -> None:
    source = _read_text_or_fail(repo_root / ".github" / "workflows" / "release.yml")
    expected_names = (
        "frame-compare-portable-win-x64-${RELEASE_TAG}.zip",
        "frame-compare-portable-win-x64-${RELEASE_TAG}.zip.sha256",
        "frame-compare-update-win-x64-${RELEASE_TAG}.zip",
        "frame-compare-update-win-x64-${RELEASE_TAG}.zip.sha256",
    )

    for name in expected_names:
        assert source.count(name) >= 2
    assert "sha256sum --check" in source
    assert '"update-manifest.sig"' in source
    assert "payload/app/src/frame_compare/" in source
    assert "does not contain the exact mandatory set" in source
    assert "exact non-empty mandatory asset set" in source
    assert '.digest // ""' in source
    assert '"sha256:${local_hash}"' in source
    assert "https://uploads.github.com/repos/${GITHUB_REPOSITORY}/releases/" in source
    assert '--write-out \'%{http_code}\'' in source
    assert '"$http_status" != "201"' in source
    assert "api.uploads.github.com" not in source
    assert "tag_sha\" != \"$EXPECTED_SHA\"" in source


def test_ci_requires_clean_distribution_build_and_install(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "ci.yml"
    workflow = _read_text_or_fail(workflow_path)

    parsed = _load_workflow(workflow_path)
    assert parsed["on"]["workflow_dispatch"] == ""
    assert "uv build --out-dir dist" in workflow
    assert ".dist-venv/bin/python scripts/verify_distribution.py dist" in workflow
    assert "uv pip install --python .dist-venv/bin/python dist/*.whl" in workflow
    assert ".dist-venv/bin/frame-compare version" in workflow
    assert ".dist-venv/bin/frame-compare --help" in workflow
    assert (
        "needs: [lint, security, dependency-audit, typecheck, test, import-lints, "
        "package, report-browser]" in workflow
    )
    assert '[[ "${{ needs.dependency-audit.result }}" != "success" ]]' in workflow
    assert '[[ "${{ needs.package.result }}" != "success" ]]' in workflow


def test_ci_audits_locked_runtime_dependencies_on_linux_and_windows(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    job = workflow["jobs"]["dependency-audit"]

    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["timeout-minutes"] == "15"
    assert job["strategy"] == {
        "fail-fast": "false",
        "matrix": {"os": ["ubuntu-latest", "windows-latest"]},
    }
    named_steps = {step["name"]: step for step in job["steps"] if "name" in step}
    assert named_steps["Install locked audit tool"]["run"] == "uv sync --group dev --frozen"
    assert named_steps["Export locked runtime graph"]["run"] == (
        "uv export --frozen --no-dev --all-extras --no-emit-project "
        "--format requirements.txt "
        '--output-file "${{ runner.temp }}/audit-requirements.txt"'
    )
    audit = named_steps["Reject known dependency vulnerabilities"]["run"]
    assert "uv run --no-sync pip-audit" in audit
    assert "--strict" in audit
    assert "--require-hashes" in audit
    assert "--disable-pip" in audit
    assert "--vulnerability-service pypi" in audit
    assert '--requirement "${{ runner.temp }}/audit-requirements.txt"' in audit
    assert "--ignore-vuln" not in audit


def test_ci_runs_generated_report_smoke_in_preflighted_system_browser(
    repo_root: Path,
) -> None:
    workflow = _load_workflow(repo_root / ".github" / "workflows" / "ci.yml")
    job = workflow["jobs"]["report-browser"]

    assert job["runs-on"] == "ubuntu-24.04"
    named_steps = {step["name"]: step for step in job["steps"] if "name" in step}
    preflight = named_steps["Preflight Chrome or Chromium"]
    preflight_script = preflight["run"]
    assert "command -v google-chrome" in preflight_script
    assert "command -v chromium" in preflight_script
    assert "ERROR: Ubuntu 24.04 runner has no Chrome or Chromium executable." in preflight_script
    assert 'echo "REPORT_BROWSER=$browser" >> "$GITHUB_ENV"' in preflight_script

    smoke = named_steps["Run generated report browser smoke"]
    assert smoke["run"] == "uv run --no-sync pytest -q tests/browser/test_report_browser_smoke.py"


def test_direct_build_tools_are_pinned_exactly(repo_root: Path) -> None:
    for workflow_name in ("ci.yml", "docs.yml", "windows-portable-build.yml"):
        workflow = _read_text_or_fail(repo_root / ".github" / "workflows" / workflow_name)
        setup_count = workflow.count("astral-sh/setup-uv@")
        assert setup_count > 0
        assert workflow.count('version: "0.11.31"') == setup_count
        assert 'version: "latest"' not in workflow

    with (repo_root / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)
    build_system = pyproject["build-system"]
    assert build_system["requires"] == ["hatchling==1.31.0"]
    assert "pip-audit==2.10.1" in pyproject["dependency-groups"]["dev"]


def test_docker_base_images_are_digest_pinned(repo_root: Path) -> None:
    dockerfile = _read_text_or_fail(repo_root / "Dockerfile")

    uv_image = (
        "ghcr.io/astral-sh/uv:0.11.31"
        "@sha256:ecd4de2f060c64bea0ff8ecb182ddf46ba3fcccdc8a60cfdbaf20d1a047d7437"
    )
    python_image = (
        "python:3.13.13-slim-trixie"
        "@sha256:aa938a849bcb82dce8f49480f056ab82bf5c1c3ebc294f0430f37b6820e7f286"
    )
    assert f"FROM {uv_image} AS uv" in dockerfile
    assert dockerfile.count(f"FROM {python_image}") == 2
    assert "FROM ghcr.io/astral-sh/uv:0.11.31 AS uv" not in dockerfile
    assert "FROM python:3.13.13-slim-trixie AS" not in dockerfile


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


def test_docker_integration_workflow_watches_analysis_sources(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "docker-integration.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "- src/frame_compare/analysis/**" in workflow


def test_dockerfile_installs_lock_export_with_hashes(repo_root: Path) -> None:
    dockerfile_path = repo_root / "Dockerfile"
    dockerfile = _read_text_or_fail(dockerfile_path)

    assert "FROM ghcr.io/astral-sh/uv:0.11.31@sha256:" in dockerfile
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
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "enable-cache: ${{ inputs.require_signing }}" in workflow


def test_windows_portable_workflow_keeps_python_313_release_path(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert 'python-version: "3.13.13"' in workflow
    assert 'python-version: "3.14' not in workflow
    assert "tools/windows_portable/build_portable.ps1" in workflow
    assert "WINDOWS_WORKFLOW_PROOF" not in workflow


def test_windows_portable_workflow_is_read_only_reusable_boundary(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert re.search(r"permissions:\s*\n\s+contents:\s+read", workflow)
    assert re.search(r"jobs:\s*\n\s+build:\s*\n\s+permissions:\s*\n\s+contents:\s+read", workflow)
    assert "contents: write" not in workflow
    assert "release:" not in workflow
    assert "softprops/action-gh-release" not in workflow
    assert "workflow_call:" in workflow
    assert "expected_sha:" in workflow
    assert "release_tag:" in workflow
    assert "REQUIRE_SIGNING: ${{ inputs.require_signing }}" in workflow
    assert "prepare_release_assets:" in workflow


def test_windows_portable_workflow_smokes_installed_shim(repo_root: Path) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    workflow = _read_text_or_fail(workflow_path)

    assert "Smoke: extracted install shim" in workflow
    assert '& "$bundle/install.cmd"' in workflow
    assert "Programs/FrameCompare/bin/frame-compare.cmd" in workflow
    assert "& $shim version" in workflow
    assert "& $shim --help" in workflow


def test_windows_portable_workflow_proves_code_only_update_without_pr_secrets(
    repo_root: Path,
) -> None:
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
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
    workflow_path = repo_root / ".github" / "workflows" / "windows-portable-build.yml"
    source = _read_text_or_fail(workflow_path)
    workflow = _load_workflow(workflow_path)
    build = workflow["jobs"]["build"]
    sign = _step_by_name(build, "Sign code-only update zip")
    verify = _step_by_name(build, "Verify code-only update zip layout")
    prepare = _step_by_name(build, "Prepare exact orchestrated release assets")
    verify_assets = _step_by_name(build, "Verify exact orchestrated release asset set")
    upload = _step_by_name(build, "Upload exact orchestrated release assets")

    assert set(workflow["jobs"]) == {"build"}
    assert sign["env"]["WINDOWS_UPDATE_SIGNING_KEY_XML"] == (
        "${{ secrets.WINDOWS_UPDATE_SIGNING_KEY_XML }}"
    )
    assert (
        "WINDOWS_UPDATE_SIGNING_KEY_XML is required for reusable release and manual runs."
        in sign["run"]
    )
    assert "tools/windows_portable/sign_update.ps1" in sign["run"]
    assert sign["if"] == "env.REQUIRE_SIGNING == 'true'"
    assert verify["env"]["REQUIRE_SIGNED_UPDATE"] == "${{ env.REQUIRE_SIGNING }}"
    assert "Signed update zip is missing update-manifest.sig." in verify["run"]
    assert prepare["if"] == "inputs.prepare_release_assets"
    assert (
        "Expected exactly one signed update zip, found $($updateSources.Count)."
        in prepare["run"]
    )
    assert "frame-compare-update-win-x64-$($env:RELEASE_TAG).zip" in prepare["run"]
    assert "exact mandatory set" in verify_assets["run"]
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["name"] == "frame-compare-release-assets"
    assert (
        "dist/release-assets/frame-compare-update-win-x64-${{ "
        "inputs.release_tag }}.zip.sha256"
    ) in upload["with"]["path"]
    assert "update_signed" not in source
