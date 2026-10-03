"""Regression tests for the v3.9 audit batch.

Every test here pins a defect found by the v3.9 audit of plan-console.py.
The shared theme is INVISIBILITY: content that existed in the plan files
but was counted by no list and blocked no gate, so the console reported a
plan as clean while it was not. A green test suite did not catch any of
them, which is why each is pinned explicitly here.
"""
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "pc_audit39", HERE.parent / "plan-console.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------------------------------ 1. DEFERRED false positive
def test_deferred_mention_in_prose_does_not_resolve_item():
    # THE defect: the bracketed form was a plain re.search, so an item
    # merely DISCUSSING the tag counted as RESOLVED — silently un-blocking
    # Freeze, which is the exact failure DEFERRED exists to prevent.
    assert pc.is_deferred(
        "- [ ] check the DEFERRED mechanism (DEFERRED means skip)") is False
    assert pc.count_open_recon(
        "- [ ] check the DEFERRED mechanism (DEFERRED means skip)") == 1


def test_deferred_legitimate_forms_still_resolve():
    # the tightening must not break the forms the docs and existing tests
    # rely on, including the TRAILING note
    for line in ("- [ ] DEFERRED (owner-approved 2026-09-04): token tables",
                 "- [ ] DEFERRED: needs prod access",
                 "- [ ] (DEFERRED) old check",
                 "- [ ] deferred by owner",
                 "- [ ] the flaky probe (DEFERRED - no env yet)"):
        assert pc.is_deferred(line) is True, line
        assert pc.count_open_recon(line) == 0, line


def test_deferred_mentions_stay_open():
    for line in ("- [ ] not DEFERRED yet",
                 "- [ ] what about DEFERRED?",
                 "- [ ] verify the DEFERRED tag is honored"):
        assert pc.is_deferred(line) is False, line
        assert pc.count_open_recon(line) == 1, line


# ------------------------------------------------- 4. OWNER-ONLY recon items
def test_is_owner_only_recognizes_the_tag_forms():
    for line in ("- [ ] OWNER-ONLY: confirm the prod row count",
                 "- [ ] (OWNER-ONLY) needs credentials",
                 "- [ ] confirm the count (OWNER-ONLY - needs DB)"):
        assert pc.is_owner_only(line) is True, line
    for line in ("- [ ] normal agent-runnable grep check",
                 "prose, not a checkbox"):
        assert pc.is_owner_only(line) is False, line


def test_owner_only_recon_items_are_counted_apart():
    # the v3.8 contract bans the agent from running these, so they are
    # not "agent work" and must be separable from it
    text = ("- [x] EXISTS: SOURCE.md\n"
            "- [ ] OWNER-ONLY: confirm the prod row count\n"
            "- [ ] agent-runnable grep check\n")
    assert pc.count_open_recon(text) == 2          # total unchanged
    assert pc.count_open_recon_owner_only(text) == 1
    assert pc.count_open_recon(text, include_owner_only=False) == 1


def test_owner_only_recon_gate_names_the_real_remedy(tmp_path):
    # the old detail said "tick them in the Owner pass tab" for an item
    # the agent is forbidden to run -- advice that asks the owner to forge
    # the assertion the ban exists to protect
    pdir = tmp_path / "plans" / "oo"
    write(pdir / "PART-01.draft.md", "# draft\n")
    write(pdir / "RECON-CHECKLIST.md",
          "- [ ] OWNER-ONLY: confirm the prod row count\n")
    g = {x["id"]: x for x in pc.freeze_gate_report(pdir)}["recon"]
    assert g["ok"] is False
    assert "OWNER-ONLY" in g["detail"]
    assert "Owner-actions" in g["detail"]


def test_snapshot_exposes_owner_only_and_stranded(tmp_path):
    pdir = tmp_path / "plans" / "snap"
    write(pdir / "PART-01.draft.md", "# draft\n")
    write(pdir / "RECON-CHECKLIST.md",
          "- [ ] OWNER-ONLY: confirm the prod count\n")
    write(pdir / "OPEN-QUESTIONS.md", ESCALATION_APPENDED)
    snap = pc.plan_snapshot(pdir)
    assert snap["recon_owner_only"] == 1
    assert snap["stranded"] == 1
    # the strip keys must exist even on a missing dir, or the render would
    # KeyError on a plan that has no checklist yet
    assert pc.plan_snapshot(tmp_path / "nope")["recon_owner_only"] == 0


# ------------------------------------------------ 5. misc audit hardening
def test_version_matches_the_documented_feature_set():
    # the app reported 1.2.0 while the code was v3.8/v3.9
    assert pc.APP_VERSION != "1.2.0"
    assert pc.APP_VERSION.count(".") == 1


def test_busy_disable_covers_the_escalate_button():
    # escalate writes BOTH plan files, so it must be locked while a chain
    # runs, exactly like btn_owner_resolve
    assert "btn_escalate" in pc.BUSY_DISABLE


def test_owner_only_uses_the_same_tag_discipline_as_deferred():
    # the two classifiers share their helpers so they cannot drift again
    for pair in (("- [ ] DEFERRED: x", "- [ ] OWNER-ONLY: x"),
                 ("- [ ] the item (DEFERRED - later)",
                  "- [ ] the item (OWNER-ONLY - needs DB)")):
        assert pc.is_deferred(pair[0]) == pc.is_owner_only(pair[1]), pair
# ================================================= v3.9 Owner-pass tab layout
# Both defects reported from a 1366x768 screenshot:
#   1. Owner actions was so narrow that "Mark done" was not rendered at all
#   2. "Agent: finish owner pass" was pushed below the visible area
# Root causes, both measured rather than guessed:
#   1. each pane's BUTTON BAR sets that pane's requested width; the three
#      summed to ~1400px, and pack carved the whole deficit out of the
#      LAST pane packed. On top of that, tk.Text/ScrolledText default to
#      80 CHARACTERS (~657px), so the Open-questions pane reserved half
#      the row for itself.
#   2. `body` is packed with expand=True BEFORE the bottom button row, and
#      expand is applied only after every slave has taken its requested
#      height — so the button row was pushed off the bottom.
import time

import pytest


@pytest.fixture()
def owner_window(tmp_path, monkeypatch):
    """A real App with the OWNER PASS tab selected and mapped, so widget
    geometry is actual. Same Tk-retry discipline as the other suites."""
    tk = pytest.importorskip("tkinter")
    root = None
    for attempt in range(3):
        try:
            root = tk.Tk()
            break
        except tk.TclError:
            if attempt == 2:
                pytest.skip("no Tk display available")
            time.sleep(0.2)
    monkeypatch.setattr(pc, "_high_contrast_active", lambda: False)
    monkeypatch.setattr(pc, "CFG", tmp_path / "plan-console.json")
    monkeypatch.setattr(pc.App, "_fetch_models", lambda self: None)
    monkeypatch.setattr(pc.App, "_auto_command_check",
                        lambda self, repo=None: None)
    app = pc.App(root)
    root.update_idletasks()
    root.deiconify()
    app.nb.select(2)                    # Owner pass
    _pump(root)
    yield app, root
    try:
        root.destroy()
    except tk.TclError:
        pass

@pytest.mark.parametrize("w,h", [(1600, 1000), (1366, 768), (1200, 800),
                                 (1024, 700), (820, 600)])
def test_every_owner_pass_button_is_actually_rendered(owner_window, w, h):
    """Defect 1: "Mark done" existed in the widget tree at 1px wide.
    Every button in all three bars must have real width and sit inside
    the window AND inside its own pane."""
    app, root = owner_window
    root.state("normal")
    root.geometry("%dx%d" % (w, h))
    _pump(root)
    rw = root.winfo_width()
    rx0 = root.winfo_rootx()      # rootx is ABSOLUTE screen space while the
                                  # width is not, so every comparison below
                                  # has to rebase onto the window origin
    for bar, btns in app._owner_bars:
        pane = bar.master
        pane_left = pane.winfo_rootx() - rx0
        pane_right = pane_left + pane.winfo_width()
        for b in btns:
            label = b.cget("text")
            left = b.winfo_rootx() - rx0
            assert b.winfo_width() > 5, (
                "%dx%d: %r collapsed to %dpx"
                % (w, h, label, b.winfo_width()))
            assert left + b.winfo_width() <= rw + 1, (
                "%dx%d: %r runs off the window" % (w, h, label))
            assert left >= pane_left - 1, (
                "%dx%d: %r escaped its pane to the left" % (w, h, label))
            assert left + b.winfo_width() <= pane_right + 1, (
                "%dx%d: %r overlaps the neighbouring pane" % (w, h, label))


@pytest.mark.parametrize("w,h", [(1600, 1000), (1366, 768), (1024, 700),
                                 (820, 600)])
def test_bottom_action_row_is_inside_the_tab(owner_window, w, h):
    """Defect 2: "Agent: finish owner pass" was clipped below the tab."""
    app, root = owner_window
    root.state("normal")
    root.geometry("%dx%d" % (w, h))
    _pump(root)
    bar2 = app.btn_owner_resolve.master
    tab = app._flow_hint.master
    assert bar2.winfo_y() + bar2.winfo_height() <= tab.winfo_height() + 1, (
        "%dx%d: bottom action row runs past the tab (y=%d h=%d tab=%d)"
        % (w, h, bar2.winfo_y(), bar2.winfo_height(), tab.winfo_height()))
    assert app.btn_owner_resolve.winfo_width() > 5, (
        "%dx%d: 'Agent: finish owner pass' collapsed" % (w, h))


def test_text_widgets_do_not_demand_eighty_columns(owner_window):
    """Root cause of the pane imbalance: tk.Text/ScrolledText default to
    80 CHARACTERS (~657px). Left at the default, the Open-questions pane
    reserves half the row and starves the panes to its right."""
    app, root = owner_window
    for name, w in (("answer", app.answer), ("q_full", app.q_full)):
        assert w.winfo_reqwidth() < 200, (
            "%s requests %dpx — the default 80-column width is back"
            % (name, w.winfo_reqwidth()))


def test_panes_get_comparable_widths(owner_window):
    """No pane may be starved by a sibling's content any more."""
    app, root = owner_window
    root.state("normal")
    root.geometry("1366x768")
    _pump(root)
    widths = [lst.master.winfo_width()
              for lst in (app.oq_list, app.rc_list, app.oa_list)]
    assert min(widths) > 0.25 * max(widths), (
        "panes wildly unequal: %s" % widths)


def test_reflow_wraps_and_rewraps_bidirectionally(owner_window):
    """The bars must recover when the window grows again, and must not
    oscillate: _flow_buttons only reports a change on a real change."""
    app, root = owner_window
    root.state("normal")

    def cols():
        return [getattr(b, "_flow_cols", 0) for b, _ in app._owner_bars]

    root.geometry("1366x768")
    _pump(root)
    wide = cols()
    root.geometry("820x600")
    _pump(root)
    narrow = cols()
    assert narrow[0] <= wide[0], "should wrap tighter when narrower"
    root.geometry("1366x768")
    _pump(root)
    assert cols() == wide, "should re-flow back out to the wide layout"


def test_reflow_does_not_oscillate(owner_window):
    """A reflow changes bar heights -> fires <Configure> -> could reflow
    again forever. Count events across a resize cycle."""
    app, root = owner_window
    root.state("normal")
    root.geometry("1366x768")
    _pump(root)
    seen = {"n": 0}
    app._owner_body.bind("<Configure>", lambda _e: seen.__setitem__(
        "n", seen["n"] + 1), add="+")
    root.geometry("1024x700")
    _pump(root)
    root.geometry("820x600")
    _pump(root)
    root.geometry("1366x768")
    _pump(root)
    assert seen["n"] < 40, "reflow is oscillating (%d Configure events)" \
        % seen["n"]


def test_flow_buttons_packs_as_many_as_fit():
    """The wrap rule itself, on real buttons: never more per row than the
    target allows, and never fewer than one."""
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.withdraw()
    try:
        bar = ttk.Frame(root)
        btns = [ttk.Button(bar, text="button number %d with a long label" % i)
                for i in range(3)]
        root.update_idletasks()
        wide = sum(b.winfo_reqwidth() for b in btns) + 24
        assert pc._flow_buttons(bar, btns, wide) is True
        assert bar._flow_cols == 3, "should fit on one row when given room"
        # second call with the SAME target must be a no-op (no oscillation)
        assert pc._flow_buttons(bar, btns, wide) is False
        # a target that fits only the first must give 1 per row
        one = btns[0].winfo_reqwidth() + 8
        assert pc._flow_buttons(bar, btns, one) is True
        assert bar._flow_cols == 1
        assert all(b.winfo_manager() == "grid" for b in btns)
    finally:
        try:
            root.destroy()
            root.destroy()
        except tk.TclError:
            pass


# ============================ v3.9 collapsible setup panel (top-bar reclaim)
def _tab_height(app, root):
    app.nb.select(2)
    _pump(root)
    return app._flow_hint.master.winfo_height()


def test_collapsing_setup_reclaims_vertical_space(owner_window):
    """The point of the panel: the setup rows are ~114px of permanent
    chrome, which squeezed the tab. Collapsing must hand that space to the
    notebook, not merely hide the widgets."""
    app, root = owner_window
    root.state("normal")
    root.geometry("1366x768")
    expanded = _tab_height(app, root)
    app.cfg["setup_collapsed"] = True
    app._apply_setup_visibility()
    collapsed = _tab_height(app, root)
    assert collapsed > expanded + 60, (
        "collapsing freed only %dpx (expanded %d -> collapsed %d)"
        % (collapsed - expanded, expanded, collapsed))


def test_expanding_setup_gives_the_space_back(owner_window):
    """grid_remove() must be reversible into the SAME cell — a bare
    .grid() restores into row 0 and stacks the panel on the header."""
    app, root = owner_window
    root.state("normal")
    root.geometry("1366x768")
    app.cfg["setup_collapsed"] = True
    app._apply_setup_visibility()
    collapsed = _tab_height(app, root)
    app.cfg["setup_collapsed"] = False
    app._apply_setup_visibility()
    expanded = _tab_height(app, root)
    assert expanded < collapsed - 60, "expanding did not restore the space"
    assert app.repo.winfo_height() > 5, (
        "the repo field must be back on screen after expanding")
    info = app._setup_wrap.grid_info()
    assert int(info["row"]) == 1, (
        "the panel must return to row 1, not row %s" % info["row"])


def test_live_row_stays_visible_when_collapsed(owner_window):
    """Cancel / Theme / About / the progress caption must never be hidden:
    Cancel is only meaningful mid-chain and the progress text is the only
    sign anything is happening."""
    app, root = owner_window
    app.cfg["setup_collapsed"] = True
    app._apply_setup_visibility()
    _pump(root)
    for w in (app.btn_cancel, app.theme_cb, app.prog):
        assert w.winfo_height() > 5, "%r collapsed with the setup panel" \
            % w.cget("text")
    assert app.btn_cancel.winfo_ismapped()


def test_collapse_is_refused_before_a_repo_is_chosen(owner_window):
    """The panel holds the 'point this at your project folder' field, so
    it must not collapse away on a first run."""
    app, root = owner_window
    app.repo_var.set("")                     # no repo chosen at all
    app.cfg["setup_collapsed"] = True
    collapsed = app._apply_setup_visibility()
    assert collapsed is False, "must stay open until a repo is chosen"
    assert app._setup_toggle.cget("text").endswith("▾")


def test_collapsed_summary_reports_the_live_configuration(owner_window,
                                                          tmp_path):
    """Collapsing must not leave the owner guessing which repo/mode the app
    is pointed at — and the summary must not go stale."""
    repo = tmp_path / "my-project"
    repo.mkdir()
    app, root = owner_window
    app.repo_var.set(str(repo))
    app.model_cb.set("some/model-id")
    app.use_key.set(True)
    _pump(root)
    text = app._setup_summary.cget("text")
    assert "my-project" in text, text
    assert "some/model-id" in text, text
    assert "API key on" in text, text
    # and it follows a change
    app.use_key.set(False)
    _pump(root)
    assert "paste mode" in app._setup_summary.cget("text")


def test_collapsed_state_is_persisted(owner_window, tmp_path):
    app, root = owner_window
    app.cfg["setup_collapsed"] = True
    app._apply_setup_visibility()
    app._save_cfg()
    saved = json.loads(pc.CFG.read_text(encoding="utf-8"))
    assert saved.get("setup_collapsed") is True

def test_live_bar_reads_left_to_right(owner_window):
    """The live row must read "... Cancel | Theme | <value> | About".

    Regression: the row was rebuilt with side="right" packing, where the
    FIRST widget packed lands RIGHTMOST. Issued in the wrong order it
    rendered "About | Dark | Theme | Cancel" — the "Theme" caption sitting
    to the RIGHT of its own combobox. Asserted on real x positions, since
    that is the only way the reading order is actually observable."""
    app, root = owner_window
    _pump(root)
    order = sorted(
        ((app.btn_cancel, "cancel"), (app._theme_label, "theme"),
         (app.theme_cb, "value"), (app.btn_about, "about")),
        key=lambda t: t[0].winfo_rootx())
    names = [n for _, n in order]
    assert names == ["cancel", "theme", "value", "about"], (
        "live bar reads %s — 'Theme' must sit immediately LEFT of its "
        "combobox" % " | ".join(names))


def test_live_bar_controls_are_not_crowded(owner_window):
    """Adjacent controls must have a real gap, not touch.

    Regression: padx is (left, right) in the WIDGET's own coordinates, so
    for a right-packed widget "left" faces the neighbour. Transcribing
    About's old grid padx=(12, 0) into pack as padx=(0, 12) put the whole
    12px on the window edge and left About jammed against the Theme
    dropdown with a 0px gap. Order is pinned by the test above; this one
    pins the spacing itself, again on measured geometry."""
    app, root = owner_window
    _pump(root)
    widgets = [app.btn_cancel, app._theme_label, app.theme_cb, app.btn_about]
    gaps = [widgets[i].winfo_rootx()
            - (widgets[i - 1].winfo_rootx() + widgets[i - 1].winfo_width())
            for i in range(1, len(widgets))]
    assert gaps[0] >= 8, "Cancel sits on the 'Theme' caption: %dpx" % gaps[0]
    assert gaps[1] >= 3, "'Theme' sits on its dropdown: %dpx" % gaps[1]
    assert gaps[2] >= 8, "About is crowded against the dropdown: %dpx" % gaps[2]

def _pump(root, n=25):
    for _ in range(n):
        root.update_idletasks()
        root.update()


# ------------------------------------------- 3. the escalation the owner lost
ESCALATION_APPENDED = (
    "# OPEN QUESTIONS - demo\n\n"
    "1. PROBLEM: auth provider unknown\n"
    "   QUESTION: which provider?\n"
    "   RECOMMEND: keep existing\n\n"
    "## Owner actions\n\n"
    "- [ ] Confirm the prod count. `git log -1`\n\n"
    # the agent appends a NEW question at the end without closing the
    # section first -- the natural thing to do, since Owner actions is last
    "1. PROBLEM: the Coolify app id is unknown\n"
    "   QUESTION: what is the Coolify app id?\n"
    "   RECOMMEND: read it off the panel\n")


def test_escalation_appended_into_owner_section_is_not_invisible():
    # THE reported bug. The escalated question must be discoverable
    # SOMEWHERE: it is now reported as a stranded escalation.
    orphans = pc.unaccounted_escalations(ESCALATION_APPENDED)
    assert len(orphans) == 1, orphans
    assert "Coolify app id" in orphans[0]
# ============================================ 3.10 one version line, everywhere
def test_version_is_consistent_across_app_and_docs():
    """One version line, everywhere.

    Regression: the project carried THREE different app versions at once —
    APP_VERSION showed one value in the title bar and About box, the
    UserGuide still said 1.1.0 in its title/header/footer, and
    no-api-key-guide.html still said 1.0.0. Nothing asserted they agreed,
    so each could drift independently on every edit.

    The trap this must NOT trip over: the guides legitimately say
    "Python 3.9" (the minimum interpreter), which is NOT the app version.
    Only "Plan Console <v>" / "PLAN CONSOLE <v>" claims are checked."""
    here = Path(__file__).resolve().parent.parent
    claim = re.compile(r"(?:Plan Console|PLAN CONSOLE)\s+(\d+\.\d+)")
    found = {}
    for rel in ("UserGuide.txt", "UserGuide.html", "no-api-key-guide.html",
                "README.md"):
        for m in claim.finditer((here / rel).read_text(encoding="utf-8")):
            found.setdefault(rel, set()).add(m.group(1))
    stale = {f: sorted(v) for f, v in found.items()
             if v - {pc.APP_VERSION}}
    assert not stale, (
        "docs disagree with APP_VERSION %s: %s" % (pc.APP_VERSION, stale))


def test_python_requirement_lines_were_not_mistaken_for_the_version():
    """The guides' "Python 3.9" is the interpreter requirement, not the app
    version. The sweep above must never rewrite it."""
    here = Path(__file__).resolve().parent.parent
    for rel in ("UserGuide.txt", "UserGuide.html"):
        t = (here / rel).read_text(encoding="utf-8")
        assert re.search(r"Python 3\.9", t), rel


def test_version_bump_is_visible_in_the_ui(owner_window):
    """APP_VERSION is what the title bar and About box show, so a bump that
    only edits the docs would leave the running app reporting the old one."""
    app, root = owner_window
    _pump(root)
    assert pc.APP_VERSION in root.title(), (
        "window title %r does not carry APP_VERSION %r"
        % (root.title(), pc.APP_VERSION))
    assert pc.APP_VERSION.count(".") == 1, pc.APP_VERSION


def test_escalation_written_above_the_section_is_a_normal_question():
    # the documented fix: a question above the heading is listed normally
    good = ESCALATION_APPENDED.replace(
        "\n\n1. PROBLEM: the Coolify app id",
        "\n\n## New gaps\n\n1. PROBLEM: the Coolify app id")
    assert pc.unaccounted_escalations(good) == []
    assert len(pc.parse_questions(good)) == 2


def test_owner_actions_bullets_are_not_reported_as_stranded():
    # the normal case must stay silent, or the warning becomes noise the
    # owner learns to ignore
    text = ("## Owner actions\n\n"
            "- [ ] Confirm the prod count. `git log -1` (expect: matches)\n"
            "- [x] already handled `git status`\n")
    assert pc.unaccounted_escalations(text) == []


def test_stranded_escalation_raises_a_warning_gate(tmp_path):
    pdir = tmp_path / "plans" / "demo"
    write(pdir / "PART-01.draft.md", "# draft\n")
    write(pdir / "RECON-CHECKLIST.md", "- [x] done\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    write(pdir / "OPEN-QUESTIONS.md", ESCALATION_APPENDED)
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    g = gates["escalation"]
    assert g is not None, "a stranded escalation must raise a gate"
    # a WARNING, never a hard block: a formatting quirk must not strand a
    # legitimate plan
    assert g["ok"] is True
    assert g["level"] == "warn"
    assert "Coolify" in g["detail"]


def test_no_stranded_gate_on_a_well_formed_file(tmp_path):
    pdir = tmp_path / "plans" / "ok"
    write(pdir / "PART-01.draft.md", "# draft\n")
    write(pdir / "RECON-CHECKLIST.md", "- [x] done\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    write(pdir / "OPEN-QUESTIONS.md",
          "1. PROBLEM: a\n   QUESTION: b?\n   RECOMMEND: c\n\n"
          "## Owner actions\n\n- [x] ran `git status`\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert "escalation" not in gates
    # the question above is still open, so the questions gate MUST fail —
    # this asserts the warning is absent, not that the plan is clean
    assert gates["questions"]["ok"] is False
    assert gates["owner_actions"]["ok"] is True


# ------------------------------------- 2. owner-section case-sensitivity bug
def test_owner_section_heading_is_case_insensitive():
    # '## owner actions' opened the question parser's skipped region but
    # the action parser looked for the exact literal '## Owner actions',
    # so its content was counted by NEITHER and the gate silently passed.
    for header in ("## Owner actions", "## owner actions",
                   "## OWNER ACTIONS", "## Owner Actions",
                   "## Owner actions (OWNER-ONLY items)"):
        text = ("1. PROBLEM: a\n   QUESTION: b?\n   RECOMMEND: c\n\n"
                "%s\n- [ ] run the migration `py -3 migrate`\n" % header)
        assert pc.count_open_owner_actions(text) == 1, header
        assert len(pc.parse_owner_actions(text)) == 1, header


def test_both_parsers_agree_on_section_extent():
    # a '###' subsection used to close one parser's region and not the
    # other's; both must now stop at a heading of ANY depth
    text = ("1. PROBLEM: a\n   QUESTION: b?\n   RECOMMEND: c\n\n"
            "## Owner actions\n\n- [ ] real action `git status`\n"
            "### Sub notes\n\n- [ ] not an action\n")
    assert pc.count_open_owner_actions(text) == 1
    assert len(pc.parse_questions(text)) == 1


def test_owner_actions_code_fence_still_excluded():
    text = ("## Owner actions\n```\n- [ ] `git commit` in a fence\n```\n"
            "- [ ] real `git status`\n")
    assert pc.count_open_owner_actions(text) == 1