"""Stage 2: pick keyframe timestamps with PySceneDetect and extract API-sized JPEGs."""

import json
from pathlib import Path

from .util import log, run_ffmpeg

SETTLE_DELAY = 0.7      # sample after a scene change so the UI has settled (settle_delay setting)
MIN_GAP = 2.0           # minimum spacing between candidate frames (min_gap setting)
BACKFILL_GAP = 30.0     # gaps longer than this get interval samples...
BACKFILL_EVERY = 20.0   # ...at this spacing (safety nets, deliberately not settings)
SPARSE_INTERVAL = 15.0  # pure interval sampling when detection finds almost nothing
API_LONG_EDGE = 1568    # keeps each image ~1100-1600 tokens instead of ~4784


def detect_candidates(
    video: Path, duration: float, threshold: float, settle_delay: float = SETTLE_DELAY
) -> list[tuple[float, float]]:
    """Return [(timestamp, content_score)] for visually-distinct moments."""
    from scenedetect import SceneManager, StatsManager, open_video
    from scenedetect.detectors import ContentDetector

    stats = StatsManager()
    manager = SceneManager(stats)
    manager.add_detector(ContentDetector(threshold=threshold, min_scene_len=15))
    stream = open_video(str(video))
    manager.detect_scenes(stream, show_progress=False)

    candidates = []
    for start, _end in manager.get_scene_list():
        t = start.get_seconds()
        if t < 0.1:  # the implicit scene at 0 is handled by the always-kept first frame
            continue
        try:
            score = stats.get_metrics(start.get_frames(), ["content_val"])[0] or 0.0
        except Exception:
            score = 0.0
        candidates.append((min(t + settle_delay, duration - 0.1), float(score)))
    return candidates


def plan_timestamps(
    candidates: list[tuple[float, float]], duration: float, max_frames: int,
    min_gap: float = MIN_GAP,
) -> list[tuple[float, float]]:
    """Merge, backfill, and cap candidates. Pure function (tested)."""
    first = (min(1.0, duration / 2), 1e9)  # huge scores: never dropped by the cap
    last = (max(duration - 1.0, duration / 2), 1e9)

    # enforce minimum gap, keeping the later (more settled) candidate
    merged: list[tuple[float, float]] = []
    for t, score in sorted(candidates):
        if merged and t - merged[-1][0] < min_gap:
            merged[-1] = (t, max(score, merged[-1][1]))
        else:
            merged.append((t, score))

    if len(merged) < 5 and duration > 120:
        t = SPARSE_INTERVAL
        while t < duration - 1:
            merged.append((t, 0.0))
            t += SPARSE_INTERVAL
        merged.sort()

    # backfill long quiet stretches so slow scrolling/typing isn't missed
    points = sorted({round(t, 2): s for t, s in [first, *merged, last]}.items())
    filled: list[tuple[float, float]] = []
    for i, (t, score) in enumerate(points):
        filled.append((t, score))
        if i + 1 < len(points):
            gap_end = points[i + 1][0]
            fill = t + BACKFILL_EVERY
            while gap_end - t > BACKFILL_GAP and fill < gap_end - min_gap:
                filled.append((fill, 0.0))
                fill += BACKFILL_EVERY

    filled.sort()
    if len(filled) > max_frames:
        # drop lowest-score frames until under the cap (first/last are score 1e9)
        keep = sorted(sorted(filled, key=lambda p: -p[1])[:max_frames])
        filled = keep
    return filled


def select_and_extract(
    video: Path, duration: float, work: Path, threshold: float, max_frames: int,
    settle_delay: float = SETTLE_DELAY, min_gap: float = MIN_GAP,
) -> list[dict]:
    frames_dir = work / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    log.info("detecting scene changes (threshold=%.1f)...", threshold)
    candidates = detect_candidates(video, duration, threshold, settle_delay)
    planned = plan_timestamps(candidates, duration, max_frames, min_gap)
    log.info("selected %d frames (%d from scene detection)", len(planned), len(candidates))

    manifest = []
    for t, score in planned:
        name = f"f_{int(t * 10):07d}.jpg"
        out = frames_dir / name
        run_ffmpeg([
            "-ss", f"{t:.3f}", "-i", video,
            "-frames:v", "1", "-q:v", "2",
            "-vf", f"scale='min({API_LONG_EDGE},iw)':-2",
            out,
        ])
        manifest.append({"timestamp": round(t, 2), "file": name, "score": round(score, 2)})

    (work / "frames.json").write_text(json.dumps(manifest, indent=2))
    return manifest
