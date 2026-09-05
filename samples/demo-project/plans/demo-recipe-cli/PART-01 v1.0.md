PART 01 — demo-recipe-cli | v1.0 frozen 2026-08-20

PART 01 — PROJECT CONTEXT: demo-recipe-cli
Owner-maintained. Freeze as "PART-01 v1.0" (file "PART-01 v1.0.md",
written by the Plan Console "Freeze" button) before Session 1; edits
require a version bump + owner approval. Sections A–F mandatory; G
recommended.

A. MISSION & SCOPE
   Mission: give the owner a small offline CLI ("rc") that manages a
   personal recipe collection: append new recipes, list, search, and
   export a single-file HTML cookbook — while never modifying the
   existing recipes.csv rows or the recipes/ folder contents.
   Session budget: 2 sessions.
   Session map (gates column: use stable ids — "g1: pytest green, g2: parity vs RECON §4"):
     # | one-line scope | gates | deploy?
     1 | recipes.csv loader + add/list/search commands | g1, g2 | no
     2 | export to dist/cookbook.html + pytest suite + packaging | g3, g4 | no
   Legacy inventory: recipes.csv (master index), recipes/ (one .md per
   recipe — the owner's master copies)
   Out of scope: editing or reorganizing existing recipes; any AI or
   network feature; anything beyond the four CLI verbs.

B. VERIFIED INFRASTRUCTURE FACTS   (every line: fact — verified YYYY-MM-DD)
   - Python 3.11 is the default interpreter — VERIFIED 2026-08-18 (owner-run: python --version)
   - recipes.csv is append-only for this tool; header row: name,category,source,notes — VERIFIED 2026-08-18 (owner-run: Get-Content recipes.csv -TotalCount 1)
   - recipes/ holds 120 .md files named <slug>.md — VERIFIED 2026-08-19 (recon: EXISTS check)
   - PowerShell 7 is the owner shell; the repo folder is the working directory — VERIFIED 2026-08-19 (recon)
   - No network access is required for any session — VERIFIED 2026-08-19 (plan decision, §A)

C. TARGET STRUCTURE
   rc.py                       # entry point, argparse subcommands
   recidb.py                   # recipes.csv reader/appender (append-only)
   rendering.py                # list/search output + HTML cookbook export
   dist/cookbook.html          # generated export (never hand-edited)
   test/test_recidb.py         # pytest suite

D. ROUTING / CONFIG TABLE   (the ONLY place task→provider→model lives)
   (empty by design — the CLI performs no external model calls; this is
   an offline stdlib-only tool. Any future AI feature must define its
   row here first.)

E. BUSINESS RULES   (state only DELTAS from PART-00 defaults)
   Metering: none — no metered operations.
   Timeouts: n/a — no external providers.
   Streaming: none.
   Runtime model policy: n/a — no configured models.
   Error-code deltas: exit codes replace HTTP codes — 2 bad usage,
   3 missing file, 4 unsupported category.

F. ARTIFACTS MAP
   Source of truth: plans/demo-recipe-cli/PART-01 v1.0.md (this plan)
   Agent-appended: PROGRESS.md, BLOCKED.md
   Console-appended (agent never edits): HEALTH.md (Plan-health audit trail)
   Reference docs: recipes.csv, recipes/
   Owner-only (agent never touches): recipes/ (read-only), recipes.csv
   (append-only — existing rows immutable)

G. KNOWN QUIRKS & EXCEPTIONS
   - Windows console: recipe titles contain non-ASCII characters, so
     rc.py reconfigures sys.stdout to UTF-8 before printing.
   - §A session 2 is NOT a deploy session: "deploy" here means writing
     dist/cookbook.html locally; owner supervision unnecessary (§G
     override of the PART-00 last-session rule).
   - recipes.csv quoting: existing rows are never rewritten; the
     appender quotes only new fields that contain commas.

## OWNER ANSWERS

(All answers integrated into §A–§G on 2026-08-19; section intentionally
empty — it is a TEMPORARY inbox only while questions await the owner.)
