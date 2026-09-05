# OPEN-QUESTIONS — demo-recipe-cli
# Status: CLOSED — every question was answered by the owner on 2026-08-19
# and integrated into PART-01.draft.md (§A–§G). The console counts 0 open
# questions here; the resolved history below is deliberately written as
# '#' comment lines so the Freeze gate stays green.

# RESOLVED HISTORY (kept for the record — console-ignored comment lines)
# 1. one recipes.csv vs one file per recipe — DECIDED: recipes.csv stays the
#    index; "add" appends a row AND creates recipes/<slug>.md.
# 2. where the exported cookbook lands — DECIDED: dist/cookbook.html (a new
#    folder, never inside recipes/).
# 3. CSV encoding — DECIDED: UTF-8, comma-separated; existing rows are never
#    rewritten, new fields containing commas get quoted.

## Owner actions

- [x] Confirm the default interpreter is 3.11 on the owner machine → verifies §B "Python 3.11 is the default interpreter" `python --version` (expect: matches)
- [x] Confirm recipes.csv was untouched by the dry-run import → verifies §B "recipes.csv is append-only for this tool" `git status --porcelain` (expect: no matches)
