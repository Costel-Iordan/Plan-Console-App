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
