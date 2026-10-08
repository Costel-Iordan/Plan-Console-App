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
# indented, NO leading pipe). v3.10 — a leading-pipe markdown table is
# now EQUALLY valid; see MAP_PIPE_ROWS and the session-map section below.
FROZEN_ROWS = (
    "# PART 01 — demo | v1.0 frozen 2026-09-26\n\n"
    "    # | one-line scope | gates | deploy?\n"
    "    1 | Implement the parser | g1, g2 | no\n"
    "    2 | Deploy to production | g7 | split\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ------------------------------------------ v3.10 §A session-map shapes
# The defect: fold_map_rows treated every leading-pipe line as a WRAP of
# the row above it — both have only whitespace before the first '|' — so a
# markdown table's header swallowed row 1 and row 1 swallowed row 2. The
# whole table folded into one line, session_map_rows() returned {}, and
# Plan health printed "no session rows in PART-01 §A" for a plan whose
# PROGRESS.md recorded the session as PASS. The comment above used to warn
# that a leading '|' was unsupported; it is supported now.

MAP_PLAN = ("# PART 01 — demo | v1.0 frozen 2026-10-02\n"
            "\nA. MISSION & SCOPE\n"
            "   Session map:\n"
            "{rows}"
            "\nB. VERIFIED INFRASTRUCTURE FACTS\n"
            "   x\n")
TEMPLATE_MAP = ("     # | one-line scope | gates | deploy?\n"
                "     1 | Implement the parser | g1, g2 | no\n"
                "     2 | Deploy to production | g7 | split\n")
PIPE_MAP = ("   | # | one-line scope | gates | deploy? |\n"
            "   | 1 | Implement the parser | g1, g2 | no |\n"
            "   | 2 | Deploy to production | g7 | split |\n")
# two plain rows: a split row renders as legs, so it needs two PROGRESS
# records per session before the plan counts as fully recorded
PLAIN_MAP = ("     # | one-line scope | gates | deploy?\n"
             "     1 | Implement the parser | g1, g2 | no\n"
             "     2 | Wire the edge functions | g3 | no\n")
EXPECTED_MAP = {1: ("Implement the parser", "g1, g2", False, False),
                2: ("Deploy to production", "g7", True, True)}


def frozen_with_map(tmp_path, rows):
    pdir = tmp_path / "plans" / "demo"
    write(pdir / "PART-01 v1.0.md", MAP_PLAN.format(rows=rows))
    return pdir


@pytest.mark.parametrize("rows", [TEMPLATE_MAP, PIPE_MAP],
                         ids=["template-shape", "leading-pipe-table"])
def test_session_map_reads_either_table_shape(tmp_path, rows):
    assert pc.session_map_rows(frozen_with_map(tmp_path, rows)) == EXPECTED_MAP


@pytest.mark.parametrize("rows", [TEMPLATE_MAP, PIPE_MAP],
                         ids=["template-shape", "leading-pipe-table"])
def test_row_count_and_gates_parsers_agree(tmp_path, rows):
    """One table, one answer. session_map_rows() and session_row_gates()
    reading different cell offsets is how a plan was told 'no session
    rows' by one parser while the other found the gates."""
    pdir = frozen_with_map(tmp_path, rows)
    text = (pdir / "PART-01 v1.0.md").read_text(encoding="utf-8")
    for n in pc.session_map_rows(pdir):
        assert pc.session_row_gates(text, n), n


def test_pipe_table_row_with_no_deploy_cell(tmp_path):
    pdir = frozen_with_map(tmp_path, "   | 1 | Implement the parser | g1 |\n")
    assert pc.session_map_rows(pdir) == {
        1: ("Implement the parser", "g1", False, False)}


def test_session_number_with_trailing_dot_is_a_row(tmp_path):
    # session_row_gates has always accepted '1.' / '1)' / '1:'; the row
    # parser tested cells[0].isdigit(), so a dotted row produced gates
    # from one parser and no row from the other
    pdir = frozen_with_map(tmp_path, "   | 1. | Implement | g1 | no |\n")
    assert list(pc.session_map_rows(pdir)) == [1]


def test_map_row_cells_drops_table_punctuation():
    assert pc.map_row_cells("| 1 | do it | g1 | no |") == ["1", "do it",
                                                           "g1", "no"]
    assert pc.map_row_cells("  1 | do it | g1 | no") == ["1", "do it",
                                                         "g1", "no"]


# ------------------------- v3.10 a scope cell wrapped by plain indentation
# The reported bug. fold_map_rows only folds a continuation that BEGINS with
# '|'. This plan indents its continuations instead, so nothing folded: each
# row's first line carried 2 cells and was dropped for having fewer than 3,
# and the stranded '| gN | no' terminator sat on a line whose first cell was
# prose ('redeploy', 'in scope'). All eight sessions vanished and Plan health
# reported 'no session rows in PART-01 §A' for a plan whose PROGRESS.md
# recorded session 1 as PASS.
WRAPPED_MAP = (
    "     # | one-line scope | gates | deploy?\n"
    "     1 | Router request-budget fix: thinkingBudget 0 in\n"
    "       callGemini (A1) and cut the default\n"
    "       timeoutMs 45 000 -> 20 000 (A6). CONFIRMED 2026-10-03 |\n"
    "       g1 | no\n"
    "     2 | Deploy session, owner-supervised | g8 | yes\n")


def test_wrapped_scope_row_is_one_row(tmp_path):
    rows = pc.session_map_rows(frozen_with_map(tmp_path, WRAPPED_MAP))
    assert sorted(rows) == [1, 2]
    assert rows[1][1] == "g1"
    assert rows[1][2] is False
    assert rows[1][3] is False
    # the whole scope, all three physical lines, space-joined (the trailing
    # '|' opens an empty cell, and empty cells are not cells)
    assert rows[1][0] == (
        "Router request-budget fix: thinkingBudget 0 in callGemini (A1) "
        "and cut the default timeoutMs 45 000 -> 20 000 (A6). "
        "CONFIRMED 2026-10-03")
    assert rows[2][2] is True


def test_wrapped_scope_row_gates_resolve(tmp_path):
    pdir = frozen_with_map(tmp_path, WRAPPED_MAP)
    text = (pdir / "PART-01 v1.0.md").read_text(encoding="utf-8")
    assert pc.session_row_gates(text, 1) == ["g1"]
    assert pc.session_row_gates(text, 2) == ["g8"]


def test_wrapping_does_not_reach_past_the_row(tmp_path):
    """A row that never gets its third cell must not swallow the rest of
    the plan — §B, §C and §E are all indented too. (session_map_rows
    drops the unfinished row itself: a session row must declare gates.)"""
    pdir = frozen_with_map(
        tmp_path,
        "     1 | a scope with no gates column at all, wrapping\n"
        "       across several indented lines and never closing\n")
    out = pc.complete_map_rows(
        (pdir / "PART-01 v1.0.md").read_text(encoding="utf-8").splitlines())
    row = next(l for l in out if l.lstrip().startswith("1 |"))
    assert row.startswith("     1 | a scope with no gates column")
    assert "across several indented lines" in row, row
    assert "VERIFIED INFRASTRUCTURE" not in row
    assert len(row) < 200
    # and the plan below the map is still there, verbatim
    assert "B. VERIFIED INFRASTRUCTURE FACTS" in out


def test_prose_below_the_map_is_never_absorbed(tmp_path):
    """The whole plan, checked directly: only continuation lines that belong
    to an unfinished row may move, and no heading may disappear."""
    body = ("     # | one-line scope | gates | deploy?\n"
            "     1 | wrapped scope that keeps going\n"
            "       and going | g1 | no\n"
            "B. VERIFIED INFRASTRUCTURE FACTS\n"
            "   every fact — verified 2026-10-04\n"
            "   more indented prose that must survive\n"
            "C. TARGET STRUCTURE\n"
            "   src/app/api/thing/route.ts\n")
    pdir = frozen_with_map(tmp_path, body)
    out = pc.complete_map_rows(
        (pdir / "PART-01 v1.0.md").read_text(encoding="utf-8").splitlines())
    joined = "\n".join(out)
    for must in ("B. VERIFIED INFRASTRUCTURE FACTS", "C. TARGET STRUCTURE",
                 "every fact — verified 2026-10-04",
                 "more indented prose that must survive",
                 "src/app/api/thing/route.ts"):
        assert must in joined, must


def test_blank_line_ends_an_unfinished_row(tmp_path):
    out = pc.complete_map_rows(
        ["  1 | scope with no gates", "", "  unrelated | text | here"])
    assert "unrelated" not in out[0]


def test_real_plan_shape_end_to_end(tmp_path):
    """The exact failure, as reported: 8 wrapped rows, session 1 recorded."""
    pdir = frozen_with_map(
        tmp_path,
        "   Session budget: 8 sessions (7 + deploy).\n"
        "   Session map (standing gates every session):\n"
        "     # | one-line scope | gates | deploy?\n"
        "     1 | fix the router budget, which takes a lot of prose to\n"
        "       describe across more than one line because it is a big\n"
        "       change | g1 | no\n"
        "     1a | OWNER-ONLY, no gate: retained for numbering only\n"
        "       | g1a: void | no\n"
        "     2 | deploy, owner-supervised | g8 | yes\n")
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1 | status: PASS | P00 v1.0\n")

    class _App(pc.App):
        def __init__(self):
            pass
        _frozen_file = staticmethod(pc.find_frozen_file)
        _ip_summary = staticmethod(lambda p: (None, 0, "", ""))
        _git_dirty = staticmethod(lambda r: None)

    rows = pc.session_map_rows(pdir)
    assert sorted(rows) == [1, 2], rows
    assert "1a" not in rows, "a void sub-row authorizes nothing"
    lines = pc.App._mkhealth(_App(), tmp_path, pdir.name)
    assert "no session rows" not in lines[0], lines
    assert "1  OK" in lines[1], lines
    assert "2 sessions" in lines[0], lines


def test_fold_map_rows_still_folds_a_wrapped_gates_cell():
    assert pc.fold_map_rows(
        ["  1 | scope | g1, g2, g4,", "    | g5 | no"]
    ) == ["  1 | scope | g1, g2, g4,  g5 | no"]


def test_fold_map_rows_still_folds_a_wrapped_scope_cell():
    assert pc.fold_map_rows(
        ["  1 | stand up the ingest across", "    | three regions | g1 | no"]
    ) == ["  1 | stand up the ingest across  three regions | g1 | no"]


def test_fold_map_rows_leaves_a_following_row_alone():
    assert pc.fold_map_rows(
        ["  1 | scope | g1, g4,", "    | g5 | no", "  2 | next | g6 | no"]
    ) == ["  1 | scope | g1, g4,  g5 | no", "  2 | next | g6 | no"]


# ------------------------------- v3.10 an unreadable map is not a done plan
# next_pending_session() looped over sorted(rows) and fell through to the
# 'all sessions recorded' return when rows was EMPTY — so any §A parse
# failure made the plan strip GREEN and read 'next: all sessions recorded
# ✓' for a plan whose sessions had never been read, while Plan health on
# the same frozen file said 'no session rows in PART-01 §A'. Two surfaces,
# one file, and the confident one was wrong in the dangerous direction.

NO_ROWS_MAP = "   Session map: to be written by the owner.\n"


def _next(pdir):
    return pc.next_pending_session(pdir)


def test_unreadable_map_is_not_reported_as_all_done(tmp_path):
    pdir = frozen_with_map(tmp_path, NO_ROWS_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n")
    nxt = _next(pdir)
    assert nxt["unreadable"] is True
    assert nxt["label"] != "all sessions recorded"
    assert "no session rows" in nxt["label"]
    assert nxt["copyable"] is False, "nothing may be prefilled from a map " \
                                    "the console could not read"


def test_a_genuinely_finished_plan_is_still_all_done(tmp_path):
    pdir = frozen_with_map(tmp_path, PLAIN_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n"
          "SESSION 2 | 2026-10-04 | gates: g3 | status: PASS | P00 v1.0\n")
    nxt = _next(pdir)
    assert nxt["unreadable"] is False
    assert nxt["label"] == "all sessions recorded"


def test_every_row_recorded_reads_as_done_not_unreadable(tmp_path):
    """The distinction that matters: an empty map and a fully-recorded map
    are different facts and must never produce the same answer."""
    pdir = frozen_with_map(tmp_path, PLAIN_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n"
          "SESSION 2 | 2026-10-04 | gates: g3 | status: PASS | P00 v1.0\n")
    assert pc.session_map_rows(pdir) != {}
    assert _next(pdir)["label"] == "all sessions recorded"


def test_a_partly_run_plan_offers_the_next_session(tmp_path):
    pdir = frozen_with_map(tmp_path, PLAIN_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n")
    nxt = _next(pdir)
    assert nxt["n"] == 2 and nxt["copyable"] is True
    assert nxt.get("unreadable") is not True


def test_unfrozen_plan_still_has_no_next(tmp_path):
    pdir = tmp_path / "plans" / "demo"
    pdir.mkdir(parents=True)
    assert _next(pdir) is None


def test_strip_does_not_go_green_on_an_unreadable_map(tmp_path):
    """The strip is the surface that misled: accent-green + a tick meant
    'nothing left to do'."""
    pdir = frozen_with_map(tmp_path, NO_ROWS_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n")

    class _W:
        def __init__(self):
            self.out = {}

        def configure(self, **k):
            self.out.update(k)

        def pack(self, **k):
            pass

    class _App(pc.App):
        def __init__(self):
            self.strip_state, self.strip_next = _W(), _W()
            self.strip_action, self.strip_slug = _W(), _W()
            self.colors = []
            self._strip_fg = lambda w, c: self.colors.append(c)
            self.repo_path = lambda: tmp_path
            self.slug_var = type("V", (), {"get": staticmethod(
                lambda: "demo")})()

        _frozen_file = staticmethod(pc.find_frozen_file)
        _ip_summary = staticmethod(lambda p: (None, 0, "", ""))
        _git_dirty = staticmethod(lambda r: None)

    app = _App()
    pc.App._strip_render(app)
    assert "all sessions recorded" not in app.strip_next.out["text"]
    assert app.strip_next.out["text"].startswith("next: session map")
    assert "accent-green" not in app.colors, app.colors
    assert app.strip_action.out["text"].startswith("Plan health")


def test_health_reports_the_session_that_progress_records(tmp_path):
    """The reported bug end to end: a plan whose PROGRESS.md says
    SESSION 1 PASS, but whose §A is a markdown table, was reported as
    'no session rows in PART-01 §A'."""
    pdir = frozen_with_map(
        tmp_path,
        "   | # | one-line scope | gates | deploy? |\n"
        "   | 1 | Implement the parser | g1, g2 | no |\n"
        "   | 2 | Wire the edge functions | g3 | no |\n")
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n")

    class _App(pc.App):
        def __init__(self):            # no Tk: stub the two GUI reads
            pass
        _frozen_file = staticmethod(pc.find_frozen_file)
        _ip_summary = staticmethod(lambda p: (None, 0, "", ""))
        _git_dirty = staticmethod(lambda r: None)

    lines = _App()._mkhealth(tmp_path, pdir.name)
    assert "no session rows" not in lines[0], lines
    assert "1  OK" in lines[1], lines
    assert "passed: 1/2" in lines[-2], lines


# ------------------------------------- v3.11 declared checks ('## Checks')
# A gate the owner cannot run is a wish: the agent asserts 'status: PASS'
# in PROGRESS.md and the console never checks. A lint or typecheck failure
# could therefore only reach the agent by the owner running the tool and
# pasting the output by hand. '## Checks' in the FROZEN plan makes those
# commands first-class.
CHECKS_PLAN = (
    "# PART 01 — demo | v1.0 frozen 2026-10-04\n\n"
    "A. MISSION & SCOPE\n"
    "     # | one-line scope | gates | deploy?\n"
    "     1 | do it | g1 | no\n"
    "B. VERIFIED INFRASTRUCTURE FACTS\n"
    "   a fact\n"
    "\n## Checks\n"
    "- LINT: `npm run lint`\n"
    "- TYPES: `npm run typecheck`\n"
    "- EXPLICIT: `npm test` (expect: exit 0)\n"
    "\n## Owner actions\n"
    "- [ ] unrelated `git status`\n")


def test_parse_checks_reads_id_and_command():
    got = pc.parse_checks(CHECKS_PLAN)
    assert [c["id"] for c in got] == ["LINT", "TYPES", "EXPLICIT"]
    assert got[0]["command"] == "npm run lint"
    assert got[2]["expect"] == "exit 0"
    assert [c["error"] for c in got] == [None, None, None]


def test_checks_section_does_not_disturb_owner_actions():
    got = pc.parse_owner_actions(CHECKS_PLAN)
    assert [a["command"] for a in got] == ["git status"]


def test_checks_absent_is_empty_not_an_error():
    assert pc.parse_checks("# PART 01\n\nA. SCOPE\n   x\n") == []


def test_check_without_an_id_is_invalid_not_skipped():
    """A check that silently never runs is the failure mode this feature
    exists to remove, so it comes back NAMED."""
    got = pc.parse_checks("## Checks\n- `npm run orphan`\n")
    assert len(got) == 1
    assert got[0]["id"] is None
    assert got[0]["command"] == "npm run orphan"
    assert "no id" in got[0]["error"]


def test_check_without_a_command_is_invalid():
    got = pc.parse_checks("## Checks\n- LINT: nothing in backticks\n")
    assert "no command" in got[0]["error"]


def test_unsupported_expect_is_refused_by_name():
    """Never silently downgraded to 'exit 0': the owner asked for a
    criterion the console does not implement."""
    got = pc.parse_checks("## Checks\n- X: `npm run x` (expect: no matches)\n")
    assert got[0]["command"] == "npm run x"
    assert "no matches" in got[0]["error"]


def test_check_command_is_the_backticked_span_only():
    """Same rule the owner-action parser uses: the command is the
    backticked span, on one line. Trailing prose on the bullet is NOT
    guessed at as part of the command — silently appending it would run
    something the owner never wrote."""
    got = pc.parse_checks(
        "## Checks\n- LINT: `npx eslint src` --max-warnings 0\n")
    assert got[0]["command"] == "npx eslint src"
    assert got[0]["error"] is None
    # a command wrapped onto the continuation line is not completed either
    got = pc.parse_checks(
        "## Checks\n- LINT: `npx eslint src`\n  --max-warnings 0\n")
    assert got[0]["command"] == "npx eslint src"


def test_checks_in_a_code_fence_never_count():
    assert pc.parse_checks(
        "## Checks\n```\n- LINT: `npm run lint`\n```\n") == []


class _R:
    def __init__(self, code, out="", err=""):
        self.returncode, self.stdout, self.stderr = code, out, err


def _stub(code=0, out="", err=""):
    def runner(cmd, **kw):
        runner.calls.append(kw)
        return _R(code, out, err)
    runner.calls = []
    return runner


def test_run_checks_reports_exit_code_as_the_verdict():
    checks = pc.parse_checks("## Checks\n- LINT: `npm run lint`\n")
    ok = pc.run_checks(".", checks, runner=_stub(0))
    assert ok[0]["ok"] is True and ok[0]["code"] == 0
    bad = pc.run_checks(".", checks, runner=_stub(1, out="88:11  error  any"))
    assert bad[0]["ok"] is False and bad[0]["code"] == 1
    assert "88:11  error  any" in bad[0]["output"]


def test_run_checks_never_executes_an_invalid_check():
    checks = pc.parse_checks("## Checks\n- X: `npm run x` (expect: nope)\n")
    stub = _stub(0)
    got = pc.run_checks(".", checks, runner=stub)
    assert got[0]["ok"] is None            # neither pass nor fail
    assert stub.calls == []                # and nothing was executed


def test_run_checks_bounds_every_command_with_a_timeout():
    stub = _stub(0)
    pc.run_checks(".", pc.parse_checks(CHECKS_PLAN), timeout=42, runner=stub)
    assert stub.calls and all(c["timeout"] == 42 for c in stub.calls)


def test_run_checks_merges_stderr_and_trims_from_the_end():
    # a lint failure lists findings at the BOTTOM; the tail is what the
    # agent needs, so the head is what gets dropped
    checks = [{"id": "LINT", "command": "npm run lint", "expect": None,
               "error": None}]
    stub = _stub(1, out="".join("noise %d\n" % i for i in range(1, 60))
                 + "99:1  error  the real finding")
    got = pc.run_checks(".", checks, runner=stub)[0]
    assert "the real finding" in got["output"]
    assert "noise 1" not in got["output"]
    assert "earlier lines omitted" in got["output"]


def test_a_timeout_or_a_crash_never_reads_as_a_pass():
    import subprocess

    checks = [{"id": "LINT", "command": "npm run lint", "expect": None,
               "error": None}]

    def timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 300)

    def crash(cmd, **kw):
        raise OSError("no such file")

    for runner, needle in ((timeout, "timed out"), (crash, "could not run")):
        got = pc.run_checks(".", checks, runner=runner)[0]
        assert got["ok"] is False
        assert needle in got["error"]


def test_render_separates_invalid_from_fail():
    checks = pc.parse_checks("## Checks\n"
                              "- LINT: `npm run lint`\n"
                              "- X: `npm run x` (expect: nope)\n")
    text = pc.render_check_results(
        pc.run_checks(".", checks, runner=_stub(1)))
    assert "INVALID" in text and "FAIL" in text
    assert "0 passed, 1 failed, 1 not run" in text


def test_declared_checks_reads_the_frozen_plan_not_the_draft(tmp_path):
    pdir = tmp_path / "plans" / "demo"
    write(pdir / "PART-01.draft.md", "## Checks\n- DRAFT: `npm run draft`\n")
    assert pc.declared_checks(pdir) == [], "a mutable sidecar must not gate"
    write(pdir / "PART-01 v1.0.md",
          "# PART 01 — demo | v1.0 frozen\n\n"
          "## Checks\n- LINT: `npm run lint`\n")
    assert [c["id"] for c in pc.declared_checks(pdir)] == ["LINT"]


def test_check_results_round_trip_through_the_last_run_file(tmp_path):
    pdir = tmp_path / "plans" / "demo"
    pdir.mkdir(parents=True)
    results = pc.run_checks(tmp_path, pc.parse_checks(CHECKS_PLAN),
                            runner=_stub(0))
    assert pc.write_check_results(pdir, "demo", results) is None
    assert pc.last_check_results(pdir) == {"LINT": "PASS", "TYPES": "PASS",
                                           "EXPLICIT": "PASS"}


def test_no_last_run_means_unrun_never_green(tmp_path):
    pdir = tmp_path / "plans" / "demo"
    pdir.mkdir(parents=True)
    assert pc.last_check_results(pdir) == {}


class _HealthApp(pc.App):
    """_mkhealth with the two GUI reads stubbed — no Tk, no subprocess."""

    def __init__(self):
        pass

    _frozen_file = staticmethod(pc.find_frozen_file)
    _ip_summary = staticmethod(lambda p: (None, 0, "", ""))
    _git_dirty = staticmethod(lambda r: None)


def _frozen_with_checks(tmp_path, checks="- LINT: `npm run lint`\n",
                        rows=TEMPLATE_MAP):
    pdir = frozen_with_map(tmp_path, rows)
    f = pdir / "PART-01 v1.0.md"
    write(f, f.read_text(encoding="utf-8") + "\n## Checks\n" + checks)
    return pdir


def test_health_surfaces_checks_without_blocking_anything(tmp_path):
    pdir = _frozen_with_checks(tmp_path, rows=PLAIN_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n")
    body = "\n".join(pc.App._mkhealth(_HealthApp(), tmp_path, pdir.name))
    assert "declared checks (1" in body
    assert "not run yet" in body
    assert "PASS" not in body, body          # never implies a pass
    assert "VERDICT: NEXT = session 2" in body, "a check must not gate Freeze"
    assert "passed: 1/2" in body


def test_health_reports_a_failed_check_from_the_last_run(tmp_path):
    pdir = _frozen_with_checks(tmp_path)
    results = pc.run_checks(
        tmp_path, pc.parse_checks("## Checks\n- LINT: `npm run lint`\n"),
        runner=_stub(1))
    pc.write_check_results(pdir, pdir.name, results)
    body = "\n".join(pc.App._mkhealth(_HealthApp(), tmp_path, pdir.name))
    assert "FAIL (last run)" in body
    assert "does not block Freeze on its own" in body


def test_health_stays_quiet_when_no_checks_are_declared(tmp_path):
    pdir = frozen_with_map(tmp_path, TEMPLATE_MAP)
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-10-04 | gates: g1, g2 | status: PASS | P00 v1.0\n")
    body = "\n".join(pc.App._mkhealth(_HealthApp(), tmp_path, pdir.name))
    assert "declared checks" not in body


def test_console_never_writes_source_on_a_check_run(tmp_path):
    """The boundary that keeps this feature out of forgery territory: a run
    may only create CHECKS.last.md. Nothing under src/ may be created or
    changed."""
    pdir = _frozen_with_checks(tmp_path)
    src = tmp_path / "src"
    write(src / "a.ts", "export const a = 1\n")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    results = pc.run_checks(
        tmp_path, pc.parse_checks("## Checks\n- LINT: `npm run lint`\n"),
        runner=_stub(0))
    pc.write_check_results(pdir, pdir.name, results)
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    changed = [p for p in after if p not in before or after[p] != before[p]]
    assert [p.name for p in changed] == [pc.CHECKS_LAST_FILE], changed
    assert (src / "a.ts").read_bytes() == before[src / "a.ts"]


def test_a_failing_run_never_ticks_a_recon_item(tmp_path):
    pdir = _frozen_with_checks(tmp_path)
    rc = pdir / "RECON-CHECKLIST.md"
    write(rc, "- [ ] EXISTS: src/a.ts\n")
    pc.run_checks(tmp_path,
                  pc.parse_checks("## Checks\n- LINT: `npm run lint`\n"),
                  runner=_stub(1))
    assert "- [ ] EXISTS: src/a.ts" in rc.read_text(encoding="utf-8")


# ------------------------------------------------- owner-pass status line
READY = "PART-01 READY"
# (nq, na, noa, nu, nu_owner, validation) -> the next step the label must
# name. Every row must produce a line whose ONLY em-dash clause is the
# next step, whatever else is outstanding.
STATES = [
    ((3, 0, 1, 4, 0, READY), "answer questions"),
    ((0, 2, 0, 0, 0, READY), "'Agent: finish owner pass'"),
    ((0, 0, 1, 0, 0, READY), "owner actions"),
    ((0, 0, 0, 5, 2, READY), "owner-only recon item"),
    ((0, 0, 0, 3, 0, READY), "tick recon items"),
    ((0, 0, 0, 0, 0, "3 findings"), "re-validate"),
    ((0, 0, 0, 0, 0, None), "'Validate draft'"),
    ((0, 0, 0, 0, 0, READY), "ready to Freeze"),
]


@pytest.mark.parametrize("state,expected", STATES)
def test_status_line_names_the_next_step(state, expected):
    assert expected in pc.owner_status_text(*state)


@pytest.mark.parametrize("state,expected", STATES)
def test_status_line_never_stacks_a_second_clause(state, expected):
    """v3.10 — the defect: two branches appended a SECOND em-dash clause
    ("next: 'Agent: finish owner pass' — integrates 2 answered
    question(s) into the draft"), so the line read as two stacked
    messages and the trailing count looked like another instruction.
    Counters first, then exactly one ' — ', then the advice."""
    text = pc.owner_status_text(*state)
    assert text.count(" — ") == 1, text
    counters, _, advice = text.partition(" — ")
    assert counters.count("—") == 0, counters
    assert advice.startswith("next: ") or advice == "ready to Freeze", text


def test_status_line_counts_are_always_present():
    text = pc.owner_status_text(1, 2, 3, 4, 2, READY)
    assert text.startswith("1 open question(s), 2 answer(s) awaiting "
                           "integration, 3 owner action(s), 4 unchecked "
                           "item(s) (2 owner-only)")


def test_status_line_open_questions_outrank_everything():
    # a stale report must never become the advice while questions wait
    assert "answer questions" in pc.owner_status_text(
        1, 0, 0, 0, 0, None)
    assert "answer questions" in pc.owner_status_text(
        1, 0, 0, 0, 0, "stale")


def test_status_line_validation_is_the_last_resort():
    # ...and once nothing else is outstanding it IS the next step, so the
    # label can never say "ready to Freeze" over a stale report
    assert "re-validate" in pc.owner_status_text(0, 0, 0, 0, 0, "stale")
    assert "ready to Freeze" in pc.owner_status_text(0, 0, 0, 0, 0, READY)


def test_val_is_ready_needs_the_exact_marker():
    assert pc.val_is_ready("PART-01 READY") is True
    assert pc.val_is_ready("  PART-01 READY\n") is True
    assert pc.val_is_ready("PART-01 READY\n2 findings") is False
    assert pc.val_is_ready(None) is False
    assert pc.val_is_ready("") is False


def test_gate_and_status_line_agree_on_validated(tmp_path):
    """One rule for 'validated', so the label cannot say ready to Freeze
    while the Freeze button would refuse."""
    pdir = tmp_path / "plans" / "v"
    write(pdir / "PART-01.draft.md", DRAFT)
    write(pdir / "RECON-CHECKLIST.md", "- [x] done\n")
    for body, ready in ((READY, True), ("findings\n", False), (None, False)):
        target = pdir / "VALIDATION.md"
        if body is None:
            target.unlink(missing_ok=True)
        else:
            write(target, body)
        gate = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
        assert gate["validation"]["ok"] is ready, body
        label = pc.owner_status_text(0, 0, 0, 0, 0,
                                     None if body is None else body)
        assert ("ready to Freeze" in label) is ready, body


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
