"""Regression tests for the v1.2.0 UI/UX batch 1 pure helpers:
freeze_gate_report · next_pending_session · plan_snapshot — plus the
plan strip and the Next-session prefill on a real (withdrawn) App.

Run either way:
    py test/test_freeze_gates.py
    py -m pytest test/test_freeze_gates.py
"""

# Copyright 2026 Costel Iordan (costel.iordan@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import importlib.util
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "plan_console", HERE.parent / "plan-console.py")
pc = importlib.util.module_from_spec(_spec)
sys.modules["plan_console"] = pc
_spec.loader.exec_module(pc)

DRAFT = "# PART 01 — demo draft\n\n§A body\n"
# §A session-map rows in the template's shape (templates/PART-01.md §A:
# indented, NO leading pipe — a leading '|' would make fold_map_rows
# treat the row as a wrap of the previous line)
FROZEN_ROWS = (
    "# PART 01 — demo | v1.0 frozen 2026-09-26\n\n"
    "    # | one-line scope | gates | deploy?\n"
    "    1 | Implement the parser | g1, g2 | no\n"
    "    2 | Deploy to production | g7 | split\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------- freeze gates
def test_all_gates_pass_on_clean_plan(tmp_path):
    pdir = tmp_path / "plans" / "clean"
    write(pdir / "PART-01.draft.md", DRAFT)
    write(pdir / "RECON-CHECKLIST.md", "- [x] checked item\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    gates = pc.freeze_gate_report(pdir)
    assert [g["id"] for g in gates] == ["draft", "frozen", "questions",
                                        "owner_actions", "parked", "recon",
                                        "validation"]
    assert all(g["ok"] for g in gates), gates


def test_missing_draft_and_validation_block(tmp_path):
    pdir = tmp_path / "plans" / "bare"
    pdir.mkdir(parents=True)
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["draft"]["ok"] is False
    assert "run intake first" in gates["draft"]["detail"]
    assert gates["validation"]["ok"] is False
    assert "Validate draft" in gates["validation"]["detail"]


def test_open_questions_gate_shows_preview(tmp_path):
    pdir = tmp_path / "plans" / "q"
    write(pdir / "PART-01.draft.md", DRAFT)
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: the gap\n   QUESTION: do we migrate?\n"
          "   RECOMMEND: yes\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    g = gates["questions"]
    assert g["ok"] is False
    assert "1 open question(s)" in g["detail"]
    assert "do we migrate?" in g["detail"], "QUESTION line must preview"
    assert "Owner pass" in g["detail"]


def test_owner_actions_gate_enforced_for_freeze(tmp_path):
    # v1.2.0 fix: the real Freeze skipped this v3.5 gate (the dry run
    # didn't) — freeze_gate_report is now the single source for both.
    pdir = tmp_path / "plans" / "oa"
    write(pdir / "PART-01.draft.md", DRAFT)
    write(pdir / "OPEN-QUESTIONS.md",
          "## Owner actions\n- [ ] run the migration `py -3 migrate`\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["questions"]["ok"] is True, "bullets are not questions"
    assert gates["owner_actions"]["ok"] is False
    assert "1 unchecked owner action(s)" in gates["owner_actions"]["detail"]


def test_parked_answers_gate(tmp_path):
    pdir = tmp_path / "plans" / "parked"
    write(pdir / "PART-01.draft.md",
          DRAFT + "## OWNER ANSWERS\n- Q: Which engine?\n- A: Postgres\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["parked"]["ok"] is False
    assert "1 owner answer(s) parked" in gates["parked"]["detail"]


def test_recon_gate_ticked_vs_deferred(tmp_path):
    pdir = tmp_path / "plans" / "recon"
    write(pdir / "PART-01.draft.md", DRAFT)
    rc = pdir / "RECON-CHECKLIST.md"
    write(rc, "- [ ] unchecked item\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["recon"]["ok"] is False
    # owner-marked DEFERRED counts as resolved (v2.0 rule; the tag must
    # start the item or sit in brackets — DEFERRED_START_RE /
    # DEFERRED_BRACKET_RE)
    write(rc, "- [x] done\n- [ ] the flaky probe (DEFERRED — no env yet)\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["recon"]["ok"] is True
    write(rc, "- [x] done\n- [ ] genuinely open item\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["recon"]["ok"] is False


def test_validation_gate_requires_exact_ready(tmp_path):
    pdir = tmp_path / "plans" / "val"
    write(pdir / "PART-01.draft.md", DRAFT)
    val = pdir / "VALIDATION.md"
    write(val, "PART-01 READY (see findings)")   # stale/wordy report
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["validation"]["ok"] is False
    write(val, "PART-01 READY")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["validation"]["ok"] is True


def test_frozen_gate_reports_versioned_name(tmp_path):
    pdir = tmp_path / "plans" / "frozen"
    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS)
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["frozen"]["ok"] is False
    assert "PART-01 v1.0.md" in gates["frozen"]["detail"]


def test_report_never_mutates(tmp_path):
    pdir = tmp_path / "plans" / "nomut"
    write(pdir / "PART-01.draft.md", DRAFT)
    before = sorted(str(p.relative_to(pdir)) for p in pdir.rglob("*"))
    pc.freeze_gate_report(pdir)
    pc.plan_snapshot(pdir)
    after = sorted(str(p.relative_to(pdir)) for p in pdir.rglob("*"))
    assert before == after


# ------------------------------------------------------ next session
def test_next_pending_session_not_frozen_is_none(tmp_path):
    pdir = tmp_path / "plans" / "empty"
    pdir.mkdir(parents=True)
    assert pc.next_pending_session(pdir) is None


def test_next_pending_session_plain_flow(tmp_path):
    pdir = tmp_path / "plans" / "plain"
    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS)
    nxt = pc.next_pending_session(pdir)
    assert (nxt["n"], nxt["leg"], nxt["copyable"]) == (1, "", True)
    assert nxt["label"] == "session 1"
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS | P00 v1.0\n")
    nxt = pc.next_pending_session(pdir)
    assert (nxt["n"], nxt["leg"]) == (2, "a"), "split row 2 starts at leg a"
    assert nxt["copyable"] is True
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS | P00 v1.0\n"
          "SESSION 2a | 2026-09-26 | gates: g7 | status: PASS | P00 v1.0\n"
          "SESSION 2b | 2026-09-26 | gates: g7 | status: PASS | P00 v1.0\n")
    nxt = pc.next_pending_session(pdir)
    assert nxt["n"] is None
    assert nxt["label"] == "all sessions recorded"
    assert nxt["copyable"] is False


def test_next_pending_session_deploy_window(tmp_path):
    pdir = tmp_path / "plans" / "deploy"
    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS | P00 v1.0\n"
          "SESSION 2a | 2026-09-26 | gates: g7 | status: PASS | P00 v1.0\n")
    nxt = pc.next_pending_session(pdir)
    assert (nxt["n"], nxt["leg"], nxt["copyable"]) == (2, "b", True)
    assert "DEPLOY WINDOW" in nxt["label"], "leg a PASS → owner deploys now"


def test_next_pending_session_leg_a_not_pass_blocks_copy(tmp_path):
    pdir = tmp_path / "plans" / "notpass"
    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS | P00 v1.0\n"
          "SESSION 2a | 2026-09-26 | gates: g7 | status: FAIL | P00 v1.0\n")
    nxt = pc.next_pending_session(pdir)
    assert nxt["copyable"] is False, "leg a not PASS → nothing to copy yet"
    assert "not PASS yet" in nxt["label"]


# ------------------------------------------------------ plan snapshot
def test_plan_snapshot_stages(tmp_path):
    empty = tmp_path / "plans" / "none"
    empty.mkdir(parents=True)
    assert pc.plan_snapshot(empty)["stage"] == "empty"
    assert pc.plan_snapshot(tmp_path / "plans" / "ghost")["exists"] is False

    pdir = tmp_path / "plans" / "full"
    write(pdir / "PART-01.draft.md", DRAFT)
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: b?\n   RECOMMEND: c\n"
          "## Owner actions\n- [ ] do the thing\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] open recon\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    snap = pc.plan_snapshot(pdir)
    assert snap["stage"] == "draft"
    assert (snap["questions"], snap["owner_actions"], snap["recon"]) == \
        (1, 1, 1)
    assert snap["validation"] == "ready"
    assert snap["next"] is None and snap["frozen_name"] is None
    assert len(snap["gates"]) == 7

    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS)
    write(pdir / "BLOCKED.md", "gate g1 failed twice\n")
    write(pdir / "IN-PROGRESS.md",
          "SESSION 1 started 2026-09-26\nstopped — tests red\n")
    snap = pc.plan_snapshot(pdir)
    assert snap["stage"] == "frozen"
    assert snap["frozen_name"] == "PART-01 v1.0.md"
    assert snap["blocked"] is True
    assert snap["in_progress"] == (1, "")


# --------------------------------------------- plan strip (real Tk App)
@pytest.fixture()
def app_window(tmp_path, monkeypatch):
    """A real (withdrawn) Plan Console App on a temp config, offline.
    Skips the test only when Tk genuinely cannot initialise."""
    tk = pytest.importorskip("tkinter")
    # A bare `except TclError: skip` turned a TRANSIENT Tk() failure into a
    # silent skip: this fixture builds and destroys a full App ~19 times in
    # one process, and on Windows the Nth Tk() intermittently raised
    # TclError. Measured 5 skips in 8 runs — a gate that reports green
    # because it quietly stopped running (the GATE SANITY failure class).
    # Retry a few times, then skip for real. A genuinely absent display
    # still skips on the first attempt.
    root = None
    for attempt in range(3):
        try:
            root = tk.Tk()
            break
        except tk.TclError:
            if attempt == 2:
                pytest.skip("no Tk display available")
            time.sleep(0.2)
    root.withdraw()
    monkeypatch.setattr(pc, "_high_contrast_active", lambda: False)
    monkeypatch.setattr(pc, "CFG", tmp_path / "plan-console.json")
    monkeypatch.setattr(pc.App, "_fetch_models", lambda self: None)
    # safety: the App fixture must never touch the REAL repo — with CFG
    # patched, repo_path() defaults to cwd, and a scheduled or preflight
    # _auto_command_check would offer to overwrite the real commands/
    # (it did exactly that once). No-op it for the fixture's lifetime.
    monkeypatch.setattr(pc.App, "_auto_command_check",
                        lambda self, repo=None: None)
    app = pc.App(root)
    root.update()
    yield app, root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "PART-00.md", "# PART 00\n")
    write(repo / "commands" / "new-plan.md", "# new-plan\n")
    return repo


def _touch(path):
    """Bump mtime so a same-size rewrite still registers as a change."""
    st = path.stat()
    path.write_bytes(path.read_bytes())
    import os
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))


def _frozen_repo(tmp_path, progress=""):
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS)
    if progress:
        write(pdir / "PROGRESS.md", progress)
    return repo, pdir


def test_strip_reflects_frozen_plan(app_window, tmp_path):
    app, root = app_window
    repo, _pdir = _frozen_repo(tmp_path)
    app.repo_var.set(str(repo))
    app._refresh_slug_values(clear_invalid=True)
    app.slug_var.set("demo-plan")
    app._strip_refresh()
    root.update()
    assert app.strip_slug.cget("text") == "Plan: demo-plan"
    assert "frozen (PART-01 v1.0.md)" in app.strip_state.cget("text")
    assert app.strip_next.cget("text") == "next: session 1"
    assert app.strip_action.cget("text") == "Copy session 1 →"
    assert app._strip_action_kind == "copy"


def test_strip_draft_state_points_at_first_failing_gate(app_window,
                                                        tmp_path):
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "PART-01.draft.md", DRAFT)
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: b?\n   RECOMMEND: c\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._strip_refresh()
    root.update()
    assert "draft" in app.strip_state.cget("text")
    assert "validation ✗" in app.strip_state.cget("text")
    assert app._strip_action_kind == "tab"
    # questions fail first → the action jumps to the Owner pass tab
    assert app.strip_action.cget("text") == "Open Owner pass →"


def test_strip_empty_slug_hints(app_window):
    app, root = app_window
    app.slug_var.set("")
    app._strip_refresh()
    root.update()
    assert app.strip_slug.cget("text") == "Plan: —"
    assert app._strip_action_kind is None


def test_next_session_prefills_and_copies(app_window, tmp_path,
                                          monkeypatch):
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    calls = []
    monkeypatch.setattr(app, "on_copy_instr", lambda: calls.append(1))
    app.on_next_session()
    assert app.snum.get() == "2", "session 1 → advance to 2 (leg a)"
    assert app.leg_var.get() == "a"
    assert calls == [1], "copy must run as part of the same click"


def test_next_session_is_a_plain_increment(app_window, tmp_path,
                                           monkeypatch):
    """v1.2.1 — the button is +1 on the number in the box, NOT a jump to
    the first not-done session. A jump quietly renumbered the box around
    a re-run or BLOCKED session, so the box stopped meaning "the session
    I am on". Sitting on session 1 with session 2 recorded must still
    advance to 2, not skip to 3."""
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n"
                 "SESSION 2 | 2026-09-26 | gates: g7 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    calls = []
    monkeypatch.setattr(app, "on_copy_instr", lambda: calls.append(1))
    app.snum.set("1")
    app.on_next_session()
    assert app.snum.get() == "2", "increment, not a jump past recorded work"
    assert calls == [1]


def test_next_session_refuses_to_run_off_the_map(app_window, tmp_path,
                                                 monkeypatch):
    """The increment is applied LAST: a target §A never declared must
    leave the box alone rather than copy an instruction for it.
    _session_guards only checks PREDECESSORS, so nothing downstream
    would have caught this."""
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    calls = []
    monkeypatch.setattr(app, "on_copy_instr", lambda: calls.append(1))
    monkeypatch.setattr(pc.messagebox, "showinfo", lambda *a, **k: None)
    app.snum.set("2")          # last session in FROZEN_ROWS is 2
    app.on_next_session()
    assert app.snum.get() == "2", "no run off the end of §A"
    assert calls == [], "nothing to copy"


def test_next_session_gap_in_map_refuses_and_lists(app_window, tmp_path,
                                                   monkeypatch):
    """A §A that skips a number (1, 3) must not be advanced into: the
    message names what §A actually declares so the gap is visible."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "PART-01 v1.0.md", FROZEN_ROWS.replace(
        "    2 | Deploy to production | g7 | split",
        "    3 | Deploy to production | g7 | no"))
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS | P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    calls = []
    monkeypatch.setattr(app, "on_copy_instr", lambda: calls.append(1))
    seen = []
    monkeypatch.setattr(pc.messagebox, "showinfo",
                        lambda *a, **k: seen.append(a[1] if len(a) > 1 else ""))
    app.snum.set("1")
    app.on_next_session()
    assert app.snum.get() == "1", "session 2 is not declared — do not move"
    assert calls == []
    assert seen and "3" in seen[0], "the message must list what §A declares"


def test_next_session_empty_box_starts_at_one(app_window, tmp_path,
                                              monkeypatch):
    """An empty or non-numeric box is 0, so +1 lands on session 1 — never
    on 0, and never a ValueError dialog."""
    app, root = app_window
    repo, _pdir = _frozen_repo(tmp_path)
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    calls = []
    monkeypatch.setattr(app, "on_copy_instr", lambda: calls.append(1))
    for junk in ("", "abc"):
        app.snum.set(junk)
        app.on_next_session()
        assert app.snum.get() == "1", "junk %r must start at 1" % junk
    assert calls == [1, 1]


def test_next_session_keeps_split_leg_across_clicks(app_window, tmp_path,
                                                    monkeypatch):
    """v1.2.1 — the increment must not drop the split-deploy leg: with
    leg a PASS it lands on b (the DEPLOY WINDOW copy), otherwise on a."""
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    monkeypatch.setattr(app, "on_copy_instr", lambda: None)
    app.snum.set("1")
    app.on_next_session()
    assert (app.snum.get(), app.leg_var.get()) == ("2", "a"), "leg a first"

    # leg a now PASS → the same button lands on leg b
    write(repo / "plans" / "demo-plan" / "PROGRESS.md",
          "SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS | P00 v1.0\n"
          "SESSION 2a | 2026-09-26 | gates: g7 | status: PASS | P00 v1.0\n")
    app.snum.set("1")
    app.on_next_session()
    assert (app.snum.get(), app.leg_var.get()) == ("2", "b"), "leg b next"


# ------------------------------------------- v1.2.1 swallowed-failure fixes
def test_deploy_window_reports_write_failure(app_window, tmp_path,
                                            monkeypatch):
    """The bug this guards: _log_deploy_window swallowed a failed write
    and the caller then told the owner "audit line appended to
    HEALTH.md". A failed write must be visible, and the success claim
    must be withheld."""
    app, root = app_window
    pdir = tmp_path / "plans" / "dw"
    pdir.mkdir(parents=True)

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(pc.Path, "open", boom)
    assert app._log_deploy_window(pdir, "dw", 6) is False, \
        "a failed HEALTH.md append must return False, not None/silence"

    monkeypatch.undo()
    assert app._log_deploy_window(pdir, "dw", 6) is True
    assert "DEPLOY WINDOW" in (pdir / "HEALTH.md").read_text(encoding="utf-8")


def test_deploy_window_success_claim_follows_the_flag(app_window, tmp_path,
                                                     monkeypatch):
    """on_copy_instr must only say the audit line landed when it did.
    Driven end-to-end through the leg-b copy path, not by reading the
    source: _log_deploy_window returns False -> no success claim, and a
    warning instead."""
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n"
                 "SESSION 2a | 2026-09-26 | gates: g7 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    monkeypatch.setattr(pc.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(app, "_show_instruction", lambda *a, **k: None)
    said, warned = [], []
    app.say = lambda target, msg: said.append(msg)
    monkeypatch.setattr(pc.messagebox, "showwarning",
                        lambda *a, **k: warned.append(a))

    app.snum.set("2")
    app.leg_var.set("b")
    monkeypatch.setattr(app, "_log_deploy_window", lambda *a, **k: False)
    app.on_copy_instr()
    assert not any("audit line appended" in m for m in said), \
        "must NOT claim the audit line landed: %r" % said
    assert any("WARN" in m for m in said), said
    assert warned, "a failed audit write must warn the owner, not just log"

    # and when it DID land, the claim is made
    said.clear(); warned.clear()
    monkeypatch.setattr(app, "_log_deploy_window", lambda *a, **k: True)
    app.on_copy_instr()
    assert any("audit line appended" in m for m in said), said
    assert not warned


def test_context_pack_logs_skipped_file(app_window, tmp_path, monkeypatch):
    """R-02 (§E): the audit log must show what was NOT sent, or the owner
    cannot tell 'did not match' from 'matched but unreadable'."""
    app, root = app_window
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    write(repo / "PART-00.md", "# PART 00\n")
    # _context_pack derives its search words from identifiers of 5+ chars
    # in the checklist, so the matched name needs one too
    (repo / "src" / "parser.py").write_text("x = 1\n", encoding="utf-8")
    said = []
    app.say = lambda target, msg: said.append(msg)

    real_open = pc.Path.open

    def deny_parser(self, *a, **k):
        if self.name == "parser.py":
            raise OSError("locked")
        return real_open(self, *a, **k)

    monkeypatch.setattr(pc.Path, "open", deny_parser)
    app._context_pack(repo, "check the parser behaviour")
    joined = " ".join(said)
    assert "SKIPPED" in joined, said
    assert "parser.py" in joined


def test_strip_refresh_surfaces_permanent_failure(app_window, monkeypatch):
    """A 3 s poll that swallows forever shows STALE state and looks
    correct. After a run of consecutive failures the strip must say so."""
    app, root = app_window
    said = []
    app.say = lambda target, msg: said.append(msg)

    def boom():
        raise ValueError("render bug")

    monkeypatch.setattr(app, "_strip_render", boom)
    app._strip_fails = 0
    app._strip_warned = False
    app._strip_refresh()          # hiccup 1-2: tolerated, silent
    app._strip_refresh()
    assert not any("STALE" in m for m in said), "one hiccup must stay quiet"
    app._strip_refresh()          # 3rd: permanent fault -> must surface
    assert any("STALE" in m for m in said), said
    assert app._strip_warned is True
    # and a success clears the counter, so a later fault warns afresh
    app._strip_warned = False
    monkeypatch.setattr(app, "_strip_render", lambda: None)
    app._strip_refresh()
    assert app._strip_fails == 0


def test_strip_copy_action_honours_its_own_label(app_window, tmp_path,
                                                  monkeypatch):
    """Regression: _strip_action_go used to call on_next_session(), which is
    now a +1. The strip's label is derived from PROGRESS.md and reads
    "Copy session 2 ->", so clicking it must copy session 2 even when the
    spinbox holds something else entirely."""
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    copied = []
    monkeypatch.setattr(app, "on_copy_instr",
                        lambda: copied.append(app.snum.get()))

    app.snum.set("1")
    app._strip_refresh()
    root.update()
    # session 2 is a SPLIT row in FROZEN_ROWS, so the strip offers leg a
    assert "Copy leg 2a" in app.strip_action.cget("text"), \
        app.strip_action.cget("text")
    assert app._strip_copy_target == (2, "a")

    # the spinbox now sits somewhere the strip never mentioned
    app.snum.set("7")
    app._strip_action_go()
    assert app.snum.get() == "2", "strip must copy the session it NAMED"
    assert app.leg_var.get() == "a", "and the leg it advertised"
    assert copied == ["2"]


def test_strip_copy_is_guarded_while_a_chain_runs(app_window, tmp_path,
                                                  monkeypatch):
    """R-11 gap: the strip's copy action writes the instruction file and
    (leg b) HEALTH.md, so it belongs in BUSY_DISABLE's category. As a Label
    it had no `state` option and was never guarded, which made the PRIMARY
    path the one path that could still write mid-chain — while btn_next,
    which does the same thing, was disabled."""
    app, root = app_window
    repo, _pdir = _frozen_repo(
        tmp_path,
        progress="SESSION 1 | 2026-09-26 | gates: g1, g2 | status: PASS "
                 "| P00 v1.0\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    copied = []
    monkeypatch.setattr(app, "on_copy_instr",
                        lambda: copied.append(app.snum.get()))
    told = []
    monkeypatch.setattr(pc.messagebox, "showinfo",
                        lambda *a, **k: told.append(a))

    app.snum.set("1")
    app._strip_refresh()
    root.update()
    assert app._strip_action_kind == "copy"

    # start a chain the way the app does (the queue needs an explicit drain)
    app.q.put(("__busy__", (True, "testing")))
    app._drain()
    root.update()
    assert getattr(app, "_strip_locked", False) is True, \
        "the strip copy must be locked while a chain runs"
    assert str(app.btn_next.cget("state")) == "disabled", \
        "...and so must the button that does the same thing"

    app._strip_action_go()
    assert copied == [], "no instruction file may be written mid-chain"
    assert told, "the owner must be told why nothing happened"

    # chain over -> unlocked, and the copy works again
    app.q.put(("__busy__", (False, "")))
    app._drain()
    root.update()
    assert getattr(app, "_strip_locked", False) is False
    app._strip_action_go()
    assert copied == ["2"]


def test_strip_copy_target_is_cleared_on_non_copy_states(app_window, tmp_path,
                                                        monkeypatch):
    """A target must not outlive the label that advertised it."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkeypatch.setattr(app, "_auto_command_check", lambda repo=None: None)
    app._strip_refresh()
    root.update()
    assert app._strip_copy_target is None
    assert app._strip_action_kind in (None, "tab")


# ------------------------------------------- v1.2.1 auto-reload + discoverability
def test_owner_refresh_preserves_selection(app_window, tmp_path):
    """The rebuild used to wipe every selection, so the owner's place was
    lost and the next button press acted on a DIFFERENT item."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: first one?\n   RECOMMEND: yes\n"
          "2. PROBLEM: b\n   QUESTION: second one?\n   RECOMMEND: no\n")
    write(pdir / "RECON-CHECKLIST.md",
          "- [ ] recon one\n- [ ] recon two\n- [ ] recon three\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    monkey = lambda *a, **k: None
    app._auto_command_check = monkey

    app.on_owner_refresh()
    assert app.oq_list.size() == 2 and app.rc_list.size() == 3
    app.oq_list.selection_set(1)
    app.rc_list.selection_set(2)
    app.on_owner_refresh()
    assert app.oq_list.curselection() == (1,), app.oq_list.curselection()
    assert app.rc_list.curselection() == (2,), app.rc_list.curselection()


def test_owner_refresh_clamps_selection_to_new_size(app_window, tmp_path):
    """The agent can remove rows; a selection past the end would silently
    point at nothing."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: first?\n"
          "2. PROBLEM: b\n   QUESTION: second?\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] one\n- [ ] two\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._auto_command_check = lambda *a, **k: None

    app.on_owner_refresh()
    app.rc_list.selection_set(1)
    write(pdir / "RECON-CHECKLIST.md", "- [ ] only one left\n")
    app.on_owner_refresh()
    assert app.rc_list.size() == 1
    assert app.rc_list.curselection() == (), "stale index must be dropped"


def test_auto_refresh_picks_up_agent_changes(app_window, tmp_path):
    """The whole point: the agent edits the files, the lists update without
    a Refresh click."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md", "1. PROBLEM: a\n   QUESTION: one?\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] recon one\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._auto_command_check = lambda *a, **k: None

    app.on_owner_refresh()                 # baseline the stamp
    assert app.oq_list.size() == 1
    # first poll only baselines, it must not fire a reload
    assert app._maybe_auto_owner_refresh(pdir) is False

    # the agent answers one question in the file
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: one?\n"
          "2. PROBLEM: b\n   QUESTION: two?\n")
    _touch(pdir / "OPEN-QUESTIONS.md")
    assert app._maybe_auto_owner_refresh(pdir) is True, "must reload"
    assert app.oq_list.size() == 2, app.oq_list.size()


def test_auto_refresh_refuses_with_unsaved_answer_text(app_window, tmp_path):
    """An auto-refresh must never cost unsaved work: the rebuild resets the
    question panes, so pending text would end up beside another question."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md", "1. PROBLEM: a\n   QUESTION: one?\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] recon one\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._auto_command_check = lambda *a, **k: None
    said = []
    app.say = lambda target, msg: said.append(msg)

    app.on_owner_refresh()
    app._maybe_auto_owner_refresh(pdir)          # baseline
    app.answer.insert("1.0", "  my unsaved answer")
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: one?\n"
          "2. PROBLEM: b\n   QUESTION: two?\n")
    _touch(pdir / "OPEN-QUESTIONS.md")

    assert app._maybe_auto_owner_refresh(pdir) is False, "must NOT reload"
    assert app.oq_list.size() == 1, "lists must be left alone"
    assert app._owner_stale is True
    assert any("unsaved" in m for m in said), said
    # and it says it only once, not every 3 s
    said.clear()
    app._maybe_auto_owner_refresh(pdir)
    assert not any("unsaved" in m for m in said), said


def test_strip_advertises_the_double_click(app_window):
    """Discoverability: the modal was reachable ONLY by double-clicking and
    nothing on screen said so."""
    app, root = app_window
    text = app._modal_hint.cget("text")
    assert "Double-click" in text
    assert "owner-action" in text and "recon" in text.lower()


def test_owner_lists_keep_independent_selections(app_window, tmp_path):
    """Tk's default exportselection=True makes listboxes fight over the
    CLIPBOARD selection, so only ONE could hold a selection: picking a
    recon row silently cleared the question selection (and wiped the
    full-question pane via an empty <<ListboxSelect>>). Nothing in the app
    relies on the export - all four clipboard writes are explicit."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: q1?\n"
          "2. PROBLEM: b\n   QUESTION: q2?\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] r1\n- [ ] r2\n")
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: q1?\n\n## Owner actions\n"
          "- [ ] do the thing\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._auto_command_check = lambda *a, **k: None
    app.on_owner_refresh()
    root.update()

    app.oq_list.selection_set(0)
    app.rc_list.selection_set(1)
    app.oa_list.selection_set(0)
    root.update()
    assert app.oq_list.curselection() == (0,), app.oq_list.curselection()
    assert app.rc_list.curselection() == (1,), app.rc_list.curselection()
    assert app.oa_list.curselection() == (0,), app.oa_list.curselection()
    # a mouse click does emit <<ListboxSelect>> (a programmatic set does
    # not), so the full-question pane follows a real selection
    app._show_full_question()
    assert "q1?" in app.q_full.get("1.0", "end")


def test_owner_refresh_restores_full_question_pane(app_window, tmp_path):
    """Restoring the selection is not enough: a programmatic selection_set
    emits no <<ListboxSelect>>, so the pane has to be re-shown explicitly
    or it keeps the placeholder while a row sits selected."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: q1?\n   RECOMMEND: yes\n"
          "2. PROBLEM: b\n   QUESTION: q2?\n   RECOMMEND: no\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] r1\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._auto_command_check = lambda *a, **k: None
    app.on_owner_refresh()
    app.oq_list.selection_set(1)
    app.on_owner_refresh()
    assert app.oq_list.curselection() == (1,)
    assert "q2?" in app.q_full.get("1.0", "end"), \
        app.q_full.get("1.0", "end")


def test_poll_wires_the_auto_reload(app_window, tmp_path):
    """The wiring, not just the helper: one tick of the 3 s poll must be
    enough for an agent-side edit to reach the Owner-pass lists. Without
    this, disabling the call in _strip_tick would leave every other test
        green."""
    app, root = app_window
    repo = _make_repo(tmp_path)
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "OPEN-QUESTIONS.md", "1. PROBLEM: a\n   QUESTION: one?\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] recon one\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    app._auto_command_check = lambda *a, **k: None
    app.on_owner_refresh()
    assert app.oq_list.size() == 1

    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: one?\n"
          "2. PROBLEM: b\n   QUESTION: two?\n")
    _touch(pdir / "OPEN-QUESTIONS.md")

    app._strip_tick()                      # one poll tick
    try:
        root.update()
        assert app.oq_list.size() == 2, \
            "the 3 s poll must propagate the agent's change: %d" % \
            app.oq_list.size()
    finally:
        job = getattr(app, "_strip_job", None)
        if job:
            try:
                root.after_cancel(job)
            except Exception:
                pass


def test_busy_lists_disjoint_and_complete():
    assert not (set(pc.BUSY_DISABLE) & set(pc.BUSY_KEEP_LIVE))
    assert {"btn_status", "btn_showval", "btn_freeze_dry",
            "btn_oa_copy"} <= set(pc.BUSY_KEEP_LIVE)
    assert {"btn_freeze", "btn_proceed", "btn_next",
            "btn_health"} <= set(pc.BUSY_DISABLE)


def test_busy_split_button_states(app_window):
    """v1.2.0 — while a chain runs, read-only tools stay LIVE and
    chain-starting buttons go disabled (R-11 split)."""
    app, root = app_window
    app.q.put(("__busy__", (True, "testing")))
    app._drain()
    root.update()
    assert str(app.btn_status.cget("state")) == "normal"
    assert str(app.btn_freeze_dry.cget("state")) == "normal"
    assert str(app.btn_cancel.cget("state")) == "normal"
    assert str(app.btn_freeze.cget("state")) == "disabled"
    assert str(app.btn_next.cget("state")) == "disabled"
    app.q.put(("__busy__", (False, "")))
    app._drain()
    root.update()
    assert str(app.btn_freeze.cget("state")) == "normal"
    assert str(app.btn_cancel.cget("state")) == "disabled"


def test_freeze_gate_dialog_renders(app_window, tmp_path):
    app, root = app_window
    tk = pytest.importorskip("tkinter")
    repo, pdir = _frozen_repo(tmp_path)   # frozen gate fails → jump button
    gates = pc.freeze_gate_report(pdir)
    app._freeze_gates_dialog("demo-plan", gates, "Freeze check",
                             verb="Freeze")
    root.update()

    def _all_texts(w):
        out = []
        if w.winfo_class() in ("TButton", "TLabel", "Label"):
            out.append(str(w.cget("text")))
        for c in w.winfo_children():
            out.extend(_all_texts(c))
        return out

    tops = [w for w in app.root.winfo_children()
            if isinstance(w, tk.Toplevel)
            and "Freeze check gates" in w.title()]
    assert len(tops) == 1, "exactly one gate dialog"
    dlg = tops[0]
    joined = "\n".join(_all_texts(dlg))
    assert "4 of 7 gates pass" in joined
    assert "already frozen (PART-01 v1.0.md)" in joined
    # the jump button targets the FIRST failing gate — in this fixture
    # the frozen plan has no draft, and the draft gate sorts first
    assert "Go to Intake →" in joined
    assert "Close" in joined
    dlg.destroy()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
