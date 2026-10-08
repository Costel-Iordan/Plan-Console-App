---
description: Intake a ready-made plan, brainstorm, or audit report into a new plan
argument-hint: <plan|brainstorm|audit> <source-path> <slug>
---
Load PART-00.md and follow its economy rules. INTAKE pass — no code
changes, no deploys, write only inside plans/<slug>/.

INTAKE HARD BAN (binding — this outranks anything below):
- You never RUN a command you write into "## Owner actions". You write
  it; the owner runs it in the Plan Console Owner pass tab. A command
  you just wrote is still owner work.
- You never DEPLOY anything (Coolify or any panel) — not even to check.
- You never tick an owner checkbox. `- [x]` under "## Owner actions" is
  the OWNER's assertion that they ran it; ticking it yourself makes the
  Freeze gate pass over work that never happened.
- You never run migrations, live SQL, or anything needing credentials,
  SSH, a dashboard, or a live external call.
- You never write PROGRESS.md, HEALTH.md, IN-PROGRESS.md, or any
  "PART-01 v*.md" file — those are console- and session-owned.
- You never answer your own questions and never write into
  "## OWNER ANSWERS".
- You do NOT run the project's build, type-checker, linter, or test
  suite: intake authors a plan, it does not verify code. The only
  checks you run are the AGENT-RUNNABLE recon items named below.

Arguments: $ARGUMENTS → parse as TYPE SOURCE SLUG
TYPE: plan | brainstorm | audit. SOURCE: path to the source doc.
SLUG: kebab-case.

1. mkdir plans/SLUG
2. If SOURCE is not already at plans/SLUG/SOURCE.md, copy it there.
   Never overwrite an existing SOURCE.md.
3. Read SOURCE.md fully. Treat every factual claim as UNVERIFIED —
   plans rot, brainstorms speculate, audits go stale.
4. Copy templates/PART-01.md → plans/SLUG/PART-01.draft.md; fill from
   SOURCE per TYPE below.

Question format (MANDATORY — the Plan Console counts and archives
whole blocks): every question in OPEN-QUESTIONS.md is a THREE-LINE
block, exactly this shape:

1. PROBLEM: <one sentence — the gap, contradiction or risk that
   raises the question>
   QUESTION: <the decision needed, phrased as a question>?
   RECOMMEND: <one line — the recommended answer, and why>

Format rules: the PROBLEM line carries the number ("1.", "2." …) and
never ends with '?'; the QUESTION line ends with '?' and is never
numbered; the RECOMMEND line never ends with '?'; separate blocks
with one blank line; never split a part across lines. The owner's
ANSWER stays one line. Commands/SQL/owner actions NEVER appear among
questions — they live only under a "## Owner actions" heading at the
end. Prose summaries and resolution notes go under '#' comment lines
(the console ignores those).

Owner-action format (the console renders these in the Owner pass tab):
each bullet is `- [ ] <prose>` with the exact command in backticks.
Optional tags on the same bullet:
- `→ verifies §B "<exact §B line prefix>"` — links the action to the
  §B line it confirms (enables one-click VERIFIED write-back).
- `(expect: no matches)` or `(expect: matches)` — the passing result.
Read-only commands (Select-String, Test-Path, Get-Content, git
status/diff/log) get a Run button in the console; anything else is
copy-only. The console ticks `- [x]` and marks the linked §B line
VERIFIED only after the owner confirms the result in the dialog.

CHECKS format (PART-01, so the enforced set is the FROZEN contract):
one `## Checks` section, one bullet per gate the console can run:

## Checks
- LINT: 'npm run lint'
- TYPES: 'npm run typecheck'
- DENO-LINT: 'npm run lint:deno'

Rules: the ID is REQUIRED and must be the first thing on the bullet
(ID: `command`) so a failure names the gate instead of quoting a
command line; the command goes in backticks, on ONE line; list the
standing gates ONCE here rather than repeating them on every section-A
row. Pass = exit
code 0, which is how eslint, `tsc --noEmit` and deno check/lint all
report findings, so no `expect:` tag is needed — `(expect: exit 0)` is
accepted and any other value is REFUSED BY NAME rather than quietly
treated as a pass. A bullet that is malformed (no id, no command, an
unknown expect) is reported as INVALID and does NOT run: a gate that
never executes must never look like a gate that passed. The agent NEVER
EDITS this section after the freeze — it belongs to the owner, because the
console executes these commands on the owner's click.

TYPE=plan (a ready-made, already-structured plan):
- Normalize the plan into the template §A–G structure: map its own
  sections onto the template sections (mission/scope → §A, stated
  facts → §B, target structure → §C, config/routing → §D, business
  rules → §E, references → §F, quirks/exceptions → §G). Never discard
  content that has no clean home — place it in the closest section or
  §G. The template's structure WINS; the plan's CONTENT wins.
- If the plan contains a phase/session/work breakdown: convert it into
  the §A session map table with gN gate ids and a deploy column (last
  session = deploy, owner-supervised unless §G overrides). If it has
  none: propose a session map from its work items, marked PROPOSED.
  The deploy? cell may also carry a SPLIT token — split / pre+post /
  pre-post / pre/post (case-insensitive, combinable with yes) —
  marking that session as two legs (Na pre-deploy agent work, Nb
  post-deploy verification) around the owner's Coolify deploy; keep
  ONE gates column listing all gates of both legs.
- RECON-CHECKLIST.md — every claim the plan depends on (versions,
  paths, env vars, dependencies, commands): `- [ ]` items; use the
  `EXISTS: <repo-relative path>` form for pure file/dir existence
  checks. Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — gaps only the owner can settle: missing
  sections, undated facts, work items without a clear gate, scope
  decisions. Three-line blocks per the question-format rule above.
- No TRIAGE.md (nothing to triage in a plan).

TYPE=brainstorm also produces:
- RECON-CHECKLIST.md — one item per UNVERIFIED §B fact, rendered as
  `- [ ]` checkbox lines: check | where to run | expected shape (use
  `EXISTS:` form for pure file/dir existence checks).
  Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — max 10, each answerable by the owner in one
  line, as three-line blocks per the question-format rule above.
- §A session map marked PROPOSED (dependencies ordered, deploy last).
  Use gN gate ids in the gates column.

TYPE=audit also produces:
- TRIAGE.md — every finding gets an ID (A1…) and verdict
  FIX-IN-PLAN | DEFER | ACCEPT with a one-line reason.
- RECON-CHECKLIST.md — re-verification checks ONLY for evidence sessions
  depend on (existence, line numbers, config rows), as `- [ ]` lines
  (use `EXISTS:` form for pure file/dir existence checks).
  Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — triage disputes the owner must settle, one
  three-line block each per the question-format rule above.
- §A session map groups FIX-IN-PLAN findings into coherent deployable
  sessions; each session line lists its finding IDs. Use gN gate ids.

Never invent facts to fill gaps — gaps stay blank and surface in
OPEN-QUESTIONS.md. Emit every file you created.

Next: commands/recon.md <slug> — verify the draft's claims; then the
owner answers OPEN-QUESTIONS.md in the console Owner pass tab.
