---
description: Execute a numbered session of a plan
argument-hint: <slug> <session-number>
---
Arguments: $ARGUMENTS → SLUG N

Load: PART-00.md → plans/SLUG/PART-01.md → plans/SLUG/PROGRESS.md →
plans/SLUG/RECON.md only if this session needs it.

Guards (stop if any fail):
- PART-01.md exists and is frozen (v-header present); drafts are not executable
- PROGRESS.md shows sessions 1..N-1 complete
- N exists in the §A session map

Scope and gates come from §A session N. If N is the deploy session:
owner-supervised; gates before AND after deploy; never proceed past a
failed post-deploy gate.

Close by appending exactly ONE canonical PROGRESS.md line (format per
PART-00 SESSION MECHANICS):
SESSION N | YYYY-MM-DD | gates: <passed gN ids> | status: PASS|PARTIAL|FAIL|BLOCKED — reason | P00 v<version>
Gate IDs come from PART-01 §A session N. Execute per PART-00. Stop after
gates pass and the PROGRESS line is appended.
