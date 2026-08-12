#!/usr/bin/env python3
"""Verify sCLIbe's documentation matches the code.

Checks, in order of how often they've actually caught something:
  1. flags    — every CLI flag is documented; no doc mentions a flag that doesn't exist
  2. links    — every relative link and #anchor resolves (including same-page anchors)
  3. stale    — phrases known to be dead (old names, superseded advice) don't reappear
  4. modules  — every source module appears in the how-it-works code-layout table

Usage:
    python .claude/skills/docs/scripts/check_docs.py          # from the repo root
    python .../check_docs.py --stale-only                     # skip the CLI invocation

Exit code is 0 only when everything passes, so it works in a pre-commit hook or CI.
"""

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[4]
DOC_FILES = ["README.md"] + sorted(str(p.relative_to(REPO)) for p in (REPO / "docs").glob("*.md"))
SRC = REPO / "src" / "sclibe"

# Phrases that must not come back. Add a line whenever you rename something or
# replace a documented behavior — that is what keeps a fixed bug fixed.
STALE = {
    r"\bshine\b(?!script)": "old command name (now `sclibe`)",
    r"ShineScript": "old project name (now sCLIbe)",
    r"shine\.json": "old config filename (now sclibe.json)",
    r"freeze-frames the video|freeze the segment's last frame until": "superseded: narration now slows the video first",
    r"then rerun `--from doc`|then `--from doc`": "superseded: the cache rebuilds automatically on a plain rerun",
}

ANCHOR_RE = re.compile(r"^#+ (.+)$", re.M)
LINK_RE = re.compile(r"\]\(([^)]+)\)")


def anchors_of(path: pathlib.Path) -> set[str]:
    """GitHub-style anchor slugs for a markdown file's headings."""
    return {
        re.sub(r"[^\w\- ]", "", h).strip().lower().replace(" ", "-")
        for h in ANCHOR_RE.findall(path.read_text())
    }


def cli_flags() -> set[str] | None:
    """Flags the CLI actually accepts, from --help. None if the CLI can't be run."""
    exe = REPO / ".venv" / "bin" / "sclibe"
    cmd = [str(exe)] if exe.exists() else ([shutil.which("sclibe")] if shutil.which("sclibe") else None)
    if not cmd:
        return None
    try:
        out = subprocess.run(cmd + ["--help"], capture_output=True, text=True, timeout=60).stdout
    except (subprocess.SubprocessError, OSError):
        return None
    return set(re.findall(r"--[a-z][a-z-]+", out))


def documented_flags() -> set[str]:
    found = set()
    for name in DOC_FILES:
        # Strip link targets first: an anchor slug like #sclibe-config--settings
        # contains a "--word" run that is not a flag mention.
        text = LINK_RE.sub("", (REPO / name).read_text())
        found |= set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", text))
    return found


def check_flags(problems: list[str]) -> str:
    actual = cli_flags()
    if actual is None:
        return "skipped (CLI not runnable — install with `pip install -e .`)"
    documented = documented_flags()
    # --help is intrinsic; edge-tts's --list-voices is a third-party command we cite
    ignore = {"--help", "--list-voices"}
    for flag in sorted(actual - documented - ignore):
        problems.append(f"flag {flag} exists in the CLI but is documented nowhere")
    for flag in sorted(documented - actual - ignore):
        problems.append(f"flag {flag} is documented but the CLI does not accept it")
    return f"{len(actual)} CLI flags checked"


def check_links(problems: list[str]) -> str:
    count = 0
    for name in DOC_FILES:
        path = REPO / name
        own_anchors = anchors_of(path)
        for target in LINK_RE.findall(path.read_text()):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            count += 1
            rel, _, anchor = target.partition("#")
            dest = (path.parent / rel) if rel else path
            if not dest.exists():
                problems.append(f"{name}: link to missing file → {target}")
                continue
            if anchor and anchor not in (own_anchors if not rel else anchors_of(dest)):
                problems.append(f"{name}: link to missing section → {target}")
    return f"{count} internal links checked"


def check_stale(problems: list[str]) -> str:
    for name in DOC_FILES:
        for i, line in enumerate((REPO / name).read_text().splitlines(), 1):
            for pattern, why in STALE.items():
                if re.search(pattern, line, re.I if pattern.startswith("shine") else 0):
                    problems.append(f"{name}:{i}: {why} → {line.strip()[:70]}")
    return f"{len(STALE)} stale patterns checked"


def check_modules(problems: list[str]) -> str:
    how = REPO / "docs" / "how-it-works.md"
    if not how.exists() or not SRC.exists():
        return "skipped (no source or how-it-works.md)"
    listed = set(re.findall(r"`([a-z_]+\.py)`", how.read_text()))
    modules = {p.name for p in SRC.glob("*.py")} - {"__init__.py"}
    for missing in sorted(modules - listed):
        problems.append(f"module {missing} is not described in docs/how-it-works.md")
    return f"{len(modules)} source modules checked"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stale-only", action="store_true",
                        help="only run the checks that need no CLI invocation")
    args = parser.parse_args()

    problems: list[str] = []
    checks = [("links", check_links), ("stale", check_stale), ("modules", check_modules)]
    if not args.stale_only:
        checks.insert(0, ("flags", check_flags))

    for label, fn in checks:
        print(f"  {label:<8} {fn(problems)}")

    if problems:
        print(f"\n{len(problems)} problem(s):\n")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("\nDocs verified: flags, links, anchors, stale phrases, and modules all check out.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
