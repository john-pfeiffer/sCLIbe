"""shine — turn a screen recording into a step-by-step guide and a narrated video.

Pipeline: probe -> frames -> analyze -> doc -> video -> narrate
Only `analyze` costs money (one Claude API call). Every stage checkpoints its
output, so re-runs skip finished work; `--from STAGE` forces a stage (and
everything after it) to rerun — e.g. hand-edit steps.json, then `--from doc`.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import analyze as analyze_mod
from . import doc as doc_mod
from . import frames as frames_mod
from . import ingest, narrate, video as video_mod
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="shine",
        description="Turn a screen recording into a step-by-step guide and a narrated video.",
    )
    parser.add_argument("video", type=Path, help="input screen recording (.mov, .mp4, ...)")
    parser.add_argument("-o", "--output-root", type=Path, default=Path("output"),
                        help="root output directory (default: ./output)")
    parser.add_argument("--model", default="claude-opus-5",
                        help="Claude model for analysis (default: claude-opus-5; "
                             "claude-haiku-4-5 is ~5x cheaper)")
    parser.add_argument("--context", metavar="TEXT",
                        help="tell the AI what the recording shows, e.g. "
                             "\"Our WooCommerce refund process on the staging site\" — "
                             "greatly improves step titles and narration")
    parser.add_argument("--from", dest="from_stage", choices=STAGES, metavar="STAGE",
                        help=f"force re-run from this stage onward ({', '.join(STAGES)})")
    parser.add_argument("--force", action="store_true", help="re-run every stage")
    parser.add_argument("--no-video", action="store_true",
                        help="generate the written guide only")
    parser.add_argument("--voice", default="Samantha", help="macOS `say` voice (default: Samantha)")
    parser.add_argument("--rate", type=int, default=175, help="speech rate wpm (default: 175)")
    styling = parser.add_argument_group("styling")
    styling.add_argument("--accent", default="#2563eb", metavar="HEX",
                         help="brand color for banners, title card, and guide.html "
                              "(default: #2563eb)")
    styling.add_argument("--font", default="Helvetica Neue", metavar="NAME",
                         help="font for video text and guide.html — any installed Mac font "
                              "(default: Helvetica Neue)")
    styling.add_argument("--font-scale", type=float, default=1.0, metavar="N",
                         help="multiplier on rendered text sizes (default: 1.0)")
    styling.add_argument("--no-banners", action="store_true",
                         help="no step label overlay on video segments")
    styling.add_argument("--no-title-card", action="store_true",
                         help="no narrated intro card before step 1")
    parser.add_argument("--threshold", type=float, default=10.0,
                        help="scene-change sensitivity, lower = more frames (default: 10)")
    parser.add_argument("--max-frames", type=int, default=60,
                        help="cap on frames sent to the API (default: 60)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if not args.video.exists():
        sys.exit(f"error: {args.video} not found")
    try:
        ffcolor(args.accent)
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    check_tools(require_say=not args.no_video)

    job = Job(
        video=args.video,
        outdir=args.output_root / args.video.stem,
        model=args.model,
        voice=args.voice,
        rate=args.rate,
        threshold=args.threshold,
        max_frames=args.max_frames,
        context=args.context,
        style=Style(
            accent=args.accent,
            font=args.font,
            font_scale=args.font_scale,
            banners=not args.no_banners,
            title_card=not args.no_title_card,
        ),
    )
    job.work.mkdir(parents=True, exist_ok=True)

    from_index = STAGES.index(args.from_stage) if args.from_stage else None
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
