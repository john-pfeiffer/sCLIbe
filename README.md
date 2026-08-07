# ShineScript

**Turn a screen recording into process documentation — automatically.**

Record yourself doing a task (QuickTime, Loom, OBS — anything that produces a video file). Run one command. ShineScript uses AI to figure out the steps you performed and produces:

| Output | What it is |
|---|---|
| `guide.md` / `guide.html` | A step-by-step written guide with numbered steps and full-resolution screenshots |
| `final-video.mp4` | Your recording with dead time cut out, a chapter marker per step, and AI voiceover narration |
| `steps.json` | The AI's step breakdown — hand-editable, so you can fix wording and regenerate for free |

It's a self-hosted alternative to tools like Scribe: no subscription, no uploads to a third-party service. The only cost is one Claude API call per video — **roughly $0.35 for a 10-minute recording** on the default model, or ~$0.07 on the budget model. Video editing, scene detection, and text-to-speech all run locally for free.

## Quickstart

Already have Homebrew and an Anthropic API key? (If not, start with the [setup guide](docs/setup.md).)

```bash
brew install ffmpeg
git clone git@github.com:john-pfeiffer/sCLIbe.git && cd sCLIbe
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
export ANTHROPIC_API_KEY="sk-ant-..."   # add to ~/.zshrc to make it permanent

shine
```

That's it — shine asks for the recording (drag the file into the terminal) and for a one-sentence description of what it shows, then makes everything. Stable preferences (brand color, font, voice, model) live in an optional `shine.json` — set them once with `--save-config` (see the [usage guide](docs/usage.md#persistent-settings-shinejson)).

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
               steps.json  ←— hand-edit this, then rerun `--from doc` for $0
```

Every stage saves its output and is skipped on re-runs. The **only paid stage** is `analyze` (one Claude API call), and its result is checkpointed in `steps.json` — so you can iterate on the guide and video as many times as you like without paying again.

## Requirements

- macOS (uses the built-in `say` command for narration)
- [Homebrew](https://brew.sh), ffmpeg, Python 3.11+
- An [Anthropic API key](https://console.anthropic.com)

## Repository layout

```
src/shinescript/     the pipeline (one module per stage — see docs/how-it-works.md)
tests/               unit tests for the pure logic (pytest)
docs/                full documentation
output/              generated results (gitignored)
samples/             test videos (gitignored)
```

## Tests

```bash
pip install pytest && pytest
```
