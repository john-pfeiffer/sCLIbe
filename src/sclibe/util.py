"""Shared helpers: subprocess wrappers for ffmpeg/ffprobe, timestamp formatting."""

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("sclibe")

# Resolved absolute paths for external tools, filled in by check_tools(). Falling
# back to the bare name keeps unit tests and direct module use working.
TOOL_PATHS: dict[str, str] = {}

# Homebrew's bin dirs are often missing from PATH (e.g. shells without
# `brew shellenv`) — look there directly so sclibe works regardless.
FALLBACK_DIRS = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]


def find_tool(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for prefix in FALLBACK_DIRS:
        candidate = Path(prefix) / name
        if candidate.is_file():
            return str(candidate)
    return None


def tool(name: str) -> str:
    return TOOL_PATHS.get(name, name)


class ToolError(RuntimeError):
    pass


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    log.debug("$ %s", " ".join(str(c) for c in cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise ToolError(
            f"command failed ({proc.returncode}): {' '.join(str(c) for c in cmd)}\n{proc.stderr.strip()}"
        )
    return proc


def run_ffmpeg(args: list[str]) -> None:
    run([tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *[str(a) for a in args]])


def ffprobe_json(args: list[str]) -> dict:
    proc = run([tool("ffprobe"), "-v", "error", "-print_format", "json", *[str(a) for a in args]])
    return json.loads(proc.stdout)


def media_duration(path) -> float:
    info = ffprobe_json(["-show_format", str(path)])
    return float(info["format"]["duration"])


def fmt_ts(seconds: float) -> str:
    """72.4 -> '01:12'."""
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def check_tools(require_say: bool = True) -> None:
    needed = ["ffmpeg", "ffprobe"] + (["say"] if require_say else [])
    missing = []
    for name in needed:
        found = find_tool(name)
        if found:
            TOOL_PATHS[name] = found
        else:
            missing.append(name)
    if missing:
        sys.exit(
            f"error: required tool(s) not found: {', '.join(missing)}.\n"
            "Install ffmpeg with: brew install ffmpeg"
        )
