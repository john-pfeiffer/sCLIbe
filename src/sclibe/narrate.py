"""Stage 6: TTS narration, fitted per step, muxed and concatenated into the final video."""

from pathlib import Path

from .style import TITLE_CARD_SECONDS, Style
from .tts import synth
from .util import log, media_duration, run_ffmpeg
from .video import ENCODE_ARGS, apply_chapters, concat, make_title_card

AUDIO_ARGS = ["-c:a", "aac", "-ar", "48000", "-ac", "2"]

# When narration outruns its segment, slow the video down (screen recordings
# tolerate slow motion well) so on-screen actions stay under the words that
# describe them. Beyond this factor, freeze the last frame for the remainder.
MAX_SLOWDOWN = 2.0


def stretch_plan(dur_v: float, dur_a: float) -> tuple[float, float]:
    """(setpts factor, trailing freeze seconds) to fit video to audio. Pure (tested)."""
    if dur_a <= dur_v:
        return 1.0, 0.0
    factor = min(dur_a / dur_v, MAX_SLOWDOWN)
    freeze = max(0.0, dur_a - dur_v * factor)
    return factor, freeze


def fit_and_mux(segment: Path, audio: Path, out: Path) -> None:
    """Combine a video segment with its narration. Audio is never cut: shorter
    audio is padded with silence; longer audio slows the video (then freezes)."""
    dur_v = media_duration(segment)
    dur_a = media_duration(audio)
    factor, freeze = stretch_plan(dur_v, dur_a)
    if factor == 1.0 and freeze == 0.0:
        run_ffmpeg([
            "-i", segment, "-i", audio,
            "-map", "0:v", "-map", "1:a",
            "-af", "apad", "-c:v", "copy", *AUDIO_ARGS,
            "-t", f"{dur_v:.3f}",
            out,
        ])
        return
    vf = f"[0:v]setpts={factor:.4f}*PTS"
    if freeze > 0.05:
        vf += f",tpad=stop_mode=clone:stop_duration={freeze:.3f}"
    vf += "[v]"
    run_ffmpeg([
        "-i", segment, "-i", audio,
        "-filter_complex", vf,
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
    tts_provider: str,
    voice: str | None,
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
            width, height, TITLE_CARD_SECONDS, style, workdir,
        )
        intro_audio = synth(
            steps_data["process_summary"], audio_dir / "intro", tts_provider, voice, rate
        )
        intro = narrated_dir / "step-00.mp4"
        fit_and_mux(card, intro_audio, intro)
        narrated_files.append(intro)
        titles.append("Intro")
        log.info("added narrated title card")

    for step, segment in zip(steps, segments):
        n = step["number"]
        audio = synth(step["narration"], audio_dir / f"step-{n:02d}", tts_provider, voice, rate)
        out = narrated_dir / f"step-{n:02d}.mp4"
        fit_and_mux(segment, audio, out)
        narrated_files.append(out)
        titles.append(f"Step {step['number']} — {step['title']}")
        log.info("narrated step %d/%d", n, len(steps))

    combined = workdir / "combined.mp4"
    concat(narrated_files, combined)
    durations = [media_duration(f) for f in narrated_files]
    apply_chapters(combined, titles, durations, final_out)
