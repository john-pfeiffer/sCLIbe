# Configuration

Everything sCLIbe can be configured to do, and the two ways to change it.

You never *have* to configure anything — sCLIbe works out of the box with sensible defaults. Configuration is for the preferences you'd otherwise retype on every run: your brand color, your narration voice, which AI model does the analysis.

**Contents:** [Where settings live](#where-settings-live) · [Two ways to change them](#two-ways-to-change-settings) · [Every setting](#every-setting) · [Analysis providers](#analysis-providers) · [Narration voices](#narration-voices) · [Saved voices](#saved-voices) · [Recipes](#recipes)

---

## Where settings live

One JSON file. sCLIbe looks in two places, in order:

1. **`sclibe.json`** in the directory you run from — per-project settings
2. **`~/.sclibe.json`** in your home folder — your personal defaults

The first one found wins. Most people only ever have the second. To see which is active:

```bash
sclibe config path
```

If neither exists, sCLIbe uses its built-in defaults, and the first setting you save creates `~/.sclibe.json` for you.

**Precedence, highest first:** a command-line flag → the config file → the built-in default. So a flag is always a one-off override that doesn't change your saved settings:

```bash
sclibe rec.mov --accent "#B45309"    # this run only; your saved accent is untouched
```

---

## Two ways to change settings

Both edit the same file and are completely interchangeable — use whichever you prefer, whenever.

### With commands

```bash
sclibe config                          # show every setting and its current value
sclibe config set accent "#0E7C5B"     # change one setting
sclibe config set model claude-haiku-4-5
sclibe config set banners false
sclibe config path                     # where is the file?
```

`sclibe config` marks anything you've customized, so you can see at a glance what differs from the defaults:

```
config file: /Users/you/.sclibe.json

  model        = 'claude-opus-5'
  tts          = 'elevenlabs'   (custom)
  voice        = 'narrator'   (custom)
  rate         = 175
  ...
```

### By editing the JSON

```bash
sclibe config edit        # opens in $EDITOR, or TextEdit
```

The file always contains **every** setting spelled out — not just the ones you've changed — so you can see the full set of what's adjustable in one place and edit anything directly:

```json
{
  "model": "claude-opus-5",
  "tts": "elevenlabs",
  "voice": "narrator",
  "voices": {
    "narrator": { "tts": "elevenlabs", "voice": "UgBBYS2sOqTuMpoF3BR0" }
  },
  "rate": 175,
  "threshold": 10.0,
  "max_frames": 60,
  "output_root": "output",
  "accent": "#2563eb",
  "font": "Helvetica Neue",
  "font_scale": 1.0,
  "banners": true,
  "title_card": true
}
```

Changes take effect on the next run. A hand-written file with only some keys works fine too — anything missing falls back to the default.

### From a run you liked

```bash
sclibe rec.mov --accent "#0E7C5B" --font "Avenir Next" --save-config
```

`--save-config` writes that run's effective settings to `./sclibe.json` — handy for making a one-off experiment permanent.

---

## Every setting

### Analysis — the AI that turns your recording into steps

| Setting | Default | What it does |
|---|---|---|
| `model` | `claude-opus-5` | Which vision model reads the frames. The provider is inferred from the name — see [Analysis providers](#analysis-providers). This is the only setting that affects cost. |

### Narration — the voiceover

| Setting | Default | What it does |
|---|---|---|
| `tts` | `edge` | Voice provider: `edge`, `say`, `openai`, or `elevenlabs` — see [Narration voices](#narration-voices) |
| `voice` | *provider default* | A specific voice, or a name from your [saved voices](#saved-voices) |
| `voices` | `{}` | Your saved voice roster — managed with `sclibe voices` |
| `rate` | `175` | Speaking speed in words per minute; 175 is each provider's normal pace |

### Styling — how the video and guide look

| Setting | Default | What it does |
|---|---|---|
| `accent` | `#2563eb` | Brand color for the video's step banners, the intro title card, and headings in `guide.html` |
| `font` | `Helvetica Neue` | Font for video text and the HTML guide — any font installed on your Mac (check Font Book for exact names) |
| `font_scale` | `1.0` | Multiplier on all rendered text sizes; `1.3` for noticeably bigger banners |
| `banners` | `true` | Show the "Step 2 — Fill the form" label at the start of each segment |
| `title_card` | `true` | Open the video with a narrated title card |

### Frames and cost

| Setting | Default | What it does |
|---|---|---|
| `threshold` | `10.0` | Scene-change sensitivity. **Lower catches more**: drop to `6` if steps are being missed; raise to `18` if a busy or animated screen produces far too many frames. |
| `max_frames` | `60` | Hard cap on frames sent to the AI. This is your main cost lever — frames are most of what you pay for. |

### Output

| Setting | Default | What it does |
|---|---|---|
| `output_root` | `output` | Where results are written, relative to where you run sCLIbe. Each recording gets its own folder inside it. |

---

## Analysis providers

You need an API key for **one** of these. Pick a provider just by setting `model`; sCLIbe works out where to send the request.

| Model setting | Provider | API key | Also needs |
|---|---|---|---|
| `claude-opus-5` (default), `claude-haiku-4-5`, … | Anthropic | `ANTHROPIC_API_KEY` | — |
| `gpt-4o`, other `gpt-*` | OpenAI | `OPENAI_API_KEY` | `pip install openai` |
| `grok-4`, other `grok-*` | xAI | `XAI_API_KEY` | `pip install openai` |

```bash
sclibe config set model gpt-4o     # switch providers — that's the whole change
```

**Choosing:** `claude-opus-5` gives the best step breakdowns on subtle or unusual interfaces. `claude-haiku-4-5` costs about a fifth as much and is genuinely fine for straightforward UIs — a good default for high volume. Roughly $0.35 vs $0.07 for a 10-minute recording.

Keys go in your shell profile so every terminal has them:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc && source ~/.zshrc
```

> Cursor can't be used here — it's an editor subscription, not an API service. Its underlying models are the same ones listed above, so pointing sCLIbe at `claude-*` or `gpt-*` gets you the same intelligence directly.

---

## Narration voices

Four providers, from free to studio-grade. Narration is **free by default** — no key, no account.

| `tts` | Quality | Cost | Needs |
|---|---|---|---|
| `edge` *(default)* | Very good neural voices | Free | Internet (falls back to `say` automatically when offline) |
| `say` | Robotic but serviceable | Free | Nothing — built into macOS, works offline |
| `openai` | Excellent | ~$0.015/min | `OPENAI_API_KEY` + `pip install openai` |
| `elevenlabs` | Best available | Free tier ~10 min/month; plans from $5/month | `ELEVENLABS_API_KEY` |

Finding voice names for each provider:

```bash
.venv/bin/edge-tts --list-voices | grep en-US   # edge, e.g. en-US-EmmaMultilingualNeural
say -v '?'                                       # say, e.g. "Ava (Premium)"
```

For `openai` use a voice name like `onyx` or `alloy`; for `elevenlabs` use a **voice ID** from your VoiceLab (elevenlabs.io → Voices → the ID under a voice).

**Free upgrade for `say`:** download an Enhanced voice under System Settings → Accessibility → Spoken Content → Manage Voices, then `sclibe config set voice "Ava (Premium)"`.

Re-voicing an existing video is free and takes seconds — it reuses the AI analysis:

```bash
sclibe rec.mov --voice en-US-EmmaMultilingualNeural --from narrate
```

---

## Saved voices

Rather than pasting voice IDs, save them under names you'll remember. Each saved voice remembers its provider, so switching voices switches providers too.

```bash
sclibe voices                                          # list them; the active one is marked
sclibe voices add narrator elevenlabs UgBBYS2sOqTuMpoF3BR0
sclibe voices add backup edge en-US-EmmaMultilingualNeural
sclibe voices use narrator                             # make it the narration voice
```

A saved name works anywhere a voice is accepted, which makes auditioning easy:

```bash
sclibe rec.mov --voice backup --from narrate     # try the other one, free
```

These all mean the same thing, so you don't have to remember an exact phrasing: `sclibe voices use NAME`, `sclibe voice use NAME`, `sclibe config voice use NAME`, and `set` / `select` / `switch` in place of `use`.

---

## Recipes

**Set up your brand once** — every future run uses it automatically:

```bash
sclibe config set accent "#0E7C5B"
sclibe config set font "Avenir Next"
sclibe voices add narrator elevenlabs YOUR_VOICE_ID
sclibe voices use narrator
```

**Cheap mode for drafts** (~$0.07 instead of ~$0.35 per 10 minutes):

```bash
sclibe config set model claude-haiku-4-5
```

**Share settings with your team** — commit a `sclibe.json` in a shared repo; anyone running sCLIbe from that folder gets the same branding, since a project file beats the personal one.

**A different look for one client** — put a `sclibe.json` with their colors in their folder and run from there; your `~/.sclibe.json` still applies everywhere else.

**Plain video, no overlays:**

```bash
sclibe config set banners false
sclibe config set title_card false
```

---

## See also

- [Command reference](commands.md) — every command and flag, including the ones not tied to a setting
- [Usage guide](usage.md) — recording well, reading the output, editing results
- [Troubleshooting](troubleshooting.md) — when a voice, key, or provider misbehaves
