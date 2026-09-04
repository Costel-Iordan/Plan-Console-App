---
description: Intake a brainstorm or audit report into a new plan
argument-hint: <brainstorm|audit> <source-path> <slug>
---
Load PART-00.md and follow its economy rules. INTAKE pass — no code
changes, no deploys, write only inside plans/<slug>/.

Arguments: $ARGUMENTS → parse as TYPE SOURCE SLUG
TYPE: brainstorm | audit. SOURCE: path to the source doc. SLUG: kebab-case.

1. mkdir plans/SLUG
2. If SOURCE is not already at plans/SLUG/SOURCE.md, copy it there.
   Never overwrite an existing SOURCE.md.
3. Read SOURCE.md fully. Treat every factual claim as UNVERIFIED
   (brainstorms speculate; audits rot).
4. Copy templates/PART-01.md → plans/SLUG/PART-01.draft.md; fill from SOURCE.

TYPE=brainstorm also produces:
- RECON-CHECKLIST.md — one item per UNVERIFIED §B fact, rendered as
  `- [ ]` checkbox lines: check | where to run | expected shape.
  Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — max 10, each answerable by the owner in one line.
- §A session map marked PROPOSED (dependencies ordered, deploy last).
  Use gN gate ids in the gates column.

TYPE=audit also produces:
- TRIAGE.md — every finding gets an ID (A1…) and verdict
  FIX-IN-PLAN | DEFER | ACCEPT with a one-line reason.
- RECON-CHECKLIST.md — re-verification checks ONLY for evidence sessions
  depend on (existence, line numbers, config rows), as `- [ ]` lines.
- OPEN-QUESTIONS.md — triage disputes the owner must settle.
- §A session map groups FIX-IN-PLAN findings into coherent deployable
  sessions; each session line lists its finding IDs. Use gN gate ids.

Never invent facts to fill gaps — gaps stay blank and surface in
OPEN-QUESTIONS.md. Emit every file you created.
