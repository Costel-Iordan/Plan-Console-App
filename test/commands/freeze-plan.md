---
description: Promote a validated draft to frozen PART-01 v1.0
          (agent fallback — the Plan Console "Freeze" button does this
          automatically and is the normal path)
argument-hint: <slug>
---
Load PART-00.md. Target: plans/$ARGUMENTS/

Preconditions (stop and report if any fail — never auto-resolve):
1. PART-01.draft.md exists and no "PART-01 v*.md" is present yet
2. OPEN-QUESTIONS.md has no open questions (numbered question blocks,
   counted once per block, or legacy '?'-ending one-liners, outside
   "## Owner actions" and code fences; the console counts the same way)
3. RECON-CHECKLIST.md has no unresolved `- [ ]` items (or
   owner-marked DEFERRED)
4. plans/SLUG/VALIDATION.md says "PART-01 READY" (run
   commands/validate-plan.md if missing)

If all pass:
- Write "PART-01 v1.0.md" = draft + header "PART 01 — <slug> | v1.0
  frozen <date>" (the version lives IN the filename)
- Keep the draft as history; create PROGRESS.md with header
  "# PROGRESS — <slug> | PART-01 v1.0 | <date>"
- Report "FROZEN v1.0 — N sessions mapped, deploy = session N"
