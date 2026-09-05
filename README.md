# Plan Console

A single-file Tkinter desktop app that turns pasted plans, brainstorms, or
audit reports into a structured, frozen project plan — and then manages the
session lifecycle (execution, progress gates, blocked-incident resolution)
for ANY coding agent (Zoo Code, Claude Code, Cursor, …).

## Quick start

1. Install Python 3.9+ (tkinter included with the python.org installers).
2. Double-click `plan.bat` (Windows) or run `py plan-console.py`.
3. Point **Repo folder** at your project and click **Init starter repo**
   (creates `PART-00.md`, `templates/`, `commands/`).

## How it works

- **Intake** — paste a plan/brainstorm/audit; the console writes
  `plans/<slug>/SOURCE.md` and either calls the OpenRouter API (if you tick
  *Use API key*) or copies a ready-made instruction for your agent.
- **Owner pass** — answer open questions (three-line PROBLEM/QUESTION/
  RECOMMEND blocks), tick recon checklist items, and run/copy the plan's
  **Owner actions** (commands only the owner may run, from `## Owner
  actions` in OPEN-QUESTIONS.md); every answer/removal is archived
  (`owner-pass.log` + `OPEN-QUESTIONS.md.bak` — nothing is lost).
- **Freeze** — gates on zero open questions, zero unchecked recon items,
  zero unchecked owner actions and `VALIDATION.md == "PART-01 READY"`;
  writes `PART-01 v1.0.md`.
- **Sessions** — copies a session instruction (with standing orders from
  `AGENT-ORDERS.md`) for your agent; Status / Session report / Plan health
  parse `PROGRESS.md` leniently and flag drift instead of hiding it.

Full walkthrough: see `UserGuide.html` / `UserGuide.txt`. Working without an
API key: see `no-api-key-guide.pdf`.

## Security & privacy notes

- The OpenRouter API key is **never persisted** — it lives in the entry field
  for the current session only, or in the `OPENROUTER_API_KEY` environment
  variable. `plan-console.json` is gitignored.
- In API mode, the console inlines repo files into prompts (intake context
  pack: up to 8 files, ~4 KB each). **Data leaves your machine** via
  OpenRouter. Without a key, nothing is sent anywhere — instructions are
  copied for your own agent to run locally.
- Files produced by the model are only ever written inside
  `plans/<slug>/` of the target repo (path guard in `parse_files`, covered
  by unit tests).

## Tests

```bash
py -m pytest test/ -q   # or run either file directly: py test/test_parsers.py
```

- `test/test_parsers.py` — pure-parser regression tests: question-block
  counting, lenient `PROGRESS.md` parsing, recon checkbox rules, DEFERRED
  tag semantics, the `<<<FILE>>>` path guard, slug dropdown scoping,
  plan-marker scanning, owner-action parsing, and the read-only command
  whitelist (including shell-separator rejection).
- `test/test_theme.py` — theme-system tests: `THEMES` completeness and
  hex validity, guide-palette lockstep, and OS-theme/high-contrast
  detection fallbacks.

No Tk, no network, no repo access.

## Layout

| Path | Purpose |
|---|---|
| `plan-console.py` | The whole app (parsers, UI, OpenRouter client) |
| `plan.bat` | Windows launcher (handles the Store python stub) |
| `commands/`, `templates/`, `PART-00.md` | Starter files deployed into target repos |
| `AGENT-ORDERS.md` | Standing orders prepended to session instructions |
| `test/` | Parser regression tests + a fixture starter repo |
