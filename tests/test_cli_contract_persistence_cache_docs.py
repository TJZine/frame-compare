from __future__ import annotations

from pathlib import Path


def test_current_cli_contract_documents_run_folder_identity_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_cli_contract = " ".join(cli_contract.split())
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "folder names are capped at 64 characters",
        "do not include exact timestamps",
        "collisions use compact numeric suffixes such as `_2` and `_3`",
        "`<run-folder>/run_info.toml`",
        "UTC `created_at` with a `Z` suffix",
        "`naming_source`",
        "`source_filenames`",
        "absent optional values omitted rather than serialized as null",
        "not a final outcome manifest",
        "If `run_info.toml` cannot be written, the run fails immediately",
    ):
        assert expected in normalized_cli_contract

    for expected in (
        "`<run-folder>/run_info.toml`: root-level run identity metadata",
        "Exact timestamps are not part of folder names",
        "The exact creation time lives in `<run-folder>/run_info.toml`",
        "written before probing, rendering, or other runtime-heavy work",
    ):
        assert expected in normalized_architecture


def test_current_cli_contract_documents_analysis_ignore_window_and_cache_domain() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    analysis_heading = "## Config-Only Analysis Surface"
    slowpics_heading = "## Config-Only slow.pics Surface"
    assert analysis_heading in cli_contract, f"Missing heading: {analysis_heading}"

    analysis_section = cli_contract.split(analysis_heading, maxsplit=1)[1].split(
        slowpics_heading,
        maxsplit=1,
    )[0]
    normalized_analysis_section = " ".join(analysis_section.split())
    for expected in (
        "`user_frames = []`",
        "`random_frame_count = 10`",
        "`dark_frame_count = 0`",
        "`bright_frame_count = 0`",
        "`motion_frame_count = 0`",
        "`ignore_lead_seconds = 0.0`",
        "`ignore_trail_seconds = 0.0`",
        "`min_window_seconds = 5.0`",
        "original selected-reference source-frame numbers",
        "Removed stale analysis keys `selection_mode` and `frame_count` fail validation explicitly",
        "there are no dedicated `run` flags",
        "source-specific base trim domain",
        "do not physically trim sources",
        "reported source-frame numbers",
        "standard typed selection error",
    ):
        assert expected in normalized_analysis_section

    command_heading = "## Command Surface"
    command_override_surface = cli_contract.split(command_heading, maxsplit=1)[1].split(
        analysis_heading,
        maxsplit=1,
    )[0]
    for unsupported_flag in (
        "--ignore-lead-seconds",
        "--ignore-trail-seconds",
        "--min-window-seconds",
    ):
        assert unsupported_flag not in command_override_surface

    cache_section = cli_contract.split("### Cache Mode Semantics", maxsplit=1)[1].split(
        "### Report Auto-Open Ownership",
        maxsplit=1,
    )[0]
    normalized_cache_section = " ".join(cache_section.split())
    for expected in (
        "stable all-source selection-domain token",
        "`analysis_source_path`",
        "`reference_path`",
        "Cache schema v8 stores `analysis_source_path`, `performance_mode`, `algorithm_id`",
        "exact selectable metric source range",
        "explicit `sampled_source_frames` map",
        "`metric_active_rect`",
        "active-rect source, detection mode, and active-rect resolver algorithm ID",
        "performance modes, metric algorithm identities, or active-rect metric domains",
        "active-rect metric domains",
        "active-rect resolver policy",
        "each clip's resolved active rectangle",
        "produce coordinate-specific metric/cache identities",
        'When `sources.analysis_source = "reference"`',
        "source trims",
        "effective FPS values",
        "configured analysis ignore-window settings",
        "final shared selectable window",
        "probe cache is missing",
        "rather than validating a weaker fingerprint",
        "Previous alignment reuse is not part of analysis cache-only prevalidation",
        '`previous_offsets = "always"`',
        "missing previous alignment offsets do not fail `--from-cache-only`",
        "does not delete shared previous-offset reuse entries",
        "Alignment can compute current-run offsets",
        "<resolved paths.generated_dir>/cache/alignment/",
    ):
        assert expected in normalized_cache_section


def test_current_cli_contract_documents_previous_offsets_output_and_persistence() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    cli_contract = (repo_root / "docs" / "current-cli-contract.md").read_text(encoding="utf-8")
    run_section = cli_contract.split("## `run` Command Contract", maxsplit=1)[1].split(
        "## CLI Flag To Config Mapping",
        maxsplit=1,
    )[0]
    persistence_section = cli_contract.split("## Persistence Rules", maxsplit=1)[1].split(
        "### Tonemap Preset And Target Resolution",
        maxsplit=1,
    )[0]
    normalized_run = " ".join(run_section.split())
    normalized_persistence = " ".join(persistence_section.split())

    for expected in (
        '`--json` is incompatible with `audio_alignment.previous_offsets = "prompt"`',
        '`previous_offsets = "always"` is compatible with `--json`',
        '`--quiet` is incompatible with `audio_alignment.previous_offsets = "prompt"`',
        "`previous offsets` row reports only the effective config mode",
        "`disabled`, `prompt`, or `always`",
        "disables ANSI styling for the previous-offset reuse table and prompt",
        "shared alignment reuse entries live below it at `cache/alignment`",
        "`--diagnose-paths` does not report the shared alignment cache path separately",
    ):
        assert expected in normalized_run

    for expected in (
        '`audio_alignment.previous_offsets = "prompt"` or `"always"`',
        "`audio_alignment.force_interactive = true`",
        "`audio_alignment.cache_results = false`",
        "The config is not written when either conflict is present",
    ):
        assert expected in normalized_persistence


def test_current_architecture_documents_shared_alignment_reuse_cache_seams() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "<resolved paths.generated_dir>/cache/alignment/alignment_reuse.toml",
        "`frame_compare.services.alignment_reuse_cache`",
        "shared previous alignment offset reuse cache",
        "`generated/manual_overrides.toml` or `<run-folder>/generated/manual_overrides.toml`",
        "stable generated area when run folders are disabled",
        "current run folder when run folders are enabled",
        "`WorkspacePaths.shared_alignment_cache_dir`",
        "shared workspace-level `<resolved paths.generated_dir>/cache/alignment` path",
        "`frame_compare.utils.types.AlignmentRequest`",
        "`frame_compare.orchestration.phase_tasks.run_align_phase()`",
        "typed orchestration-to-services request seam",
        "layer-neutral primitives or dependency-light shared utility types",
        "must not import orchestration-owned or analysis-owned identity types",
        "`frame_compare.services.alignment_reuse_prompt`",
        "`frame_compare.services.types.AlignmentProvenance`",
        "`computed_this_run`",
        "`vspreview_confirmed_this_run`",
        "`shared_computed_offsets`",
        "`shared_previous_offsets`",
        "`preexisting_manual_override`",
        "rather than inferring eligibility from the final flattened `AlignmentResult.source`",
    ):
        assert expected in normalized_architecture
    for stale in (
        "`generated/audio_offsets.toml`",
        "`<run-folder>/generated/audio_offsets.toml`",
        "run-scoped alignment cache",
        "run-scoped VSPreview-confirmed manual alignment overrides",
    ):
        assert stale not in normalized_architecture


def test_current_architecture_documents_shared_probe_cache_for_cache_only() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    architecture = (repo_root / "docs" / "current-architecture.md").read_text(encoding="utf-8")
    normalized_architecture = " ".join(architecture.split())

    for expected in (
        "shared clip probe cache used by `--from-cache-only` prevalidation",
        "before run-folder reservation",
        "current-run clip probe cache when run folders are enabled",
        "written to both the current run folder and the shared generated probe cache",
        "validate the exact all-source analysis selection domain",
    ):
        assert expected in normalized_architecture
