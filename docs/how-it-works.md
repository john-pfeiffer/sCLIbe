# How it works

The pipeline internals, the `steps.json` format, and the cost math. Read this if you're modifying the code or curious what happens under the hood.

## Pipeline overview

```
                 ┌──────────────────────────────────────────────────────────┐
your-recording ─▶│ 1 probe   ffprobe metadata            → meta.json        │ free
                 │ 2 frames  scene detection + extraction → work/frames/*   │ free
                 │ 3 analyze Claude vision → steps        → steps.json      │ PAID
                 │ 4 doc     screenshots + guide          → guide.md/.html  │ free
                 │ 5 video   cut dead time into segments  → work/segments/* │ free
                 │ 6 narrate TTS + mux + concat + chapters→ final-video.mp4 │ free
                 └──────────────────────────────────────────────────────────┘
```

Each stage lives in its own module under `src/sclibe/` and writes a checkpoint artifact. `cli.py` orchestrates; `cache.py` decides reuse: a stage is skipped only when its outputs exist, the settings it was built with (recorded in `work/stagestate.json`) still match, and no input file is newer than the outputs. So editing `steps.json` or changing the voice/style triggers exactly the right rebuilds on a plain rerun. The paid `analyze` stage is special — when its inputs drift it explains what changed and asks before spending money. `--force` and `--from STAGE` override everything.

## Stage details

### 1. probe (`ingest.py`)

One `ffprobe` call. Records duration, resolution, and fps to `meta.json`. Duration drives everything downstream (clamping, backfill, prompts).

### 2. frames (`frames.py`)

The goal: **20–60 frames that capture every meaningful moment** of a recording, not thousands.

1. **PySceneDetect** `ContentDetector` scans the video with a low threshold (default 10 vs. the library's default 27) — screen recordings have subtle transitions (a dropdown opens, a modal appears), not hard cuts.
2. Each detected change becomes a candidate at **change + `settle_delay`** (default 0.7s) — sampling after the UI has settled avoids mid-animation frames that confuse the model.
3. Candidates closer than `min_gap` (default 2s) are merged (later one wins).
4. **Backfill:** any gap longer than 30s gets interval samples every 20s (catches slow scrolling/typing the detector missed). If detection found almost nothing on a long video, it falls back to sampling every 15s.
5. The first and last moments are always kept. If over `--max-frames`, the lowest-scoring candidates are dropped.
6. Each frame is extracted as a JPEG at **max 1568px long edge** — that's the token sweet spot (~1,100–1,600 tokens/image vs ~4,784 at full resolution) with no meaningful loss in the model's ability to read UI text.

The manifest (`work/frames.json`) records each frame's timestamp and detection score.

### 3. analyze (`analyze.py`) — the paid stage

One request to the configured vision model — Anthropic (`claude-*`), OpenAI (`gpt-*`), or xAI (`grok-*`), inferred from the model name; the request shape below is per provider but the pipeline is identical:

- **Content**: an optional author-supplied context block (`--context`), then the frames as base64 images, each preceded by a `Frame at t=41.2s:` label, followed by the task instructions.
- **Structured output**: every provider is called with a schema-enforced parse (`messages.parse` on Anthropic, `chat.completions.parse` on OpenAI/xAI) against the Pydantic `StepList`, so the response is *guaranteed* valid JSON matching the schema — there is no fragile text parsing.
- **The prompt asks for**: one step per meaningful user action (5–15 for a typical recording); non-overlapping time ranges that exclude idle time (that's what defines "dead time" for the video cut); a `key_frame_time` matching one of the provided frames; and a narration script sized to ~2.5 words/second of the step's duration so it roughly fits the segment.

The raw model output then goes through deterministic cleanup in `sanitize()`: clamp times to the video, sort steps, split overlapping ranges at their midpoint, snap `key_frame_time` to the nearest real frame, renumber.

The result is written to `steps.json` along with `_meta` (model used, and a hash of the frame manifest — if you later regenerate frames with different settings, the tool detects the mismatch and warns instead of silently using stale analysis).

Actual token usage and cost are printed after every call.

### 4. doc (`doc.py`)

For each step, re-extracts `key_frame_time` from the original video at **full resolution** (the downsampled API frames are never reused for the guide). Writes `guide.md` (plain markdown, plays well with GitHub/Notion/Obsidian) and `guide.html` (same content through the `markdown` package, wrapped in a self-contained template with inline CSS — no external assets, works from a double-click or an intranet share).

### 5. video (`video.py`)

- Each step's `[start_time, end_time]` gets ±0.25s of breathing room, clamped so ranges never overlap.
- Each range is cut with an accurate seek and **re-encoded** (`libx264`, capped at 1080p) rather than stream-copied — stream copy can only cut on keyframes, which produces sloppy cut points and concat glitches. Screen content encodes fast.
- Everything outside the step ranges — idle screens, waiting, wandering — is simply never cut into a segment. That's the dead-time removal.
- Unless `--no-banners`: a lower-third label ("Step N — Title") in the accent color is burned into the first 4 seconds of each segment via ffmpeg's `drawtext` (text goes through a `textfile` to avoid escaping issues; fonts resolve by name through fontconfig).

### 6. narrate (`narrate.py`)

Unless `--no-title-card`: an intro card is generated with the `process_summary` read over it as narration. The intro audio is synthesized first and the card is rendered exactly long enough for it (minimum 3.5s), so the card never needs stretching. The card has three looks — text on the accent background (default), a user-supplied image letterboxed onto the accent color with the text overlaid, or the image alone (`title_card_image` / `title_card_text` in `style.py`'s `title_card_mode`) — and `title_text`/`subtitle_text` replace the AI title and step count when set. All variants match the segments' resolution/fps so concat stays lossless.

Per step:

1. TTS via the configured provider (`tts.py`): `edge` (free Microsoft neural voices, default, auto-falls back to `say` offline), `say` (offline macOS), `openai` (premium), or `elevenlabs` (best-in-class, voice IDs from your VoiceLab).
2. **Fit policy — narration is never cut off, and stays in sync:**
   - audio shorter than the segment → pad the audio with trailing silence
   - audio longer than the segment → **slow the video down** (up to `max_slowdown`, default 2×, via `setpts`) so the on-screen action stays under the words describing it; only freeze the last frame for anything beyond that. At `max_slowdown: 1.0` the video is never slowed — it holds the last frame instead.
3. Mux audio onto the segment (AAC 48kHz stereo).

Then all narrated segments (title card first, when enabled) are concatenated (concat demuxer, stream copy — all segments share identical encoding parameters), and chapter metadata is attached via an ffmetadata file (`[CHAPTER]` blocks with millisecond offsets) — an "Intro" chapter for the card, then one per step. QuickTime, VLC, and YouTube all read these chapters.

## `steps.json` reference

```jsonc
{
  "_meta": {
    "model": "claude-opus-5",     // model that produced this analysis
    "frames_hash": "a1b2c3d4e5f6", // hash of the frame manifest (staleness check)
    "video": "my-recording.mov",
    "duration": 612.5,
    "context": "..."               // the --context text this analysis was given (null if none)
  },
  "process_title": "Create a Customer Invoice",
  "process_summary": "How to create and send an invoice from the billing dashboard.",
  "steps": [
    {
      "number": 1,                 // renumbered automatically; order = start_time order
      "title": "...",              // imperative heading, used in the guide and chapters
      "description": "...",        // 1-3 sentences shown in the written guide
      "start_time": 12.4,          // seconds — segment start (minus 0.25s pad)
      "end_time": 31.0,            // seconds — segment end (plus 0.25s pad)
      "key_frame_time": 18.2,      // which moment becomes the step's screenshot
      "narration": "..."           // read aloud by TTS over this step's segment
    }
  ]
}
```

Safe to hand-edit: any text field, and the time fields (keep ranges in order and non-overlapping — the video stage clamps but doesn't reorder after your edits). After editing, just rerun — the cache notices and rebuilds doc, video, and narration.

## Cost math

Cost = frames × tokens-per-frame × model input price, plus a small output cost.

A 10-minute recording → ~40 frames × ~1,400 tokens ≈ 56K input tokens + ~2K output:

| Model | Input $/MTok | Output $/MTok | Per 10-min video |
|---|---|---|---|
| `claude-opus-5` (default) | $5 | $25 | **≈ $0.34** |
| `claude-sonnet-5` | $3 | $15 | ≈ $0.20 |
| `claude-haiku-4-5` | $1 | $5 | **≈ $0.07** |

Levers: `--max-frames` caps the biggest cost driver; `--model` trades quality for price; re-runs from `steps.json` are always $0. The exact cost of every run is printed from the API's own usage numbers.

## Code layout

| File | Responsibility |
|---|---|
| `cli.py` | argparse, stage orchestration, prompts, the `Job` dataclass |
| `cache.py` | per-stage fingerprints + input mtime checks (`stale_reason` pure/tested) |
| `config.py` | `sclibe.json` loading/validation, `merge_settings` precedence (pure/tested), `--save-config` |
| `style.py` | `Style` dataclass (accent/font/scale/toggles), `ffcolor`/`fit_fontsize` (pure/tested) |
| `ingest.py` | stage 1 — probe |
| `frames.py` | stage 2 — candidate selection (`plan_timestamps` is pure/tested) + extraction |
| `analyze.py` | stage 3 — Pydantic schema, prompt, API call, `sanitize()` (pure/tested) |
| `doc.py` | stage 4 — screenshots, markdown, HTML template |
| `video.py` | stage 5 — `padded_ranges`/`chapter_spans`/`ffmetadata_escape` (pure/tested), cutting, concat, chapters |
| `narrate.py` | stage 6 — `stretch_plan` (pure/tested), fit-and-mux, final assembly |
| `tts.py` | voice providers: edge / say / openai, per-provider default voices |
| `util.py` | subprocess wrappers for ffmpeg/ffprobe, tool checks |

Design rule: anything with logic worth testing is a pure function (no I/O), covered in `tests/test_smoke.py`; the rest is thin orchestration around `ffmpeg`, `say`, and the API.
