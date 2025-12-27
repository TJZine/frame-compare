# Business Requirements

> **Module:** Requirements Specification  
> **Version:** 1.0

---

## 1. Business Context

### 1.1 Current State Analysis

Frame Compare is a Python CLI tool serving the video encoding and quality control community. It automates the tedious process of:

- Selecting representative frames from video sources
- Aligning multiple encodes via audio cross-correlation  
- Rendering comparison screenshots with HDR tonemapping
- Publishing to comparison hosting services

**Primary users:** Fansub/QC teams, boutique remaster teams, archivists, automation engineers.

### 1.2 Problem Statement

The current v0.0.14 implementation presents several business challenges:

1. **Adoption Friction**: VapourSynth installation complexity limits user onboarding
2. **Reliability Concerns**: Accumulated technical debt causes intermittent failures
3. **Maintenance Burden**: Monolithic code structure hinders feature development
4. **Platform Gaps**: macOS support paused, limiting market reach

### 1.3 Desired Future State

A rebuilt Frame Compare that:

- **Deploys instantly** via Docker without dependency management
- **Operates reliably** with comprehensive test coverage
- **Extends easily** through clean module boundaries
- **Serves universally** across Linux and Windows (macOS post-launch)

### 1.4 Business Value

| Value | Description |
|-------|-------------|
| **Time Savings** | Automated frame selection eliminates hours of manual work |
| **Quality Consistency** | Deterministic selection ensures reproducible comparisons |
| **Collaboration** | slow.pics integration enables team review workflows |
| **Professionalism** | HDR tonemapping produces publication-ready screenshots |

---

## 2. Business Requirements Matrix

| BR-ID | Requirement | Business Justification | Priority | Source |
|-------|-------------|------------------------|----------|--------|
| BR-001 | System must discover and analyze video files in a designated directory | Core functionality for batch processing | P0 | project_documentation.md |
| BR-002 | System must select representative frames using configurable algorithms | Ensures meaningful comparison points | P0 | analysis/ module |
| BR-003 | System must align audio across multiple encodes | Synchronizes frames for accurate comparison | P0 | alignment.py |
| BR-004 | System must render screenshots with proper color handling | Produces accurate visual output | P0 | screenshot/, render/ |
| BR-005 | System must support HDR to SDR tonemapping | Enables HDR content comparison on SDR displays | P0 | vs/tonemap.py |
| BR-006 | System must publish comparisons to slow.pics | Primary distribution channel for results | P0 | publishers.py |
| BR-007 | System must resolve media metadata from TMDB | Provides professional titles for comparisons | P1 | tmdb.py |
| BR-008 | System must generate offline HTML reports | Enables local review without internet | P1 | report.py |
| BR-009 | System must cache analysis results for reuse | Improves performance on repeated runs | P1 | cache.py |
| BR-010 | System must support preset configurations | Simplifies common workflow patterns | P1 | presets.py |
| BR-011 | System must handle Dolby Vision metadata | Supports premium HDR format | P1 | dovi_tool.py |
| BR-012 | System must integrate with VSPreview for manual alignment | Enables fine-tuned offset adjustment | P2 | vspreview.py |

---

## 3. Business Process Flows

### 3.1 Standard Comparison Workflow

```yaml
Process: Video Comparison Generation
ID: BP-001
Owner: End User
Trigger: User executes `frame-compare run` command

Preconditions:
  - Video files present in input directory
  - Configuration file exists or defaults apply
  - Network access for slow.pics (optional)

Steps:
  1:
    Actor: User
    Action: Places video files in comparison_videos directory
    System Response: N/A (file system operation)
  2:
    Actor: User
    Action: Executes `frame-compare run`
    System Response: Validates configuration and discovers video files
  3:
    Actor: System
    Action: Performs audio alignment analysis
    System Response: Calculates per-clip time offsets
  4:
    Actor: System
    Action: Selects representative frames
    System Response: Returns frame numbers based on luminance/motion/random criteria
  5:
    Actor: System
    Action: Renders screenshots with tonemapping
    System Response: Generates PNG files in screenshots directory
  6:
    Actor: System
    Action: Uploads to slow.pics (if enabled)
    System Response: Returns comparison URL
  7:
    Actor: System
    Action: Generates HTML report (if enabled)
    System Response: Creates offline viewer

Postconditions:
  - Screenshots generated in configured directory
  - slow.pics URL available (if upload enabled)
  - HTML report accessible (if report enabled)
  - Cache files updated for future runs

Exception Paths:
  - Condition: No video files found
    Handling: Exit with descriptive error message
  - Condition: VapourSynth not available
    Handling: Fall back to FFmpeg renderer
  - Condition: slow.pics upload fails
    Handling: Retry with backoff, warn on final failure
  - Condition: Audio alignment fails
    Handling: Proceed without alignment, warn user

Business Rules Applied:
  - BR-001, BR-002, BR-003, BR-004, BR-005, BR-006
```

### 3.2 Configuration Wizard Workflow

```yaml
Process: Guided Setup
ID: BP-002
Owner: New User
Trigger: User runs `frame-compare wizard` or first run without config

Preconditions:
  - No existing config.toml (for auto-trigger)
  - Interactive terminal available

Steps:
  1:
    Actor: System
    Action: Detects missing configuration
    System Response: Prompts to run wizard
  2:
    Actor: User
    Action: Accepts wizard prompt
    System Response: Begins interactive configuration
  3:
    Actor: System
    Action: Prompts for input directory
    System Response: Validates path exists
  4:
    Actor: System
    Action: Prompts for slow.pics preferences
    System Response: Configures upload settings
  5:
    Actor: System
    Action: Prompts for TMDB API key (optional)
    System Response: Stores API key securely
  6:
    Actor: System
    Action: Writes config.toml
    System Response: Confirms configuration saved

Postconditions:
  - Valid config.toml created
  - User can proceed with comparison workflow

Exception Paths:
  - Condition: Invalid directory provided
    Handling: Re-prompt with error message
  - Condition: User cancels wizard
    Handling: Exit without config, seed template

Business Rules Applied:
  - BR-009 (configuration persistence)
```

### 3.3 Doctor/Diagnostics Workflow

```yaml
Process: Dependency Verification
ID: BP-003
Owner: User/Support
Trigger: User runs `frame-compare doctor`

Preconditions:
  - None (diagnostic tool)

Steps:
  1:
    Actor: User
    Action: Executes `frame-compare doctor`
    System Response: Initiates dependency checks
  2:
    Actor: System
    Action: Checks VapourSynth availability
    System Response: Reports version or missing status
  3:
    Actor: System
    Action: Checks FFmpeg/FFprobe
    System Response: Reports version or missing status
  4:
    Actor: System
    Action: Checks optional dependencies (VSPreview, pyperclip)
    System Response: Reports availability
  5:
    Actor: System
    Action: Validates configuration paths
    System Response: Reports path accessibility
  6:
    Actor: System
    Action: Summarizes system status
    System Response: Displays pass/fail summary

Postconditions:
  - User understands system readiness
  - Actionable guidance provided for missing dependencies

Business Rules Applied:
  - System reliability requirements
```

---

## 4. Business Rules Catalog

### 4.1 Frame Selection Rules

| Rule ID | Rule Description | Enforcement |
|---------|------------------|-------------|
| BSR-001 | Minimum 3 frames must be selected per comparison | Validation |
| BSR-002 | Frame selection must be deterministic given same seed | Algorithm |
| BSR-003 | Luminance quantile selection must include darkest and brightest frames | Algorithm |
| BSR-004 | Motion scoring must identify high-action scenes | Algorithm |

### 4.2 Audio Alignment Rules

| Rule ID | Rule Description | Enforcement |
|---------|------------------|-------------|
| BAR-001 | Reference track defaults to first video file | Configuration |
| BAR-002 | Alignment offsets must be persisted for reuse | Cache |
| BAR-003 | Manual VSPreview adjustments override calculated offsets | Priority |

### 4.3 Publishing Rules

| Rule ID | Rule Description | Enforcement |
|---------|------------------|-------------|
| BPR-001 | slow.pics uploads require valid comparison images | Validation |
| BPR-002 | Upload failures must retry with exponential backoff | Network layer |
| BPR-003 | Shortcut creation is best-effort (non-blocking) | Error handling |

### 4.4 Configuration Rules

| Rule ID | Rule Description | Enforcement |
|---------|------------------|-------------|
| BCR-001 | CLI flags override config file values | Precedence |
| BCR-002 | Environment variables override config file values | Precedence |
| BCR-003 | Config file changes require no code changes | Design |

---

## 5. User Stories Summary

| Story ID | As a... | I want to... | So that... | Priority |
|----------|---------|--------------|------------|----------|
| US-001 | Encoder | Select frames automatically | I save hours of manual work | P0 |
| US-002 | QC Reviewer | See synchronized comparisons | I can accurately assess quality | P0 |
| US-003 | Fansub Team Lead | Share comparisons via slow.pics | Team members can review remotely | P0 |
| US-004 | Archivist | Reproduce comparisons later | I maintain consistent documentation | P1 |
| US-005 | Automation Engineer | Script comparison generation | I integrate with CI/CD pipelines | P1 |
| US-006 | HDR Enthusiast | See accurate tonemapped output | I evaluate HDR encode quality | P0 |
| US-007 | New User | Configure easily via wizard | I start quickly without documentation | P1 |
| US-008 | Power User | Save preset configurations | I apply consistent settings across projects | P2 |
