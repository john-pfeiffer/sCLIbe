"""sclibe (CLI Scribe) — turn a screen recording into a step-by-step guide and a narrated video.

Pipeline: probe -> frames -> analyze -> doc -> video -> narrate
Only `analyze` costs money (one Claude API call). Every stage checkpoints its
output, so re-runs skip finished work; `--from STAGE` forces a stage (and
everything after it) to rerun — e.g. hand-edit steps.json, then `--from doc`.

Settings resolution: CLI flags > sclibe.json (cwd, then ~/.sclibe.json) > defaults.
Context is prompted for interactively when not given via --context.
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import analyze as analyze_mod
from . import doc as doc_mod
from . import frames as frames_mod
from . import ingest, narrate, video as video_mod
from .config import DEFAULTS, load_config, merge_settings, save_config
from .style import Style, ffcolor
from .util import ToolError, check_tools, log

STAGES = ["probe", "frames", "analyze", "doc", "video", "narrate"]
VIDEO_STAGES = {"video", "narrate"}


@dataclass
class Job:
    video: Path
    outdir: Path
    model: str
    voice: str
    rate: int
    threshold: float
    max_frames: int
    context: str | None = None
    style: Style = field(default_factory=Style)
    meta: dict = field(default_factory=dict)
    segments: list = field(default_factory=list)

    @property
    def work(self) -> Path:
        return self.outdir / "work"

    @property
    def steps_path(self) -> Path:
        return self.outdir / "steps.json"


# ---- stage runners: each checks its artifact, runs, and records state on the Job ----

def stage_probe(job: Job, force: bool) -> None:
    meta_path = job.outdir / "meta.json"
    if meta_path.exists() and not force:
        job.meta = ingest.load_meta(meta_path)
        log.info("probe: cached")
        return
    job.meta = ingest.probe(job.video, meta_path)


def stage_frames(job: Job, force: bool) -> None:
    manifest_path = job.work / "frames.json"
    if manifest_path.exists() and not force:
        log.info("frames: cached (%s)", manifest_path)
        return
    frames_mod.select_and_extract(
        job.video, job.meta["duration"], job.work, job.threshold, job.max_frames
    )


def stage_analyze(job: Job, force: bool) -> None:
    manifest = json.loads((job.work / "frames.json").read_text())
    if job.steps_path.exists() and not force:
        cached = analyze_mod.load_steps(job.steps_path)
        if cached.get("_meta", {}).get("frames_hash") != analyze_mod.frames_hash(manifest):
            log.warning(
                "steps.json was generated from a DIFFERENT frame set — "
                "rerun with --from analyze to regenerate (this costs an API call)"
            )
        log.info("analyze: cached (steps.json) — no API cost")
        return
    analyze_mod.analyze(
        job.video, manifest, job.work / "frames", job.meta["duration"],
        job.model, job.steps_path, context=job.context,
    )


def stage_doc(job: Job, force: bool) -> None:
    if (job.outdir / "guide.md").exists() and not force:
        log.info("doc: cached")
        return
    doc_mod.generate(job.video, analyze_mod.load_steps(job.steps_path), job.outdir, job.style)


def stage_video(job: Job, force: bool) -> None:
    steps = analyze_mod.load_steps(job.steps_path)["steps"]
    seg_dir = job.work / "segments"
    expected = [seg_dir / f"seg-{s['number']:02d}.mp4" for s in steps]
    if all(f.exists() for f in expected) and not force:
        job.segments = expected
        log.info("video: cached (%d segments)", len(expected))
        return
    job.segments = video_mod.cut_segments(
        job.video, steps, job.meta["duration"], job.work, job.style
    )


def stage_narrate(job: Job, force: bool) -> None:
    final = job.outdir / "final-video.mp4"
    if final.exists() and not force:
        log.info("narrate: cached (%s)", final)
        return
    narrate.narrate(
        analyze_mod.load_steps(job.steps_path), job.segments, job.work,
        final, job.voice, job.rate, job.style, job.meta,
    )


RUNNERS = {
    "probe": stage_probe,
    "frames": stage_frames,
    "analyze": stage_analyze,
    "doc": stage_doc,
    "video": stage_video,
    "narrate": stage_narrate,
}


def build_parser() -> argparse.ArgumentParser:
    # Config-file-backed options default to None so we can tell "not given on the
    # CLI" from an explicit value; merge_settings() layers in sclibe.json + defaults.
    parser = argparse.ArgumentParser(
        prog="sclibe",
        description="Turn a screen recording into a step-by-step guide and a narrated video.",
        epilog="Persistent settings live in sclibe.json (current directory) or ~/.sclibe.json; "
               "create one with --save-config. CLI flags always win.",
    )
    parser.add_argument("video", type=Path, nargs="?", default=None,
                        help="input screen recording (.mov, .mp4, ...) — "
                             "if omitted, you'll be asked for it")
    parser.add_argument("-o", "--output-root", type=Path, default=None,
                        help=f"root output directory (default: ./{DEFAULTS['output_root']})")
    parser.add_argument("--model", default=None,
                        help=f"Claude model for analysis (default: {DEFAULTS['model']}; "
                             "claude-haiku-4-5 is ~5x cheaper)")
    parser.add_argument("--context", metavar="TEXT",
                        help="tell the AI what the recording shows — if omitted, you'll be "
                             "prompted whenever a (paid) analysis is about to run")
    parser.add_argument("--from", dest="from_stage", choices=STAGES, metavar="STAGE",
                        help=f"force re-run from this stage onward ({', '.join(STAGES)})")
    parser.add_argument("--force", action="store_true", help="re-run every stage")
    parser.add_argument("--no-video", action="store_true",
                        help="generate the written guide only")
    parser.add_argument("--voice", default=None,
                        help=f"macOS `say` voice (default: {DEFAULTS['voice']})")
    parser.add_argument("--rate", type=int, default=None,
                        help=f"speech rate wpm (default: {DEFAULTS['rate']})")
    styling = parser.add_argument_group("styling")
    styling.add_argument("--accent", default=None, metavar="HEX",
                         help="brand color for banners, title card, and guide.html "
                              f"(default: {DEFAULTS['accent']})")
    styling.add_argument("--font", default=None, metavar="NAME",
                         help="font for video text and guide.html — any installed Mac font "
                              f"(default: {DEFAULTS['font']})")
    styling.add_argument("--font-scale", type=float, default=None, metavar="N",
                         help="multiplier on rendered text sizes (default: 1.0)")
    styling.add_argument("--no-banners", action="store_true", default=None,
                         help="no step label overlay on video segments")
    styling.add_argument("--no-title-card", action="store_true", default=None,
                         help="no narrated intro card before step 1")
    parser.add_argument("--threshold", type=float, default=None,
                        help="scene-change sensitivity, lower = more frames "
                             f"(default: {DEFAULTS['threshold']:g})")
    parser.add_argument("--max-frames", type=int, default=None,
                        help=f"cap on frames sent to the API (default: {DEFAULTS['max_frames']})")
    parser.add_argument("--save-config", action="store_true",
                        help="write the effective settings to ./sclibe.json and continue")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def clean_path(raw: str) -> Path:
    """Normalize a pasted or Finder-dragged path: quotes, backslash escapes, ~. Pure (tested)."""
    text = raw.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    text = re.sub(r"\\(.)", r"\1", text)  # Terminal drag-drop escapes spaces etc.
    return Path(text).expanduser()


def prompt_for_video() -> Path:
    print("Paste the path to your screen recording (or drag the file into this window):")
    while True:
        try:
            raw = input("video> ")
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit("cancelled")
        if not raw.strip():
            sys.exit("cancelled")
        path = clean_path(raw)
        if path.is_file():
            return path
        print(f"not found: {path} — try again (Enter to cancel)")


def prompt_for_context() -> str | None:
    """One-line interactive prompt, only used when a paid analysis is about to run."""
    print(
        "\nDescribe what this recording shows — the app, the business purpose, and who\n"
        "the guide is for. This greatly improves the result. (Enter to skip)"
    )
    try:
        answer = input("context> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return answer or None


def main() -> None:
    args = build_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    settings = merge_settings(
        {
            "model": args.model,
            "voice": args.voice,
            "rate": args.rate,
            "threshold": args.threshold,
            "max_frames": args.max_frames,
            "output_root": str(args.output_root) if args.output_root else None,
            "accent": args.accent,
            "font": args.font,
            "font_scale": args.font_scale,
            "banners": False if args.no_banners else None,
            "title_card": False if args.no_title_card else None,
        },
        load_config(),
    )

    # Fail fast on environment problems before asking the user anything.
    check_tools(require_say=not args.no_video)
    try:
        ffcolor(settings["accent"])
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    if args.video is None:
        if not sys.stdin.isatty():
            sys.exit("error: no video given (usage: sclibe VIDEO)")
        args.video = prompt_for_video()
    if not args.video.exists():
        sys.exit(f"error: {args.video} not found")

    if args.save_config:
        log.info("saved settings to %s", save_config(settings))

    outdir = Path(settings["output_root"]) / args.video.stem
    from_index = STAGES.index(args.from_stage) if args.from_stage else None

    # Ask for context only when the paid analysis will actually run this time.
    context = args.context
    analyze_will_run = args.force or not (outdir / "steps.json").exists() or (
        from_index is not None and from_index <= STAGES.index("analyze")
    )
    if context is None and analyze_will_run and sys.stdin.isatty():
        context = prompt_for_context()

    job = Job(
        video=args.video,
        outdir=outdir,
        model=settings["model"],
        voice=settings["voice"],
        rate=settings["rate"],
        threshold=settings["threshold"],
        max_frames=settings["max_frames"],
        context=context,
        style=Style(
            accent=settings["accent"],
            font=settings["font"],
            font_scale=settings["font_scale"],
            banners=settings["banners"],
            title_card=settings["title_card"],
        ),
    )
    job.work.mkdir(parents=True, exist_ok=True)

    try:
        for i, stage in enumerate(STAGES):
            if args.no_video and stage in VIDEO_STAGES:
                continue
            force = args.force or (from_index is not None and i >= from_index)
            RUNNERS[stage](job, force)
    except ToolError as exc:
        sys.exit(f"error: {exc}")

    log.info("\ndone → %s", job.outdir.resolve())


if __name__ == "__main__":
    main()
