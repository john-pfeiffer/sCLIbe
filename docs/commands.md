# Command reference

Every command, flag, and environment variable. The other docs explain *when* to use things; this page is the complete *what exists*.

```
sclibe                          run interactively (asks for video + context)
sclibe VIDEO [flags]            run on a recording
sclibe config ...               view and change settings
sclibe voices ...               manage saved narration voices
```

---

## `sclibe` — run the pipeline

```bash
sclibe                          # interactive: prompts for the video path, then context
sclibe VIDEO                    # video given; prompts for context only if analysis will run
sclibe VIDEO [flags]            # fully scripted
```

- With no video argument, sclibe asks for the path — pasting or dragging the file from Finder both work (quotes and escapes are cleaned up).
- The context question only appears when a **paid** analysis is actually about to run; cached re-runs and non-interactive shells are never prompted.
- Re-runs rebuild only what changed (see [usage — cache](usage.md#6-understanding-cache-and-re-runs)).

### Flags

Every flag is a one-off override of the corresponding [config setting](#sclibe-config--settings); flags always win over `sclibe.json`.

| Flag | Default | What it does |
|---|---|---|
| `--model NAME` | `claude-opus-5` | Vision model for analysis — the provider is inferred from the name: `claude-*` (Anthropic), `gpt-*` (OpenAI, e.g. `gpt-4o`), `grok-*` (xAI). `claude-haiku-4-5` is ~5× cheaper than the default. |
| `--context "TEXT"` | *prompted* | What the recording shows. If omitted, asked interactively when a paid analysis is about to run. |
| `--context-file PATH` | — | A file (plain text or markdown) with context or details for the AI; combined with `--context` when both are given |
| `--no-video` | off | Written guide only — skips cutting, narration, and the final video |
| `--from STAGE` | — | Force a rerun from this stage onward: `probe`, `frames`, `analyze`, `doc`, `video`, `narrate` |
| `--force` | off | Redo every stage, **including the paid analysis** |
| `--tts NAME` | `edge` | Narration provider: `edge` (free neural voices; auto-falls back to `say` offline), `say` (offline), `openai` (~$0.015/min), `elevenlabs` (best; `--voice` takes a voice ID) |
| `--voice NAME` | *per provider* | A saved voice name (see `sclibe voices`) or a provider voice: edge → `edge-tts --list-voices`; say → `say -v '?'`; openai → e.g. `onyx`; elevenlabs → a voice ID |
| `--rate WPM` | `175` | Narration speed in words per minute (175 = normal speed) |
| `--accent HEX` | `#2563eb` | Brand color: video banners, title card, `guide.html` headings |
| `--font NAME` | `Helvetica Neue` | Font for video text and the HTML guide (any installed Mac font) |
| `--font-scale N` | `1.0` | Multiplier on rendered text sizes |
| `--no-banners` | off | No step-label overlay on video segments |
| `--no-title-card` | off | No narrated intro card before step 1 |
| `--title-card-image PATH` | — | Image for the intro card, letterboxed on the accent color; text is overlaid unless `--no-title-card-text` |
| `--no-title-card-text` | off | Title card image only, no text overlaid (needs `--title-card-image`) |
| `--title-text "TEXT"` | *AI title* | Custom title on the intro card, instead of the AI-generated process title |
| `--subtitle-text "TEXT"` | *step count* | Custom subtitle on the intro card, instead of "N steps" |
| `--threshold N` | `10` | Scene-change sensitivity; lower = more frames |
| `--max-frames N` | `60` | Cap on frames sent to the API (cost control) |
| `--settle-delay N` | `0.7` | Seconds to wait after a detected change before taking the screenshot — raise for slow UIs or animations |
| `--min-gap N` | `2` | Minimum seconds between screenshots |
| `--max-slowdown N` | `2` | How much a segment may slow to fit its narration; `1.0` = never slow, hold the last frame instead |
| `-o DIR` / `--output-root DIR` | `./output` | Output root directory |
| `--save-config` | off | Write this run's effective settings to `./sclibe.json` |
| `-v` / `--verbose` | off | Show every underlying ffmpeg command |
| `-h` / `--help` | — | Usage summary |

---

## `sclibe config` — settings

Settings live in **one JSON file**: `sclibe.json` in the current directory if present, else `~/.sclibe.json`. The file always contains the complete current state; commands and hand-edits are interchangeable ways to change the same file.

| Command | Does |
|---|---|
| `sclibe config` (or `config show`) | Print every setting and the saved-voice roster; values differing from the defaults are marked `(custom)` |
| `sclibe config set KEY VALUE` | Change one setting (e.g. `sclibe config set accent "#0E7C5B"`, `sclibe config set banners false`) |
| `sclibe config edit` | Open the config file in `$EDITOR` (or TextEdit), materialized with every key visible |
| `sclibe config path` | Print which config file is active |

Valid keys for `set`: `model`, `tts`, `voice`, `rate`, `threshold`, `max_frames`, `settle_delay`, `min_gap`, `max_slowdown`, `output_root`, `accent`, `font`, `font_scale`, `banners`, `title_card`, `title_card_image`, `title_card_text`, `title_text`, `subtitle_text` — each one explained with its default in the [configuration guide](configuration.md#every-setting). Values are parsed as JSON when possible (`175`, `true`, `1.3`), otherwise taken as strings. The nested `voices` roster is managed with `sclibe voices` (or by editing the file).

---

## `sclibe voices` — saved narration voices

A roster of voices under friendly names. Each saved voice remembers its provider, so switching voices switches providers too. Saved names also work anywhere `--voice` is accepted. For the providers themselves and how to find voice names, see the [configuration guide](configuration.md#narration-voices).

| Command | Does |
|---|---|
| `sclibe voices` (or `voices list`) | List saved voices; the active one is marked |
| `sclibe voices add NAME PROVIDER VOICE_ID` | Save a voice (e.g. `sclibe voices add narrator elevenlabs UgBB...`) |
| `sclibe voices use NAME` | Make a saved voice the narration voice |

**Forgiving forms** — these all work and mean the same thing: `sclibe voice ...` (singular), `sclibe config voice ...` / `sclibe config voices ...` (nested under config), and `set` / `select` / `switch` as synonyms for `use`.

```bash
sclibe voices add narrator elevenlabs UgBBYS2sOqTuMpoF3BR0
sclibe voices add backup edge en-US-EmmaMultilingualNeural
sclibe voices use narrator
sclibe config voice set backup      # same as: sclibe voices use backup
```

---

## Environment variables

| Variable | Needed when | Where to get it |
|---|---|---|
| `ANTHROPIC_API_KEY` | Analysis with `claude-*` models (the default) | [console.anthropic.com](https://console.anthropic.com) |
| `OPENAI_API_KEY` | Analysis with `gpt-*` models, or `--tts openai` (both also need `pip install openai`) | [platform.openai.com](https://platform.openai.com) |
| `XAI_API_KEY` | Analysis with `grok-*` models | [console.x.ai](https://console.x.ai) |
| `ELEVENLABS_API_KEY` | `--tts elevenlabs` | [elevenlabs.io](https://elevenlabs.io) → profile → API keys |
| `EDITOR` | Optional — which editor `sclibe config edit` opens | your shell profile |

Add keys to `~/.zshrc` (`export ANTHROPIC_API_KEY="..."`) so every terminal has them. Only **one** analysis key is required — whichever provider your `model` setting uses.

---

## Helper commands from the providers

Not sclibe commands, but you'll use them alongside it:

```bash
.venv/bin/edge-tts --list-voices | grep en-US    # browse the free neural voices
say -v '?'                                       # list installed macOS voices
ffprobe -v error -show_chapters final-video.mp4  # verify chapter markers
```
