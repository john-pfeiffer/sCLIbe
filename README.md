# sCLIbe

**Turn a screen recording into process documentation — automatically.**

Record yourself doing a task (QuickTime, Loom, OBS — anything that produces a video file). Run one command. sCLIbe uses AI to figure out the steps you performed and produces:

| Output | What it is |
|---|---|
| `guide.md` / `guide.html` | A step-by-step written guide with numbered steps and full-resolution screenshots |
| `final-video.mp4` | Your recording with dead time cut out, a chapter marker per step, and AI voiceover narration |
| `steps.json` | The AI's step breakdown — hand-editable, so you can fix wording and regenerate for free |

It's a self-hosted alternative to tools like Scribe: no subscription, no uploads to a third-party service. The only cost is one Claude API call per video — **roughly $0.35 for a 10-minute recording** on the default model, or ~$0.07 on the budget model. Video editing, scene detection, and text-to-speech all run locally for free.

## Quickstart

Already have Homebrew and an analysis API key? (If not, start with the [setup guide](docs/setup.md).)

```bash
brew install ffmpeg
git clone git@github.com:john-pfeiffer/sCLIbe.git && cd sCLIbe
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
export ANTHROPIC_API_KEY="sk-ant-..."   # add to ~/.zshrc to make it permanent

sclibe
```

That's it — sclibe asks for the recording (drag the file into the terminal) and for a one-sentence description of what it shows, then makes everything. Stable preferences (brand color, font, voice, model) are set once — see [Configuration](#configuration) below.

Output lands in `output/my-recording/`. Open `guide.html` in a browser, play `final-video.mp4` in QuickTime.

## Documentation

| Doc | Read it when... |
|---|---|
| [Setup](docs/setup.md) | You're installing on a Mac for the first time (from zero — includes getting an API key) |
| [Usage guide](docs/usage.md) | You want to record well, understand the output, tweak flags, or edit results |
| [How it works](docs/how-it-works.md) | You want the pipeline internals, the `steps.json` format, or the cost math |
| [Troubleshooting](docs/troubleshooting.md) | Something errored or the output isn't what you expected |

## The 30-second mental model

```
your-recording.mov
       │
       ▼
 probe → frames → analyze → doc → video → narrate
  free    free     PAID     free   free    free
                    │
                    ▼
               steps.json  ←— hand-edit this and rerun; affected stages rebuild for $0
```

Every stage saves its output *and the settings it ran with* — re-runs rebuild only what changed (a new voice rebuilds narration, a new accent rebuilds video and doc, an edited `steps.json` rebuilds everything downstream). The **only paid stage** is `analyze` (one Claude API call), and it never re-runs without asking — so you can iterate on the guide and video as many times as you like without paying again.

## Configuration

All settings live in **one JSON file** — `sclibe.json` in the folder you run from, or `~/.sclibe.json` as the per-user default (`sclibe config path` shows which is active). The file always contains the complete current state, and there are two equivalent ways to change it — commands and hand-edits write the same file:

```bash
sclibe config                          # show every setting (customized ones marked)
sclibe config set accent "#0E7C5B"     # change one setting
sclibe config set model gpt-4o         # switch the analysis provider by model name
sclibe config edit                     # open the JSON in your editor instead
```

**Settings:** `model`, `tts`, `voice`, `rate`, `threshold`, `max_frames`, `output_root`, `accent`, `font`, `font_scale`, `banners`, `title_card` — every one also available as a CLI flag for one-off overrides (flags always win).

**Analysis providers** — pick by model name: `claude-*` (Anthropic, default), `gpt-*` (OpenAI), `grok-*` (xAI). One API key for whichever you use.

**Narration voices** — four providers (`edge` free neural default, `say` offline, `openai`, `elevenlabs`), plus a saved-voice roster so you can switch by name:

```bash
sclibe voices                                        # list saved voices
sclibe voices add narrator elevenlabs VOICE_ID       # save one under a friendly name
sclibe voices use narrator                           # make it the narration voice
```

Full details: [usage guide → config commands, saved voices, providers](docs/usage.md#config-commands).

## Requirements

- macOS, with [Homebrew](https://brew.sh), ffmpeg, and Python 3.11+
- An API key for **any one** analysis provider: [Anthropic](https://console.anthropic.com) (default, `claude-*` models), [OpenAI](https://platform.openai.com) (`gpt-*`), or [xAI](https://console.x.ai) (`grok-*`)
- Narration needs nothing extra: the default voice is free (Microsoft neural voices over the internet, falling back to the built-in macOS `say` offline). Optional premium voices: OpenAI (~$0.015/min) or ElevenLabs (`ELEVENLABS_API_KEY`)

## Repository layout

```
src/sclibe/     the pipeline (one module per stage — see docs/how-it-works.md)
tests/          unit tests for the pure logic (pytest)
docs/           full documentation
output/         generated results (gitignored)
samples/        test videos (gitignored)
```

## Tests

```bash
pip install pytest && pytest
```
