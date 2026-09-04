"""Regression tests for the Plan Console parsers (pure functions only —
no Tk, no network, no repo access).

Run either way:
    py test/test_parsers.py
    py -m pytest test/test_parsers.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "plan_console", HERE.parent / "plan-console.py")
pc = importlib.util.module_from_spec(_spec)
sys.modules["plan_console"] = pc
_spec.loader.exec_module(pc)


# ----------------------------------------------------------- parse_questions
def test_numbered_block_counts_once():
    text = ("1. PROBLEM: the gap\n"
            "   QUESTION: do we migrate?\n"
            "   RECOMMEND: yes, in one pass\n")
    qs = pc.parse_questions(text)
    assert len(qs) == 1, "a three-line block must count as ONE question"


def test_legacy_question_mark_line_counts():
    assert len(pc.parse_questions("Should we migrate?\n")) == 1


def test_owner_section_and_fences_never_count():
    text = ("## Owner actions\n"
            "1. run the migration script\n"
            "```\n"
            "is this sql ok?\n"
            "```\n")
    assert pc.parse_questions(text) == []


def test_flush_left_prose_after_block_not_absorbed():
    text = ("1. PROBLEM: gap\n"
            "   QUESTION: decide?\n"
            "   RECOMMEND: x\n"
            "Summary prose at flush left?\n")
    # the header block is one question; the prose line ends with '?'
    # so it counts as a legacy question (exact v2.0 behavior)
    assert len(pc.parse_questions(text)) == 2


# ------------------------------------------------------- parse_gates_field
def test_canonical_gate_list():
    ids, all_flag = pc.parse_gates_field("g1, g2")
    assert ids == ["g1", "g2"] and not all_flag


def test_drift_variants():
    for raw in ("G1 g-2", "g1 g2", "g1;g2", "g1/g2", "g_1 g2",
                "g1: pytest green, g2: lint", "[g1, g2]"):
        ids, _ = pc.parse_gates_field(raw)
        assert ids == ["g1", "g2"], raw


def test_range_expansion():
    ids, _ = pc.parse_gates_field("g1-g3")
    assert ids == ["g1", "g2", "g3"]


def test_all_and_none():
    assert pc.parse_gates_field("all")[1] is True
    assert pc.parse_gates_field("all gates passed")[1] is True
    assert pc.parse_gates_field("none") == ([], False)
    assert pc.parse_gates_field("n/a") == ([], False)
    assert pc.parse_gates_field("-") == ([], False)


def test_bare_numbers_only_without_g_ids():
    assert pc.parse_gates_field("1, 2")[0] == ["g1", "g2"]
    # a g-prefixed id anywhere means bare numbers are descriptions
    ids, _ = pc.parse_gates_field("g1 and 12 subtasks")
    assert ids == ["g1"]


# -------------------------------------------------- parse_progress_record
def test_canonical_record():
    line = ("SESSION 3 | 2025-06-01 | gates: g1, g2 | status: PASS | "
            "P00 v1.1")
    rec = pc.parse_progress_record(line)
    assert rec["n"] == 3
    assert rec["date"] == "2025-06-01"
    assert rec["gates"] == ["g1", "g2"]
    assert rec["status"] == "PASS"
    assert rec["canonical"]


def test_drifted_record_still_parses_and_flags():
    line = "Session #2 — Gates: passed g1,g2 — status BLOCK (no p00)"
    rec = pc.parse_progress_record(line)
    assert rec["n"] == 2
    assert rec["gates"] == ["g1", "g2"]
    assert rec["status"] == "BLOCKED"
    assert not rec["canonical"]


def test_no_session_token_returns_none():
    assert pc.parse_progress_record("random prose") is None


# ------------------------------------------------------------ read_progress
def _write_progress(tmpdir, body):
    p = Path(tmpdir) / "PROGRESS.md"
    p.write_text(body, encoding="utf-8")
    return p


def test_read_progress_folds_multiline_record(tmp_path):
    p = _write_progress(tmp_path,
                        "SESSION 4 |\n"
                        "gates: g1, g2 |\n"
                        "status: PASS | P00 v1.1\n"
                        "\n"
                        "some unrelated prose line\n")
    recs = pc.read_progress(p)
    assert len(recs) == 1
    assert recs[0]["gates"] == ["g1", "g2"]


def test_read_progress_skips_comments(tmp_path):
    p = _write_progress(tmp_path,
                        "# PROGRESS — header\n"
                        "SESSION 1 | 2025-01-01 | gates: g1 | status: PASS"
                        " | P00 v1.1\n")
    recs = pc.read_progress(p)
    assert [r["n"] for r in recs] == [1]


def test_latest_sessions_last_wins():
    recs = [{"n": 1, "status": "FAIL"}, {"n": 1, "status": "PASS"},
            {"n": 2, "status": "PASS"}]
    out, dups = pc.latest_sessions(recs)
    assert out[1]["status"] == "PASS"
    assert dups == [1]


# ------------------------------------------------------ session_row_gates
def test_session_row_gates_table_row():
    plan = ("# x\n"
            "A. SESSIONS\n"
            "  # | scope | gates | deploy?\n"
            "  1 | do it | g1: pytest, g2: lint | no\n"
            "B. next\n")
    assert pc.session_row_gates(plan, 1) == ["g1", "g2"]
    assert pc.session_row_gates(plan, 2) == []


def main():
    fns = [(k, v) for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for name, fn in fns:
        try:
            if "tmp_path" in fn.__code__.co_varnames:
                fn(tmp_path=__import__("tempfile").mkdtemp())
            else:
                fn()
            print("PASS %s" % name)
        except AssertionError as exc:
            failed += 1
            print("FAIL %s — %s" % (name, exc))
    print("---")
    print("%d/%d passed" % (len(fns) - failed, len(fns)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
