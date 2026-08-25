"""Stage 5: cut per-step segments, concat, chapter metadata, and the intro title card."""

from pathlib import Path

from .style import BANNER_SECONDS, Style, ffcolor, fit_fontsize, title_card_mode
from .util import log, run_ffmpeg

SEGMENT_PAD = 0.25  # breathing room around each step's range

# All video encodes share these args, including constant 30fps and a fixed track
# timescale — screen recordings are variable-frame-rate (QuickTime especially), and
# concat with stream copy silently corrupts timestamps unless every part matches.
FPS = 30
ENCODE_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
    "-r", str(FPS), "-video_track_timescale", "15360",
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


def banner_filter(textfile: Path, style: Style) -> str:
    """Lower-third step label shown for the first BANNER_SECONDS of a segment."""
    return (
        f"drawtext=textfile='{textfile}':font='{style.font}':fontcolor=white"
        f":fontsize=h/22*{style.font_scale:.2f}"
        f":box=1:boxcolor={ffcolor(style.accent)}@0.85:boxborderw=14"
        f":x=w*0.03:y=h*0.88:enable='lt(t,{BANNER_SECONDS})'"
    )


def cut_segments(
    video: Path, steps: list[dict], duration: float, workdir: Path, style: Style
) -> list[Path]:
    seg_dir = workdir / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    out_files = []
    for step, (start, end) in zip(steps, padded_ranges(steps, duration)):
        out = seg_dir / f"seg-{step['number']:02d}.mp4"
        vf = "scale=-2:'min(1080,ih)'"
        if style.banners:
            textfile = seg_dir / f"banner-{step['number']:02d}.txt"
            textfile.write_text(f"Step {step['number']} — {step['title']}")
            vf += "," + banner_filter(textfile, style)
        run_ffmpeg([
            "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", video,
            "-vf", vf, *ENCODE_ARGS, "-an",
            out,
        ])
        out_files.append(out)
    log.info(
        "cut %d segments (dead time removed%s)",
        len(out_files), ", step banners on" if style.banners else "",
    )
    return out_files


def make_title_card(
    title: str, subtitle: str, width: int, height: int,
    seconds: float, style: Style, workdir: Path,
) -> Path:
    """Silent intro card matching the segments' encoding, for concat compatibility.

    Modes (see style.title_card_mode): text on the accent color, an image
    letterboxed onto the accent color, or the image with text overlaid."""
    mode = title_card_mode(style)
    out = workdir / "title-card.mp4"

    text_layers = ""
    if mode in ("text", "image+text"):
        title_file = workdir / "card-title.txt"
        sub_file = workdir / "card-subtitle.txt"
        title_file.write_text(title)
        sub_file.write_text(subtitle)
        title_size = int(fit_fontsize(title, width, height // 10) * style.font_scale)
        sub_size = max(14, int(height / 32 * style.font_scale))
        # over an image, box the text so it stays readable on any background
        box = ":box=1:boxcolor=black@0.45:boxborderw=18" if mode == "image+text" else ""
        text_layers = (
            f"drawtext=textfile='{title_file}':font='{style.font}':fontcolor=white"
            f":fontsize={title_size}:x=(w-text_w)/2:y=h*0.42-text_h/2{box},"
            f"drawtext=textfile='{sub_file}':font='{style.font}':fontcolor=white@0.85"
            f":fontsize={sub_size}:x=(w-text_w)/2:y=h*0.58{box}"
        )

    if mode in ("image", "image+text"):
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={ffcolor(style.accent)},setsar=1"
        )
        if text_layers:
            vf += "," + text_layers
        run_ffmpeg([
            "-loop", "1", "-framerate", str(FPS), "-i", style.title_card_image,
            "-t", f"{seconds:.2f}", "-vf", vf,
            *ENCODE_ARGS,
            out,
        ])
    else:
        run_ffmpeg([
            "-f", "lavfi",
            "-i", f"color=c={ffcolor(style.accent)}:s={width}x{height}:d={seconds:.2f}:r={FPS}",
            "-vf", text_layers,
            *ENCODE_ARGS,
            out,
        ])
    return out


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
