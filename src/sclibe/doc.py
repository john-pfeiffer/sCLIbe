"""Stage 4: written guide — full-res screenshots, guide.md, guide.html."""

from pathlib import Path

from .style import Style
from .util import fmt_ts, log, run_ffmpeg

HTML_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ --accent: {accent}; }}
  body {{ font-family: "{font}", -apple-system, "Segoe UI", sans-serif; line-height: 1.6;
         max-width: 860px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ border-bottom: 3px solid var(--accent); padding-bottom: .4rem; }}
  h3 {{ margin-top: 2.2rem; color: var(--accent); }}
  img {{ max-width: 100%; border: 1px solid #d5d5d5; border-radius: 6px;
        box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
  .ts {{ color: #777; font-size: .85em; }}
  @media print {{ img {{ box-shadow: none; }} }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def generate(video: Path, steps_data: dict, outdir: Path, style: Style) -> None:
    shots = outdir / "screenshots"
    shots.mkdir(parents=True, exist_ok=True)

    lines = [f"# {steps_data['process_title']}", "", steps_data["process_summary"], ""]
    for step in steps_data["steps"]:
        shot = shots / f"step-{step['number']:02d}.png"
        run_ffmpeg([
            "-ss", f"{step['key_frame_time']:.3f}", "-i", video,
            "-frames:v", "1", shot,
        ])
        lines += [
            f"### Step {step['number']} — {step['title']}",
            "",
            step["description"],
            "",
            f'<span class="ts">at {fmt_ts(step["start_time"])}</span>',
            "",
            f"![Step {step['number']}](screenshots/{shot.name})",
            "",
        ]

    md_text = "\n".join(lines)
    (outdir / "guide.md").write_text(md_text)

    import markdown

    html_body = markdown.markdown(md_text)
    (outdir / "guide.html").write_text(
        HTML_TEMPLATE.format(
            title=steps_data["process_title"], body=html_body,
            accent=style.accent, font=style.font,
        )
    )
    log.info("wrote guide.md and guide.html (%d steps)", len(steps_data["steps"]))
