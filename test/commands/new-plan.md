---
description: Intake a ready-made plan, brainstorm, or audit report into a new plan
argument-hint: <plan|brainstorm|audit> <source-path> <slug>
---
Load PART-00.md and follow its economy rules. INTAKE pass — no code
changes, no deploys, write only inside plans/<slug>/.

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
