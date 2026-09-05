PROJECT BRIEF — pasted into the Plan Console Intake tab on 2026-08-17

I keep losing recipes. Right now I have a recipes.csv file with one row
per recipe (name, category, source, notes) and a recipes/ folder with
one Markdown file per recipe (120 files, not going anywhere — they are
my master copies).

I want a small offline CLI, "rc", that:
- add: append a new row to recipes.csv and scaffold recipes/<slug>.md
- list: print the table, optionally filtered by category
- search: search across the CSV notes column and the .md files
- export: write a clean single-file HTML cookbook from the CSV + .md files

Rules I care about:
- Never modify or rename recipes.csv or the recipes/ folder — the tool
  only APPENDS a row and CREATES a new .md file. Everything else is
  read-only.
- Pure Python 3 standard library. No pip installs, no AI features.
- Windows terminal (PowerShell) is the primary environment.
