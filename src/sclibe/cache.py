"""Stage cache bookkeeping: each stage records the settings ("fingerprint") it ran
with; a stage is reused only when its outputs exist, the fingerprint still matches,
and no input file is newer than the outputs. So changing the voice reruns narration,
editing steps.json reruns doc/video/narration, and so on — automatically.
"""

import json
from pathlib import Path

STATE_FILE = "stagestate.json"


def load_state(work: Path) -> dict:
    path = work / STATE_FILE
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def record(work: Path, stage: str, fingerprint: dict) -> None:
    state = load_state(work)
    state[stage] = fingerprint
    (work / STATE_FILE).write_text(json.dumps(state, indent=2))


def stale_reason(
    old_fp: dict | None,
    new_fp: dict,
    artifact_mtimes: list[float],
    input_mtimes: list[float],
) -> str | None:
    """Why a stage must rerun, or None if the cache is good. Pure (tested)."""
    if input_mtimes and artifact_mtimes and max(input_mtimes) > min(artifact_mtimes) + 0.5:
        return "inputs changed"
    if old_fp is None:
        return None  # pre-tracking outputs: trust settings once (adopted on this run)
    if old_fp != new_fp:
        changed = sorted(k for k in new_fp if old_fp.get(k) != new_fp.get(k))
        return f"settings changed ({', '.join(changed)})"
    return None


def check(work: Path, stage: str, fingerprint: dict,
          artifacts: list[Path], inputs: list[Path]) -> str | None:
    """Filesystem-aware wrapper around stale_reason."""
    if not all(p.exists() for p in artifacts):
        return "output missing"
    return stale_reason(
        load_state(work).get(stage),
        fingerprint,
        [p.stat().st_mtime for p in artifacts],
        [p.stat().st_mtime for p in inputs if p.exists()],
    )
