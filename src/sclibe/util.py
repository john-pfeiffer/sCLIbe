"""Shared helpers: subprocess wrappers for ffmpeg/ffprobe, timestamp formatting."""

import json
import logging
import shutil
import subprocess
import sys

log = logging.getLogger("sclibe")


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
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *[str(a) for a in args]])


def ffprobe_json(args: list[str]) -> dict:
    proc = run(["ffprobe", "-v", "error", "-print_format", "json", *[str(a) for a in args]])
    return json.loads(proc.stdout)


def media_duration(path) -> float:
    info = ffprobe_json(["-show_format", str(path)])
    return float(info["format"]["duration"])


def fmt_ts(seconds: float) -> str:
    """72.4 -> '01:12'."""
    m, s = divmod(int(round(seconds)), 60)
    return f"{m:02d}:{s:02d}"


def check_tools(require_say: bool = True) -> None:
    missing = [t for t in ("ffmpeg", "ffprobe") if shutil.which(t) is None]
    if require_say and shutil.which("say") is None:
        missing.append("say")
    if missing:
        sys.exit(
            f"error: required tool(s) not found on PATH: {', '.join(missing)}.\n"
            "Install ffmpeg with: brew install ffmpeg"
        )
