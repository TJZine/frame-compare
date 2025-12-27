# Functional Requirements Specification

> **Module:** Requirements Specification  
> **Version:** 1.0

---

## 1. Module: Frame Analysis (`analysis/`)

### FR-ANAL-001: Frame Discovery

```yaml
Title: Discover video files in input directory
Description: |
  System scans configured input directory for supported video formats and builds
  a processing queue with metadata extraction.
Actor: System (triggered by CLI)
Preconditions:
  - Input directory path configured and accessible
  - At least one supported video file present
Input:
  - Field: input_dir
    Type: Path
    Constraints: Must exist, must be readable
    Required: yes
  - Field: file_patterns
    Type: list[str]
    Constraints: Valid glob patterns
    Required: no (defaults to *.mkv, *.mp4, etc.)
Processing:
  1. Resolve input directory from config/CLI/env
  2. Scan directory for matching files
  3. Sort files naturally (natsort)
  4. Extract basic metadata (duration, resolution, codec)
  5. Build ClipPlan objects for each file
Output:
  - List of ClipPlan objects with file references
Postconditions:
  - All discoverable videos queued for processing
Business Rules:
  - BR-001
Priority: P0
Complexity: Medium
Dependencies: []
Acceptance Criteria:
  - GIVEN a directory with video files WHEN discovery runs THEN all matching files are found
  - GIVEN an empty directory WHEN discovery runs THEN appropriate error is raised
  - GIVEN mixed file types WHEN discovery runs THEN only video files are selected
```

### FR-ANAL-002: Frame Metrics Calculation

```yaml
Title: Calculate luminance and motion metrics for all frames
Description: |
  For each video, compute per-frame luminance and motion scores to enable
  intelligent frame selection.
Actor: System
Preconditions:
  - Video file accessible via VapourSynth or FFmpeg
  - Configuration specifies analysis parameters
Input:
  - Field: clip
    Type: VapourSynth clip or file path
    Required: yes
  - Field: sample_rate
    Type: int
    Constraints: 1-100 (frames per second to analyze)
    Required: no (default from config)
Processing:
  1. Open video with VapourSynth (preferred) or FFmpeg
  2. Sample frames at configured rate
  3. Calculate luminance (Y channel mean)
  4. Calculate motion score (frame difference)
  5. Cache results with hash-based key
Output:
  - FrameMetrics dataclass with arrays
Postconditions:
  - Metrics cached for reuse
Business Rules:
  - BSR-002 (deterministic given same input)
Priority: P0
Complexity: High
Dependencies: [FR-ANAL-001]
Acceptance Criteria:
  - GIVEN a video WHEN metrics run THEN luminance and motion arrays populated
  - GIVEN cached metrics WHEN same video analyzed THEN cache is reused
  - GIVEN different config WHEN analysis runs THEN cache is invalidated
```

### FR-ANAL-003: Frame Selection

```yaml
Title: Select representative frames based on metrics
Description: |
  Apply selection algorithms (quantile, motion, random) to choose frames
  for comparison screenshots.
Actor: System
Preconditions:
  - Frame metrics calculated for all clips
  - Selection configuration valid
Input:
  - Field: metrics
    Type: FrameMetrics
    Required: yes
  - Field: frame_count
    Type: int
    Constraints: 3-100
    Required: yes
  - Field: random_seed
    Type: int
    Required: no (default 42)
  - Field: selection_mode
    Type: enum (quantile, motion, random, mixed)
    Required: no (default mixed)
Processing:
  1. Calculate selection windows based on mode
  2. Apply quantile selection for darkest/brightest
  3. Apply motion scoring for high-action frames
  4. Apply seeded random for variety
  5. Deduplicate and sort frame numbers
Output:
  - List of frame numbers to capture
Postconditions:
  - Frame selection deterministic for same seed
Business Rules:
  - BSR-001 (minimum 3 frames)
  - BSR-002 (deterministic)
  - BSR-003, BSR-004
Priority: P0
Complexity: High
Dependencies: [FR-ANAL-002]
Acceptance Criteria:
  - GIVEN same seed WHEN selection runs twice THEN identical frames selected
  - GIVEN quantile mode WHEN 10 frames requested THEN darkest and brightest included
  - GIVEN <3 frames requested WHEN validation runs THEN error raised
```

---

## 2. Module: Audio Alignment (`alignment/`)

### FR-ALIGN-001: Audio Extraction

```yaml
Title: Extract audio streams from video files
Description: |
  Extract audio tracks from each video for cross-correlation analysis.
Actor: System
Preconditions:
  - Video files have audio tracks
  - FFmpeg available
Input:
  - Field: video_path
    Type: Path
    Required: yes
  - Field: audio_track
    Type: int
    Constraints: ≥0
    Required: no (default 0)
  - Field: sample_rate
    Type: int
    Constraints: 8000-48000
    Required: no (default from config)
Processing:
  1. Probe video for audio streams
  2. Select specified track (or first)
  3. Extract to temporary WAV
  4. Resample to target rate
Output:
  - Path to extracted audio file
Postconditions:
  - Temporary audio file created
Business Rules:
  - BAR-001
Priority: P0
Complexity: Medium
Dependencies: [FR-ANAL-001]
Acceptance Criteria:
  - GIVEN video with audio WHEN extraction runs THEN WAV file created
  - GIVEN video without audio WHEN extraction runs THEN graceful error
```

### FR-ALIGN-002: Cross-Correlation Analysis

```yaml
Title: Calculate time offset between audio tracks
Description: |
  Use cross-correlation to determine temporal offset between reference
  and comparison audio tracks.
Actor: System
Preconditions:
  - Audio extracted from all clips
Input:
  - Field: reference_audio
    Type: numpy.ndarray
    Required: yes
  - Field: comparison_audio
    Type: numpy.ndarray
    Required: yes
Processing:
  1. Normalize audio amplitudes
  2. Compute cross-correlation via FFT
  3. Find correlation peak
  4. Convert sample offset to time
  5. Apply dynamic time warping if needed
Output:
  - Offset in seconds (positive = comparison ahead)
  - Correlation confidence score
Postconditions:
  - Offset cached in generated/audio_offsets.toml
Business Rules:
  - BAR-002
Priority: P0
Complexity: High
Dependencies: [FR-ALIGN-001]
Acceptance Criteria:
  - GIVEN identical audio WHEN correlation runs THEN offset is 0
  - GIVEN shifted audio WHEN correlation runs THEN offset matches shift
  - GIVEN unrelated audio WHEN correlation runs THEN low confidence reported
```

---

## 3. Module: Screenshot Rendering (`screenshot/`, `render/`)

### FR-SCREEN-001: Frame Extraction

```yaml
Title: Extract specific frames from video
Description: |
  Render individual frames as images using VapourSynth or FFmpeg.
Actor: System
Preconditions:
  - Frame numbers determined by selection
  - Alignment offsets applied
Input:
  - Field: clip
    Type: VapourSynth clip
    Required: yes
  - Field: frame_numbers
    Type: list[int]
    Required: yes
  - Field: output_dir
    Type: Path
    Required: yes
Processing:
  1. Apply trim/offset to clip
  2. For each frame number:
     a. Seek to frame
     b. Apply color processing
     c. Render to PNG
     d. Apply overlay (if enabled)
  3. Save with consistent naming
Output:
  - List of PNG file paths
Postconditions:
  - Screenshots created in output directory
Priority: P0
Complexity: Medium
Dependencies: [FR-ANAL-003, FR-ALIGN-002]
Acceptance Criteria:
  - GIVEN frame numbers WHEN extraction runs THEN PNG files created
  - GIVEN VapourSynth unavailable WHEN extraction runs THEN FFmpeg fallback used
```

### FR-SCREEN-002: HDR Tonemapping

```yaml
Title: Convert HDR content to SDR
Description: |
  Apply libplacebo tonemapping to HDR sources for SDR display.
Actor: System
Preconditions:
  - Source clip is HDR (detected or configured)
  - libplacebo plugin available
Input:
  - Field: clip
    Type: VapourSynth clip (HDR)
    Required: yes
  - Field: preset
    Type: enum (reference, filmic, contrast, bt2390_spec, spline, bright_lift, highlight_guard)
    Required: no (default from config)
  - Field: target_nits
    Type: int
    Constraints: 100-400
    Required: no (default 203)
Processing:
  1. Detect HDR metadata (mastering display, MaxCLL, MaxFALL)
  2. Select tonemap curve based on preset
  3. Apply libplacebo tonemapping
  4. Apply post-gamma adjustments if configured
  5. Convert to 8-bit RGB
Output:
  - SDR VapourSynth clip
Postconditions:
  - HDR content viewable on SDR displays
Business Rules:
  - BR-005
Priority: P0
Complexity: High
Dependencies: []
Acceptance Criteria:
  - GIVEN HDR clip WHEN tonemapping runs THEN SDR output produced
  - GIVEN SDR clip WHEN tonemapping runs THEN clip passes through unchanged
  - GIVEN different presets WHEN applied THEN visually distinct outputs
```

### FR-SCREEN-003: Overlay Rendering

```yaml
Title: Add informational overlay to screenshots
Description: |
  Render text overlay with file info, frame number, and diagnostics.
Actor: System
Preconditions:
  - Screenshot rendered
  - Overlay mode configured
Input:
  - Field: image
    Type: PIL Image or numpy array
    Required: yes
  - Field: metadata
    Type: dict (filename, frame_num, resolution, etc.)
    Required: yes
  - Field: overlay_mode
    Type: enum (minimal, standard, diagnostic)
    Required: no (default standard)
Processing:
  1. Calculate overlay position
  2. Render text with configured font
  3. Apply semi-transparent background
  4. Composite onto image
Output:
  - Image with overlay
Priority: P1
Complexity: Low
Dependencies: [FR-SCREEN-001]
Acceptance Criteria:
  - GIVEN minimal mode WHEN overlay applied THEN only filename shown
  - GIVEN diagnostic mode WHEN overlay applied THEN HDR metadata included
```

---

## 4. Module: Publishing (`services/publishers.py`)

### FR-PUB-001: slow.pics Upload

```yaml
Title: Upload comparison images to slow.pics
Description: |
  Publish rendered screenshots to slow.pics for sharing.
Actor: System
Preconditions:
  - Screenshots generated
  - Network available
Input:
  - Field: screenshots
    Type: list[Path]
    Required: yes
  - Field: title
    Type: str
    Required: yes
  - Field: visibility
    Type: enum (public, unlisted, private)
    Required: no (default unlisted)
Processing:
  1. Build multipart upload payload
  2. Create comparison on slow.pics
  3. Upload images with progress tracking
  4. Retry on failure with exponential backoff
  5. Create local .url shortcut
Output:
  - slow.pics comparison URL
  - Shortcut file path
Postconditions:
  - Comparison accessible via returned URL
Business Rules:
  - BPR-001, BPR-002, BPR-003
Priority: P0
Complexity: Medium
Dependencies: [FR-SCREEN-001]
Acceptance Criteria:
  - GIVEN valid screenshots WHEN upload succeeds THEN URL returned
  - GIVEN network failure WHEN upload retries THEN exponential backoff applied
  - GIVEN shortcut write failure WHEN upload succeeds THEN URL still returned
```

---

## 5. Module: CLI Interface (`cli_entry.py`)

### FR-CLI-001: Run Command

```yaml
Title: Execute full comparison pipeline
Description: |
  Main entry point that orchestrates the complete workflow.
Actor: User
Command: frame-compare run
Options:
  --root PATH: Override workspace root
  --config PATH: Specify config file
  --input PATH: Override input directory
  --no-cache: Force recomputation
  --from-cache-only: Render from cache
  --quiet/--verbose: Output control
Processing:
  1. Load configuration (file → env → CLI)
  2. Resolve workspace paths
  3. Discover video files
  4. Apply audio alignment
  5. Select frames
  6. Render screenshots
  7. Publish results
  8. Generate reports
Output:
  - Exit code 0 on success
  - Screenshots, URLs, reports as side effects
Priority: P0
Complexity: High
Dependencies: [All other modules]
```

### FR-CLI-002: Wizard Command

```yaml
Title: Interactive configuration setup
Description: |
  Guided setup for new users.
Actor: User
Command: frame-compare wizard
Processing:
  1. Prompt for input directory
  2. Prompt for slow.pics settings
  3. Prompt for TMDB API key
  4. Validate inputs
  5. Write config.toml
Output:
  - Valid config.toml file
Priority: P1
```

### FR-CLI-003: Doctor Command

```yaml
Title: Dependency diagnostics
Description: |
  Verify system readiness.
Actor: User
Command: frame-compare doctor
Processing:
  1. Check VapourSynth
  2. Check FFmpeg/FFprobe
  3. Check optional dependencies
  4. Report status with actionable guidance
Output:
  - Diagnostic report with pass/fail/warn
Priority: P1
```

---

## 6. Module: Configuration (`config_loader.py`)

### FR-CFG-001: Configuration Loading

```yaml
Title: Load and merge configuration sources
Description: |
  Load configuration from TOML file, environment variables, and CLI arguments
  with proper precedence.
Precedence: CLI > Environment > Config File > Defaults
Input:
  - config.toml file
  - FRAME_COMPARE_* environment variables
  - CLI arguments
Output:
  - Merged RuntimeConfig dataclass
Validation:
  - Type coercion with validation
  - Path existence checks
  - Enum value validation
Priority: P0
Acceptance Criteria:
  - GIVEN CLI --root flag WHEN config loaded THEN CLI value wins
  - GIVEN invalid enum WHEN loading THEN validation error raised
  - GIVEN missing optional WHEN loading THEN default applied
```

---

## 7. Feature Priority Summary

| Priority | Features | Count |
|----------|----------|-------|
| P0 | Frame Analysis, Audio Alignment, Screenshot Rendering, HDR Tonemapping, slow.pics Publishing, CLI Run, Config Loading | 7 |
| P1 | TMDB Integration, HTML Report, Dolby Vision, Preset System, Doctor/Wizard | 5 |
| P2 | VSPreview Integration, Clipboard | 2 |
