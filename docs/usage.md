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

## 2. Run sCLIbe

```bash
cd sCLIbe
source .venv/bin/activate
sclibe
```

(Or just `sclibe` from anywhere, if you set up the alias from [setup — step 6](setup.md#6-optional-run-sclibe-from-anywhere-recommended).)

That's the whole command. sclibe asks for the two things that change every run:

```
Paste the path to your screen recording (or drag the file into this window):
video> ~/Desktop/my-recording.mov

Describe what this recording shows — the app, the business purpose, and who
the guide is for. This greatly improves the result. (Enter to skip)
context> Our monthly invoice run in QuickBooks, for new accountants.
```

Drag the file from Finder straight into the Terminal window — quoted or escaped paths are handled. Everything else (brand color, font, voice, model) comes from your `sclibe.json` (see below). You can still pass the path and context as arguments for scripting: `sclibe rec.mov --context "..."`.

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
sclibe ~/Desktop/my-recording.mov --from doc
```

That reruns the doc, video, and narration stages in seconds — **zero API cost**. This edit-and-rerun loop is the intended workflow: let the AI do the first 90%, polish the words yourself.

## 5. Flags reference

```bash
sclibe VIDEO [flags]
```

| Flag | Default | What it does |
|---|---|---|
| `--model NAME` | `claude-opus-5` | Claude model for analysis. `claude-haiku-4-5` is ~5× cheaper and fine for straightforward UIs; use the default for complex or subtle processes. |
| `--context "TEXT"` | *prompted* | Tell the AI what the recording shows. If omitted, sclibe asks interactively whenever a paid analysis is about to run. |
| `--no-video` | off | Written guide only — skips cutting, narration, and the final video |
| `--from STAGE` | — | Force a rerun from this stage onward: `probe`, `frames`, `analyze`, `doc`, `video`, `narrate`. Everything before it uses cache. |
| `--force` | off | Redo every stage, **including the paid analysis** |
| `--voice NAME` | `Samantha` | macOS narration voice (`say -v '?'` lists them; Enhanced voices sound much better — see [setup](setup.md)) |
| `--rate WPM` | `175` | Narration speed in words per minute |
| `--accent HEX` | `#2563eb` | Brand color used for the video's step banners and title card, and for headings in `guide.html` |
| `--font NAME` | `Helvetica Neue` | Font for video text and the HTML guide — any font installed on the Mac (check Font Book for names) |
| `--font-scale N` | `1.0` | Multiplier on all rendered text sizes (e.g. `1.3` for bigger banners) |
| `--no-banners` | off | Skip the step-label overlay at the start of each video segment |
| `--no-title-card` | off | Skip the narrated intro card before step 1 |
| `--threshold N` | `10` | Scene-change sensitivity. Lower = more frames captured. Raise it if you get hundreds of frames from a busy screen; lower it (e.g. 6) if steps are being missed. |
| `--max-frames N` | `60` | Hard cap on frames sent to the API (cost control). Longer videos get thinned to fit. |
| `-o DIR` / `--output-root DIR` | `./output` | Output root directory |
| `--save-config` | off | Write this run's effective settings to `./sclibe.json` for future runs |
| `-v` / `--verbose` | off | Verbose logging (shows every ffmpeg command) |

All defaults in this table can be overridden persistently via `sclibe.json` — see below.

### Give the AI context (recommended)

Without context, the AI only sees pixels — it has to guess what app you're in and why. **You don't need a flag for this**: whenever a paid analysis is about to run and you didn't pass `--context`, sclibe asks you interactively:

```
Describe what this recording shows — the app, the business purpose, and who
the guide is for. This greatly improves the result. (Enter to skip)
context> _
```

You can still pass it on the command line (useful for scripts):

```bash
sclibe rec.mov --context "Our monthly invoice run in QuickBooks. The operator is \
an accountant; the popup at the end is the confirmation email preview."
```

Good context mentions: the app/site, the business purpose, who the guide is for, and anything on screen that would otherwise look confusing. The context is saved into `steps.json` so you can see what a past run was told. The prompt only appears when analysis will actually run — cached re-runs and non-interactive shells never ask. Changing context alone doesn't invalidate a cached analysis — add `--from analyze` to redo it (paid call).

### Persistent settings: `sclibe.json`

Stable preferences — brand color, font, voice, model — don't belong on every command line. Put them in a config file and forget them:

```bash
sclibe rec.mov --accent "#0E7C5B" --font "Avenir Next" --save-config
```

`--save-config` writes the run's effective settings to `./sclibe.json`; every later run picks it up automatically (`~/.sclibe.json` works too, as a per-user fallback). You can also write the file by hand — any subset of keys is fine:

```json
{
  "accent": "#0E7C5B",
  "font": "Avenir Next",
  "voice": "Samantha (Enhanced)",
  "model": "claude-opus-5"
}
```

Valid keys: `model`, `voice`, `rate`, `threshold`, `max_frames`, `output_root`, `accent`, `font`, `font_scale`, `banners`, `title_card`. Precedence is always **CLI flag > sclibe.json > built-in default**. Committing a `sclibe.json` to a shared repo is a nice way to give the whole team the same branding.

### Styling the video and guide

The final video opens with a **title card** (process title on your accent color, with the summary read as narration) and each step starts with a **lower-third banner** showing its number and title. The same accent color and font style the HTML guide's headings, so docs and video match your brand:

```bash
sclibe rec.mov --accent "#0E7C5B" --font "Avenir Next"
sclibe rec.mov --no-title-card --no-banners        # plain video, no overlays
```

Styling is free to change after the fact — it doesn't touch the AI analysis:

```bash
sclibe rec.mov --accent "#B45309" --from video     # restyle banners + card + video ($0)
sclibe rec.mov --accent "#B45309" --from doc       # also refresh guide.html colors ($0)
```

### Common invocations

```bash
sclibe                                       # interactive: asks for the video + context
sclibe rec.mov --context "New-hire guide to our invoice workflow in QuickBooks"
sclibe rec.mov --model claude-haiku-4-5      # cheap first pass (~$0.07)
sclibe rec.mov --no-video                    # just the written guide
sclibe rec.mov --from narrate --voice "Ava (Premium)" --rate 165   # re-voice only
sclibe rec.mov --from analyze                # redo the AI analysis (paid) after changing frames
sclibe rec.mov -o ~/Guides                   # put output somewhere else
```

## 6. Understanding cache and re-runs

Running the same command twice does almost nothing — every stage sees its output already exists and skips. The rules:

- `--from STAGE` invalidates that stage and everything after it
- `--force` invalidates everything
- Deleting `output/<name>/` starts completely fresh
- If you rerun frame extraction (e.g. with a new `--threshold`), the tool notices `steps.json` was built from a *different* frame set and warns you — rerun `--from analyze` if you want the analysis to match

The stage order is: `probe → frames → analyze → doc → video → narrate`. Only `analyze` costs money.
