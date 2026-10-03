---
description: Execute a numbered session of a plan
argument-hint: <slug> <session-number>
---
Arguments: $ARGUMENTS → SLUG N (for a SPLIT deploy session the console
passes the leg as a suffix: SLUG Na / SLUG Nb — see the SPLIT-DEPLOY
PROTOCOL below)

Load: PART-00.md → the frozen plan in plans/SLUG/ ("PART-01 v1.0.md",
or whichever "PART-01 v*.md" exists; a legacy PART-01.md with a freeze
header is also valid — drafts are NOT executable) →
plans/SLUG/PROGRESS.md → plans/SLUG/RECON.md only if this session
needs it.

Guards (stop if any fail):
- the frozen PART-01 file exists (see naming above)
- PROGRESS.md shows sessions 1..N-1 complete
- for a leg argument (Na/Nb): sessions 1..N-1 complete AND, for leg b,
  leg a shows status: PASS (the Coolify deploy happens BETWEEN the legs)
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

SPLIT-DEPLOY PROTOCOL (the §A deploy? cell says split / pre+post /
pre-post / pre/post — binding):
- The deploy session has TWO legs with SEPARATE canonical lines:
  SESSION Na — pre-deploy work (every §A gate you can pass BEFORE any
  deploy). End leg a: append its canonical line, then STOP.
  SESSION Nb — post-deploy verification against the DEPLOYED build,
  run ONLY after the owner has executed the Coolify deploy (the console
  gates the Nb instruction copy on the owner's confirmation and logs it
  to HEALTH.md).
- The agent NEVER deploys. The §G agent-deploy exception does NOT
  extend to Coolify — panel access is owner-only.
- Leg a never does leg b's work; leg b never re-runs pre-deploy work.
- Gates: list ONLY the gates that passed in THAT leg; the union of both
  legs must cover the §A declared set. A leg re-run appends a
  corrective line (last wins per leg).
- Between the legs is the DEPLOY WINDOW: the agent has NOTHING to run.
Canonical examples (split deploy session 6, g7 = post-deploy smoke):
  SESSION 6a | 2026-09-16 | gates: g1, g2 | status: PASS | P00 v1.1
  SESSION 6b | 2026-09-18 | gates: g7 | status: PASS | P00 v1.1
- Prose: mention legs inside a record's note, never as a record start
  ('SESSION 6a addendum…' would open a spurious record).

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

Close by appending exactly ONE canonical PROGRESS.md line. Copy the
shape EXACTLY — five pipe-separated fields on ONE physical line:
SESSION <N> | <YYYY-MM-DD> | gates: <ids> | status: <PASS/PARTIAL/FAIL/BLOCKED> — <reason> | P00 v<version>
Worked examples (same shape, real values — keep the field order):
SESSION 3 | 2025-06-01 | gates: g1, g2 | status: PASS — 42/42 tests green; parity verified | P00 v1.1
SESSION 4 | 2025-06-02 | gates: g4 | status: PARTIAL — g5 needs an owner API key; steps in BLOCKED.md | P00 v1.1
This line is how the Plan Console reports gates in Plan health:
- ONE physical line — never wrap it, however long the reason.
- The reason sits BETWEEN the status word and the final '| P00'
  field, after an em dash — never after P00, never its own field.
- Lowercase 'gates:' and 'status:' labels with colons.
- Gate ids EXACTLY as spelled in PART-01 §A session N — never bare
  numbers, never 'all'.
- List ONLY the gates that passed (a PARTIAL line lists the passed
  subset; the reason explains the rest).
- Drop ' — <reason>' only when nothing needs saying (the line then
  ends '... | status: PASS | P00 v<version>').
- The version is the 'Version' line of YOUR PART-00.md — never copy
  the example's.
The console parses leniently and flags non-canonical lines, but
canonical is what reports cleanly.

GATE SANITY (every session): a gate that silently does nothing is WORSE
than a gate that fails, because it is reported as green. Before reporting
any gate green, confirm it actually ran IN THIS REPO:
  * typecheck - it compiled a file set, not zero files. Confirm with the
    compiler's --listFilesOnly (or equivalent) and check the file count is
    non-trivial. Printing help text and exiting 0/1 is NOT a pass.
  * tests - the runner reported a test count, and it is not 0.
If a gate command behaves unexpectedly (prints usage/help, reports a
missing script, or resolves against a different tree than you expect),
find out what it actually resolved against - its working directory and
whether a package.json / node_modules exists ABOVE the repo root - before
trusting its result. Re-run gates with absolute paths when in doubt.
Record the invocation that worked in the session notes so the next
session does not rediscover it.

Execute per PART-00. Stop after gates pass and the PROGRESS line is
appended.

Next: the next session number (Plan health shows it), or
commands/plan-status.md <slug> after the last session.
