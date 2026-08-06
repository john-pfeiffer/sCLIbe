# Usage guide

From recording a process to a polished guide and video.

## 1. Record your screen

Any tool that produces a video file works. The easiest on a Mac is built-in:

- Press **⌘⇧5**, choose *Record Entire Screen* or *Record Selected Portion*, click **Record**
- Do the task
- Click the stop button in the menu bar; the recording saves to the Desktop as a `.mov`

### Recording tips (these directly affect output quality)

- **One task per recording.** "How to create a customer invoice" — not three loosely related things. The AI produces one titled process per video.
- **Work at a natural, deliberate pace.** Pause briefly after each meaningful click so the UI settles — those settled moments become the screenshots.
- **Don't worry about hesitation and waiting.** Idle time, slow page loads, and cursor wandering get cut from the final video automatically.
- **Close what you don't want documented.** Notifications, unrelated windows, and personal info can end up in screenshots. Do Not Disturb mode helps.
- **Don't type real passwords on screen.** The AI is instructed never to transcribe sensitive values, but the *video frames themselves* end up in the guide — use a test account or type credentials off-screen.
- **5–15 minutes is the sweet spot.** Longer recordings work but get sampled more sparsely (see `--max-frames` below).

## 2. Run ShineScript

```bash
cd sCLIbe
source .venv/bin/activate
shine ~/Desktop/my-recording.mov --context "What this recording shows"
```

You'll see each stage log as it runs. The line to watch:

```
analyzing 42 frames with claude-opus-5 (this is the paid step)...
API usage: 58123 input + 1984 output tokens ≈ $0.340
```

A 10-minute video takes a few minutes end to end (most of it is video encoding, not the API).

## 3. What you get

Everything lands in `output/<video-name>/` (relative to where you ran the command):

```
output/my-recording/
├── steps.json        the AI's step breakdown — the editable source of truth
├── guide.md          the written guide (markdown — great for GitHub/Notion/Obsidian)
├── guide.html        the same guide, styled — double-click to open in a browser
├── screenshots/      one full-resolution PNG per step
├── final-video.mp4   edited video: dead time cut, chapters, narration
├── meta.json         video metadata
└── work/             intermediates (API frames, cut segments, audio) — safe to ignore
```

Chapter markers show up in QuickTime's timeline (and YouTube if you upload).

## 4. Fix wording without paying again

The AI call is checkpointed in `steps.json`. Open it in any editor — each step looks like:

```json
{
  "number": 2,
  "title": "Fill out the customer form",
  "description": "Enter the customer's name and email, then select a plan.",
  "start_time": 41.2,
  "end_time": 63.0,
  "key_frame_time": 55.3,
  "narration": "Next, fill in the customer's details. Double-check the email before moving on."
}
```

Edit any `title`, `description`, or `narration` (or nudge the time ranges), then regenerate:

```bash
shine ~/Desktop/my-recording.mov --from doc
```

That reruns the doc, video, and narration stages in seconds — **zero API cost**. This edit-and-rerun loop is the intended workflow: let the AI do the first 90%, polish the words yourself.

## 5. Flags reference

```bash
shine VIDEO [flags]
```

| Flag | Default | What it does |
|---|---|---|
| `--model NAME` | `claude-opus-5` | Claude model for analysis. `claude-haiku-4-5` is ~5× cheaper and fine for straightforward UIs; use the default for complex or subtle processes. |
| `--context "TEXT"` | — | Tell the AI what the recording shows. One or two sentences of business context dramatically improves step titles, descriptions, and narration — the AI otherwise has to guess from pixels alone. |
| `--no-video` | off | Written guide only — skips cutting, narration, and the final video |
| `--from STAGE` | — | Force a rerun from this stage onward: `probe`, `frames`, `analyze`, `doc`, `video`, `narrate`. Everything before it uses cache. |
| `--force` | off | Redo every stage, **including the paid analysis** |
| `--voice NAME` | `Samantha` | macOS narration voice (`say -v '?'` lists them; Enhanced voices sound much better — see [setup](setup.md)) |
| `--rate WPM` | `175` | Narration speed in words per minute |
| `--threshold N` | `10` | Scene-change sensitivity. Lower = more frames captured. Raise it if you get hundreds of frames from a busy screen; lower it (e.g. 6) if steps are being missed. |
| `--max-frames N` | `60` | Hard cap on frames sent to the API (cost control). Longer videos get thinned to fit. |
| `-o DIR` / `--output-root DIR` | `./output` | Output root directory |
| `-v` / `--verbose` | off | Verbose logging (shows every ffmpeg command) |

### Give the AI context (recommended)

Without context, the AI only sees pixels — it has to guess what app you're in and why. A sentence or two fixes that:

```bash
shine rec.mov --context "Our monthly invoice run in QuickBooks. The operator is \
an accountant; the popup at the end is the confirmation email preview."
```

Good context mentions: the app/site, the business purpose, who the guide is for, and anything on screen that would otherwise look confusing. The context is saved into `steps.json` so you can see what a past run was told. Changing `--context` alone doesn't invalidate a cached analysis — add `--from analyze` to redo it (paid call).

### Common invocations

```bash
shine rec.mov --context "New-hire guide to our invoice workflow in QuickBooks"
shine rec.mov --model claude-haiku-4-5      # cheap first pass (~$0.07)
shine rec.mov --no-video                    # just the written guide
shine rec.mov --from narrate --voice "Ava (Premium)" --rate 165   # re-voice only
shine rec.mov --from analyze                # redo the AI analysis (paid) after changing frames
shine rec.mov -o ~/Guides                   # put output somewhere else
```

## 6. Understanding cache and re-runs

Running the same command twice does almost nothing — every stage sees its output already exists and skips. The rules:

- `--from STAGE` invalidates that stage and everything after it
- `--force` invalidates everything
- Deleting `output/<name>/` starts completely fresh
- If you rerun frame extraction (e.g. with a new `--threshold`), the tool notices `steps.json` was built from a *different* frame set and warns you — rerun `--from analyze` if you want the analysis to match

The stage order is: `probe → frames → analyze → doc → video → narrate`. Only `analyze` costs money.
