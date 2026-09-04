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

OWNER-ONLY items: append exact commands/SQL to OPEN-QUESTIONS.md under
"## Owner actions" — do not stall on them.

Emit every file you changed (RECON-CHECKLIST.md, PART-01.draft.md,
OPEN-QUESTIONS.md if touched). End with one line in your notes:
verified X / pending-owner Y / failed Z.
