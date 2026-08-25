# Troubleshooting

Problems, causes, and fixes — roughly in the order you might hit them.

## Setup problems

### `command not found: sclibe`

The virtual environment isn't active in this terminal:

```bash
cd sCLIbe && source .venv/bin/activate
```

You need to do this once per terminal session (or invoke it directly: `.venv/bin/sclibe ...`).

### `bad interpreter: ... no such file or directory` (after moving/renaming the project folder)

Python virtual environments hardcode their absolute path — moving or renaming the project folder breaks the `.venv` inside it. Recreate it (fast, nothing else is lost):

```bash
cd <project-folder>
rm -rf .venv
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e .
```

If you use the run-from-anywhere alias, also update the path in `~/.zshrc` and `source ~/.zshrc`.

### `error: required tool(s) not found on PATH: ffmpeg`

```bash
brew install ffmpeg
```

If it's installed but still not found, Homebrew's bin directory isn't on your PATH — on Apple Silicon add `eval "$(/opt/homebrew/bin/brew shellenv)"` to `~/.zshrc`.

### `error: ANTHROPIC_API_KEY is not set`

The key isn't in this shell. Check with `echo ${ANTHROPIC_API_KEY:0:7}` — you should see `sk-ant-`. If empty:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-YOUR-KEY"' >> ~/.zshrc
source ~/.zshrc
```

See [setup — step 4](setup.md#4-get-an-analysis-api-key-one-of-three) for getting a key in the first place.

### API errors during analyze

| Error mentions | Meaning | Fix |
|---|---|---|
| `authentication` / 401 | Key is wrong or revoked | Re-copy the key from console.anthropic.com |
| `credit` / `billing` | No API credit on the account | Add credit in Console → Settings → Billing |
| `rate_limit` / 429 | Too many requests (unlikely at this usage) | Wait a minute and rerun — finished stages are cached |
| `overloaded` / 529 | API busy | Rerun in a minute; the SDK already retried twice |

A failed analyze costs nothing if no response came back, and rerunning skips all the free stages that already completed.

## Frame selection problems

### Too few frames / steps are missing from the guide

The scene detector didn't register subtle changes. Lower the threshold and redo:

```bash
sclibe rec.mov --threshold 6 --from frames
```

(`--from frames` also invalidates the later stages, so a fresh analysis will run — that's a new paid call.)

### Hundreds of frames selected / cost warning feels high

Animated or video-heavy screens trigger constant "scene changes". Raise the threshold, or rely on the cap:

```bash
sclibe rec.mov --threshold 18 --from frames     # less sensitive
sclibe rec.mov --max-frames 40 --from frames    # hard cost cap
```

You can sanity-check what will be sent before paying: look at `output/<name>/work/frames/` after the frames stage — those JPEGs are exactly what goes to the API.

### The screenshots show the wrong moment

Edit `key_frame_time` for that step in `steps.json` (pick any timestamp from `work/frames.json`, or any time in the video), then:

```bash
sclibe rec.mov --from doc
```

## Analysis problems

### `steps.json was generated from a DIFFERENT frame set` warning

You re-extracted frames (new threshold/max-frames) after the analysis ran. The cached analysis still refers to the old frames. If the old analysis is fine, ignore the warning; to redo it against the new frames:

```bash
sclibe rec.mov --from analyze     # paid call
```

### Steps are too coarse / too granular, or descriptions are thin

- **Add `--context` first** — a sentence about the app and business purpose is the biggest quality lever, and it works on any model: `sclibe rec.mov --context "..."` makes sclibe notice the changed context and ask before re-running the analysis (paid call; `--from analyze` skips the question). For real detail, put it in a file: `--context-file notes.md`. Check `_meta.context` in `steps.json` to see what a past run was told.
- Try the default Opus model if you used Haiku — quality difference is real on subtle UIs
- Merge or split steps by hand in `steps.json` (it's just JSON — copy a step object, adjust the time ranges, rerun `--from doc`)

## Video & narration problems

### Narration sounds robotic

You're probably on the offline `say` provider (the automatic fallback when the free neural voices can't be reached). The default `edge` provider sounds far more natural — check your internet connection and rerun `--from narrate` (free). To browse other neural voices:

```bash
.venv/bin/edge-tts --list-voices | grep en-US
sclibe rec.mov --from narrate --voice en-US-EmmaMultilingualNeural
```

If you need offline narration to sound better, download Enhanced macOS voices for free (System Settings → Accessibility → Spoken Content → Manage Voices) and use `--tts say --voice "Ava (Premium)"`.

### Voice error

Voice names are provider-specific and case-sensitive: edge voices come from `edge-tts --list-voices`, `say` voices from `say -v '?'`. Re-voicing is instant and free (`--from narrate`).

### Video goes slow-motion (or holds a frame) while narration keeps talking

Working as designed: when a step's narration runs longer than its video segment, the segment is slowed (up to `max_slowdown`, default 2×) so the on-screen action stays in sync with the words, and only holds the last frame beyond that. If a step feels draggy, shorten that step's `narration` text in `steps.json` (or widen its `start_time`/`end_time`), then `sclibe rec.mov --from narrate`. If you'd rather never see slow motion at all, `--max-slowdown 1.0` (or `sclibe config set max_slowdown 1.0`) plays every segment at normal speed and holds its last frame for the rest of the narration.

### Narration describes things after the video has moved past them

That's the failure the slow-motion fit exists to prevent — if you still see it, the step's `narration` is probably describing actions from *outside* its `start_time`–`end_time` range. Trim the narration to what happens inside the range (or widen the range), then `--from narrate`.

### Title card image is missing, cropped, or unreadable

- `error: title card image not found` — the `title_card_image` path (config or `--title-card-image`) doesn't point at a file; `~` is expanded, so check the path with `ls`.
- The image shows with colored bars around it: that's the letterboxing — the image's aspect ratio differs from the video's, so it's fitted and padded with the accent color. Export the image at the video's aspect ratio (usually 16:9) for a full-bleed card.
- Text is hard to read over the image: the overlay already gets a dark box behind it, but a busy image can still fight it — use `--no-title-card-text` and bake the title into the image, or pick a calmer image.
- Use PNG or JPEG; other formats depend on your ffmpeg build.

### Chapters don't show up

They're in the file — QuickTime shows them in the ⫶ chapters menu / timeline, VLC under Playback → Chapters. Verify with:

```bash
ffprobe -v error -show_chapters output/<name>/final-video.mp4
```

Some players (e.g. web `<video>` tags) simply don't display chapter metadata.

### The final video cut something I wanted to keep

Everything outside the steps' `[start_time, end_time]` ranges is treated as dead time. Widen the relevant step's range in `steps.json` and rerun `--from video`.

## Still stuck?

Run with `-v` to see every underlying `ffmpeg` command, and check the intermediates in `output/<name>/work/` — each stage's raw output is there. Deleting `output/<name>/` entirely and rerunning gives you a clean slate (one new paid call).
