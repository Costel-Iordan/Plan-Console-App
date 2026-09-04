---
description: Pre-freeze gap report for a plan
argument-hint: <slug>
---
Load PART-00.md. Validate plans/$ARGUMENTS/PART-01.draft.md (or
PART-01.md if no draft) against templates/PART-01.md. Check ONLY:
- missing mandatory sections (A–F)
- §B lines lacking verification dates
- provider/model IDs appearing outside §D
- contradictions: §D vs §G, §E vs PART-00 defaults, §A map vs §C tree
- session-map gaps: sessions without gates, deploy not last, gates
  lacking gN ids
- unanswered questions in OPEN-QUESTIONS.md
- unresolved `- [ ]` items in RECON-CHECKLIST.md

Write the findings to plans/$ARGUMENTS/VALIDATION.md (one line per
finding, overwrite previous). If none: write exactly "PART-01 READY".
Findings only — no fixes, no rewrites.
