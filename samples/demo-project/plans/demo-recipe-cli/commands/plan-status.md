---
description: Report what a plan needs next
argument-hint: <slug>
---
Read plans/$ARGUMENTS/ only. Report in ≤6 lines:
- stage: intake | recon | owner-pass (answers → owner-resolve
  integration) | validation | frozen | in-progress | done
- last PROGRESS.md line
- interrupted: IN-PROGRESS.md exists → re-run the session command (it resumes)
- blockers: unanswered questions, owner answers not yet integrated
  (## OWNER ANSWERS in PART-01.draft.md), unresolved recon items
- next action as the exact command to run
No fixes, no rewrites.
