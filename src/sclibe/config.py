"""Persistent settings: sclibe.json in the current directory, falling back to ~/.sclibe.json.

Set SCLIBE_CONFIG to a file path to use that file instead (created on first write) —
this is how a wrapper such as the Vibeo Mac app keeps its own settings separate.

CLI flags override the config file; the config file overrides built-in defaults.
Context is deliberately NOT a config key — it changes per recording, so the CLI
prompts for it instead (see cli.py).
"""

import json
import os
import sys
from pathlib import Path

from .util import log

DEFAULTS = {
    "model": "claude-opus-5",
    "tts": "edge",       # edge (free neural voices) | say | openai | elevenlabs
    "voice": None,       # provider voice name/ID, a saved name from `voices`, or None = provider default
    "voices": {},        # saved roster: {"name": {"tts": "...", "voice": "..."}}
    "pronunciations": {},  # audio-only respellings: {"Cohrt": "co-hort"} — written guide keeps the real spelling
    "rate": 175,
    "threshold": 10.0,
    "max_frames": 60,
    "settle_delay": 0.7,   # seconds after a detected change before the screenshot
    "min_gap": 2.0,        # minimum seconds between screenshots
    "max_slowdown": 2.0,   # slow-motion cap when narration outruns a segment; 1.0 = freeze only
    "output_root": "output",
    "accent": "#2563eb",
    "font": "Helvetica Neue",
    "font_scale": 1.0,
    "banners": True,
    "title_card": True,
    "title_card_image": None,  # path to an intro card image; None = accent-color background
    "title_card_text": True,   # overlay title/subtitle text on the card
    "title_text": None,        # custom card title; None = the AI-generated process title
    "subtitle_text": None,     # custom card subtitle; None = "N steps"
}


def env_config_path() -> Path | None:
    """The file named by SCLIBE_CONFIG, if the variable is set (non-empty). Pure (tested)."""
    raw = os.environ.get("SCLIBE_CONFIG", "").strip()
    return Path(raw).expanduser() if raw else None


def config_path() -> Path | None:
    """First existing config: $SCLIBE_CONFIG, then ./sclibe.json, then ~/.sclibe.json."""
    forced = env_config_path()
    if forced is not None:
        return forced if forced.exists() else None
    for candidate in (Path("sclibe.json"), Path.home() / ".sclibe.json"):
        if candidate.exists():
            return candidate
    return None


def load_config() -> dict:
    path = config_path()
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        sys.exit(f"error: {path} is not valid JSON: {exc}")
    unknown = set(data) - set(DEFAULTS)
    if unknown:
        sys.exit(
            f"error: unknown key(s) in {path}: {', '.join(sorted(unknown))}\n"
            f"valid keys: {', '.join(sorted(DEFAULTS))}"
        )
    log.info("using settings from %s", path)
    return data


def merge_settings(cli: dict, config: dict) -> dict:
    """Layer CLI (None = not given) over config over DEFAULTS. Pure (tested)."""
    out = {}
    for key, default in DEFAULTS.items():
        cli_value = cli.get(key)
        out[key] = cli_value if cli_value is not None else config.get(key, default)
    from .tts import PROVIDERS

    if out["tts"] not in PROVIDERS:
        raise ValueError(
            f"invalid tts provider {out['tts']!r} — use one of: {', '.join(PROVIDERS)}"
        )
    if out["settle_delay"] < 0:
        raise ValueError("settle_delay must be >= 0 seconds")
    if out["min_gap"] <= 0:
        raise ValueError("min_gap must be > 0 seconds")
    if out["max_slowdown"] < 1.0:
        raise ValueError("max_slowdown must be >= 1.0 (1.0 = never slow the video)")
    pron = out["pronunciations"]
    if not isinstance(pron, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in pron.items()
    ):
        raise ValueError(
            'pronunciations must map words to respellings, e.g. {"Cohrt": "co-hort"}'
        )
    return out


def resolve_voice(settings: dict) -> dict:
    """If `voice` names an entry in the saved roster, expand it to that entry's
    provider + voice ID. Applied at run time; the config file keeps the friendly
    name. Pure (tested)."""
    from .tts import PROVIDERS

    roster = settings.get("voices") or {}
    name = settings.get("voice")
    if name and name in roster:
        entry = roster[name]
        settings = dict(settings)
        settings["tts"] = entry.get("tts", settings["tts"])
        settings["voice"] = entry["voice"]
        if settings["tts"] not in PROVIDERS:
            raise ValueError(
                f"saved voice {name!r} has invalid provider {settings['tts']!r}"
            )
    return settings


def materialized(data: dict) -> dict:
    """The full current state: every setting, explicit. What the config file holds. Pure (tested)."""
    return {key: data.get(key, DEFAULTS[key]) for key in DEFAULTS}


def save_config(settings: dict) -> Path:
    path = Path("sclibe.json")
    path.write_text(json.dumps({k: settings[k] for k in DEFAULTS}, indent=2) + "\n")
    return path


# ---- `sclibe config` / `sclibe voices` subcommands ----

def _active_file() -> Path:
    """The config file edits go to: $SCLIBE_CONFIG if set, else the one in use,
    else ~/.sclibe.json (created)."""
    return env_config_path() or config_path() or Path.home() / ".sclibe.json"


def _read_file(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _write_file(path: Path, data: dict) -> None:
    """Every write materializes the FULL state, so the file is always a complete,
    hand-editable picture of the current configuration."""
    path.write_text(json.dumps(materialized(data), indent=2) + "\n")


def _show() -> None:
    path = config_path()
    data = _read_file(path) if path else {}
    merge_settings({}, data)  # validate; show raw values so roster names stay readable
    print(f"config file: {path or '(none — using defaults; edits will go to ~/.sclibe.json)'}\n")
    for key in DEFAULTS:
        if key == "voices":
            continue
        value = data.get(key, DEFAULTS[key])
        marker = "" if value == DEFAULTS[key] else "   (custom)"
        print(f"  {key:<16} = {value!r}{marker}")
    roster = data.get("voices") or {}
    print(f"\nsaved voices ({len(roster)}):" if roster else "\nsaved voices: none — add one with: sclibe voices add NAME PROVIDER VOICE_ID")
    for name, entry in roster.items():
        active = "  <- active" if data.get("voice") == name else ""
        print(f"  {name:<14} {entry.get('tts', '?'):<11} {entry.get('voice', '?')}{active}")


def _set(key: str, raw_value: str) -> None:
    if key not in DEFAULTS or key == "voices":
        valid = ", ".join(k for k in sorted(DEFAULTS) if k != "voices")
        sys.exit(f"error: unknown key {key!r} — valid keys: {valid}\n"
                 "(voices are managed with `sclibe voices add/use`, "
                 "or edit the voices block in the file directly)")
    try:
        value = json.loads(raw_value)  # numbers, booleans, null
    except json.JSONDecodeError:
        value = raw_value              # plain string
    path = _active_file()
    data = _read_file(path)
    data[key] = value
    try:
        merge_settings({}, data)       # validate before persisting
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    _write_file(path, data)
    print(f"set {key} = {value!r} in {path}")


def _edit() -> None:
    import subprocess

    path = _active_file()
    _write_file(path, _read_file(path))  # materialize full state so every key is visible
    editor = os.environ.get("EDITOR")
    if editor:
        subprocess.run([editor, str(path)])
    else:
        subprocess.run(["open", "-t", str(path)])
        print(f"opened {path}")


def _voices_list() -> None:
    path = config_path()
    data = _read_file(path) if path else {}
    roster = data.get("voices") or {}
    if not roster:
        print("no saved voices — add one with: sclibe voices add NAME PROVIDER VOICE_ID")
        return
    for name, entry in roster.items():
        active = "  <- active" if data.get("voice") == name else ""
        print(f"  {name:<14} {entry.get('tts', '?'):<11} {entry.get('voice', '?')}{active}")
    print("\nswitch with: sclibe voices use NAME")


def _voices_add(name: str, provider: str, voice_id: str) -> None:
    from .tts import PROVIDERS

    if provider not in PROVIDERS:
        sys.exit(f"error: unknown provider {provider!r} — use one of: {', '.join(PROVIDERS)}")
    path = _active_file()
    data = _read_file(path)
    data.setdefault("voices", {})[name] = {"tts": provider, "voice": voice_id}
    _write_file(path, data)
    print(f"added voice {name!r} ({provider}: {voice_id}) to {path}")
    if data.get("voice") != name:
        print(f"make it the narration voice with: sclibe voices use {name}")


def _voices_use(name: str) -> None:
    path = _active_file()
    data = _read_file(path)
    roster = data.get("voices") or {}
    if name not in roster:
        known = ", ".join(roster) or "(none saved)"
        sys.exit(f"error: no saved voice named {name!r} — saved: {known}")
    data["tts"] = roster[name].get("tts", data.get("tts", DEFAULTS["tts"]))
    data["voice"] = name
    _write_file(path, data)
    print(f"narration voice is now {name!r} ({data['tts']}: {roster[name]['voice']})")


def _voices_available(rest: list[str]) -> None:
    """`sclibe voices available PROVIDER [--json]` — the voices a provider offers."""
    from .tts import PROVIDERS, available_voices
    from .util import ToolError

    as_json = "--json" in rest
    args = [a for a in rest if a != "--json"]
    if len(args) != 1 or args[0] not in PROVIDERS:
        sys.exit(f"usage: sclibe voices available PROVIDER [--json]   (PROVIDER: {', '.join(PROVIDERS)})")
    try:
        voices = available_voices(args[0])
    except ToolError as exc:
        sys.exit(f"error: {exc}")
    except Exception as exc:  # offline, service change
        sys.exit(f"error: could not list {args[0]} voices: {exc}")
    if as_json:
        print(json.dumps(voices, indent=2))
        return
    for v in voices:
        extra = f"  {v['gender']}" if v.get("gender") else ""
        print(f"  {v['id']:<40} {v.get('locale', ''):<10}{extra}")
    print(f"\n{len(voices)} voices — use one with: sclibe voices add NAME {args[0]} VOICE_ID")


def _voices_preview(rest: list[str]) -> None:
    """`sclibe voices preview (NAME | PROVIDER VOICE_ID) [--text T] [--out PATH] [--rate N]`
    Synthesizes a sample sentence and plays it (afplay) or writes it to --out."""
    from .tts import PREVIEW_TEXT, PROVIDERS, synth
    from .util import ToolError, check_tools, run

    text, out, rate, positional = PREVIEW_TEXT, None, None, []
    it = iter(rest)
    for arg in it:
        if arg == "--text":
            text = next(it, "") or text
        elif arg == "--out":
            out = next(it, None)
        elif arg == "--rate":
            rate = next(it, None)
        else:
            positional.append(arg)
    path = config_path()
    data = _read_file(path) if path else {}
    settings = merge_settings({}, data)
    if len(positional) == 1:
        settings["voice"] = positional[0]
        if positional[0] not in (data.get("voices") or {}):
            sys.exit(f"error: no saved voice named {positional[0]!r} — "
                     "give PROVIDER VOICE_ID to preview an unsaved one")
    elif len(positional) == 2:
        if positional[0] not in PROVIDERS:
            sys.exit(f"error: unknown provider {positional[0]!r} — use one of: {', '.join(PROVIDERS)}")
        settings["tts"], settings["voice"] = positional
    elif positional:
        sys.exit("usage: sclibe voices preview [NAME | PROVIDER VOICE_ID] [--text T] [--out PATH]")
    settings = resolve_voice(settings)
    if rate is not None:
        settings["rate"] = int(rate)
    check_tools(require_say=settings["tts"] in ("say", "edge"))
    import tempfile

    base = Path(out).with_suffix("") if out else Path(tempfile.mkdtemp(prefix="sclibe-preview-")) / "preview"
    try:
        audio = synth(text, base, settings["tts"], settings["voice"], settings["rate"],
                      settings["pronunciations"])
    except ToolError as exc:
        sys.exit(f"error: {exc}")
    if out:
        print(audio)  # the extension follows the provider (.mp3 or .aiff)
        return
    print(f"playing {settings['tts']} voice {settings['voice'] or '(default)'} …")
    try:
        run(["afplay", str(audio)])
    except ToolError as exc:
        sys.exit(f"error: {exc}")


def _voices_command(rest: list[str]) -> None:
    sub = rest[0] if rest else "list"
    if sub == "list":
        _voices_list()
    elif sub == "add" and len(rest) == 4:
        _voices_add(rest[1], rest[2], rest[3])
    elif sub in ("use", "set", "select", "switch") and len(rest) == 2:
        _voices_use(rest[1])
    elif sub == "available":
        _voices_available(rest[1:])
    elif sub == "preview":
        _voices_preview(rest[1:])
    else:
        sys.exit("usage: sclibe voices [list | add NAME PROVIDER VOICE_ID | use NAME | "
                 "available PROVIDER [--json] | preview [NAME | PROVIDER VOICE_ID] [--text T] [--out PATH]]")


def command(argv: list[str]) -> None:
    """Handle `sclibe config ...` and `sclibe voices ...` (singular/nested forms too)."""
    cmd, rest = argv[0], argv[1:]
    if cmd in ("voices", "voice"):
        return _voices_command(rest)
    # cmd == "config"
    sub = rest[0] if rest else "show"
    if sub in ("voices", "voice"):
        return _voices_command(rest[1:])   # `sclibe config voice use NAME` etc.
    if sub == "show":
        _show()
    elif sub == "set" and len(rest) >= 3:
        _set(rest[1], " ".join(rest[2:]))
    elif sub == "edit":
        _edit()
    elif sub == "path":
        print(_active_file())
    else:
        sys.exit(
            "usage: sclibe config [show | set KEY VALUE | edit | path]\n"
            "       sclibe voices [list | add NAME PROVIDER VOICE_ID | use NAME | "
            "available PROVIDER | preview ...]"
        )
