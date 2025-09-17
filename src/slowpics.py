from __future__ import annotations

"""Slow.pics upload orchestration."""

from pathlib import Path
from typing import List
from urllib.parse import urlsplit
import logging
import time

import requests

from .datatypes import SlowpicsConfig


class SlowpicsAPIError(RuntimeError):
    """Raised when slow.pics API interactions fail."""


_SLOWPICS_BASE = "https://slow.pics/api"


logger = logging.getLogger(__name__)


def _raise_for_status(response: requests.Response, context: str) -> None:
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise SlowpicsAPIError(f"{context} failed ({response.status_code}): {detail}")


def _post_json(session: requests.Session, url: str, payload: dict, context: str) -> requests.Response:
    resp = session.post(url, json=payload, timeout=30)
    _raise_for_status(resp, context)
    return resp


def _upload_file(session: requests.Session, url: str, file_path: Path, payload: dict, context: str) -> requests.Response:
    with file_path.open("rb") as handle:
        files = {"image": (file_path.name, handle, "image/png")}
        data = {key: str(value) for key, value in payload.items() if value is not None}
        resp = session.post(url, files=files, data=data, timeout=60)
    _raise_for_status(resp, context)
    return resp


def _redact_webhook(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except Exception:
        return "webhook"
    if parsed.netloc:
        return parsed.netloc
    return parsed.path or "webhook"


def _post_direct_webhook(session: requests.Session, webhook_url: str, canonical_url: str) -> None:
    redacted = _redact_webhook(webhook_url)
    payload = {"content": canonical_url}
    backoff = 1.0
    for attempt in range(1, 4):
        try:
            resp = session.post(webhook_url, json=payload, timeout=10)
            if resp.status_code < 300:
                logger.info("Posted slow.pics URL to webhook host %s", redacted)
                return
            message = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:
            message = exc.__class__.__name__
        logger.warning(
            "Webhook post attempt %s to %s failed: %s",
            attempt,
            redacted,
            message,
        )
        if attempt < 3:
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
    logger.error("Giving up on webhook delivery to %s after %s attempts", redacted, 3)


def upload_comparison(image_files: List[str], screen_dir: Path, cfg: SlowpicsConfig) -> str:
    """Upload screenshots to slow.pics and return the collection URL."""

    if not image_files:
        raise SlowpicsAPIError("No image files provided for upload")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "frame-compare/1.0",
    })

    try:
        landing = session.get("https://slow.pics/comparison", timeout=15)
        landing.raise_for_status()
    except requests.RequestException as exc:
        raise SlowpicsAPIError(f"Failed to establish slow.pics session: {exc}") from exc

    xsrf_token = session.cookies.get("XSRF-TOKEN")
    if not xsrf_token:
        raise SlowpicsAPIError("Missing XSRF token from slow.pics response")

    session.headers.update({
        "Origin": "https://slow.pics",
        "Referer": "https://slow.pics/comparison",
        "X-Xsrf-Token": xsrf_token,
    })

    create_payload = {
        "title": cfg.collection_name or "Frame Comparison",
        "public": bool(cfg.is_public),
        "hentai": bool(cfg.is_hentai),
        "tmdbId": cfg.tmdb_id or None,
        "removeAfterDays": int(cfg.remove_after_days or 0) or None,
    }
    create_resp = _post_json(session, f"{_SLOWPICS_BASE}/collections", create_payload, "Collection creation")
    try:
        create_json = create_resp.json()
    except ValueError as exc:
        raise SlowpicsAPIError("Invalid JSON response when creating collection") from exc

    collection_id = create_json.get("uuid") or create_json.get("collectionUuid")
    collection_key = create_json.get("key")
    if not collection_id or not collection_key:
        raise SlowpicsAPIError("Missing collection identifiers in slow.pics response")

    upload_url = f"{_SLOWPICS_BASE}/collections/{collection_id}/items"

    for order, file_path in enumerate(image_files):
        path = Path(file_path)
        if not path.is_file():
            raise SlowpicsAPIError(f"Image file not found: {file_path}")

        payload = {
            "collectionUuid": collection_id,
            "collectionKey": collection_key,
            "order": order,
        }
        _upload_file(session, upload_url, path, payload, context=f"Upload frame {order}")

    if cfg.webhook_url:
        webhook_payload = {
            "collectionUuid": collection_id,
            "collectionKey": collection_key,
            "webhookUrl": cfg.webhook_url,
        }
        _post_json(session, f"{_SLOWPICS_BASE}/collections/{collection_id}/webhook", webhook_payload, "Webhook notification")

    canonical_url = f"https://slow.pics/c/{collection_id}/{collection_key}"
    if cfg.webhook_url:
        _post_direct_webhook(session, cfg.webhook_url, canonical_url)
    if cfg.create_url_shortcut:
        shortcut_path = screen_dir / f"slowpics_{collection_id}.url"
        shortcut_path.write_text(f"[InternetShortcut]\nURL={canonical_url}\n", encoding="utf-8")
    return canonical_url
