# Complete Audit — Plan Console

- **Date:** 2026-09-04
- **Scope:** Full project — application code, tests, starter/command/template files, config, gitignore, docs, HTML/CSS/JS assets
- **Method:** Code-review checklist (correctness, security, performance, quality, testing, documentation)
- **Changes made:** None (findings only)

## ✅ Health (what's solid)

| Check | Result |
|---|---|
| Test suite | **75/75 pass** in 0.49s (55 parser + 20 theme tests) |
| Compilation | `py_compile` clean |
| Secrets | `plan-console.json` contains **no API key**; key is session-only/env-var, never persisted, and the file is gitignored |
| Path guard | `parse_files()` (plan-console.py:931) blocks `..`/backslash/absolute escapes; unit-tested (`test_parse_files_rejects_escape_paths`) |
| Starter sync | On-disk `commands/`, `templates/`, `PART-00.md` **exactly match** built-in `STARTER_FILES` |
| Theme lockstep | `THEMES` (plan-console.py:287) tokens match `assets/console.css` verbatim (light + dark) |
| Docs | `UserGuide.html` correctly links `assets/console.css` + `assets/theme.js`; `plan.bat` handles the Microsoft Store python stub properly |

## 🔴 Blocking

1. **Uncommitted work** — `git status` shows 519 uncommitted insertions across `plan-console.py` and `test/test_parsers.py` (the entire v3.2–v3.4 feature set: shared slug var, recent slugs, plan-marker scanning, slug feedback). One bad `git checkout` loses it all. **Commit first.**

## 🟡 Important

2. **Missing stale-index guard in `on_tick_toggle()` (plan-console.py:2340)** — `on_answer_save`/`on_question_remove` verify the file hasn't changed since Refresh; the recon tick does not. If the agent rewrites `RECON-CHECKLIST.md` between Refresh and tick, the toggle **modifies the wrong line**.
3. **`EXISTS` auto-verify path traversal** — `on_verify_exists()` (plan-console.py:2362) does `(repo / path).exists()` with no `..` guard, so `- [ ] EXISTS: ../../somefile` checks (and ticks) paths **outside the repo** — inconsistent with the `parse_files` guard.
4. **Test-fixture drift** — 5 files in `test/commands/` differ from the built-ins (missing trailing "Next:" lines: `new-plan.md`, `recon.md`, `freeze-plan.md`, `session.md`, `plan-status.md`). Tests don't read them, but the fixture no longer represents what Init deploys.
5. **Leftover temp file** — `_validation_tmp.md` at repo root, untracked; content duplicates the `plans/ui-ux-plan` validation report.
6. **README test docs stale** — the Tests section mentions only `test_parsers.py`; `test_theme.py` (20 tests) is undocumented.

## 🟢 Minor

7. `.gitignore` doesn't list `.pytest_cache/` (currently masked only by pytest's auto-generated internal ignore file).
8. `_high_contrast_active()` (plan-console.py:337) returns `True` on non-Windows → custom themes never apply on macOS/Linux (documented safe default, but dark mode is effectively Windows-only).
9. `test_theme.py` comments cite "UserGuide.html :root" — the palette actually lives in `assets/console.css` (UserGuide links it); comment is slightly stale.
10. `_remember_model()` (plan-console.py:3262) writes `CFG` directly, bypassing `_save_cfg()`'s field normalization — harmless duplication today.

## Verdict

The codebase is in **good shape**: security posture is sound (no persisted keys, path guards, repo-relative checks), parsers are thoroughly unit-tested, and starter files are in sync. The two real code risks are the unguarded recon tick (#2) and the `EXISTS` traversal (#3); the most urgent action is committing the v3.2–v3.4 work (#1).

**Recommended fix order:** commit the work (#1) → surgical guards for #2 and #3 → cleanup items (#4–#6).
