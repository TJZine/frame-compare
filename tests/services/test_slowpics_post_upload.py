from __future__ import annotations

from pathlib import Path

from frame_compare.config.schema import ConfigSchema
from frame_compare.services.slowpics_post_upload import (
    SlowpicsPostUploadRequest,
    run_slowpics_post_upload_actions,
)
from frame_compare.services.slowpics_shortcut import SlowpicsShortcutResult
from frame_compare.services.slowpics_webhook import (
    WEBHOOK_VALIDATION_WARNING,
    SlowpicsWebhookResult,
)
from frame_compare.utils.post_upload_actions import PostUploadActionResult
from frame_compare.utils.types import WorkspacePaths


def _workspace(
    root: Path,
    *,
    run_dir: Path | None = None,
    screenshots_dir: Path | None = None,
    generated_dir: Path | None = None,
) -> WorkspacePaths:
    return WorkspacePaths(
        root=root,
        input_dir=root / "comparison_videos",
        run_dir=run_dir,
        screenshots_dir=screenshots_dir or root / "screenshots",
        generated_dir=generated_dir or root / "generated",
        config_dir=root / "config",
        config_file=root / "config" / "config.toml",
    )


def _request(
    tmp_path: Path,
    *,
    run_dir: Path | None = None,
    create_url_shortcut: bool = True,
    webhook_url: str | None = None,
    slowpics_url: str = "https://slow.pics/c/example",
    collection_title: str = "Frame Comparison",
) -> SlowpicsPostUploadRequest:
    root = tmp_path / "workspace"
    config = ConfigSchema().slowpics
    config.create_url_shortcut = create_url_shortcut
    config.webhook_url = webhook_url
    return SlowpicsPostUploadRequest(
        workspace=_workspace(root, run_dir=run_dir),
        config=config,
        slowpics_url=slowpics_url,
        collection_title=collection_title,
    )


async def test_run_slowpics_post_upload_actions_writes_shortcut_when_enabled(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "workspace" / "runs" / "Collateral"
    request = _request(
        tmp_path,
        run_dir=run_dir,
        slowpics_url="https://slow.pics/c/collateral-key",
        collection_title="Collateral",
    )

    output = await run_slowpics_post_upload_actions(request)

    shortcut_path = run_dir / "Collateral.url"
    assert output == (
        PostUploadActionResult(
            kind="shortcut",
            success=True,
            path=shortcut_path,
            message="slow.pics URL shortcut written",
        ),
    )
    assert shortcut_path.read_text(encoding="utf-8") == (
        "[InternetShortcut]\nURL=https://slow.pics/c/collateral-key\n"
    )


async def test_run_slowpics_post_upload_actions_returns_no_actions_when_disabled(
    tmp_path: Path,
) -> None:
    request = _request(tmp_path, create_url_shortcut=False)

    output = await run_slowpics_post_upload_actions(request)

    assert output == ()


async def test_run_slowpics_post_upload_actions_returns_shortcut_then_webhook(
    tmp_path: Path, monkeypatch
) -> None:
    run_dir = tmp_path / "workspace" / "runs" / "Collateral"
    request = _request(
        tmp_path,
        run_dir=run_dir,
        webhook_url="https://hooks.example.test/webhook/token?secret=value",
        slowpics_url="https://slow.pics/c/example",
        collection_title="Collateral",
    )
    captured: dict[str, str] = {}

    async def _fake_deliver_slowpics_webhook(
        *, webhook_url: str, slowpics_url: str
    ) -> SlowpicsWebhookResult:
        captured["webhook_url"] = webhook_url
        captured["slowpics_url"] = slowpics_url
        return SlowpicsWebhookResult(success=True, detail="HTTP 204")

    monkeypatch.setattr(
        "frame_compare.services.slowpics_post_upload.deliver_slowpics_webhook",
        _fake_deliver_slowpics_webhook,
    )

    output = await run_slowpics_post_upload_actions(request)

    assert captured == {
        "webhook_url": "https://hooks.example.test/webhook/token?secret=value",
        "slowpics_url": "https://slow.pics/c/example",
    }
    assert output == (
        PostUploadActionResult(
            kind="shortcut",
            success=True,
            path=run_dir / "Collateral.url",
            message="slow.pics URL shortcut written",
        ),
        PostUploadActionResult(
            kind="webhook",
            success=True,
            detail="HTTP 204",
            message="slow.pics webhook delivered",
        ),
    )


async def test_run_slowpics_post_upload_actions_logs_shortcut_warning(
    tmp_path: Path, monkeypatch
) -> None:
    warning_calls: list[tuple[str, dict[str, object]]] = []
    warning = "slow.pics shortcut: failed to resolve URL shortcut directory: locked"
    failure_path = tmp_path / "workspace" / "runs" / "Example" / "Example.url"

    def _fake_create_shortcut(**_kwargs: object) -> SlowpicsShortcutResult:
        return SlowpicsShortcutResult(success=False, path=failure_path, warning=warning)

    def _capture_warning(event: str, **kwargs: object) -> None:
        warning_calls.append((event, kwargs))

    monkeypatch.setattr(
        "frame_compare.services.slowpics_post_upload.create_slowpics_url_shortcut",
        _fake_create_shortcut,
    )
    monkeypatch.setattr("frame_compare.services.slowpics_post_upload.log.warning", _capture_warning)

    output = await run_slowpics_post_upload_actions(
        _request(tmp_path, create_url_shortcut=True, collection_title="Example")
    )

    assert output == (
        PostUploadActionResult(
            kind="shortcut",
            success=False,
            path=failure_path,
            warning=warning,
        ),
    )
    assert warning_calls == [
        (
            "slowpics_shortcut_create_failed",
            {"path": str(failure_path), "warning": warning},
        ),
    ]


async def test_run_slowpics_post_upload_actions_webhook_failure_is_warning_only_and_redacted(
    tmp_path: Path, monkeypatch
) -> None:
    warning = "slow.pics webhook: delivery failed after 3 attempts"
    warning_calls: list[tuple[str, dict[str, object]]] = []

    async def _fake_deliver_slowpics_webhook(
        *,
        webhook_url: str,
        slowpics_url: str,
    ) -> SlowpicsWebhookResult:
        assert webhook_url == "https://secret.example.test/webhook/token?secret=value"
        assert slowpics_url == "https://slow.pics/c/example"
        return SlowpicsWebhookResult(success=False, warning=warning)

    def _capture_warning(event: str, **kwargs: object) -> None:
        warning_calls.append((event, kwargs))

    monkeypatch.setattr(
        "frame_compare.services.slowpics_post_upload.deliver_slowpics_webhook",
        _fake_deliver_slowpics_webhook,
    )
    monkeypatch.setattr("frame_compare.services.slowpics_post_upload.log.warning", _capture_warning)

    output = await run_slowpics_post_upload_actions(
        _request(
            tmp_path,
            create_url_shortcut=False,
            webhook_url="https://secret.example.test/webhook/token?secret=value",
        )
    )

    assert output == (PostUploadActionResult(kind="webhook", success=False, warning=warning),)
    assert "secret.example.test" not in warning
    assert "/webhook/token" not in warning
    assert "secret=value" not in warning
    assert warning_calls == [
        ("slowpics_webhook_delivery_failed", {"warning": warning}),
    ]


async def test_run_slowpics_post_upload_actions_webhook_validation_failure_returns_warning(
    tmp_path: Path,
) -> None:
    output = await run_slowpics_post_upload_actions(
        _request(tmp_path, create_url_shortcut=False, webhook_url="https://[::1")
    )

    assert output == (
        PostUploadActionResult(
            kind="webhook",
            success=False,
            warning=WEBHOOK_VALIDATION_WARNING,
        ),
    )
