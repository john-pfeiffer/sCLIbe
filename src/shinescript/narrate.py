"""Stage 6: macOS `say` narration, fitted per step, muxed and concatenated into the final video."""

import subprocess
from pathlib import Path

from .style import TITLE_CARD_SECONDS, Style
from .util import ToolError, log, media_duration, run, run_ffmpeg
from .video import ENCODE_ARGS, apply_chapters, concat, make_title_card

AUDIO_ARGS = ["-c:a", "aac", "-ar", "48000", "-ac", "2"]


def tts(text: str, out_aiff: Path, voice: str, rate: int) -> None:
    cmd = ["say", "-o", str(out_aiff), "-r", str(rate)]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    try:
        run(cmd)
    except ToolError as exc:
        if voice and "not" in str(exc).lower():
            raise ToolError(
                f"voice '{voice}' failed — list available voices with: say -v '?'"
            ) from exc
        raise


def fit_and_mux(segment: Path, aiff: Path, out: Path) -> None:
    """Combine a video segment with its narration. Audio is never cut:
    shorter audio is padded with silence; longer audio freeze-frames the video."""
    dur_v = media_duration(segment)
    dur_a = media_duration(aiff)
    if dur_a <= dur_v:
        run_ffmpeg([
            "-i", segment, "-i", aiff,
            "-map", "0:v", "-map", "1:a",
            "-af", "apad", "-c:v", "copy", *AUDIO_ARGS,
            "-t", f"{dur_v:.3f}",
            out,
        ])
    else:
        extra = dur_a - dur_v
        run_ffmpeg([
            "-i", segment, "-i", aiff,
            "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={extra:.3f}[v]",
            "-map", "[v]", "-map", "1:a",
            *ENCODE_ARGS, *AUDIO_ARGS,
            "-t", f"{dur_a:.3f}",
            out,
        ])


def segment_dims(meta: dict) -> tuple[int, int]:
    """Output width/height after the segments' scale=-2:'min(1080,ih)' filter."""
    height = min(1080, meta["height"])
    width = 2 * round(meta["width"] * height / meta["height"] / 2)
    return width, height


def narrate(
    steps_data: dict,
    segments: list[Path],
    workdir: Path,
    final_out: Path,
    voice: str,
    rate: int,
    style: Style,
    meta: dict,
) -> None:
    audio_dir = workdir / "audio"
    narrated_dir = workdir / "narrated"
    audio_dir.mkdir(parents=True, exist_ok=True)
    narrated_dir.mkdir(parents=True, exist_ok=True)

    steps = steps_data["steps"]
    narrated_files = []
    titles = []

    if style.title_card:
        width, height = segment_dims(meta)
        n = len(steps)
        card = make_title_card(
            steps_data["process_title"],
            f"{n} step{'s' if n != 1 else ''}",
            width, height, meta["fps"] or 30, TITLE_CARD_SECONDS, style, workdir,
        )
        intro_aiff = audio_dir / "intro.aiff"
        tts(steps_data["process_summary"], intro_aiff, voice, rate)
        intro = narrated_dir / "step-00.mp4"
        fit_and_mux(card, intro_aiff, intro)
        narrated_files.append(intro)
        titles.append("Intro")
        log.info("added narrated title card")

    for step, segment in zip(steps, segments):
        n = step["number"]
        aiff = audio_dir / f"step-{n:02d}.aiff"
        tts(step["narration"], aiff, voice, rate)
        out = narrated_dir / f"step-{n:02d}.mp4"
        fit_and_mux(segment, aiff, out)
        narrated_files.append(out)
        titles.append(f"Step {step['number']} — {step['title']}")
        log.info("narrated step %d/%d", n, len(steps))

    combined = workdir / "combined.mp4"
    concat(narrated_files, combined)
    durations = [media_duration(f) for f in narrated_files]
    apply_chapters(combined, titles, durations, final_out)
