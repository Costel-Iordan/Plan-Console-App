# Plan Console — bundled sample project

This is a **bundled example**, not a real project. It shows what a Plan
Console "repo folder" looks like when the full workflow has already been
run on a small, relatable task, so a first-time user can see every
artifact in its finished state before running the workflow live.

Part of the Plan Console examples, Copyright © Costel Iordan
(costel.iordan@gmail.com), licensed under the Apache License, Version 2.0.

## What is inside

```
samples/demo-project/
├── README.md                     ← you are here
└── plans/
    ├── demo-recipe-cli/          ← FINISHED example: intake → … → all sessions PASS
    │   ├── SOURCE.md               the text that was pasted into the Intake tab
    │   ├── PART-01.draft.md        the owner-approved draft (kept as history)
    │   ├── PART-01 v1.0.md         the frozen plan (written by the Freeze button)
    │   ├── RECON-CHECKLIST.md      every recon item ticked `- [x]`
    │   ├── OPEN-QUESTIONS.md       closed: 0 open questions, owner actions done
    │   ├── VALIDATION.md           says exactly "PART-01 READY" (the Freeze gate)
    │   ├── PROGRESS.md             session records, incl. a BLOCKED → PASS re-run
    │   └── HEALTH.md               console-appended Plan-health audit trail
    └── demo-journal-wip/         ← MID-WORKFLOW example: what you see BEFORE freeze
        ├── SOURCE.md               pasted brief
        ├── PART-01.draft.md        draft with one answer parked in ## OWNER ANSWERS
        ├── RECON-CHECKLIST.md      2 ticked, 1 open, 1 DEFERRED
        └── OPEN-QUESTIONS.md       2 open questions, 1 unchecked owner action
```

The example scenario is a tiny offline CLI ("rc") that manages a personal
recipe collection: it appends rows to `recipes.csv`, creates one Markdown
file per recipe, and exports a single-file HTML cookbook — without ever
modifying the owner's existing files.

## How to explore it in Plan Console

1. Start Plan Console.
2. Click **"Open sample project…"** (Intake tab) and pick a folder — the
   app copies this sample there and points the **Repo folder** field at
   it. This is the recommended way in.
3. Explore the files above. Useful things to try on the COPY:
   - Intake tab → Slug `demo-recipe-cli` → the Owner pass tab shows
     **"ready to Freeze"** state (everything green) for the finished plan.
   - Owner pass tab → Slug `demo-journal-wip` → **Refresh** → see open
     questions, the parked owner answer, and "What's blocking Freeze?".
   - Sessions tab → Slug `demo-recipe-cli` → Status / Plan health to see
     how PROGRESS.md is read.

## Important: copy before you try — never mutate the bundled sample

The app WRITES into the repo folder it points at (scaffolds, ticks
checkboxes, freezes plans). Do **not** point Plan Console at this
bundled `samples/demo-project/` folder itself:

- To explore interactively, COPY the sample to a new folder (the
  "Open sample project…" button does exactly that), or select any new
  empty folder and click **Init starter repo** — that writes the starter
  `PART-00.md`, `templates/` and `commands/` (it never overwrites
  existing files, so the sample's plan files are safe).
- This bundled copy is intentionally read-only reference material.
