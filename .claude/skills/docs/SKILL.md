---
name: docs
description: Write and maintain sCLIbe's documentation (README.md and docs/) so it always matches the code. Use this whenever you add or change a flag, command, config key, provider, or pipeline behavior; whenever the user says the docs are stale, wrong, incomplete, or that they can't find something; and before committing any user-visible change. Run scripts/check_docs.py before claiming docs are up to date — rereading them is not enough, and it has caught real breakage that careful reading missed.
---

# Documentation for sCLIbe

## Why this exists

Docs here don't rot because anyone is careless — they rot because a change lands in one file and the *other* four still describe the old world. Real examples from this repo:

- A feature shipped with four analysis providers while the README still said "An Anthropic API key" was required.
- Renaming a heading silently broke a cross-reference in another file.
- The config system was fully built and documented in one buried sentence, so the user reasonably concluded it wasn't documented at all.
- Advice to run `--from doc` survived long after the cache started rebuilding automatically.

None of these are visible by rereading the file you just edited. They are visible mechanically, which is what the bundled script is for.

## Start and finish with the checker

```bash
python .claude/skills/docs/scripts/check_docs.py
```

It verifies flags (CLI `--help` vs docs, both directions), every relative link and `#anchor`, a list of phrases that must stay dead, and that each source module appears in the how-it-works table. Run it **before** you edit to see the current state, and **again after** — "I read it and it looks right" is exactly the check that missed every bug above.

When you rename something or replace documented behavior, add the dead phrase to `STALE` in the script. That's what keeps a fixed bug fixed.

## Where things belong

Each file answers one question. Putting content in the wrong one is why users can't find it.

| File | Answers | Keep out |
|---|---|---|
| `README.md` | "What is this and should I use it?" | Deep detail — link instead |
| `docs/setup.md` | "How do I install it from zero?" | Usage beyond the first run |
| `docs/usage.md` | "How do I do the thing well?" | Exhaustive flag lists |
| `docs/commands.md` | "What can I do?" — every command, flag, env var | Narrative and tutorials |
| `docs/how-it-works.md` | "How does it work internally?" | Anything a user needs to operate it |
| `docs/troubleshooting.md` | "Why did that happen?" | Feature documentation |

**One canonical home per fact.** `commands.md` owns the complete flag table; `usage.md` shows the handful people use daily and links there. Two copies of the same table drift within a week — when you catch a duplicate, delete the lesser copy and link.

## What a change requires

A user-visible change is not done until the docs match. Work down this list:

1. **New flag or command** → `commands.md` (complete reference), and `usage.md` only if it changes a common workflow. The checker fails until it's documented somewhere.
2. **New config key** → `commands.md` valid-keys list, README Configuration section, and `DEFAULTS` in `config.py` must agree.
3. **New provider or dependency** → the README **Requirements** section. This one rots fastest because it's written once at v1 and describes assumptions that quietly stop being true. Reread it in full on any change to keys, providers, or platform needs.
4. **Changed behavior** → search for the *old* behavior being taught, don't just document the new one: `grep -rn "old phrase" README.md docs/`. Then add it to `STALE`.
5. **New module** → the code-layout table in `how-it-works.md` (the checker enforces this).

## Making a feature findable

A feature documented only inside a paragraph is invisible. If a user has to already know a thing exists to find it, it isn't documented. Give anything user-facing:

- A **heading** someone would scan for (`## Configuration`, not a sentence under "Mental model")
- A **runnable example** — the shortest real command, not an abstract description
- A **row** in whatever table enumerates its category

The README's job is to make capabilities *visible* and hand off; the doc it points to carries the detail.

## Writing style

Write for a competent person who has never seen the tool. Concretely:

- **Show the command.** A fenced example beats a paragraph describing it.
- **Say what it costs.** This tool spends money and minutes; label paid steps and free ones plainly.
- **Tables for enumerable facts** (flags, keys, providers), **prose for workflows and judgment.**
- **Lead with the outcome.** "Change something, rerun, only that part rebuilds" before the mechanism.
- **Don't hedge documented behavior.** If the tool does it, state it. Save "usually/may" for genuine variability.
- **Second person, present tense.** "Run `sclibe config`" — not "the user may wish to invoke".

## Done means

- `check_docs.py` exits 0
- The change is in its canonical home, and any *other* file that mentioned the old behavior is updated
- A reader who has never used the feature could find and use it from a heading + example
- Committed — docs land in the same commit as the code they describe, so the repo is never internally inconsistent
