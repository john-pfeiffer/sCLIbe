"""Visual styling for the video (banners, title card) and the HTML guide."""

import re
from dataclasses import dataclass

BANNER_SECONDS = 4.0       # how long the step banner stays on screen
TITLE_CARD_SECONDS = 3.5   # minimum intro card length (extends to fit narration)


@dataclass
class Style:
    accent: str = "#2563eb"       # brand color: banner background, card background, HTML accents
    font: str = "Helvetica Neue"  # any font installed on the Mac (fontconfig name)
    font_scale: float = 1.0       # multiplier on all rendered text sizes
    banners: bool = True          # lower-third step label at the start of each segment
    title_card: bool = True       # narrated intro card before step 1


def ffcolor(hex_color: str) -> str:
    """'#2563eb' -> '0x2563eb' (ffmpeg color syntax). Validates the hex. Pure (tested)."""
    value = hex_color.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError(f"invalid color {hex_color!r} — expected hex like '#2563eb'")
    return "0x" + value.lower()


def fit_fontsize(text: str, width: int, max_size: int) -> int:
    """Largest font size that keeps `text` on one line within 90% of `width`. Pure (tested)."""
    if not text:
        return max_size
    return max(16, min(max_size, int(0.9 * width / (0.6 * len(text)))))
