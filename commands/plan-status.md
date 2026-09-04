---
description: Report what a plan needs next
argument-hint: <slug>
---
Read plans/$ARGUMENTS/ only. Report in ≤6 lines:
- stage: intake | recon | owner-pass | validation | frozen | in-progress | done
- last PROGRESS.md line
- interrupted: IN-PROGRESS.md exists → re-run the session command (it resumes)
- blockers: unanswered questions, unresolved recon items
- next action as the exact command to run
No fixes, no rewrites.
