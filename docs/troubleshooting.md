# Troubleshooting

Problems, causes, and fixes — roughly in the order you might hit them.

## Setup problems

### `command not found: sclibe`

The virtual environment isn't active in this terminal:

```bash
cd sCLIbe && source .venv/bin/activate
```

You need to do this once per terminal session (or invoke it directly: `.venv/bin/sclibe ...`).

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

See [setup — step 4](setup.md#4-get-an-anthropic-api-key) for getting a key in the first place.

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

- **Add `--context` first** — a sentence about the app and business purpose is the biggest quality lever, and it works on any model: `sclibe rec.mov --context "..." --from analyze` (paid call; check `_meta.context` in `steps.json` to see what a past run was told)
- Try the default Opus model if you used Haiku — quality difference is real on subtle UIs
- Merge or split steps by hand in `steps.json` (it's just JSON — copy a step object, adjust the time ranges, rerun `--from doc`)

## Video & narration problems

### Voice error, or narration sounds robotic

List installed voices and check the exact spelling (names are case-sensitive, Enhanced voices include the suffix):

```bash
say -v '?'
sclibe rec.mov --from narrate --voice "Ava (Premium)"
```

Download better voices for free: System Settings → Accessibility → Spoken Content → Manage Voices. Re-voicing is instant and free (`--from narrate`).

### Video freezes on a frame while narration keeps talking

Working as designed: when a step's narration runs longer than its video segment, the last frame is held so the audio never gets cut off. If it bothers you, shorten that step's `narration` text in `steps.json` (or widen its `start_time`/`end_time`), then `sclibe rec.mov --from narrate`.

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
