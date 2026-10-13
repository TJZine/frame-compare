---
description: Definitions of the terms used in this documentation.
---

# Glossary

These are the terms this documentation uses, with their exact meaning.

source
:   One input video that takes part in a comparison.

reference
:   The source whose frame numbers define the comparison. It appears first.

comparison
:   Any source other than the reference. The report names them Comparison 1,
    Comparison 2, and so on.

input directory
:   The folder Frame Compare searches for sources, set by `paths.input_dir` or
    `run --input`.

generated-data root
:   The folder that holds run folders and shared caches, set by `paths.generated_dir`.

run folder
:   The folder Frame Compare creates for one run inside the generated-data root.

report
:   The file `report.html` that a run writes. The report viewer is its interactive
    interface.

offset
:   The signed difference between a reference frame number and the matching comparison
    frame number.

trim
:   Frames excluded from the start or end of a source.

active picture
:   The image area without letterbox or pillarbox bars. Set it explicitly with
    `active_rect`.

alignment
:   Finding and applying offsets between sources.

applied, not applied
:   Whether an offset changes the trims. The terminal prints `APPLIED` or
    `NOT APPLIED`.

audio candidate
:   An offset found from the audio that has not been confirmed yet.

VSView alignment panel
:   The **Frame Compare Alignment Review** panel inside VSView, where you confirm or
    enter alignment by eye.

user frames
:   Frames you list in `analysis.user_frames` or `run --frames`.

frame selection
:   Choosing which frames to render.

tonemapping
:   Converting HDR video to an SDR presentation.

dry run
:   What `frame-compare run --dry-run` prints: the sources, the frames you asked for,
    and what a run would create, without opening the videos.

workspace root
:   The folder set by `--root`, which defaults to the current folder.

Windows portable bundle
:   The complete Windows distribution of Frame Compare. Its download is the complete
    portable ZIP.

Single view
:   The report view that shows one source at a time. Its configuration value is
    `overlay` (`report.default_mode`).

baked overlay
:   Text rendered into the screenshot pixels, set by `screenshots.overlay_mode`.

source labels
:   The source names the report viewer shows on the image, toggled by
    **Source labels**.

slow.pics
:   The image-comparison website Frame Compare can publish to. Its settings are in the
    `[slowpics]` table.
