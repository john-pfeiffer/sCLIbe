# Setup

Everything you need to go from a fresh Mac to a working `sclibe` command. If you already have Homebrew and Python, skip to [step 3](#3-install-sclibe).

sCLIbe is **macOS-only** — it uses the built-in `say` command for free text-to-speech.

## 1. Install Homebrew and ffmpeg

[Homebrew](https://brew.sh) is the standard Mac package manager. In Terminal:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install ffmpeg (does all the video cutting and audio work):

```bash
brew install ffmpeg
```

## 2. Install Python 3.11+

macOS ships an old Python. Install a current one:

```bash
brew install python@3.12
```

## 3. Install sCLIbe

From wherever you keep code:

```bash
git clone git@github.com:john-pfeiffer/sCLIbe.git
cd sCLIbe
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

The `.venv` is a self-contained Python environment inside the project folder — it keeps sCLIbe's dependencies from touching anything else on your machine. You'll run `source .venv/bin/activate` once per terminal session before using `sclibe`.

## 4. Get an analysis API key (one of three)

The AI step-extraction needs an API key for **one** provider — Anthropic (the default), OpenAI (`sclibe config set model gpt-4o`), or xAI (`sclibe config set model grok-4`). The steps below cover Anthropic; for the others, create a key at platform.openai.com or console.x.ai and export it as `OPENAI_API_KEY` / `XAI_API_KEY` instead.

For Anthropic (this is separate from a Claude.ai chat subscription):

1. Go to [console.anthropic.com](https://console.anthropic.com) and sign in / create an account
2. Add a small amount of billing credit (Settings → Billing) — $5 lasts a long time at ~$0.35/video
3. Go to **API Keys** → **Create Key**, and copy the key (it starts with `sk-ant-`)

Store it in your shell profile so every terminal has it:

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-YOUR-KEY-HERE"' >> ~/.zshrc
source ~/.zshrc
```

> **Never commit the key to the repo or paste it into shared documents.** Keeping it in `~/.zshrc` keeps it on your machine only.

## 5. Verify the installation

```bash
cd sCLIbe
source .venv/bin/activate
sclibe --help          # should print the usage screen
ffmpeg -version       # should print version info
say "setup complete"  # you should hear it
echo ${ANTHROPIC_API_KEY:0:7}   # should print: sk-ant-
```

If any of these fail, see [troubleshooting](troubleshooting.md).

## 6. Optional: run `sclibe` from anywhere (recommended)

By default you have to `cd` into the project and activate the venv each time. A one-time alias skips that — after this, opening a terminal and typing `sclibe` is the whole thing:

```bash
echo 'alias sclibe="$HOME/Repos/sCLIbe/.venv/bin/sclibe"' >> ~/.zshrc
source ~/.zshrc
```

(Adjust `$HOME/Repos/sCLIbe` to wherever you cloned the repo.)

> **Where output goes with the alias:** `sclibe` writes its `output/` folder — and looks for `sclibe.json` — in whatever directory you run it from. Pick one place to run it consistently (your home folder works well), or keep a `sclibe.json` there and pass `-o` when you want output elsewhere. A `~/.sclibe.json` applies no matter where you run it.

## 7. Optional: better narration voices (free)

The default macOS voices are serviceable; the **Enhanced/Premium** voices are noticeably better and free to download:

1. System Settings → **Accessibility** → **Spoken Content** → **System Voice** → **Manage Voices…**
2. Download an Enhanced voice you like (e.g. *Samantha (Enhanced)*, *Ava (Premium)*)
3. Use it with `sclibe recording.mov --voice "Ava (Premium)"`

List every installed voice with:

```bash
say -v '?'
```

## You're done

Head to the [usage guide](usage.md) to record your first process.
