"""Persistent settings: sclibe.json in the current directory, falling back to ~/.sclibe.json.

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
    "rate": 175,
    "threshold": 10.0,
    "max_frames": 60,
    "output_root": "output",
    "accent": "#2563eb",
    "font": "Helvetica Neue",
    "font_scale": 1.0,
    "banners": True,
    "title_card": True,
}


def config_path() -> Path | None:
    """First existing config: ./sclibe.json, then ~/.sclibe.json."""
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
    return resolve_voice(out)


def resolve_voice(settings: dict) -> dict:
    """If `voice` names an entry in the saved roster, expand it to that entry's
    provider + voice ID. Pure (tested)."""
    roster = settings.get("voices") or {}
    name = settings.get("voice")
    if name and name in roster:
        entry = roster[name]
        settings = dict(settings)
        settings["tts"] = entry.get("tts", settings["tts"])
        settings["voice"] = entry["voice"]
    return settings


def save_config(settings: dict) -> Path:
    path = Path("sclibe.json")
    path.write_text(json.dumps({k: settings[k] for k in DEFAULTS}, indent=2) + "\n")
    return path


# ---- `sclibe config` / `sclibe voices` subcommands ----

def _active_file() -> Path:
    """The config file edits go to: the one in use, else ~/.sclibe.json (created)."""
    return config_path() or Path.home() / ".sclibe.json"


def _read_file(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _write_file(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def _show() -> None:
    path = config_path()
    data = _read_file(path) if path else {}
    merge_settings({}, data)  # validate; show raw values so roster names stay readable
    print(f"config file: {path or '(none — using defaults; edits will go to ~/.sclibe.json)'}\n")
    for key in DEFAULTS:
        if key == "voices":
            continue
        source = "config" if key in data else "default"
        value = data.get(key, DEFAULTS[key])
        print(f"  {key:<12} = {value!r:<40} ({source})")
    roster = data.get("voices") or {}
    print(f"\nsaved voices ({len(roster)}):" if roster else "\nsaved voices: none — add one with: sclibe voices add NAME PROVIDER VOICE_ID")
    for name, entry in roster.items():
        active = "  <- active" if data.get("voice") == name else ""
        print(f"  {name:<14} {entry.get('tts', '?'):<11} {entry.get('voice', '?')}{active}")


def _set(key: str, raw_value: str) -> None:
    if key not in DEFAULTS or key == "voices":
        valid = ", ".join(k for k in sorted(DEFAULTS) if k != "voices")
        sys.exit(f"error: unknown key {key!r} — valid keys: {valid}\n"
                 "(voices are managed with: sclibe voices add/use)")
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
    if not path.exists():
        _write_file(path, {})
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


def command(argv: list[str]) -> None:
    """Handle `sclibe config ...` and `sclibe voices ...`."""
    cmd, rest = argv[0], argv[1:]
    if cmd == "config":
        sub = rest[0] if rest else "show"
        if sub == "show":
            _show()
        elif sub == "set" and len(rest) >= 3:
            _set(rest[1], " ".join(rest[2:]))
        elif sub == "edit":
            _edit()
        elif sub == "path":
            print(_active_file())
        else:
            sys.exit("usage: sclibe config [show | set KEY VALUE | edit | path]")
    elif cmd == "voices":
        sub = rest[0] if rest else "list"
        if sub == "list":
            _voices_list()
        elif sub == "add" and len(rest) == 4:
            _voices_add(rest[1], rest[2], rest[3])
        elif sub == "use" and len(rest) == 2:
            _voices_use(rest[1])
        else:
            sys.exit("usage: sclibe voices [list | add NAME PROVIDER VOICE_ID | use NAME]")
