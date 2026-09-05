# Complete Audit — Plan Console

- **Date:** 2026-09-04 *(rev. 3 — 2026-09-05, remediation pass)*
- **Scope:** Full project — application code, tests, starter/command/template files, config, gitignore, docs, HTML/CSS/JS assets
- **Method:** Code-review checklist (correctness, security, performance, quality, testing, documentation)
- **Changes made:** rev. 2 (2026-09-05) found 13 issues; **all 13 were fixed in this pass** — see "Remediation log" below. Re-verified: 87/87 tests pass, `py_compile` clean, all security probes re-run and passing.

> **Revision note (2026-09-05, rev. 3):** This revision re-audits the codebase after
> the v3.2–v3.5 feature wave and records the remediation of every finding from
> rev. 2. The codebase state reflected here is HEAD + the remediation commit
> (v3.5.1). Findings are kept for the audit trail with their final status.

## ✅ Health (what's solid)

| Check | Result |
|---|---|
| Test suite | **87/87 pass** in 0.80s (76 parser + 11 theme tests) — +2 whitelist-hardening tests, +1 non-Windows high-contrast test over rev. 2 |
| Compilation | `py_compile` clean |
| Secrets | `plan-console.json` contains **no API key**; key is session-only/env-var, never persisted, and the file is gitignored |
| Path guard | `parse_files()` (plan-console.py:1066) blocks `..`/backslash/absolute **and drive-letter** paths; unit-tested |
| Read-only whitelist | **Hardened (v3.5.1)**: `is_readonly_command()` (plan-console.py:646) now rejects shell separators (`; & | > < `` ` `` `$(`, newlines), PowerShell writer/cmdlet pipes (`out-file`, `set-content`, `tee-object`, `start-process`, `invoke-expression`, `foreach`), and git file-writing flags (`--output`, `--out`) — probes confirmed all bypass vectors are closed while legitimate read-only usage still passes; unit-tested (`test_is_readonly_command_rejects_shell_separators`, `test_is_readonly_command_still_allows_plain_pipes_in_args`) |
| Stale-index guards | **All write paths guarded (v3.5.1)**: `on_tick_toggle()` (plan-console.py:2698) now verifies the RECON-CHECKLIST line still matches what Refresh read; `_tick_owner_action()` (plan-console.py:2335) verifies the OPEN-QUESTIONS bullet still carries its prose — same rule as `on_answer_save`/`on_question_remove` |
| EXISTS auto-verify | **Traversal-proof (v3.5.1)**: `on_verify_exists()` (plan-console.py:2720) rejects `..`, backslashes, absolute and drive-letter paths — consistent with the `parse_files` guard |
| Starter sync | On-disk `commands/`, `templates/`, `PART-00.md` **exactly match** built-in `STARTER_FILES`; **test fixtures now synced too** (all 9 `test/commands/` + `test/templates/` copies byte-identical) |
| Agent orders | On-disk `AGENT-ORDERS.md` matches `AGENT_ORDERS_DEFAULT` verbatim |
| Theme lockstep | `THEMES` (plan-console.py:287) tokens match `assets/console.css` verbatim (light + dark) |
| Cross-platform themes | **Fixed (v3.5.1)**: `_high_contrast_active()` (plan-console.py:337) returns `False` on non-Windows — custom themes (incl. dark mode) now apply on macOS/Linux; only an unreadable Windows registry still falls back to True |
| Cross-repo slug leakage | Fixed in v3.3.1: `merge_slug_values()` (plan-console.py:224) scopes recent slugs to the current repo; unit-tested |
| Plan-marker scanning | v3.3.2 `is_plan_dir()` (plan-console.py:180) keeps non-plan directories out of the dropdown; 10 unit tests |
| Docs | `UserGuide.html` correctly links `assets/console.css` + `assets/theme.js`; `plan.bat` handles the Microsoft Store python stub; **README Tests section now documents both test files and the 87-test scope** |
| Config writes | **Single path (v3.5.1)**: `_remember_model()` (plan-console.py:3620) now persists through `_save_cfg()` instead of writing `CFG` directly |
| Worktree | **Clean** — all v3.5 command-file changes and audit fixes committed; `_validation_tmp.md` removed from the index and disk |

## 🔴 Blocking

None. (rev. 2's #1 whitelist bypass and #2 uncommitted work are both resolved — see Remediation log.)

## 🟡 Important

None open. (rev. 2's #3–#7 are all resolved — see Remediation log.)

## 🟢 Minor

None open. (rev. 2's #8–#13 are all resolved — see Remediation log.)

## Remediation log (rev. 2 → rev. 3)

| # | Finding (rev. 2 severity) | Fix | Verification |
|---|---|---|---|
| 1 | Read-only whitelist bypassable — owner-action "Run" could execute destructive chained/piped commands (🔴 Blocking) | `READONLY_FORBIDDEN_RE` added to [`is_readonly_command()`](../plan-console.py:646): rejects separators, redirections, writer cmdlets, `start-process`/`invoke-expression`, and git `--output`/`--out` flags | 2 new unit tests + live probes (8 bypass vectors → all `False`; 4 legit commands → all `True`) |
| 2 | Uncommitted v3.5 command-file changes (🔴 Blocking) | Committed together with the v3.5.1 remediation | `git status` clean after commit |
| 3 | Missing stale-index guard in `on_tick_toggle()`; partial guard in `_tick_owner_action()` (🟡) | Content-aware guards added to both ([`on_tick_toggle`](../plan-console.py:2698), [`_tick_owner_action`](../plan-console.py:2335)) — line must still match what Refresh read | Code review; same guard pattern as the already-tested `on_answer_save` |
| 4 | `EXISTS` auto-verify accepted `..`/absolute/drive paths (🟡) | Path rejected before `(repo / path).exists()` in [`on_verify_exists()`](../plan-console.py:2720) | Probes: `../../outside.txt` and `C:/Windows` both blocked |
| 5 | `_validation_tmp.md` tracked in git (🟡) | `git rm --cached` + deleted from disk | `git ls-files` no longer lists it |
| 6 | 3 test fixtures drifted from built-ins (🟡) | `test/commands/{freeze-plan,session,plan-status}.md` copied from the built-in sources | Programmatic byte-compare: all 9 fixture files identical |
| 7 | `COMMAND_UPDATE_NOTE` stale (v2.8 text) (🟡) | Bumped to describe the v3.5 owner-action format changes ([plan-console.py:1059](../plan-console.py:1059)) | Matches the actual newest command-file diff |
| 8 | `.pytest_cache/` not gitignored (🟢) | Added to [.gitignore](../.gitignore) | — |
| 9 | Themes permanently disabled on non-Windows (🟢) | `_high_contrast_active()` returns `False` when there is no check to perform ([plan-console.py:337](../plan-console.py:337)) | New unit test `test_high_contrast_false_on_non_windows`; registry-unreadable fallback still `True` (tested) |
| 10 | `test_theme.py` comments cited the wrong palette source (🟢) | Comments now cite `assets/console.css` | — |
| 11 | `_remember_model()` bypassed `_save_cfg()` (🟢) | Now calls `_save_cfg()` — single config-write path | — |
| 12 | Inline `import subprocess` / `import datetime` (🟢) | Removed; module-level imports / existing `date` used | `py_compile` clean |
| 13 | README test docs stale (🟢) | Tests section rewritten: both test files, current scope, run command ([README.md](../README.md)) | — |

## Cross-cutting impact check (post-remediation)

- **Whitelist hardening vs legitimate actions:** the forbidden-pattern list only fires on separators/redirects/writer cmdlets; plain `Select-String`, `Test-Path`, `Get-Content`, `Get-ChildItem`, `git status/diff/log/show` with ordinary flags still pass (unit-tested). The Owner-pass "Run" button degrades safely to "Copy command" for anything suspicious.
- **Stale-index guards vs UX:** a guard failure always shows "changed since Refresh — click Refresh" and writes nothing; no partial-write path exists (the write happens only after all guards pass).
- **EXISTS guard vs recon flow:** blocked paths count as "not found" (never ticked), so the Freeze gate stays accurate for malformed items.
- **Non-Windows theme enablement:** `_high_contrast_active()` returning `False` on non-Windows only affects platforms that previously got NO theming; Windows behavior (registry check, unreadable → `True`) is unchanged and still unit-tested.
- **Single config-write path:** `_remember_model` → `_save_cfg` also persists `last_slug`/`recent_slugs`/window size at the same moment — strictly more consistent than the old direct write.

## Verdict

All 13 findings from rev. 2 are **resolved and verified** (87/87 tests, clean compile, security probes re-run). The v3.5 security regression (bypassable read-only whitelist) is closed with a defense-in-depth pattern check plus regression tests; the two carried-over code risks (unguarded recon tick, `EXISTS` traversal) are fixed with the same content-aware guard pattern used elsewhere; the repo is fully committed and the fixture/docs/config hygiene items are cleaned up. No open findings remain.

**Recommended next actions:** none required. For future hardening, consider (a) running the whitelisted command via an argument-vector parse instead of `powershell -Command` string execution, and (b) adding an integration test that exercises `on_verify_exists`/`on_tick_toggle` end-to-end with a temp repo.
