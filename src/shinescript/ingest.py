"""Stage 1: probe the input video and record its metadata."""

import json
from pathlib import Path

from .util import ffprobe_json, log


def probe(video: Path, meta_path: Path) -> dict:
    info = ffprobe_json([
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,avg_frame_rate",
        "-show_entries", "format=duration",
        str(video),
    ])
    stream = info["streams"][0]
    num, _, den = stream["avg_frame_rate"].partition("/")
    fps = float(num) / float(den or 1) if float(den or 1) else 0.0
    meta = {
        "source": str(video.resolve()),
        "duration": float(info["format"]["duration"]),
        "width": stream["width"],
        "height": stream["height"],
        "fps": round(fps, 3),
    }
    meta_path.write_text(json.dumps(meta, indent=2))
    log.info(
        "probed %s: %.1fs, %dx%d @ %.1f fps",
        video.name, meta["duration"], meta["width"], meta["height"], meta["fps"],
    )
    return meta


def load_meta(meta_path: Path) -> dict:
    return json.loads(meta_path.read_text())
