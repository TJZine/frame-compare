"""Command-line argument helpers for tonemap overrides."""

from __future__ import annotations

import argparse
from typing import Any, Sequence

_PRESET_CHOICES = ("reference", "contrast", "filmic", "custom")
_FUNC_CHOICES = ("bt2390", "mobius", "hable")
_METRIC_CHOICES = ("abs", "ssim", "psnr", "deltae")


def build_tonemap_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("--tm-preset", choices=_PRESET_CHOICES)
    parser.add_argument("--tm-func", choices=_FUNC_CHOICES, dest="func")
    parser.add_argument("--tm-dst-max", type=float, dest="dst_max")
    parser.add_argument("--tm-dst-min", type=float, dest="dst_min")
    parser.add_argument("--tm-gamut-map", dest="gamut_mapping")
    parser.add_argument("--tm-smooth", type=int, dest="smoothing_period")
    parser.add_argument("--tm-scene-thresh-low", type=float, dest="scene_threshold_low")
    parser.add_argument("--tm-scene-thresh-high", type=float, dest="scene_threshold_high")
    parser.add_argument("--tm-verify-frame", type=int, dest="verify_frame")
    parser.add_argument("--tm-verify-search-max", type=int, dest="verify_search_max")
    parser.add_argument("--tm-verify-search-step", type=int, dest="verify_search_step")
    parser.add_argument("--tm-verify-start-frame", type=int, dest="verify_start_frame")
    parser.add_argument("--tm-verify-luma-thresh", type=float, dest="verify_luma_thresh")
    parser.add_argument("--tm-verify-metric", choices=_METRIC_CHOICES, dest="verify_metric")
    parser.add_argument("--tm-dst-primaries", dest="dst_primaries")
    parser.add_argument("--tm-dst-transfer", dest="dst_transfer")
    parser.add_argument("--tm-dst-matrix", dest="dst_matrix")
    parser.add_argument("--tm-dst-range", dest="dst_range")

    bool_opts = {
        "dpd": ["--tm-dpd"],
        "overlay": ["--tm-overlay"],
        "verify": ["--tm-verify"],
        "verify_auto_search": ["--tm-verify-auto-search"],
        "use_dovi": ["--tm-use-dovi"],
        "always_try_placebo": ["--tm-always-try-placebo"],
    }
    for dest, flags in bool_opts.items():
        parser.add_argument(*flags, action=argparse.BooleanOptionalAction, dest=dest)

    return parser


def parse_tonemap_args(argv: Sequence[str]) -> tuple[dict[str, Any], list[str]]:
    parser = build_tonemap_parser()
    try:
        parse_fn = getattr(parser, "parse_known_intermixed_args", None)
        if callable(parse_fn):
            namespace, remainder = parse_fn(argv)
        else:  # pragma: no cover - fallback for Python <3.7
            namespace, remainder = parser.parse_known_args(argv)
    except argparse.ArgumentError as exc:  # pragma: no cover - invalid CLI handled via ValueError
        raise ValueError(str(exc)) from exc

    overrides = {key: value for key, value in vars(namespace).items() if value is not None}
    return overrides, remainder
