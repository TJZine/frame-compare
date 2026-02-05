# Frame Compare
Deterministic video comparison pipeline: frame selection, HDR→SDR tonemapping, overlays/reports, and publishable outputs.

> [!NOTE]
> This repository contains Frame Compare’s ground-up rebuild. The legacy implementation lives separately as `frame-compare-legacy`.

[![Python](https://img.shields.io/badge/python-3.13%2B-3776AB)](#requirements)
[![Type Checked (Pyright)](https://img.shields.io/badge/type%20checked-pyright-1f6feb)](#quality--verification)
[![Linted (Ruff)](https://img.shields.io/badge/linted-ruff-d7ff64)](#quality--verification)
[![Conventional Commits](https://img.shields.io/badge/commits-conventional-fe5196f)](#contributing)
[![Release Please](https://img.shields.io/badge/releases-release--please-0b7285)](#releases--versioning)

---

## Table of Contents

- [What it does](#what-it-does)
- [Key ideas](#key-ideas)
- [Requirements](#requirements)
- [Install](#install)
- [Quick start](#quick-start)
- [Documentation](#documentation)
- [Quality & verification](#quality--verification)
- [Releases & versioning](#releases--versioning)
- [Contributing](#contributing)
- [Security](#security)
- [License](#license)

---

## What it does

Frame Compare helps you produce consistent, reviewable comparisons between encodes:

- Selects representative frames deterministically (including seeded randomness where required).
- Renders PNGs with overlays and stable naming.
- Produces machine-readable outputs for automation (reports/metadata) and human-readable outputs for review.
- Supports “offline-first” workflows, with optional publishing integrations.

If you want the spec-driven rebuild plan and workflow, start here:
- `docs/OPUS_REBUILD_FRAME_COMPARE/00-executive-summary.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow-quick.md` (read first)
- `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md` (canonical SSOT)

---

## Key ideas

### Determinism by default

Frame Compare is designed so the same inputs produce the same outputs:
- Stable sorting rules and explicit seeds.
- “No guessing” contracts for CLI/config where ambiguity would cause churn.
- Reproducible verification gates.

### Contract-first documentation

Canonical truth is stored as YAML/JSON contracts, with generated derived views:
- Canonical: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/`
- Derived views generator: `scripts/generate_contract_views.py`
- Readiness gate SSOT: `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`

### Workflow discipline (optional, but supported)

This repo includes an operator-minimal, file-based run system for phased implementation:
- Run artifacts live under `.agent-workflow/runs/<RUN_ID>/`
- Each artifact ends with a `## NEXT AGENT PROMPT (COPY/PASTE)` block for deterministic handoffs

See: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

---

## Requirements

- Python 3.13+
- `uv` (recommended) or `pip`
- FFmpeg available on `PATH` (for probing and fallbacks)
- Optional: VapourSynth runtime and plugins (for the primary renderer path)

---

## Install

> [!TIP]
> Prefer `uv` for reproducible environments.

### With uv

```bash
uv sync --group dev --frozen
```

### With pip (virtualenv)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
# Dev tools (this repo uses uv dependency groups; pip does not install them automatically)
python -m pip install pytest pytest-cov ruff pyright
```

---

## Quick start

This README is a high-level overview. The authoritative runbook and CLI surface are documented in the OPUS rebuild docs.

- Start here: `docs/OPUS_REBUILD_FRAME_COMPARE/00-executive-summary.md`
- Workflow and gates: `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`

---

## Usage

> [!IMPORTANT]
> The full pipeline depends on external tools (FFmpeg, VapourSynth + plugins). The most reproducible way to run the
> end-to-end commands is via Docker.

### Docker (Recommended)

Build the dev image:

```bash
docker build -t frame-compare:dev .
```

Run dependency diagnostics:

```bash
docker run --rm frame-compare:dev doctor --json
```

Run the interactive config wizard and persist output to your working directory:

```bash
docker run --rm -it \
  -v "$PWD":/workspace \
  -w /workspace \
  frame-compare:dev wizard
```

Run the pipeline (example mounts `comparison_videos/` read-only and writes outputs to `./output/`):

```bash
docker run --rm -it \
  -v "$PWD/comparison_videos":/workspace/comparison_videos:ro \
  -v "$PWD/output":/workspace/screenshots \
  -w /workspace \
  frame-compare:dev run \
    --root /workspace \
    --input /workspace/comparison_videos \
    --no-upload \
    --frame-count 10
```

> [!TIP]
> If you want `slow.pics` uploads, omit `--no-upload` and ensure your config contains the desired visibility settings.

### Local Dev (Partial, Optional-Deps Required)

Local invocations may require optional dependencies (notably VapourSynth) depending on the code-paths exercised. For
reproducible “real deps” verification, prefer Docker:

```bash
bash tools/verify_docker_integration.sh
```

### Readiness gates (repo-level)

```bash
./scripts/check-all-gates.sh
```

Or, to rerun and sync gate timestamps in `AI_READINESS_ROADMAP.md`:

```bash
bash scripts/reverify_ai_readiness.sh --update-roadmap
```

---

## Documentation

### Rebuild plan + execution workflow

- Executive overview: `docs/OPUS_REBUILD_FRAME_COMPARE/00-executive-summary.md`
- Multi-agent workflow (SSOT): `docs/OPUS_REBUILD_FRAME_COMPARE/11-agent-workflow.md`
- Master checklist: `docs/OPUS_REBUILD_FRAME_COMPARE/10-agent-master-checklist.md`
- Generated API reference: `docs/api.md` (generated by `scripts/generate_api_docs.py`)

### Contracts (SSOT)

- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/README.md`
- `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/readiness_gates.json`

---

## Quality & verification

### Command canon (two-lane)

This repo uses two lanes to keep commands deterministic:

1) Repo scripts/validators: `uv run --no-sync` with workspace cache

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/generate_contract_views.py --check
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_traceability.py --check
```

2) Tooling: prefer `.venv/bin/*`

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

### Docker integration (real deps)

For “real external deps work” verification (VapourSynth + FFmpeg), run:

```bash
bash tools/verify_docker_integration.sh
```

### Run-directory hygiene (optional workflow enforcement)

```bash
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_id.py --check-exists <RUN_ID>
UV_CACHE_DIR=./.uv_cache uv run --no-sync python scripts/validate_run_artifacts.py .agent-workflow/runs/<RUN_ID>
```

---

## Releases & versioning

### Versioning policy

- Git tags follow SemVer with a `v` prefix (for example `v0.1.0`, `v1.0.0`).
- During the rebuild, pre-1.0 tags are expected while the public surface stabilizes.

### Release automation

This repo is designed to support:
- Conventional Commits (enforced via PR titles + squash merge).
- Release automation from `main` (recommended: Release PR model via release-please).

---

## Contributing

### Workflow

1) Create a branch for your change.
2) Open a PR to `main`.
3) Use a Conventional Commit-style PR title (this becomes the squash commit message):
   - `feat(scope): add ...`
   - `fix(scope): correct ...`
   - `docs: clarify ...`
   - `chore: ...`

### Local checks

```bash
.venv/bin/pyright --warnings
.venv/bin/ruff check .
.venv/bin/pytest -q
```

### Project guardrails

Read: `CODEX.md`

---

## Security

Security invariants are documented and tested in the scaffold and workflow:
- Path traversal containment
- Subprocess argument hardening
- SSRF policy (where network features exist)

See: `docs/OPUS_REBUILD_FRAME_COMPARE/08-quality-standards.md` and `docs/OPUS_REBUILD_FRAME_COMPARE/scaffold/`

---

## License

See `LICENSE` (to be added).
