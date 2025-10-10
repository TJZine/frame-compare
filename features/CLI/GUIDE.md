# Codex Task — *Selection metadata persistence v1*

## Scope

Presentation/data plumbing only. **Do not** change the selection algorithm or which frames are chosen. This task only **records** selection facts at selection time and **loads** them later so the overlay can display “Frame Selection Type: …” without re-running analysis.

---

## Goals

1. On every run that computes selections, **persist** selection metadata:

   * Primary, versioned JSON: `generated.selection.v1.json`.
   * Inline annotations in `generated.compframes` (non-breaking).
2. On later runs (including `overlay_mode="diagnostic"`), **load** the persisted metadata and **attach** selection info to the overlay for each frame **without triggering analysis**—*if* the cache is valid.
3. Implement **safe invalidation** via a deterministic cache key.

---

## Data model

### A) `generated.selection.v1.json` (authoritative; versioned)

**File-level structure:**

```json
{
  "version": "1",
  "created_utc": "2025-10-08T03:12:45Z",
  "cache_key": "sha256:…",                // see Cache Key section
  "inputs": {
    "clips": [
      {"role":"ref","path":"…","size":..., "mtime":"…","sha1":"…"},
      {"role":"tgt","path":"…","size":..., "mtime":"…","sha1":"…"}
    ],
    "config_fingerprint": {
      "step": 4,
      "downscale_height": 480,
      "motion_method": "edge",
      "scenecut_quantile": 0.90,
      "diff_radius": 3,
      "ignore_lead_seconds": 180.0,
      "ignore_trail_seconds": 360.0,
      "rng_seed": 2020220
    }
  },
  "selections": [
    {
      "frame_index": 14972,               // target/output frame index
      "ts_tc": "00:10:25.123",            // timecode (optional)
      "type": "Bright",                   // Enum: Dark|Bright|Motion|User|Random
      "score": 0.82,                      // optional; algorithm confidence
      "source": "analyze_v3.0",           // selection engine/version tag
      "clip_role": "tgt",                 // which clip produced the displayed frame
      "notes": ""                         // optional free-form note
    }
    // … one entry per output frame
  ]
}
```

* **Enum** for `type`: `["Dark","Bright","Motion","User","Random"]` (exact casing).
* All numeric lists use **integers** for frames; **strings** for timecodes to avoid FP drift.

### B) `generated.compframes` (non-breaking annotation)

* **Do not change** existing semantics. Append **inline hints** per frame using a tolerant format that existing readers ignore (e.g., trailing comment or `key=value` fields after a separator).
* Example line (illustrative; adapt to your current line format):

```
23928    00:16:38.250    …    # sel=Bright score=0.82 src=analyze_v3.0
```

* If comments aren’t allowed, append a final token block:

```
23928    00:16:38.250    …    sel=Bright;score=0.82;src=analyze_v3.0
```

* **Never** remove or reorder existing columns. If unsure, write a small **sidecar** `generated.compframes.meta.json` with `{frame_index: {...}}`; but per your request, still attempt to annotate `generated.compframes`.

---

## Cache key & invalidation

### Cache key inputs

Build a stable `cache_key` (e.g., SHA-256 of a canonical JSON blob) over:

* `inputs.clips[*].path`, `size`, `mtime` **and** `sha1` (if available).
* `config_fingerprint` fields that influence selection (step, downscale, motion params, ignore lead/trail, rng seed).
* Program version/selection engine id (e.g., `"analyze_v3.0"`).

### Load logic

* On startup, if `generated.selection.v1.json` exists:

  1. Recompute `cache_key_current` from current inputs/config.
  2. If it **matches** stored `cache_key`, **load** selections and make them available to the overlay.
  3. If it **differs**: treat selection cache as **stale**. Do **not** load; proceed as usual (select new frames) and **rewrite** both artifacts.

### Flags (optional)

* `--no-selection-cache`: ignore existing selection cache; recompute and rewrite.
* `--freeze-selection-cache`: **load** if key matches; if not, **fail fast** with a clear message (useful for reproducible runs).

---

## Write path (when selections are produced)

* Generate the `selections[]` array in the order frames will be rendered.
* **Atomic writes** on all OSes:

  * Write to `generated.selection.v1.json.tmp`, fsync, rename to `generated.selection.v1.json`.
  * Likewise for `generated.compframes` (if rewriting) or write a new annotated copy and swap.
* Preserve line endings; do not disturb unrelated content.

---

## Read path (overlay usage)

* When a screenshot is rendered for frame `F`, resolve selection info:

  1. First try **in-memory** map `{frame_index → selectionRecord}` from `generated.selection.v1.json`.
  2. If missing (e.g., older cache), optionally fall back to `generated.compframes` annotation parsing.
  3. If still missing, the overlay prints **`Frame Selection Type: (unknown)`** (do **not** trigger analysis).

---

## Error handling

* **Partial/malformed JSON** → ignore and log once; treat as missing cache; do not crash.
* **Mismatched counts** (e.g., selections fewer than compframes) → load what exists; warn once.
* **Out-of-range frame indices** → skip with a warning.

---

## Performance & memory

* Build an **index map** once: `Map<int frame_index, SelectionRecord>`.
* Use streaming/fast JSON parser if the file is large.
* Target <10ms extra startup for typical projects.

---

## Acceptance criteria

* After a fresh run that performs selection:

  * `generated.selection.v1.json` exists with the **exact** schema above, including `cache_key`.
  * `generated.compframes` contains **non-breaking** per-frame selection hints.
* On a subsequent run with **unchanged** inputs and params:

  * No analysis is triggered to obtain selection for overlay.
  * Overlay shows **`Frame Selection Type: <Enum>`** for every frame found in the cache.
* On a subsequent run with **changed** inputs/params (e.g., seed, downscale, ignore window):

  * Cache is detected as **stale**; fresh selection is produced and both artifacts are rewritten.
* Deleting `generated.selection.v1.json` (or using `--no-selection-cache`) falls back to normal behavior (overlay may show “(unknown)” until selection completes or is recomputed).

---

## Test plan

1. **Golden write**

   * Run selection on a small clip; assert the JSON schema, `cache_key` presence, and compframes annotation pattern.
2. **Load without analysis**

   * Re-run with identical inputs; instrument to ensure selection analysis is **not** executed; overlay reads from cache.
3. **Invalidation**

   * Change `rng_seed` or `downscale_height`; assert cache miss and rewrite.
4. **Missing/partial**

   * Corrupt the JSON tail; confirm robust fallback (no crash) and warning.
5. **Large set**

   * 1k+ frames: measure overhead <10ms to load & map; overlay hits O(1) lookups.
6. **Windows-safe atomicity**

   * Verify rename strategy works on Windows (write→flush→close→rename).

---

## Rollback

* Safe: delete `generated.selection.v1.json` and remove compframes annotations (or ignore them); the program reverts to live analysis behavior.

---

### Notes

* Keep field names **stable**; if you need to evolve the schema, bump `version` and preserve backward readers.
* If the exact format of `generated.compframes` is fragile, prefer sidecar `generated.compframes.meta.json` but still include a minimal `# sel=<Type>` comment to satisfy this task’s “write to both” requirement.
