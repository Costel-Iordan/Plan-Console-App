---
description: Run the agent-runnable items of a plan's RECON-CHECKLIST
argument-hint: <slug>
---
Load PART-00.md. Read plans/$ARGUMENTS/RECON-CHECKLIST.md first.

Classify each item:
- AGENT-RUNNABLE: file/dir existence, grep, reading code/config, counts
- OWNER-ONLY: anything needing credentials, DB, dashboards, SSH, live
  external calls

Pure file/directory existence checks: emit them in the exact form
`- [ ] EXISTS: <repo-relative path>` — the Plan Console Owner-pass tab
can auto-verify and tick those in local Python.

Execute every AGENT-RUNNABLE item; record actual output next to it and
tick it `- [x]`. Promote matching PART-01.draft.md §B lines to
VERIFIED <today> ONLY where the check passed. Failures stay UNVERIFIED
with a note.

HARD BAN (binding): you never run an OWNER-ONLY item — not even when
the command is right there in the checklist or you already know it
would succeed. You never deploy, never run live SQL or migrations,
never tick an owner checkbox under "## Owner actions" (`- [x]` there is
the OWNER's own assertion that they ran it — ticking it yourself makes
the Freeze gate pass over work that never happened), and you never run
the project's build/type-checker/linter/test suite. You do not write
PROGRESS.md, HEALTH.md, IN-PROGRESS.md, or "PART-01 v*.md". Recon
verifies; it does not act.

OWNER-ONLY items: append exact commands to OPEN-QUESTIONS.md under
"## Owner actions" — do not stall on them, and never run them. Use the
owner-action format from commands/new-plan.md: `- [ ] <prose>` with the
backticked command, plus `→ verifies §B "<exact §B line prefix>"` and
`(expect: …)` tags when the command confirms an UNVERIFIED §B line (the
console then offers one-click Run + VERIFIED write-back).

Emit every file you changed (RECON-CHECKLIST.md, PART-01.draft.md,
OPEN-QUESTIONS.md if touched). End with one line in your notes:
verified X / pending-owner Y / failed Z.

Next: the owner answers OPEN-QUESTIONS.md in the Plan Console Owner
pass tab (answers land in PART-01.draft.md ## OWNER ANSWERS — a
TEMPORARY inbox), then commands/owner-resolve.md <slug> integrates
them into the draft.
