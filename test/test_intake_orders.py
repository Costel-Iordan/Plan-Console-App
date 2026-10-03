"""v3.8 — phase-scoped standing orders: the intake contract must actually
REACH the agent on every intake path, must never leak into a session
instruction (and vice versa), and the off-console owner-action backstop
must warn without blocking Freeze.

The defect these gate: AGENT-ORDERS.md was attached in exactly ONE of
seven instruction builders (on_copy_instr), so the whole intake phase —
new-plan, recon, owner-resolve, auto-resolve, and every _run_api prompt —
ran with no standing contract, and agents performed owner-only work.

Run either way:
    py test/test_intake_orders.py
    py -m pytest test/test_intake_orders.py
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

INTAKE = pc.AGENT_ORDERS_PHASE_INTAKE
SESSION = pc.AGENT_ORDERS_PHASE_SESSION

# A marker unique to each contract. Asserting on the MARKER rather than on
# shared boilerplate is what makes "no phase bleed" testable at all: both
# documents legitimately talk about scope and gates.
INTAKE_MARK = "STANDING ORDERS — INTAKE AGENT"
SESSION_MARK = "STANDING ORDERS — EXECUTION AGENT"

DRAFT_STUB = "# PART 01 — demo draft\n\n§A body\n"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _repo(tmp_path):
    """A minimal plan repo: every command file _instruction() may name."""
    repo = tmp_path / "repo"
    write(repo / "PART-00.md", "# PART 00\n")
    # _intake_chain reads this BEFORE its no-key branch, so a repo without
    # it fails silently (the chain swallows the error and logs it).
    write(repo / "templates" / "PART-01.md", "# PART 01 template\n")
    for cmd in ("new-plan", "recon", "owner-resolve", "validate-plan",
                "session", "freeze-plan"):
        write(repo / "commands" / ("%s.md" % cmd), "# %s\n" % cmd)
    return repo


@pytest.fixture()
def app_window(tmp_path, monkeypatch):
    """A real (withdrawn) App on a temp config, offline — same shape and
    same Tk-retry discipline as the other suites: a transient TclError
    must not turn into a silent skip (a gate that reports green because
    it stopped running is the failure class this repo gates against)."""
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
    root.withdraw()
    monkeypatch.setattr(pc, "_high_contrast_active", lambda: False)
    monkeypatch.setattr(pc, "CFG", tmp_path / "plan-console.json")
    monkeypatch.setattr(pc.App, "_fetch_models", lambda self: None)
    monkeypatch.setattr(pc.App, "_auto_command_check",
                        lambda self, repo=None: None)
    # The orders sidecar is seeded next to the SCRIPT — never inside this
    # test's tmp_path. Redirect HERE so a test that triggers seeding
    # cannot write AGENT-ORDERS*.md into the real install directory.
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    monkeypatch.setattr(pc, "HERE", sidecar)
    app = pc.App(root)
    root.update()
    yield app, root
    try:
        root.destroy()
    except tk.TclError:
        pass


def _capture(app, monkeypatch):
    """Capture instruction text instead of popping it up."""
    seen = []
    monkeypatch.setattr(app, "_show_instruction",
                        lambda title, text, save=None: seen.append(text))
    return seen


# ------------------------------------------------- the orders reach intake
def test_every_intake_path_carries_the_intake_orders(app_window, tmp_path,
                                                     monkeypatch):
    """The regression this whole change exists for: all five intake
    emitters must carry the contract, not one of seven."""
    app, root = app_window
    repo = _repo(tmp_path)
    app.repo_var.set(str(repo))
    app.slug_var.set("demo-plan")
    pdir = repo / "plans" / "demo-plan"
    write(pdir / "SOURCE.md", "# SOURCE\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] EXISTS: x.txt\n")
    write(pdir / "PART-01.draft.md", DRAFT_STUB)
    seen = _capture(app, monkeypatch)
    monkeypatch.setattr(app, "_or_key_value", lambda: "")

    # 1 — the multi-step intake block (hand-built, not _instruction())
    app._intake_chain(repo, "demo-plan",
                      {"kind": "plan", "recon": True, "validate": False,
                       "auto_fix": False, "model": "", "key": ""})
    assert seen, "the no-key intake path emitted no instruction"
    block = seen[-1]
    assert INTAKE_MARK in block, "intake chain lost the contract"
    assert "INTAKE BLOCK" in block
    assert "commands/new-plan.md" in block, "ordered steps must survive"

    # 2 — auto-resolve (hand-built; the remediation loop where findings
    # ask for owner-run commands — the most tempting place to run them)
    ar = app._auto_resolve_instruction(repo, "demo-plan",
                                       {"fix_draft": [], "other": [], "n": 0})
    assert INTAKE_MARK in ar, "auto-resolve lost the contract"

    # 3/4/5 — the three _instruction()-shaped emitters
    for cmd in ("recon.md", "owner-resolve.md", "validate-plan.md"):
        t = app._intake_instruction(repo, cmd, "demo-plan")
        assert INTAKE_MARK in t, "%s lost the contract" % cmd
        assert "INTAKE BLOCK" in t
        assert cmd in t, "the command block itself must survive"


def test_api_lane_prompt_carries_the_intake_orders(app_window, tmp_path,
                                                   monkeypatch):
    """_run_api is the unattended path: with a key set the console IS the
    agent, and it previously had no contract at all."""
    app, root = app_window
    repo = _repo(tmp_path)
    captured = {}

    def fake_call(prompt, model, key):
        captured["prompt"] = prompt
        return "<<<FILE: plans/demo-plan/PART-01.draft.md>>>\nx\n<<<END>>>"

    monkeypatch.setattr(app, "_api_call", fake_call)
    assert app._run_api(repo, "intake", "recon.md", "demo-plan", "demo-plan",
                        [("PART-00.md", "# PART 00\n")], "m", "k") is True
    p = captured["prompt"]
    assert INTAKE_MARK in p
    # The contract must PRECEDE the command file and FILE_RULES: it reads
    # as permanent context, and FILE_RULES' path rule must never be
    # mistaken for the behavioral ban it does not contain.
    assert p.index(INTAKE_MARK) < p.index("OUTPUT PROTOCOL")
    assert p.index(INTAKE_MARK) < p.index("# recon")


def test_intake_orders_state_the_hard_ban(app_window, tmp_path, monkeypatch):
    """Content guard: the contract must actually FORBID owner work. A
    document that only said "be careful" would pass the tests above."""
    app, _root = app_window
    repo = _repo(tmp_path)
    text = app._intake_instruction(repo, "recon.md", "demo-plan")
    for must in ("never RUN a command", "never DEPLOY",
                 "never tick an owner checkbox", "never run migrations"):
        assert must in text, "intake orders must say: %s" % must
    # The C5 inversion must be explicit, or agents run the test suite
    # mid-intake (the reason this is not the execution contract).
# --------------------------------------------------------- no phase bleed
def test_session_block_keeps_the_execution_contract(app_window, tmp_path,
                                                   monkeypatch):
    """Session output must be provably unchanged: execution orders, the
    pre-v3.8 separator text verbatim, and NO intake contract leaking in."""
    app, _root = app_window
    repo = _repo(tmp_path)
    text = pc.App._prepend_orders(None, "BODY",
                                  app._agent_orders(repo, SESSION), SESSION)
    assert SESSION_MARK in text
    assert INTAKE_MARK not in text, "intake orders must not reach a session"
    assert ("===== SESSION BLOCK (the session spec that follows) — the "
            "standing orders above apply. Authorized scope, gates and "
            "deploy rules come from PART-01 §A via commands/session.md. "
            "=====") in text, "session separator changed — C2 diffability"


def test_intake_orders_resolve_to_the_intake_file(app_window, tmp_path,
                                                  monkeypatch):
    """Precedence: a per-repo override wins for that repo, and the two
    phases never read each other's file."""
    app, _root = app_window
    repo = _repo(tmp_path)
    write(repo / pc.AGENT_ORDERS_NAME, "SESSION-ONLY-MARKER\n")
    write(repo / pc.AGENT_ORDERS_INTAKE_NAME, "INTAKE-ONLY-MARKER\n")
    assert "SESSION-ONLY-MARKER" in app._agent_orders(repo, SESSION)
    assert "INTAKE-ONLY-MARKER" in app._agent_orders(repo, INTAKE)
    # the two defaults are different documents, not one shared file
    assert (pc.AGENT_ORDERS_DEFAULT.strip()
            != pc.AGENT_ORDERS_INTAKE_DEFAULT.strip())
    assert INTAKE_MARK in pc.AGENT_ORDERS_INTAKE_DEFAULT
    assert SESSION_MARK in pc.AGENT_ORDERS_DEFAULT
    assert SESSION_MARK not in pc.AGENT_ORDERS_INTAKE_DEFAULT


def test_off_disables_each_phase_independently(app_window, tmp_path,
                                               monkeypatch):
    """An 'OFF' intake file must silence the intake contract while the
    session contract keeps working — the phases are independent."""
    app, _root = app_window
    repo = _repo(tmp_path)
    write(repo / pc.AGENT_ORDERS_INTAKE_NAME, "OFF\n")
    assert app._agent_orders(repo, INTAKE) == ""
    assert app._agent_orders(repo, SESSION), "session must survive intake OFF"
    text = app._intake_instruction(repo, "recon.md", "demo-plan")
    assert INTAKE_MARK not in text
    assert "commands/recon.md" in text, "the command block must survive"


def test_edit_orders_follows_the_active_tab(app_window, tmp_path,
                                            monkeypatch):
    """One button, phase-aware: the tab already says which contract is
    next, so the button follows it instead of duplicating."""
    app, _root = app_window
    repo = _repo(tmp_path)
    app.repo_var.set(str(repo))
    opened = []
    monkeypatch.setattr(app, "_open_path",
                        lambda p: (opened.append(p), True)[1])
    app.nb.select(0)                      # Intake
    app.on_edit_agent_orders()
    assert opened[-1].name == pc.AGENT_ORDERS_INTAKE_NAME
# ------------------------------------------------------- Phase 4 backstop
def test_agent_ticked_owner_action_is_flagged_not_blocked(tmp_path):
    """The backstop: a ticked `- [x]` with no console log entry means the
    agent ran owner work. It must WARN and still let Freeze proceed — a
    hard block on a log miss would strand a legitimate plan whose actions
    the owner ran by hand."""
    pdir = tmp_path / "plans" / "demo"
    write(pdir / "PART-01.draft.md", DRAFT_STUB)
    write(pdir / "RECON-CHECKLIST.md", "- [x] checked\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    write(pdir / "OPEN-QUESTIONS.md",
          "## Owner actions\n- [x] run the migration `py -3 migrate`\n")
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    assert gates["owner_actions_unlogged"]["ok"] is True, "must not block"
    assert gates["owner_actions_unlogged"]["level"] == "warn"
    assert pc.OWNER_PASS_LOG in gates["owner_actions_unlogged"]["detail"]
    # every other gate still passes, so Freeze really is unblocked
    assert all(g["ok"] for g in pc.freeze_gate_report(pdir))


def test_console_ticked_owner_action_is_not_flagged(tmp_path):
    """The benign case must stay silent — otherwise every owner sees a
    false alarm and learns to ignore the warning.

    Driven through the REAL _log_owner_action, not a hand-written log
    line: the detector matches on the log's format, so a fixture that
    merely looks right would pass while production false-alarms on every
    plan (at v3.5.2 the log did not exist at all — this test is what
    pins the two together)."""
    pdir = tmp_path / "plans" / "demo"
    write(pdir / "PART-01.draft.md", DRAFT_STUB)
    write(pdir / "RECON-CHECKLIST.md", "- [x] checked\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    prose = "run the migration `py -3 migrate`"
    write(pdir / "OPEN-QUESTIONS.md",
          "## Owner actions\n- [x] %s\n" % prose)

    # the real writer, with only its Tk/dialog dependencies stubbed
    app = object.__new__(pc.App)
    app._oq_file = pdir / "OPEN-QUESTIONS.md"
    said = []
    app.say = lambda t, m: said.append(m)
    pc.App._log_owner_action(app, {"command": "py -3 migrate",
                                   "prose": prose}, "marked done")
    assert (pdir / pc.OWNER_PASS_LOG).is_file(), "the log must exist"
    ids = [g["id"] for g in pc.freeze_gate_report(pdir)]
    assert "owner_actions_unlogged" not in ids, \
        "a console-ticked action must never be flagged"


def test_backstop_is_read_only_and_forgiving(tmp_path):
    """No OPEN-QUESTIONS.md, no plan dir at all: never raise. A detector
    that crashes Freeze is worse than no detector."""
    empty = tmp_path / "plans" / "none"
    empty.mkdir(parents=True)
    assert pc.externally_ticked_owner_actions(empty) == []
    assert pc.externally_ticked_owner_actions(tmp_path / "missing") == []
    # actions present but no log at all → report them (unattributable),
    # rather than assume the benign case
    pdir = tmp_path / "plans" / "nolog"
    write(pdir / "OPEN-QUESTIONS.md",
          "## Owner actions\n- [x] do the thing `cmd-here`\n")
    assert pc.externally_ticked_owner_actions(pdir) == \
        ["do the thing `cmd-here`"]


def test_backstop_ignores_unchecked_actions(tmp_path):
    """An unchecked action is not a forgery — nothing to warn about."""
    pdir = tmp_path / "plans" / "open"
    write(pdir / "OPEN-QUESTIONS.md",
          "## Owner actions\n- [ ] still pending `cmd-here`\n")
    assert pc.externally_ticked_owner_actions(pdir) == []
    assert "owner_actions_unlogged" not in [
        g["id"] for g in pc.freeze_gate_report(pdir)]


def test_pre_v38_gate_ids_unchanged(tmp_path):
    """The new gate is ADDITIVE: with nothing to flag, the id list is
    exactly the pre-v3.8 seven, so no existing caller can be surprised."""
    pdir = tmp_path / "plans" / "clean"
    write(pdir / "PART-01.draft.md", DRAFT_STUB)
    write(pdir / "RECON-CHECKLIST.md", "- [x] checked\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    write(pdir / "OPEN-QUESTIONS.md", "no owner actions here\n")
    assert [g["id"] for g in pc.freeze_gate_report(pdir)] == \
        ["draft", "frozen", "questions", "owner_actions", "parked",
         "recon", "validation"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
    app.nb.select(1)                      # Sessions
    app.on_edit_agent_orders()
    assert opened[-1].name == pc.AGENT_ORDERS_NAME


def test_orders_attached_is_logged(app_window, tmp_path, monkeypatch):
    """The provenance line is what makes a silently-dropped contract
    visible to the owner instead of invisible."""
    app, _root = app_window
    repo = _repo(tmp_path)
    said = []
    app.say = lambda t, m: said.append(m)
    app._intake_instruction(repo, "recon.md", "demo-plan")
    assert any("intake contract attached" in m for m in said), said
    # and a disabled phase says so too — silence would be ambiguous
    said.clear()
    write(repo / pc.AGENT_ORDERS_INTAKE_NAME, "OFF\n")
    app._intake_instruction(repo, "recon.md", "demo-plan")
    assert any("DISABLED" in m for m in said), said


def test_intake_command_files_carry_the_ban_too():
    """The contract is defense-in-depth over the command files: an agent
    reading only commands/new-plan.md must still meet the ban."""
    root = HERE.parent
    for name in ("new-plan.md", "recon.md"):
        body = (root / "commands" / name).read_text(encoding="utf-8")
        assert "HARD BAN" in body, "%s lost the hard ban" % name
        assert "never tick an owner checkbox" in body, name
    # and new-plan.md must forbid the build/lint/test run explicitly
    np = (root / "commands" / "new-plan.md").read_text(encoding="utf-8")
    assert "do NOT run the project's build" in np


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))