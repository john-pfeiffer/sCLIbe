"""Text-to-speech providers.

- edge   (default): Microsoft neural voices via the edge-tts package. Free, very
         natural, needs internet. Falls back to `say` automatically when offline.
- say:   macOS built-in. Free, offline, robotic-ish. Enhanced voices help.
- openai: highest quality, ~$0.015/min, needs OPENAI_API_KEY and `pip install openai`.
"""

from pathlib import Path

from .util import ToolError, log, run

PROVIDERS = ("edge", "say", "openai")

DEFAULT_VOICES = {
    "edge": "en-US-AndrewMultilingualNeural",
    "say": "Samantha",
    "openai": "onyx",
}

BASE_RATE_WPM = 175  # `say` wpm that maps to a provider's normal speed


def synth(text: str, out_base: Path, provider: str, voice: str | None, rate: int) -> Path:
    """Generate speech for `text`; returns the audio file path (extension varies)."""
    voice = voice or DEFAULT_VOICES[provider]
    if provider == "edge":
        try:
            return _edge(text, out_base.with_suffix(".mp3"), voice, rate)
        except Exception as exc:  # offline, service change, bad voice name
            log.warning("edge TTS failed (%s) — falling back to the macOS `say` voice", exc)
            return _say(text, out_base.with_suffix(".aiff"), DEFAULT_VOICES["say"], rate)
    if provider == "openai":
        return _openai(text, out_base.with_suffix(".mp3"), voice)
    return _say(text, out_base.with_suffix(".aiff"), voice, rate)


def _say(text: str, out: Path, voice: str, rate: int) -> Path:
    cmd = ["say", "-o", str(out), "-r", str(rate), "-v", voice, text]
    try:
        run(cmd)
    except ToolError as exc:
        if "voice" in str(exc).lower() or "not" in str(exc).lower():
            raise ToolError(
                f"voice '{voice}' failed — list available voices with: say -v '?'"
            ) from exc
        raise
    return out


def _edge(text: str, out: Path, voice: str, rate: int) -> Path:
    import asyncio

    import edge_tts

    pct = round((rate / BASE_RATE_WPM - 1) * 100)
    rate_str = f"{pct:+d}%"

    async def go() -> None:
        await edge_tts.Communicate(text, voice, rate=rate_str).save(str(out))

    asyncio.run(go())
    if not out.exists() or out.stat().st_size == 0:
        raise ToolError("edge TTS produced no audio")
    return out


def _openai(text: str, out: Path, voice: str) -> Path:
    try:
        from openai import OpenAI
    except ImportError:
        raise ToolError(
            "the openai TTS provider needs the openai package: .venv/bin/pip install openai"
        ) from None
    client = OpenAI()  # needs OPENAI_API_KEY
    response = client.audio.speech.create(model="gpt-4o-mini-tts", voice=voice, input=text)
    response.write_to_file(out)
    return out
