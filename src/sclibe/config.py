"""Persistent settings: sclibe.json in the current directory, falling back to ~/.sclibe.json.

CLI flags override the config file; the config file overrides built-in defaults.
Context is deliberately NOT a config key — it changes per recording, so the CLI
prompts for it instead (see cli.py).
"""

import json
import sys
from pathlib import Path

from .util import log

DEFAULTS = {
    "model": "claude-opus-5",
    "voice": "Samantha",
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
    return out


def save_config(settings: dict) -> Path:
    path = Path("sclibe.json")
    path.write_text(json.dumps({k: settings[k] for k in DEFAULTS}, indent=2) + "\n")
    return path
