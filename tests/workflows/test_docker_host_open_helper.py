from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_helper_module(repo_root: Path):
    script_path = repo_root / "tools" / "open_docker_host_target.py"
    spec = importlib.util.spec_from_file_location("docker_host_open_helper", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_translates_generated_paths(repo_root: Path, tmp_path: Path) -> None:
    helper = _load_helper_module(repo_root)
    fake_repo = tmp_path / "repo"
    generated_file = fake_repo / "generated" / "vspreview" / "session.py"
    generated_file.parent.mkdir(parents=True)
    generated_file.write_text("print('ok')\n", encoding="utf-8")
    translated_generated = helper.translate_container_path(
        "/workspace/generated/vspreview/session.py",
        repo_root=fake_repo,
    )

    assert translated_generated == generated_file.resolve()


def test_rejects_disallowed_or_unknown_workspace_roots(repo_root: Path, tmp_path: Path) -> None:
    helper = _load_helper_module(repo_root)
    fake_repo = tmp_path / "repo"
    (fake_repo / "generated").mkdir(parents=True)

    with pytest.raises(ValueError, match="/workspace/config"):
        helper.translate_container_path("/workspace/config/config.toml", repo_root=fake_repo)
    with pytest.raises(ValueError, match="/workspace/comparison_videos"):
        helper.translate_container_path(
            "/workspace/comparison_videos/reference.mkv",
            repo_root=fake_repo,
        )
    with pytest.raises(
        ValueError,
        match="only /workspace/generated",
    ):
        helper.translate_container_path("/workspace/other/output.html", repo_root=fake_repo)

    with pytest.raises(
        ValueError,
        match="only /workspace/generated",
    ):
        helper.translate_container_path(
            "/workspace/screenshots/run-001/report.html", repo_root=fake_repo
        )


def test_rejects_non_canonical_or_missing_targets(repo_root: Path, tmp_path: Path) -> None:
    helper = _load_helper_module(repo_root)
    fake_repo = tmp_path / "repo"
    (fake_repo / "generated").mkdir(parents=True)

    with pytest.raises(ValueError, match="absolute"):
        helper.translate_container_path("generated/report.html", repo_root=fake_repo)
    with pytest.raises(ValueError, match="must not contain '.' or '..'"):
        helper.translate_container_path(
            "/workspace/generated/../config/config.toml", repo_root=fake_repo
        )
    with pytest.raises(ValueError, match="does not exist"):
        helper.translate_container_path("/workspace/generated/report.html", repo_root=fake_repo)


def test_rejects_symlink_escape_from_allowed_root(repo_root: Path, tmp_path: Path) -> None:
    helper = _load_helper_module(repo_root)
    fake_repo = tmp_path / "repo"
    generated_root = fake_repo / "generated"
    screenshots_root = fake_repo / "screenshots"
    outside_root = tmp_path / "outside"
    generated_root.mkdir(parents=True)
    screenshots_root.mkdir(parents=True)
    outside_root.mkdir()
    (generated_root / "escape").symlink_to(outside_root, target_is_directory=True)
    outside_file = outside_root / "report.html"
    outside_file.write_text("<html></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes the allowed host root"):
        helper.translate_container_path(
            "/workspace/generated/escape/report.html",
            repo_root=fake_repo,
        )


def test_validate_slowpics_url_accepts_only_https_slowpics(repo_root: Path) -> None:
    helper = _load_helper_module(repo_root)

    assert helper.validate_slowpics_url("https://slow.pics/c/example?view=grid") == (
        "https://slow.pics/c/example?view=grid"
    )

    with pytest.raises(ValueError, match="only https slow.pics URLs are allowed"):
        helper.validate_slowpics_url("http://slow.pics/c/example")
    with pytest.raises(ValueError, match="only https://slow.pics/... URLs are allowed"):
        helper.validate_slowpics_url("https://example.com/c/example")
    with pytest.raises(ValueError, match="must not include credentials or a port"):
        helper.validate_slowpics_url("https://slow.pics:443/c/example")


def test_validate_slowpics_url_requires_comparison_result_path(repo_root: Path) -> None:
    helper = _load_helper_module(repo_root)

    rejected_targets = (
        "https://slow.pics/",
        "https://slow.pics/comparison",
        "https://slow.pics/upload/comparison",
        "https://slow.pics/c/",
        "https://slow.pics/c/example/extra",
        "https://slow.pics/c/example#fragment",
        "https://slow.pics/c/example;param",
    )

    for target in rejected_targets:
        with pytest.raises(ValueError, match="must be a comparison URL"):
            helper.validate_slowpics_url(target)


def test_main_print_only_outputs_translated_host_path(
    repo_root: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = _load_helper_module(repo_root)
    fake_repo = tmp_path / "repo"
    generated_file = fake_repo / "generated" / "report.html"
    generated_file.parent.mkdir(parents=True)
    generated_file.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(helper, "REPO_ROOT", fake_repo)

    exit_code = helper.main(["--print-only", "/workspace/generated/report.html"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == str(generated_file.resolve())
    assert captured.err == ""
