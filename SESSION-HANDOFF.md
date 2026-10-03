> ## ⚠ HISTORICAL SNAPSHOT — superseded, do not read as current state
>
> This file records the session that ended at `3e3b649` (2026-10-03). It is
> kept for its engineering history and for **§6, the conventions, which are
> still accurate and still binding**. Everything that reports *current
> state* in it is now wrong and has been left unedited rather than
> rewritten:
>
> | Claim in this file | Reality as of `34d03cd` |
> |---|---|
> | "Last commit: `3e3b649` (unpushed)", §5 "Nothing has been pushed" | Everything is pushed; `main` == `origin/main` == `34d03cd` |
> | "`APP_VERSION` deliberately left at `1.2.0`" | **3.10**, and one version line is now enforced across app + all guides by test |
> | "`plan-console.py` — 7,048 lines, 199 defs" | larger; audit + layout batches landed after this snapshot |
> | "Suite: 140 passed" | **205 passed** |
> | 3 test files | 7, incl. `test_audit_v39.py` |
> | §3 "a real double-click has never been exercised by a human" | still the one open human item |
>
> Line-number references (`plan-console.py:3971`, `:3894`, `:3825`, …) have
> drifted. `_fit_owner_status` and `_fit_flow_hint` are gone, replaced by
> the shared `_autofit_wrap` / `_fit_to_own_column` helpers.
>
> Trust `git log` and the code over anything in §2, §5 or §3.

# SESSION HANDOFF — read this first

Last updated: 2026-10-03, late morning. Last commit: **`3e3b649`** (unpushed).

> **Clock note:** the local clock was desynchronised during the previous session and
> was corrected on 2026-10-03. `20cb059` and `27371e6` carry ~02:44 timestamps while
> `cbaea42` and `3e3b649` carry ~10:2x. That gap is the resync, not a long gap in
> work. File mtimes before the resync are likewise unreliable.

---

## 0. Two different projects — do not confuse them

This cost real time on 2026-10-03. There are **two separate repos** in play:

| | **Plan Console** (this folder) | **resume-app** |
|---|---|---|
| Path | `C:\Temp\PlanConsoleApp` | `C:\Temp\Resume\resume-app` |
| What | The desktop Tk tool that drives plan sessions | A Next.js + Supabase product |
| Git repo | this one, `main` | `C:\Temp\Resume` |

Both have something called an "admin console". They are **not** the same thing:

- **Plan Console** = the Tk app in this folder. Owner/recon panes, tooltips, modal. All UI work on 2026-10-03 happened here.
- **resume-app's admin console** = its own `/admin/usage` page (`src/app/[locale]/admin/usage/page.tsx`, `src/app/api/admin/usage/route.ts`). The AI-latency audit was about *that*.

If a request mentions recon / owner actions / panes / modal / tooltips → **this repo**.
If it mentions AI latency / Credits Consumed / edge functions / Gemini / Groq → **resume-app**.

A resume-app audit session was left loaded in the console during an earlier session.
That was the source of the confusion. Nothing in resume-app was modified.

---

## 1. What the last session did (`cbaea42`, `3e3b649`)

`20cb059` (the double-click modal) is described in §3 below. Two commits followed it,
both **local only — nothing has been pushed**; `20cb059`, `27371e6`, `cbaea42` and
`3e3b649` are all ahead of `origin/main`.

**The bug: `commands/session.md` existed in four places with two different texts.**

`27371e6` added the GATE SANITY block to the on-disk command file but never to the
`STARTER_FILES` copy embedded in `plan-console.py`. The demo project had then been
regenerated from that stale copy. So the console scaffolded plans whose session
protocol silently omitted GATE SANITY, while the repo file carried it — embedded and
sample agreed with each other and both disagreed with the repo.

That is the failure mode the GATE SANITY block itself warns about, so it was not
cosmetic. All four locations (repo root, embedded, `test/` fixture,
`samples/demo-project/plans/demo-recipe-cli`) are now one text, regenerated through
the app's own `Path.write_text` path so line endings match what the app actually
writes. `cbaea42` also carries the SPLIT-DEPLOY PROTOCOL and the self-contained
canonical PROGRESS line shape onto disk — those had existed only in the embedded copy
and in the working tree.

**`cbaea42`** — the four-way sync, the 1.2.0 release note, a stale `_freeze_blockers`
comment repointed at `freeze_gate_report` (the method it named no longer existed), and
a `.gitignore` rule for `/backup-*/`.

**`3e3b649`** — three test changes:

1. The canonical-record tests, written earlier and never committed: reason between the
   status word and the P00 tag, prefixed gate ids (`sg1`) round-tripping from the §A
   map, prose like `tag 2` rejected as an id, reason-after-P00 flagged non-canonical,
   a wrapped template copy that parses but never reports canonical. Plus Na/Nb legs as
   separate keys in `latest_sessions`, a single-`#` line always treated as prose, and
   0-based owner-action linenos matching `parse_questions`.
2. **`test_freeze_gates.py` was never committed** — it is the regression suite for the
   `freeze_gate_report` refactor, so that shared-gate-list work had no coverage in git.
   It now lands with the tests it belongs to.
3. **Both `app_window` fixtures turned ANY `TclError` from `tk.Tk()` into a skip.**
   That is not the same as "no display": the fixture builds and destroys a full App
   repeatedly in one process and the Nth `Tk()` intermittently failed, so tests silently
   stopped running — measured 5 skips in 8 runs of `test_freeze_gates`, 4 of 6
   full-suite runs. Both now retry three times before skipping.

## 2. State now

- `plan-console.py` — **7,048 lines, 199 defs, syntax OK.**
- **Suite: 140 passed, 0 skipped**, verified over repeated full runs. The zero
  skips is the point — a skipped test reports green.
- Working tree clean except untracked `SESSION-HANDOFF.md` (this file).
- **Everything is pushed.** `origin/main` == `adde9d1`. The first push was done
  deliberately *before* the except sweep so there was a remote rollback point.
- `backup-20261001-133727/` and `backup-20261003-011334/` are on disk and now
  gitignored. Now redundant with origin; still harmless to keep.
- `deferred-session-fix.patch` **deleted**. Its content (`session_row_deferred`) was
  already in `plan-console.py`; it had stopped applying and was only ever a source of
  confusion.
- Tests: `test/test_parsers.py`, `test/test_theme.py`, `test/test_freeze_gates.py`.

## 2a. `ccb984c` — four swallowed failures, and a convention

The ~40 `except ...: pass` handlers were **triaged, not blanket-removed**. Most are
correct; several are load-bearing; the `tk.TclError` teardown races *must* keep
swallowing or `after` callbacks crash the app on close. The rule is now written into
the file header (search `EXCEPTION-HANDLING CONVENTION`) so it is not re-derived.

Four were real defects:

1. **`_log_deploy_window` was the bad one.** It swallowed a failed `HEALTH.md` append,
   and the caller then told the owner *"audit line appended to HEALTH.md"*
   unconditionally. A lost audit line was reported as a written one — and that line
   records owner confirmation that a **production deploy happened**. Now returns a
   flag; the claim is made only on `True`, and failure gives a traceback, a WARN, and a
   modal naming the file to fix.
2. **`_context_pack`** swallowed `OSError` on a *matched* file, so R-02's audit log
   recorded only what was sent. The owner could not tell "did not match" from "matched
   but unreadable". Skips are now logged.
3. **`_strip_refresh`** swallowed everything behind a 3 s poll. A locked file clears
   itself; a real bug never does — so the strip showed stale state forever and looked
   correct. Now separates hiccup from permanent fault and says so after 3 consecutive
   failures.
4. Two `except Exception` around the `AGENT-ORDERS.md` default narrowed to `OSError`
   (fallback is correct, but the broad type hid real faults).

## 2b. `695b67d` — the plan strip regression I introduced, fixed

**Read this before touching `on_next_session` or `_strip_action_go` again.**

`6737b1a` made the button +1. The plan strip's action link *called* `on_next_session()`,
so that change made the strip's label a lie: it is derived from `PROGRESS.md` and reads
`Copy leg 2a →`, but a click copied whatever the spinbox held **plus one**. With the
box on a stale number it offered session 2 and copied session 8, or refused outright.

The two are now separate code paths, deliberately:

| | Semantics | Source of truth |
|---|---|---|
| **Strip** — `Copy session N →` | jumps to what the plan needs | derived from `PROGRESS.md`, self-corrects |
| **Button** — `Next session →` | +1 on what the owner typed | the owner's assertion |

The strip sets the number and leg it advertised, then copies. `on_next_session` stays
the manual accelerator. An `IN-PROGRESS.md` marker whose session number cannot be read
now says so instead of guessing.

## 2c. `adde9d1` — strip is primary, and an R-11 gap it exposed

The button is now **`+1 session →`**, not "Next session →". After `6737b1a` the old name
was simply untrue, and sharing it with the strip made the two look interchangeable. The
post-Freeze log line and `UserGuide.txt` (daily loop + button table) now point at the
strip's **`Copy session N →`** as the primary click.

**The gap:** `strip_action` is a `ttk.Label` with a click binding, so it has no `state`
option and sat in **neither** busy list — while `btn_next`, which performs the *same*
operation, was in `BUSY_DISABLE`. The strip's copy writes the instruction file and, for
leg b, `HEALTH.md`, which is verbatim `BUSY_DISABLE`'s stated category. So the primary
path was the one path that could still write mid-chain. Now gated by `_strip_locked`
(set from the same busy handler that disables the buttons) and the action label dims to
`text-muted` while locked — refusal is visible without hiding the plan state.

*If you touch the strip again:* a `Label` cannot be disabled, so any new clickable
strip affordance needs the `_strip_locked` gate too. Grep `_strip_locked` before adding
one.

## 2a. `6737b1a` — "Next session →" is now a plain +1

Owner-reported: the button did not increment the session number. Confirmed — it never
did. `on_next_session` called `next_pending_session` and **jumped** the box to the
first not-done session, so around a re-run, deferred or BLOCKED session the box
quietly renumbered itself and stopped meaning "the session I am on".

Now `n = max(int(snum) + 1, 1)`. Everything else is preserved:

- The copy still goes through `on_copy_instr` → `_session_guards`, so all guards and
  diagnostics are unchanged (and better — the "leg a not PASS" case now gets
  `_session_guards`' precise wording instead of a generic warning).
- **One guard added, because the increment made it reachable:** `_session_guards` only
  checked **predecessors**, never that `n` itself exists in the §A map. A blind
  increment could therefore build an instruction for a session §A never declared. The
  increment is applied last, after the target is confirmed in the map, so a run off
  the end (or a gap in §A) leaves the box untouched and lists what §A declares.
- Split deploy is intact: the leg still comes from `next_pending_session` — leg **b**
  once leg a is PASS (the DEPLOY WINDOW copy), leg **a** otherwise.
- Empty / non-numeric box counts as 0, so it starts at session 1.

**Unresolved, owner deprioritised it:** the session number was also observed reading
**0** rather than incrementing. Not reproduced — the parser yields no `0` key for any
plan in this repo, and the `ttk.Spinbox` stores exactly what it is given (no
clamping), so `0` would have to be written literally by one of the only three
`snum.set(...)` sites. If it recurs, instrument those three lines
(`plan-console.py:3825`, `:6366`, `:6629`) and log the value.

`APP_VERSION` deliberately left at `1.2.0` — releasing is a separate decision.

## 3. Still needs a human — the one open item

**A real double-click has never been exercised by a human.** The rest of the v3.8 modal
work is now verified, by direct method call (23/23) and by live Tk probe:

- `bind("<Double-Button-1>")` registered on both listboxes (`plan-console.py:3971`,
  `:3985`); handlers select the row *before* opening (`:4517`, `:4532`) so
  Tick/untick and Verify EXISTS act on the item just read.
- `tag_add("sel","1.0","end")` in the `state="disabled"` Text **does** take — Tk renders
  a programmatic `sel` in a disabled widget, so `Ctrl+C` lifts the whole item.
- `_open_item_dialog` destroys the old Toplevel without `grab_release()` — safe: Tk
  auto-releases a grab when its window is destroyed, and the replacement grab binds.
- `<Escape>` bound on the Toplevel **does** fire while the child Text holds focus.
- The `>8px` change guards are present on both `_fit_owner_status` (`:3894`) and
  `_fit_flow_hint` (`:3916`).

What could **not** be verified: an actual OS double-click. Synthetic `event_generate`
still does not land on the fully built app. Note the local clock resync may have been
part of why that looked inconsistent earlier — the Tk flake in §1.3 was real and is now
fixed, so **retry the synthetic double-click before assuming it is impossible.**

To test: restart the console (a running one holds whatever it loaded at launch, not the
current file), then double-click a long recon row and an owner action.

## 4. Open backlog, not started

1. **The ~146 uncommitted lines from before the file-corruption incident remain
   unrecoverable.** Between the last good pre-incident file (~6,682 lines) and the Oct-1
   backup (6,536 lines) that work was never committed and git has nothing newer than
   `27371e6` to compare against. Closed as a loss, not a task.
2. **Launcher / entry point**, raised 2026-10-03, never scoped: opening a `UserGuide.txt`
   or `AGENT-ORDERS.md` from Explorer routes through the console. `plan.bat` already
   exists in the root. Untriaged.

## 5. Push

Nothing has been pushed. `origin/main` is 4 commits behind:
`27371e6`, `20cb059`, `cbaea42`, `3e3b649`. Review the diff, then push.

## 6. Conventions worth keeping

- Don't add single-click handlers on the recon / owner listboxes. Selection *is* the click.
- Prefer a plain fix over a new feature. If a label clips, fix the wraplength; don't add a
  tooltip.
- When wrapping is dynamic, always guard the `<Configure>` handler with a threshold or you
  get a resize feedback loop.
- **A starter file lives in four places.** Change one, change all four, or R-09 fails.
  Embedded + root + `test/` + `samples/demo-project/plans/demo-recipe-cli`.
- **Never let a gate skip silently.** Apply this to tests too: a fixture that skips on a
  transient error reports green. Retry, then skip.
- `plan-console.py` has been truncated twice by unsafe index-based edits. Use anchored
  string edits, verify with absolute paths, and re-check line count + def count +
  `ast.parse` immediately after every edit.