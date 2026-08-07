"""Stage 3: send keyframes to a vision model, get back validated steps. The one paid stage.

The analysis provider is chosen by the model name:
  claude-*  -> Anthropic  (ANTHROPIC_API_KEY)
  gpt-*/o*  -> OpenAI     (OPENAI_API_KEY, needs `pip install openai`)
  grok-*    -> xAI        (XAI_API_KEY, needs `pip install openai` — xAI is OpenAI-compatible)
"""

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

from pydantic import BaseModel

from .util import log

# $/MTok (input, output) — used only to print an actual-cost line after the call
PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "gpt-4o": (2.5, 10.0),
}


def provider_for(model: str) -> str:
    """Map a model name to its provider. Pure (tested)."""
    if model.startswith("claude"):
        return "anthropic"
    if model.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if model.startswith("grok"):
        return "xai"
    raise ValueError(
        f"can't tell which provider serves model {model!r} — "
        "use a claude-*, gpt-*, or grok-* model name"
    )


def require_key(env_var: str, hint: str) -> str:
    value = os.environ.get(env_var)
    if not value:
        sys.exit(f"error: {env_var} is not set. {hint}\n"
                 f'  export {env_var}="..."  (add it to ~/.zshrc)')
    return value


class Step(BaseModel):
    number: int
    title: str            # imperative: "Open the Orders dashboard"
    description: str      # 1-3 sentences for the written guide
    start_time: float     # seconds — beginning of the action on screen
    end_time: float       # seconds — action visibly complete
    key_frame_time: float # must equal one of the provided frame timestamps
    narration: str        # spoken TTS script sized to the segment


class StepList(BaseModel):
    process_title: str
    process_summary: str
    steps: list[Step]


SYSTEM_PROMPT = (
    "You are analyzing frames from a screen recording of a business process, to produce "
    "a step-by-step how-to guide and a narrated tutorial video. Each frame is labeled with "
    "its timestamp in seconds. Group frames into discrete user actions ('steps')."
)

TASK_INSTRUCTIONS = """\
The video is {duration:.0f} seconds long. Produce the step list, following these rules:

- One step per meaningful user action. Merge frames that show the same action in progress. \
A 10-minute recording typically yields 5-15 steps, not 40.
- start_time/end_time must bound when the action actually happens on screen. Ranges must be \
in order and must not overlap. Time between steps that shows nothing new (idle screens, \
cursor wandering, waiting for loads) must be excluded from all ranges — it will be cut from \
the video.
- key_frame_time must equal the timestamp of one of the provided frames, and must fall \
INSIDE that step's start_time..end_time range — pick the frame that best illustrates the step.
- process_summary is read aloud as the video's intro: one or two short sentences, \
30 words maximum. State what the guide covers and stop. No step enumeration, no \
"in this tutorial we will".
- narration is read aloud OVER that step's video segment, so it must stay in sync with \
what's on screen: describe only what happens between start_time and end_time, present tense, \
as if guiding the viewer while they watch. HARD LIMIT: (end_time - start_time) x 2.5 words — \
narration that runs long forces the video into slow motion. For steps shorter than \
5 seconds, use one short sentence of at most 8 words (e.g. "Click Remove, and you're done."). \
Prefer merging a very short step into its neighbor over narrating it separately. The viewer can see the screen: \
don't restate the obvious, don't give background, no preamble like "In this step". \
No markdown, no URLs spelled out character by character.
- Ignore incidental content (notifications, unrelated windows). Never transcribe passwords \
or other obviously sensitive values.
"""


def frames_hash(manifest: list[dict]) -> str:
    key = json.dumps([(f["timestamp"], f["file"]) for f in manifest])
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def sanitize(result: StepList, duration: float, frame_times: list[float]) -> StepList:
    """Deterministic cleanup of model output: clamp, sort, de-overlap, snap, renumber."""
    steps = sorted(result.steps, key=lambda s: s.start_time)
    for s in steps:
        s.start_time = max(0.0, min(s.start_time, duration))
        s.end_time = max(s.start_time + 0.5, min(s.end_time, duration))
        if frame_times:
            # snap to a real frame, preferring one inside this step's range
            in_range = [t for t in frame_times if s.start_time <= t <= s.end_time]
            pool = in_range or frame_times
            s.key_frame_time = min(pool, key=lambda t: abs(t - s.key_frame_time))
    for prev, cur in zip(steps, steps[1:]):
        if cur.start_time < prev.end_time:  # overlap: split at the midpoint
            mid = round((cur.start_time + prev.end_time) / 2, 2)
            prev.end_time = mid
            cur.start_time = mid
    for i, s in enumerate(steps, start=1):
        s.number = i
    result.steps = steps
    return result


def _call_anthropic(model: str, parts: list[tuple[str, str]], instructions: str) -> tuple:
    require_key("ANTHROPIC_API_KEY", "Get a key at console.anthropic.com.")
    import anthropic

    content: list[dict] = []
    for kind, value in parts:
        if kind == "text":
            content.append({"type": "text", "text": value})
        else:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": value},
            })
    content.append({"type": "text", "text": instructions})
    response = anthropic.Anthropic().messages.parse(
        model=model,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        output_format=StepList,
    )
    return response.parsed_output, response.usage.input_tokens, response.usage.output_tokens


def _call_openai_compat(
    model: str, parts: list[tuple[str, str]], instructions: str,
    env_var: str, hint: str, base_url: str | None,
) -> tuple:
    api_key = require_key(env_var, hint)
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit(
            f"error: {model} needs the openai package: .venv/bin/pip install openai"
        )
    content: list[dict] = []
    for kind, value in parts:
        if kind == "text":
            content.append({"type": "text", "text": value})
        else:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{value}"},
            })
    content.append({"type": "text", "text": instructions})
    client = OpenAI(api_key=api_key, base_url=base_url)
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format=StepList,
    )
    message = completion.choices[0].message
    if getattr(message, "refusal", None):
        sys.exit(f"error: {model} refused the request: {message.refusal}")
    usage = completion.usage
    return message.parsed, usage.prompt_tokens, usage.completion_tokens


CALLERS = {
    "anthropic": lambda model, parts, instructions: _call_anthropic(model, parts, instructions),
    "openai": lambda model, parts, instructions: _call_openai_compat(
        model, parts, instructions,
        "OPENAI_API_KEY", "Get a key at platform.openai.com.", None,
    ),
    "xai": lambda model, parts, instructions: _call_openai_compat(
        model, parts, instructions,
        "XAI_API_KEY", "Get a key at console.x.ai.", "https://api.x.ai/v1",
    ),
}


def analyze(
    video: Path,
    manifest: list[dict],
    frames_dir: Path,
    duration: float,
    model: str,
    steps_path: Path,
    context: str | None = None,
) -> dict:
    try:
        provider = provider_for(model)
    except ValueError as exc:
        sys.exit(f"error: {exc}")

    # provider-neutral content: ("text", str) and ("image", base64-jpeg) parts in order
    parts: list[tuple[str, str]] = []
    if context:
        parts.append(("text", f"Context from the recording's author about what this shows:\n{context}"))
    for f in manifest:
        data = base64.standard_b64encode((frames_dir / f["file"]).read_bytes()).decode()
        parts.append(("text", f"Frame at t={f['timestamp']:.1f}s:"))
        parts.append(("image", data))
    instructions = TASK_INSTRUCTIONS.format(duration=duration)

    log.info(
        "analyzing %d frames with %s via %s (this is the paid step)...",
        len(manifest), model, provider,
    )
    parsed, tokens_in, tokens_out = CALLERS[provider](model, parts, instructions)
    result = sanitize(parsed, duration, [f["timestamp"] for f in manifest])

    cost_note = ""
    for prefix, (p_in, p_out) in PRICES.items():
        if model.startswith(prefix):
            cost = tokens_in / 1e6 * p_in + tokens_out / 1e6 * p_out
            cost_note = f" ≈ ${cost:.3f}"
            break
    log.info("API usage: %d input + %d output tokens%s", tokens_in, tokens_out, cost_note)

    data = {
        "_meta": {
            "model": model,
            "frames_hash": frames_hash(manifest),
            "video": video.name,
            "duration": duration,
            "context": context,
        },
        **result.model_dump(),
    }
    steps_path.write_text(json.dumps(data, indent=2))
    log.info("wrote %s (%d steps) — hand-edit it and re-run with --from doc", steps_path, len(result.steps))
    return data


def load_steps(steps_path: Path) -> dict:
    return json.loads(steps_path.read_text())
