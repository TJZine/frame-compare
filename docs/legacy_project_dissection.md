# Project Dissection & Documentation: Frame Compare

## 1. Executive Summary

**Frame Compare** is a specialized CLI tool designed for video archivists, fansubbers, and quality control (QC) engineers. Its primary purpose is to automate the generation of deterministic, scientifically accurate screenshot comparisons between different video encodes (e.g., source vs. encode, HDR vs. SDR).

The system addresses the complexity of aligning video sources that may differ in resolution, color space (HDR/SDR), and audio timing. It provides a "battery included" pipeline that handles:
1.  **Discovery**: Finding video files in a workspace.
2.  **Alignment**: Automatically syncing audio tracks to ensure frames match.
3.  **Analysis**: selecting frames based on luminance (dark/bright), motion, and randomness.
4.  **Processing**: High-fidelity HDR-to-SDR tonemapping using VapourSynth and libplacebo.
5.  **Rendering**: Exporting screenshots via VapourSynth or FFmpeg.
6.  **Publication**: Uploading to slow.pics and generating local HTML reports.

Technically, it is a Python 3.13+ CLI application that leverages **VapourSynth** as its primary image processing engine, with **FFmpeg** as a fallback and helper. It features a modular "Phased" architecture, extensive configuration via TOML, and a strong focus on reproducibility and automation.

**Critical Assessment**: The project is well-structured and follows modern Python practices (type hinting, strict linting, modular design). It is currently in a pre-1.0 state (`0.0.14`) but exhibits high complexity in its orchestration and dependency management (specifically VapourSynth).

## 2. Quick Reference Card

| Aspect | Details |
| :--- | :--- |
| **Language** | Python 3.13+ |
| **Core Engine** | VapourSynth (R72+) |
| **Key Libraries** | `click` (CLI), `rich` (UI), `numpy`/`librosa` (Audio Align), `pydantic` (implicitly via config patterns), `httpx` (Network) |
| **Config Format** | TOML (`config/config.toml`) |
| **Entry Point** | `src/frame_compare/cli_entry.py` (`frame-compare` command) |
| **Orchestrator** | `src/frame_compare/orchestration/coordinator.py` |
| **Tests** | `pytest` suite in `tests/` |

**Essential Commands**:
```bash
# Note: For reproducible/offline runs where dependencies are already synced (CI/gates),
# prefer `uv run --no-sync python ...` with `UV_CACHE_DIR=./.uv_cache`.

# Initialize workspace
uv run python -m frame_compare --write-config

# Run comparison
uv run python -m frame_compare --root . --input comparison_videos/my-set

# Check system health
uv run python -m frame_compare doctor

# Apply preset
uv run python -m frame_compare preset apply quick-compare
```

---

## 3. Detailed Documentation

### 3.1 Project Identity & Overview

*   **Project Name**: Frame Compare
*   **Type**: CLI Tool / Automation Pipeline
*   **Target Audience**: Video Encoders, Archivists, Fansub Groups.
*   **Age**: Early development (Version 0.0.14), active refactoring.
*   **Scale**: ~50+ source files, modular architecture.

### 3.2 Architecture Classification

**Layered Pipeline Architecture**:
The application uses a strict sequential pipeline pattern orchestrated by a `WorkflowCoordinator`.

1.  **CLI Layer**: Handles user input/output (`cli_entry.py`).
2.  **Orchestration Layer**: Manages the lifecycle of a run (`orchestration/`).
3.  **Service Layer**: Encapsulates domain logic (`services/` - Alignment, Metadata, Setup).
4.  **Core Domain**: Processing logic (`vs/`, `analysis/`, `render/`).
5.  **Infrastructure/Adapters**: External system interactions (`tmdb.py`, `slowpics.py`).

### 3.3 Repository Structure Map

```
frame-compare/
├── src/
│   ├── data/                 # Static resources (templates, report assets)
│   │   ├── config.toml.template
│   │   └── report/           # HTML report assets
│   ├── frame_compare/        # Source Code
│   │   ├── cli_entry.py      # Entry point (Click)
│   │   ├── runner.py         # Public API Facade
│   │   ├── orchestration/    # Pipeline Orchestrator
│   │   │   ├── coordinator.py# Main execution loop
│   │   │   ├── phases/       # Individual steps (Setup, Align, Render...)
│   │   │   └── state.py      # Shared context objects
│   │   ├── vs/               # VapourSynth Integration
│   │   │   ├── tonemap.py    # HDR->SDR Logic
│   │   │   └── source.py     # Source loading (LSMAS/FFMS2)
│   │   ├── render/           # Screenshot logic
│   │   ├── screenshot/       # Screenshot orchestration
│   │   ├── analysis/         # Frame selection logic
│   │   ├── services/         # Domain services
│   │   │   ├── alignment.py  # Audio alignment wrapper
│   │   │   └── metadata.py   # TMDB/Naming logic
│   │   ├── audio_alignment.py# Audio processing (librosa)
│   │   └── slowpics.py       # Upload client
│   └── ...
├── tests/                    # Pytest suite
├── comparison_videos/        # Default workspace input
├── config/                   # User configuration
├── docs/                     # Documentation
├── pyproject.toml            # Project metadata & dependencies
└── README.md
```

---

### 3.4 Technology Stack Deep Dive

#### Runtime Dependencies (Critical)
| Dependency | Purpose | Criticality |
| :--- | :--- | :--- |
| `vapoursynth` | Core video processing, resizing, tonemapping. | **CRITICAL** |
| `click` | CLI framework. | High |
| `rich` | Terminal output styling and progress bars. | High |
| `numpy` | Audio array processing for alignment. | High |
| `librosa` | Audio feature extraction (chroma/spectrogram). | High |
| `soundfile` | Audio I/O. | High |
| `httpx` / `requests` | API requests (TMDB, Slow.pics). | Medium |
| `guessit` / `anitopy` | Filename metadata parsing. | Medium |

#### Infrastructure
*   **Config**: TOML files using Python's `tomllib` (3.11+) or compatible parser.
*   **Caching**:
    *   `generated.compframes`: custom pickle/JSON cache for frame metrics.
    *   `generated.audio_offsets.toml`: TOML cache for alignment results.
    *   `.frame_compare.run.json`: Snapshot of the last run state.

---

### 3.5 Core Feature Inventory

#### Feature: Frame Discovery & Selection
*   **Category**: System / Analysis
*   **Function**: Analyzes video files to find "interesting" frames.
*   **Logic**:
    *   Uses VapourSynth `PlaneStats` to find darkest/brightest frames.
    *   Uses motion vectors or difference metrics for motion frames.
    *   Supports random sampling with seeded RNG for reproducibility.
    *   Skips intro/outro based on config (`ignore_lead_seconds`).

#### Feature: Audio Alignment
*   **Category**: Analysis / Processing
*   **Function**: Syncs different video sources (e.g., Blu-ray vs. Web-DL) by analyzing audio tracks.
*   **Logic**:
    *   Extracts audio using FFmpeg/VapourSynth.
    *   Downsamples and computes Cross-Correlation using `scipy`/`numpy`.
    *   Calculates offset (delay) to match sources to the reference.
    *   **Interactive Mode**: Can launch `vspreview` to let user manually verify/adjust sync.

#### Feature: HDR Tonemapping
*   **Category**: Processing (Visual)
*   **Function**: Converts HDR (HDR10, DoVi) to SDR for comparison.
*   **Logic**:
    *   Uses `libplacebo` via VapourSynth.
    *   **Presets**: `reference` (BT.2390), `filmic`, `highlight_guard`.
    *   **Configuration**: Extremely granular control (target nits, knee, spline, etc.).
    *   **Fallback**: extensive retry logic for different color spaces.

#### Feature: Screenshot Rendering
*   **Category**: Output
*   **Function**: Generates the actual PNG files.
*   **Logic**:
    *   **VapourSynth Mode**: High precision, uses `tonemap.py`.
    *   **FFmpeg Mode**: Fallback for speed or when VS is missing.
    *   **Overlays**: Adds text overlays with frame info/tonemap settings.

#### Feature: Slow.pics Integration
*   **Category**: Publication
*   **Function**: Uploads generated comparison to slow.pics.
*   **Logic**:
    *   Automates browser upload or uses API if available (simulated/reverse-engineered).
    *   Generates a "shortcut" file for easy access.

---

### 3.6 Data Architecture

The project does not use a traditional database. It relies on:

1.  **File System**:
    *   Input: `comparison_videos/<set_name>/*.mkv`
    *   Output: `screens/<set_name>/*.png`
    *   Config: `config/config.toml`

2.  **State Files**:
    *   `generated.compframes`: Serialized analysis data (frames, scores).
    *   `generated.audio_offsets.toml`: Text-based offset cache.

**Data Model (Implicit)**:
*   **ClipPlan**: Represents a video file + its processing instructions (crop, trim, align).
*   **RunContext**: The global state of the current execution.
*   **TonemapInfo**: Metadata about how a frame was processed.

---

### 3.7 Business Logic & Rules

**Key Domain Rules**:
*   **Root Containment**: All file operations must stay within the defined `--root` workspace (security/safety).
*   **Deterministic Output**: Running the same config on the same files must produce identical images (controlled via seeds).
*   **Reference-Based Alignment**: One clip is the "Reference"; others are "Targets" aligned relative to it.
*   **Config Precedence**: CLI Flags > Config File > Defaults.

---

### 3.8 Configuration & Environment

The configuration is centralized in `config.toml`.
*   **Sections**: `[paths]`, `[analysis]`, `[audio_alignment]`, `[screenshots]`, `[color]`, `[slowpics]`, `[tmdb]`, `[overrides]`.
*   **Overrides**: Users can define per-file overrides for trim and FPS in `[overrides]`.

---

### 3.9 Technical Debt & Risks

1.  **VapourSynth Dependency**: This is the biggest risk. It requires a specific system installation (Python bindings + dynamic libraries). Installation is often difficult for users.
    *   *Mitigation*: The project includes a "Doctor" module (`src/frame_compare/doctor.py`) to diagnose environment issues.
2.  **Complexity**: The `WorkflowCoordinator` and state management are robust but complex. Adding new phases requires understanding the full context flow.
3.  **Platform Support**: macOS support is noted as "paused" due to VapourSynth/L-SMASH toolchain issues.

---

## 4. Rebuild Recommendations

If rebuilding or refactoring, consider:

1.  **Dependency Isolation**:
    *   Containerize the VapourSynth environment (Docker) if possible, though this makes "local file" access harder.
    *   Alternatively, bundle a portable VapourSynth build (like `vs-portable`) to remove system dependency.

2.  **Architecture**:
    *   The "Phased" pipeline is a **good pattern** and should be preserved. It allows for clear separation of concerns.
    *   Ensure the "Context" object doesn't become a "God Object". Currently, it holds everything; splitting it into `ConfigContext` vs `RuntimeContext` might help.

3.  **UI/UX**:
    *   The current CLI is rich. A Web UI (running locally) could simplify the complex configuration (tonemapping curves, alignment verification).

4.  **Performance**:
    *   Frame analysis is expensive. Ensure the caching mechanism (`generated.compframes`) is robust and versioned to prevent stale data corruption.

## 5. Critical Path for Rebuild/MVP

1.  **Core**: VapourSynth bindings and basic script generation.
2.  **Discovery**: Finding files and reading metadata (`ffprobe` wrapper).
3.  **Render**: Basic frame extraction (no alignment, no HDR).
4.  **Analysis**: Implementing the "Dark/Bright" frame finder.
5.  **Alignment**: Adding the Audio sync logic.
6.  **HDR**: Porting the `tonemap.py` logic (complex math/param handling).
7.  **Cloud**: Slow.pics uploader.
