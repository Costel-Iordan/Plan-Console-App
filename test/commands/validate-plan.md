---
description: Pre-freeze gap report for a plan
argument-hint: <slug>
---
Load PART-00.md. Validate plans/$ARGUMENTS/PART-01.draft.md (or the
frozen "PART-01 v1.0.md" / legacy PART-01.md if no draft) against
templates/PART-01.md. Check ONLY:
- missing mandatory sections (A–F)
- §B lines lacking verification dates
- provider/model IDs appearing outside §D
- contradictions: §D vs §G, §E vs PART-00 defaults, §A map vs §C tree
- session-map gaps: sessions without gates, deploy not last, gates
  lacking gN ids
- unanswered questions in OPEN-QUESTIONS.md (open = numbered question
  blocks, counted once per block, or legacy '?'-ending one-liners,
  outside "## Owner actions" and code fences — the Plan Console counts
  the same way)
- unresolved `- [ ]` items in RECON-CHECKLIST.md (owner-marked DEFERRED
  items count as resolved)
- leftover Q/A pairs in "## OWNER ANSWERS" (integrated or marked
  NEEDS CLARIFICATION only)

Write the findings to plans/$ARGUMENTS/VALIDATION.md (one line per
finding, overwrite previous). If none: write exactly "PART-01 READY".
Findings only — no fixes, no rewrites.
