"""Machine-readable progress for wrappers (the Vibeo Mac app, scripts, editors).

With `--progress-json`, sclibe writes one JSON object per line to stdout while the
human-readable log keeps going to stderr. Events (all have an "event" key):

  {"event": "start", "video": "...", "outdir": "...", "stages": [...]}
  {"event": "stage", "stage": "frames", "status": "start" | "done" | "skipped"}
  {"event": "log",   "level": "info" | "warning" | "error", "message": "..."}
  {"event": "done",  "outdir": "...", "did_work": true, "outputs": {"guide_html": "...", ...}}
  {"event": "error", "message": "..."}

"skipped" means the stage was up to date (or excluded by --no-video), so a wrapper
can show a progress bar from the stage list without re-deriving the cache rules.
"""

import json
import logging
import sys
from pathlib import Path

OUTPUT_FILES = {
    "steps": "steps.json",
    "meta": "meta.json",
    "guide_md": "guide.md",
    "guide_html": "guide.html",
    "final_video": "final-video.mp4",
}


def format_event(event: str, **fields) -> str:
    """One NDJSON line. Paths become strings; key order is stable. Pure (tested)."""
    payload = {"event": event}
    for key, value in fields.items():
        payload[key] = str(value) if isinstance(value, Path) else value
    return json.dumps(payload, ensure_ascii=False)


def outputs_present(outdir: Path) -> dict[str, str]:
    """The named output files that exist under `outdir`. Pure given the filesystem (tested)."""
    return {
        name: str(outdir / filename)
        for name, filename in OUTPUT_FILES.items()
        if (outdir / filename).exists()
    }


class Emitter:
    """Writes events to a stream (stdout by default), flushing each line so a
    parent process sees progress as it happens."""

    def __init__(self, stream=None, enabled: bool = False):
        self.stream = stream or sys.stdout
        self.enabled = enabled

    def emit(self, event: str, **fields) -> None:
        if not self.enabled:
            return
        self.stream.write(format_event(event, **fields) + "\n")
        self.stream.flush()


class LogHandler(logging.Handler):
    """Mirrors log records as {"event": "log"} lines."""

    def __init__(self, emitter: Emitter):
        super().__init__()
        self.emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401 - logging API
        try:
            self.emitter.emit("log", level=record.levelname.lower(), message=record.getMessage())
        except Exception:  # never let progress reporting break the pipeline
            self.handleError(record)
