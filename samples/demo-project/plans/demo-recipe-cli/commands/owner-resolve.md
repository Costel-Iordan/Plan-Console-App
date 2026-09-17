---
description: Integrate owner answers, resolve validation findings, finish
             agent-runnable recon, sharpen unclear questions (never answer
             them)
argument-hint: <slug>
---
Arguments: $ARGUMENTS → SLUG

Load PART-00.md. Work only inside plans/SLUG/.

Inputs:
- plans/SLUG/PART-01.draft.md — the section "## OWNER ANSWERS" holds Q/A
  pairs supplied by the owner. Owner answers are AUTHORITATIVE FACTS.
  If a Q's text is a three-line block (PROBLEM/QUESTION/RECOMMEND),
  its RECOMMEND line is the agent's earlier suggestion — context
  only, NEVER an owner answer; integrate only the owner's answer.
- plans/SLUG/OPEN-QUESTIONS.md — questions still awaiting the owner.
- plans/SLUG/RECON-CHECKLIST.md — `- [ ]` / `- [x]` items.
- plans/SLUG/VALIDATION.md — the latest validation report, if present:
  findings ending "fix in the draft, then re-validate" are resolved by
  step 0 below (no separate fix pass is needed).

Execute in order:

0. RESOLVE VALIDATION FINDINGS. If VALIDATION.md exists and lists
   findings, apply each "fix in the draft" finding to
   PART-01.draft.md now:
   - NEVER invent facts. Add a "verified YYYY-MM-DD" marker or replace
     a placeholder ONLY when the fact is confirmed by an owner answer,
     recon evidence, or a local check you just ran; otherwise leave the
     line as it is and say in your notes why it still needs the owner.
   - Structural fixes need no new facts and are applied directly:
     session-map scope rows missing file paths, model/provider tokens
     appearing outside §D (reference §D instead), missing mandatory §E
     fields the draft already implies, contradictions between sections.
   - Do NOT edit VALIDATION.md — re-validation overwrites it.
1. INTEGRATE OWNER ANSWERS. For each Q/A pair under ## OWNER ANSWERS:
   - Move the answer's content into the correct draft section: scope or
     session-map decisions → §A; checkable facts → §B (mark
     "VERIFIED <today> — owner-confirmed" ONLY if the answer asserts a
     concrete fact); structure → §C; routing/config → §D; business
     rules → §E; artifact references → §F; quirks/exceptions → §G.
   - After integrating a pair, remove it from ## OWNER ANSWERS.
   - If an answer is ambiguous, incomplete, or contradicts the draft:
     do NOT guess its meaning. Add a NEW question to OPEN-QUESTIONS.md
     asking precisely what is unclear (quote the answer, state what
     decision is needed), and leave that pair in ## OWNER ANSWERS
     marked "NEEDS CLARIFICATION".

2. SHARPEN REMAINING QUESTIONS. For every item in OPEN-QUESTIONS.md the
   owner has not answered: if the question is vague or answerable in
   several ways, rewrite it to be concrete and one-line-answerable
   (what decision, what format, which options). You may NOT answer any
   question yourself — rewording is allowed, answering is not.
   Rewritten questions MUST keep the three-line block form
   (1. PROBLEM: … / QUESTION: …? / RECOMMEND: …); sharpen the PROBLEM
   and RECOMMEND lines too — the RECOMMEND stays a suggestion, not an
   answer. Legacy one-line questions you rewrite must be converted to
   the block form. Resolution summaries and owner commands/SQL go
   under "## Owner actions" or '#' comment lines — never as loose
   prose (the Plan Console counts one numbered block per question,
   plus legacy '?'-ending one-liners, outside "## Owner actions" and
   code fences; loose prose would break its counter).

3. FINISH AGENT-RUNNABLE RECON. Execute every RECON-CHECKLIST.md item
   you can verify locally (file/dir existence, grep, reading
   code/config, counts). Tick `- [x]` and record the actual output.
   Promote matching §B draft lines to VERIFIED <today> where the check
   passed. Failures stay `- [ ]` with a note. OWNER-ONLY items (need
   credentials/DB/dashboards/SSH): never run, never stall — ensure the
   exact command/SQL for each is listed under "## Owner actions" in
   OPEN-QUESTIONS.md.

4. Emit every file you changed (PART-01.draft.md, OPEN-QUESTIONS.md,
   RECON-CHECKLIST.md — full files). End your notes with exactly one
   line: answers integrated X / need clarification Y / questions
   sharpened Z / checklist ticked W / owner-only V / draft fixes
   applied F.

Next: commands/validate-plan.md <slug> — validation is the step after
integration; Freeze only unlocks on "PART-01 READY".
