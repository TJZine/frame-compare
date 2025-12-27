# Error Code Reference

> **Module:** Reference  
> **Version:** 1.0

> [!NOTE]
> This file is AUTO-GENERATED from `docs/OPUS_REBUILD_FRAME_COMPARE/contracts/error_codes.yaml`.
> Do not edit manually. Regenerate with: `python scripts/generate_contract_views.py`

---

## 1. Error Code Hierarchy

```text
FC-xxxx
│
├── FC-1xxx: Configuration Errors (Exit Code 2)
├── FC-2xxx: Dependency Errors (Exit Code 3)
├── FC-3xxx: Input Errors (Exit Code 4)
├── FC-4xxx: Processing Errors (Exit Code 5)
├── FC-5xxx: Network Errors (Exit Code 6)
└── FC-9xxx: Internal Errors (Exit Code 1)
```

---

## 2. Configuration Errors (FC-1xxx)

| Code | Name | Message | Hint |
|------|------|---------|------|
| FC-1001 | CONFIG_NOT_FOUND | Configuration file not found: {path} | Run 'frame-compare wizard' or create config/config.toml |
| FC-1002 | CONFIG_PARSE_ERROR | Failed to parse {path}: {details} | Check TOML syntax at the indicated line |
| FC-1003 | CONFIG_VALIDATION_ERROR | Invalid configuration: {fields} | Check field types and constraints |
| FC-1004 | PRESET_NOT_FOUND | Preset not found: {name} | Run 'frame-compare preset list' to see available |
| FC-1005 | PRESET_INVALID | Invalid preset file: {path} | Preset TOML syntax error |
| FC-1006 | CONFIG_MIGRATION_ERROR | Config migration failed: {details} | Check v1 config format or manually convert to v2 structure |

---

## 3. Dependency Errors (FC-2xxx)

| Code | Name | Message | Hint |
|------|------|---------|------|
| FC-2001 | VAPOURSYNTH_NOT_FOUND | VapourSynth not installed | Use Docker deployment or install VapourSynth R72+ |
| FC-2002 | VAPOURSYNTH_ERROR | VapourSynth error: {details} | Run 'frame-compare doctor' for diagnostics |
| FC-2003 | PLUGIN_NOT_FOUND | VapourSynth plugin not found: {plugin} | Install {plugin} or use Docker deployment |
| FC-2004 | LIBPLACEBO_ERROR | libplacebo error: {details} | Verify libplacebo installation or use FFmpeg fallback |
| FC-2005 | FFMPEG_NOT_FOUND | FFmpeg not found in PATH | Install FFmpeg 6.0+ |
| FC-2006 | FFMPEG_ERROR | FFmpeg error: {details} | Check FFmpeg output for details |
| FC-2007 | DOVI_TOOL_NOT_FOUND | dovi_tool not found | Install dovi_tool for Dolby Vision support |
| FC-2010 | PYTHON_VERSION_ERROR | Python version {version} not supported | Use Python 3.13+ |

---

## 4. Input Errors (FC-3xxx)

| Code | Name | Message | Hint |
|------|------|---------|------|
| FC-3001 | NO_VIDEOS_FOUND | No video files found in {path} | Place *.mkv,*.mp4 files in the input directory |
| FC-3002 | VIDEO_OPEN_ERROR | Failed to open video: {path} | Check file path and format |
| FC-3003 | VIDEO_CORRUPT | Video file appears corrupt: {path} | Try re-encoding or different source |
| FC-3004 | INSUFFICIENT_FRAMES | Video has {count} frames, need at least {required} | Use a longer video or reduce frame_count |
| FC-3005 | INCOMPATIBLE_VIDEOS | Videos have incompatible properties | All videos must have same frame count and fps |
| FC-3006 | DIR_NOT_FOUND | Directory not found: {path} | Create the directory or check the path |
| FC-3007 | DIR_NOT_WRITABLE | Cannot write to directory: {path} | Check permissions |
| FC-3008 | FILE_TOO_LARGE | File exceeds size limit: {path} | Use smaller video or increase limit |
| FC-3009 | PATH_ESCAPES_ROOT | Path '{candidate}' escapes workspace root | Use relative paths within workspace |
| FC-3010 | INVALID_SUBPROCESS_ARG | Invalid character in argument: {arg} | Remove shell metacharacters from the argument |
| FC-3011 | CONTROL_CHAR_IN_ARG | Control character in argument: {arg} | Remove control characters from the argument |
| FC-3012 | INVALID_PATH | Invalid path: {path} | Remove invalid characters (null bytes, control chars) from path |

---

## 5. Processing Errors (FC-4xxx)

| Code | Name | Message | Hint |
|------|------|---------|------|
| FC-4001 | FRAME_EXTRACTION_ERROR | Failed to extract frame {frame} from {clip} | Check video integrity |
| FC-4002 | METRICS_CALCULATION_ERROR | Failed to calculate metrics: {details} | Check VapourSynth logs |
| FC-4003 | TONEMAP_ERROR | Tonemapping failed: {details} | Try different preset or disable tonemapping |
| FC-4004 | RENDER_ERROR | Screenshot rendering failed | Check disk space and permissions |
| FC-4005 | AUDIO_ALIGNMENT_ERROR | Audio alignment failed: {details} | Try manual alignment or disable audio alignment |
| FC-4006 | CACHE_CORRUPTION_ERROR | Cache file corrupt: {path} | Delete cache file and retry |
| FC-4007 | CACHE_VERSION_MISMATCH | Cache version mismatch | Clear cache with --no-cache |
| FC-4010 | MEMORY_ERROR | Out of memory during processing | Reduce frame count or video resolution |
| FC-4011 | TIMEOUT_ERROR | Processing timed out | Check for infinite loops or increase timeout |
| FC-4012 | SELECTION_ERROR | Frame selection failed: {reason} | Reduce frame count or use different selection mode |
| FC-4013 | ENCODING_ERROR | Failed to encode image: {path} | Check disk space and file permissions |
| FC-4014 | OVERLAY_ERROR | Failed to apply overlay: {details} | Check font path and image format |
| FC-4015 | SOURCE_LOAD_ERROR | Failed to load video source: {path} | Check file format and VapourSynth plugins |
| FC-4016 | METADATA_ERROR | Metadata operation failed: {details} | Check file format or try --skip-metadata |
| FC-4017 | REPORT_ERROR | Report generation failed: {details} | Check disk space and permissions |
| FC-4018 | DOVI_ERROR | Dolby Vision extraction failed: {details} | Check dovi_tool installation or use --skip-dovi |

---

## 6. Network Errors (FC-5xxx)

| Code | Name | Message | Hint |
|------|------|---------|------|
| FC-5001 | NETWORK_UNREACHABLE | Network unreachable | Check internet connection |
| FC-5002 | SLOWPICS_ERROR | slow.pics upload failed: {details} | Try again or use --no-upload |
| FC-5003 | SLOWPICS_RATE_LIMITED | slow.pics rate limited | Wait and retry |
| FC-5004 | SLOWPICS_UNAVAILABLE | slow.pics service unavailable | Try again later |
| FC-5005 | TMDB_ERROR | TMDB API error: {details} | Check API key or use --skip-metadata |
| FC-5006 | TMDB_RATE_LIMITED | TMDB rate limited | Wait and retry |
| FC-5007 | NETWORK_TIMEOUT | Request timed out | Check connection or increase timeout |
| FC-5008 | SSL_ERROR | SSL certificate error | Check system time and certificates |
| FC-5010 | HTTPS_REQUIRED | HTTPS required for external requests | External URLs must use https:// scheme |
| FC-5011 | HOST_NOT_ALLOWED | Request blocked to unauthorized host: {host} | Only slow.pics and api.themoviedb.org are allowed |

---

## 7. Internal Errors (FC-9xxx)

| Code | Name | Message | Hint |
|------|------|---------|------|
| FC-9001 | INTERNAL_ERROR | Internal error: {details} | Please report this bug |
| FC-9002 | ASSERTION_FAILED | Assertion failed: {details} | Please report this bug |
| FC-9003 | UNEXPECTED_STATE | Unexpected state: {details} | Please report this bug |

---

## 8. Exit Codes

| Exit Code | Meaning | Error Categories |
|-----------|---------|------------------|
| 0 | Success | - |
| 1 | General/Internal Error | FC-9xxx |
| 2 | Configuration Error | FC-1xxx |
| 3 | Dependency Error | FC-2xxx |
| 4 | Input Error | FC-3xxx |
| 5 | Processing Error | FC-4xxx |
| 6 | Network Error | FC-5xxx |
| 130 | Interrupted (Ctrl+C) | - |
