PART 01 — PROJECT CONTEXT: demo-journal-wip
Owner-maintained. Freeze as "PART-01 v1.0" (file "PART-01 v1.0.md",
written by the Plan Console "Freeze" button) before Session 1; edits
require a version bump + owner approval. Sections A–F mandatory; G
recommended.

A. MISSION & SCOPE
   Mission: a tiny offline CLI ("jr") that opens/creates today's journal
   entry, searches past entries, and prints per-month counts. The
   journal/ folder is read-only except for TODAY's file.
   Session budget: 1 session. (PROPOSED — confirm with the owner)
   Session map (gates column: use stable ids — "g1: pytest green, g2: parity vs RECON §4"):
     # | one-line scope | gates | deploy?
     1 | today + grep + stats commands, pytest suite | g1 | no
   Legacy inventory: journal/ (daily notes; existing entries immutable)
   Out of scope: editing old entries, any sync or backup feature.

B. VERIFIED INFRASTRUCTURE FACTS   (every line: fact — verified YYYY-MM-DD)
   - Python 3.11 is the default interpreter — UNVERIFIED (owner to confirm)
   - journal/ holds daily files named YYYY-MM-DD.md — VERIFIED 2026-08-25 (recon: EXISTS check)

C. TARGET STRUCTURE
   jr.py                # argparse: today | grep | stats

D. ROUTING / CONFIG TABLE   (the ONLY place task→provider→model lives)
   (empty by design — offline stdlib-only tool)

E. BUSINESS RULES   (state only DELTAS from PART-00 defaults)
   Metering: none. Timeouts: n/a. Streaming: none.
   Runtime model policy: n/a.
   Error-code deltas: exit 2 bad usage, exit 3 missing journal/ folder.

F. ARTIFACTS MAP
   Source of truth: plans/demo-journal-wip/PART-01 v1.0.md (once frozen)
   Agent-appended: PROGRESS.md, BLOCKED.md
   Console-appended (agent never edits): HEALTH.md (Plan-health audit trail)
   Reference docs: journal/
   Owner-only (agent never touches): journal/ entries except TODAY's file

G. KNOWN QUIRKS & EXCEPTIONS
   (none yet)

## OWNER ANSWERS (appended 2026-08-25)

- Q: 1. PROBLEM: the draft budgets one session but the stats command
      could slip — keep stats in session 1 or defer it?
   A: Keep it — session 1 covers all three commands.
