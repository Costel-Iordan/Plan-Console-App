---
description: Execute a numbered session of a plan
argument-hint: <slug> <session-number>
---
Arguments: $ARGUMENTS → SLUG N

Load: PART-00.md → the frozen plan in plans/SLUG/ ("PART-01 v1.0.md",
or whichever "PART-01 v*.md" exists; a legacy PART-01.md with a freeze
header is also valid — drafts are NOT executable) →
plans/SLUG/PROGRESS.md → plans/SLUG/RECON.md only if this session
needs it.

Guards (stop if any fail):
- the frozen PART-01 file exists (see naming above)
- PROGRESS.md shows sessions 1..N-1 complete
- N exists in the §A session map

IN-PROGRESS HANDSHAKE (interruption safety — binding):
START, before any work:
- If plans/SLUG/IN-PROGRESS.md exists:
  * If PROGRESS.md already shows this session complete, the marker is
    stale — delete it and proceed normally.
  * Otherwise a previous run was interrupted: read IN-PROGRESS.md
    fully, run `git status` and `git diff`, and RECONCILE — keep and
    finish work that is correct, cleanly revert work that is wrong.
    Never redo blindly, never guess.
- Write plans/SLUG/IN-PROGRESS.md exactly:
  IN PROGRESS — session <N> | started <YYYY-MM-DD> | scope: <§A row>
  worktree at start: <git status --porcelain output, or "clean">
- Then do the session work.
STOPPING WITHOUT FINISHING (owner needed, context exhausted, blocked):
- Append one line to IN-PROGRESS.md: "stopped <date> — <reason; what
  remains>". Write BLOCKED.md if the BLOCKED protocol applies. Stop.
END, after gates pass:
- Append the canonical PROGRESS.md line FIRST, THEN delete
  IN-PROGRESS.md. (If interrupted between the two, the next run sees
  both — PROGRESS.md wins; delete the stale marker.)

Scope and gates come from §A session N. If N is a deploy session:
owner-supervised; gates before AND after deploy; never proceed past a
failed post-deploy gate. EXCEPTION: if PART-01 §G explicitly assigns
deploys to the agent (e.g. authenticated Supabase CLI in the agent's
environment), the agent may execute them itself — still with gates
before and after, and ordering constraints from §G.

BLOCKED PROTOCOL (restated from PART-00 — binding):
- A failed verification gets ONE fix attempt. If the second attempt
  also fails: write plans/SLUG/BLOCKED.md containing (a) exact
  reproduction steps, (b) what you tried and what failed, (c) what you
  need from the owner (command, credential, decision) — then STOP.
  Do NOT guess around it. BLOCKED.md is a correct outcome, not a
  failure of the session.
- If BLOCKED.md already exists at session start, read it first — it is
  the record of the previous stop; resolve or ask before redoing work.
- When blocked, still append the canonical PROGRESS line with
  status: BLOCKED — one-line reason.
- RESOLUTION: when the owner fixes the cause and the session re-runs
  to PASS, close the incident by appending one line to BLOCKED.md
  ("resolved <YYYY-MM-DD> — <how it was fixed>") and RENAMING the file
  to BLOCKED-resolved.md. NEVER delete BLOCKED.md — it is the audit
  record of the failure and its fix. The Plan Console flags "blocked"
  while the file exists and clears it on the rename; the file
  BLOCKED-resolved.md triggers nothing.

Close by appending exactly ONE canonical PROGRESS.md line (format per
PART-00 SESSION MECHANICS):
SESSION N | YYYY-MM-DD | gates: <passed gN ids> | status: PASS|PARTIAL|FAIL|BLOCKED — reason | P00 v<version>
Worked example (fill in your values):
SESSION 3 | 2025-06-01 | gates: g1, g2 | status: PASS | P00 v1.1
The Plan Console reads this line to report gates in Plan health, so
keep it strictly canonical: ONE physical line; lowercase 'gates:' and
'status:' labels with colons; gate ids in gN form ('g1, g2') — never
bare numbers, never 'all'; list ONLY the gates that passed (a PARTIAL
line lists the passed subset; the reason field explains the rest). The
console parses leniently and flags non-canonical lines, but canonical
is what reports cleanly. Gate IDs come from PART-01 §A session N.
Execute per PART-00. Stop after gates pass and the PROGRESS line is
appended.

Next: the next session number (Plan health shows it), or
commands/plan-status.md <slug> after the last session.
