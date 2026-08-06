"""Stage 6: macOS `say` narration, fitted per step, muxed and concatenated into the final video."""

import subprocess
from pathlib import Path

from .util import ToolError, log, media_duration, run, run_ffmpeg
from .video import ENCODE_ARGS, apply_chapters, concat

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


def narrate(
    steps_data: dict,
    segments: list[Path],
    workdir: Path,
    final_out: Path,
    voice: str,
    rate: int,
) -> None:
    audio_dir = workdir / "audio"
    narrated_dir = workdir / "narrated"
    audio_dir.mkdir(parents=True, exist_ok=True)
    narrated_dir.mkdir(parents=True, exist_ok=True)

    steps = steps_data["steps"]
    narrated_files = []
    for step, segment in zip(steps, segments):
        n = step["number"]
        aiff = audio_dir / f"step-{n:02d}.aiff"
        tts(step["narration"], aiff, voice, rate)
        out = narrated_dir / f"step-{n:02d}.mp4"
        fit_and_mux(segment, aiff, out)
        narrated_files.append(out)
        log.info("narrated step %d/%d", n, len(steps))

    combined = workdir / "combined.mp4"
    concat(narrated_files, combined)
    titles = [f"Step {s['number']} — {s['title']}" for s in steps]
    durations = [media_duration(f) for f in narrated_files]
    apply_chapters(combined, titles, durations, final_out)
