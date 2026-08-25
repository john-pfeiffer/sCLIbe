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
| [Usage guide](docs/usage.md) | You want to record well, understand the output, or edit results |
| [Configuration](docs/configuration.md) | You want to change a setting — voices, colors, models, providers — and make it stick |
| [Command reference](docs/commands.md) | You want to see **everything you can do** — every command, subcommand, flag, and env var |
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

sCLIbe works with no setup. Configuration is for the preferences you'd otherwise retype every run — your brand color, your narration voice, which AI model reads the recording.

Everything lives in **one JSON file** (`~/.sclibe.json`, or `sclibe.json` in the folder you run from), and there are two interchangeable ways to change it:

```bash
sclibe config                          # see every setting and its current value
sclibe config set accent "#0E7C5B"     # change one
sclibe config edit                     # or edit the JSON directly
```

What you can configure, at a glance:

| Area | Settings | Notes |
|---|---|---|
| **Analysis** | `model` | `claude-*` (default), `gpt-*`, or `grok-*` — one API key for whichever you pick |
| **Narration** | `tts`, `voice`, `rate` | Free neural voices by default; `say` offline, OpenAI, or ElevenLabs |
| **Styling** | `accent`, `font`, `font_scale`, `banners`, `title_card`, `title_card_image`, `title_card_text`, `title_text`, `subtitle_text` | Applied to both the video and `guide.html`; the title card can be text, an image, or both |
| **Frames & cost** | `threshold`, `max_frames`, `settle_delay`, `min_gap` | Frames are most of what you pay for |
| **Narration fit** | `max_slowdown` | How much a segment may slow to fit its narration; `1.0` = hold the last frame instead |
| **Output** | `output_root` | Where results are written |

Save voices under names you'll remember, and switch with one command:

```bash
sclibe voices add narrator elevenlabs VOICE_ID
sclibe voices use narrator
```

**→ [Full configuration guide](docs/configuration.md)** — every setting explained with defaults, both editing methods, all analysis and voice providers with the keys they need, and copy-paste recipes. For flag syntax, see the [command reference](docs/commands.md).

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
