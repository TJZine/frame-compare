"""Typed interface definitions for service adapters."""

from __future__ import annotations

from .publishers import (
    PublisherIO,
    ReportRendererProtocol,
    SlowpicsClientProtocol,
)

__all__ = [
    "PublisherIO",
    "ReportRendererProtocol",
    "SlowpicsClientProtocol",
]
