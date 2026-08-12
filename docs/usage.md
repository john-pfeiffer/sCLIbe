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

Edit any `title`, `description`, or `narration` (or nudge the time ranges), then just run it again:

```bash
sclibe ~/Desktop/my-recording.mov
```

The cache notices `steps.json` changed and rebuilds the doc, video, and narration automatically — **zero API cost**. This edit-and-rerun loop is the intended workflow: let the AI do the first 90%, polish the words yourself.

## 5. Flags reference

The complete list of every flag, command, and environment variable lives in the [command reference](commands.md). The ones you'll reach for day to day:

```bash
sclibe                                      # interactive: asks for the video + context
sclibe rec.mov --context "..."              # scripted run
sclibe rec.mov --model claude-haiku-4-5     # cheap analysis pass (~$0.07)
sclibe rec.mov --no-video                   # written guide only
sclibe rec.mov --voice narrator-alt         # a saved voice (see `sclibe voices`)
sclibe rec.mov --from narrate               # force the narration stage to rerun
sclibe rec.mov --force                      # redo everything, including the paid analysis
```

Every flag has a matching [config setting](configuration.md#every-setting); flags win for that one run.

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

### Settings that stick

Anything you'd otherwise retype every run — brand color, font, narration voice, which AI model does the analysis — belongs in your config file instead:

```bash
sclibe config                          # see every setting
sclibe config set accent "#0E7C5B"     # change one
sclibe voices use narrator             # switch narration voice
```

The [configuration guide](configuration.md) covers every setting, both editing methods, all analysis and voice providers with the keys they need, and ready-made recipes.

## 6. Understanding cache and re-runs

The cache is automatic — **change something, rerun the same `sclibe` command, and only the affected stages rebuild**:

| You changed | What rebuilds by itself |
|---|---|
| `steps.json` (hand-edits) | doc, video, narration |
| voice / tts / rate | narration only |
| accent / font / font-scale / banners | video + doc (narration follows) |
| threshold / max-frames | frame selection (then asks about re-analysis — see below) |
| nothing | nothing — you get "everything is already up to date" |

The one exception is the **paid** analysis stage: it never re-runs silently. If the model, context, or frame set changed, sclibe tells you what changed and asks before spending money (non-interactive runs keep the cache and warn).

Manual overrides when you want them:

- `--from STAGE` — force a rerun from `probe`, `frames`, `analyze`, `doc`, `video`, or `narrate` onward
- `--force` — redo every stage, **including the paid analysis**
- Deleting `output/<name>/` starts completely fresh

Only `analyze` costs money; everything else rebuilds free.
