"""Stage 5: cut per-step segments, concat, and chapter metadata helpers."""

from pathlib import Path

from .util import log, run_ffmpeg

SEGMENT_PAD = 0.25  # breathing room around each step's range

ENCODE_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
]


def padded_ranges(steps: list[dict], duration: float) -> list[tuple[float, float]]:
    """Apply ±SEGMENT_PAD, clamped so consecutive ranges never overlap. Pure (tested)."""
    ranges = []
    for i, step in enumerate(steps):
        start = max(0.0, step["start_time"] - SEGMENT_PAD)
        end = min(duration, step["end_time"] + SEGMENT_PAD)
        if ranges and start < ranges[-1][1]:
            start = ranges[-1][1]
        ranges.append((start, max(end, start + 0.5)))
    return ranges


def cut_segments(video: Path, steps: list[dict], duration: float, workdir: Path) -> list[Path]:
    seg_dir = workdir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    out_files = []
    for step, (start, end) in zip(steps, padded_ranges(steps, duration)):
        out = seg_dir / f"seg-{step['number']:02d}.mp4"
        run_ffmpeg([
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", video,
            "-vf", "scale=-2:'min(1080,ih)'", *ENCODE_ARGS, "-an",
            out,
        ])
        out_files.append(out)
    log.info("cut %d segments (dead time removed)", len(out_files))
    return out_files


def concat(files: list[Path], out: Path) -> None:
    list_file = out.with_suffix(".txt")
    list_file.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", out])
    list_file.unlink()


def ffmetadata_escape(text: str) -> str:
    for ch in ("\\", "=", ";", "#"):
        text = text.replace(ch, "\\" + ch)
    return text.replace("\n", " ")


def chapter_spans(durations: list[float]) -> list[tuple[int, int]]:
    """Cumulative (start_ms, end_ms) per segment. Pure (tested)."""
    spans, cursor = [], 0.0
    for d in durations:
        spans.append((int(round(cursor * 1000)), int(round((cursor + d) * 1000))))
        cursor += d
    return spans


def apply_chapters(video_in: Path, titles: list[str], durations: list[float], out: Path) -> None:
    lines = [";FFMETADATA1"]
    for title, (start, end) in zip(titles, chapter_spans(durations)):
        lines += [
            "[CHAPTER]", "TIMEBASE=1/1000",
            f"START={start}", f"END={end}",
            f"title={ffmetadata_escape(title)}",
        ]
    meta_file = out.with_suffix(".ffmeta")
    meta_file.write_text("\n".join(lines) + "\n")
    run_ffmpeg(["-i", video_in, "-i", meta_file, "-map_metadata", "1", "-c", "copy", out])
    meta_file.unlink()
    log.info("wrote %s with %d chapters", out.name, len(titles))
