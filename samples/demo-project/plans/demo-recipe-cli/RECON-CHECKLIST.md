# RECON-CHECKLIST — demo-recipe-cli
# All items verified before Freeze (2026-08-19). Format: `- [ ]` = unchecked,
# `- [x]` = verified, "DEFERRED" = owner-approved postponement.

- [x] EXISTS: recipes.csv — the master index (120 data rows + header)
- [x] EXISTS: recipes/ — one .md file per recipe, slug filenames
- [x] Python 3.11 is the default interpreter (`python --version` → Python 3.11.9)
- [x] recipes.csv header row is exactly: name,category,source,notes
- [x] No existing recipe slug collides with the planned dist/ output folder
- [x] PowerShell 7 is the owner shell; the repo folder is the working directory
