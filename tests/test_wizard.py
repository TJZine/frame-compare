from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import src.frame_compare.wizard as wizard


def test_run_wizard_prompts_updates_sections(monkeypatch, tmp_path: Path) -> None:
    """Wizard orchestration should update each config section via the helpers."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    monkeypatch.setattr(  # type: ignore[reportUnknownMemberType]
        wizard,
        "prompt_workspace_root",
        lambda root: workspace,
        raising=False,
    )
    monkeypatch.setattr(  # type: ignore[reportUnknownMemberType]
        wizard,
        "prompt_input_directory",
        lambda root, default: "custom_videos",
        raising=False,
    )
    def _slowpics(cfg: Dict[str, Any]) -> None:
        cfg["auto_upload"] = True

    monkeypatch.setattr(  # type: ignore[reportUnknownMemberType]
        wizard,
        "prompt_slowpics_options",
        _slowpics,
        raising=False,
    )
    def _audio(cfg: Dict[str, Any]) -> None:
        cfg["enable"] = True

    monkeypatch.setattr(  # type: ignore[reportUnknownMemberType]
        wizard,
        "prompt_audio_alignment_option",
        _audio,
        raising=False,
    )
    def _renderer(cfg: Dict[str, Any]) -> None:
        cfg["use_ffmpeg"] = True

    monkeypatch.setattr(  # type: ignore[reportUnknownMemberType]
        wizard,
        "prompt_renderer_preference",
        _renderer,
        raising=False,
    )

    root, config = wizard.run_wizard_prompts(tmp_path, {})

    assert root == workspace
    assert config["paths"]["input_dir"] == "custom_videos"
    assert config["slowpics"]["auto_upload"] is True
    assert config["audio_alignment"]["enable"] is True
    assert config["screenshots"]["use_ffmpeg"] is True


def test_prompt_slowpics_options_respects_user_input(monkeypatch) -> None:
    """Slow.pics prompt should honor user-confirmed choices."""

    confirm_answers = iter([True, True, False])

    def fake_confirm(message: str, default: bool = False) -> bool:
        return next(confirm_answers)

    def fake_prompt(message: str, **kwargs: Any) -> str:
        return "movie/603"

    monkeypatch.setattr(wizard.click, "confirm", fake_confirm)  # type: ignore[reportUnknownMemberType]
    monkeypatch.setattr(wizard.click, "prompt", fake_prompt)  # type: ignore[reportUnknownMemberType]

    config: Dict[str, Any] = {
        "auto_upload": False,
        "tmdb_id": "",
        "delete_screen_dir_after_upload": True,
    }

    wizard.prompt_slowpics_options(config)

    assert config["auto_upload"] is True
    assert config["tmdb_id"] == "movie/603"
    assert config["delete_screen_dir_after_upload"] is False
