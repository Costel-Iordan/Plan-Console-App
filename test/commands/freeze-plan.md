---
description: Promote a validated draft to frozen PART-01 v1.0
          (agent fallback — the Plan Console "Freeze" button does this
          automatically and is the normal path)
argument-hint: <slug>
---
Load PART-00.md. Target: plans/$ARGUMENTS/

Preconditions (stop and report if any fail — never auto-resolve):
1. PART-01.draft.md exists
2. OPEN-QUESTIONS.md has no unanswered questions
3. RECON-CHECKLIST.md has no unresolved `- [ ]` items (or owner-marked DEFERRED)
4. plans/SLUG/VALIDATION.md says "PART-01 READY" (run commands/validate-plan.md if missing)

If all pass:
- Write PART-01.md = draft + header "PART 01 — <slug> | v1.0 frozen <date>"
- Keep the draft as history; create PROGRESS.md with header
  "# PROGRESS — <slug> | PART-01 v1.0 | <date>"
- Report "FROZEN v1.0 — N sessions mapped, deploy = session N"
