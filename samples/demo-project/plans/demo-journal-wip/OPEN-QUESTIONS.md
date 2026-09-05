# OPEN-QUESTIONS — demo-journal-wip
# Three-line blocks per commands/new-plan.md. The Owner pass tab counts
# these; answering one removes the whole block. Commands/SQL/owner
# actions live only under an Owner-actions heading at the end.

1. PROBLEM: the brief does not say how the "stats" output treats a month
   that has no entries.
   QUESTION: print a zero row for empty months or skip them?
   RECOMMEND: skip — cleaner output, easy to add later.

2. PROBLEM: "today" may open the wrong editor on a machine with several
   installed editors.
   QUESTION: honor the EDITOR environment variable or hardcode notepad?
   RECOMMEND: honor EDITOR, fall back to notepad on Windows.

## Owner actions

- [ ] Confirm the work-laptop Python version → verifies §B "Python 3.11 is the default interpreter" `python --version` (expect: matches)
