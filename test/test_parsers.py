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


# ----------------------------------------------------------- recommend_line
def test_recommend_line_present():
    text = ("1. PROBLEM: the gap\n"
            "   QUESTION: do we migrate?\n"
            "   RECOMMEND: yes, in one pass\n")
    assert pc.recommend_line(text, 0) == "yes, in one pass"


def test_recommend_line_absent():
    # legacy one-liner: no block, no RECOMMEND
    assert pc.recommend_line("Should we migrate?\n", 0) == ""
    # block without a RECOMMEND line
    text = "1. PROBLEM: the gap\n   QUESTION: do we migrate?\n"
    assert pc.recommend_line(text, 0) == ""


def test_recommend_line_case_insensitive_label():
    text = ("1. PROBLEM: the gap\n"
            "   QUESTION: do we migrate?\n"
            "   recommend: yes, in one pass\n")
    assert pc.recommend_line(text, 0) == "yes, in one pass"


def test_recommend_line_wrapped_continuation():
    text = ("1. PROBLEM: the gap\n"
            "   QUESTION: do we migrate?\n"
            "   RECOMMEND: yes, in one pass\n"
            "     because the schema is small\n")
    assert pc.recommend_line(text, 0) == "yes, in one pass"


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


# ----------------------------------------------- recon checkbox parsing
# v2.6.1 — the Freeze gate / Owner-pass counter must recognize real
# checkbox lines only (anchored, optional bullet) and treat owner-marked
# DEFERRED lines as resolved. Regression: the RECON-CHECKLIST.md header
# prose "`- [ ]` = unchecked" was counted as an unchecked item and
# blocked Freeze with "1 unchecked item(s)".

def test_recon_item_state_basic():
    assert pc.recon_item_state("- [ ] EXISTS: plan-console.py") == "open"
    assert pc.recon_item_state("- [x] EXISTS: plan-console.py") == "done"
    assert pc.recon_item_state("[X] done uppercase") == "done"
    assert pc.recon_item_state("* [ ] star bullet") == "open"
    assert pc.recon_item_state("  - [ ] indented item") == "open"
    assert pc.recon_item_state("plain prose") is None


def test_recon_prose_mentioning_marker_not_counted():
    # the exact header line that caused the false Freeze blocker
    header = "Facts the plan depends on. `- [ ]` = unchecked. Order: blocks"
    assert pc.recon_item_state(header) is None
    assert pc.count_open_recon(header) == 0


def test_recon_deferred_counts_as_resolved():
    text = ("- [x] EXISTS: plan-console.py\n"
            "- [ ] DEFERRED (owner-approved 2026-09-04): token tables\n"
            "- [ ] real open item\n")
    assert pc.count_open_recon(text) == 1


def test_recon_deferred_case_insensitive():
    assert pc.count_open_recon("- [ ] deferred by owner") == 0


def test_recon_count_empty_and_all_done():
    assert pc.count_open_recon("") == 0
    assert pc.count_open_recon("- [x] a\n- [X] b\n") == 0


def test_recon_inline_brackets_mid_sentence_not_counted():
    # "[ ]" appearing mid-sentence (not at line start) is not an item
    assert pc.count_open_recon("see the `- [ ]` marker below\n") == 0


# ------------------------------------------- v2.6.2 OWNER_SECTION_RE anchor
def test_owner_section_mention_in_comment_does_not_poison_file():
    # Regression (freeze bug, ui-ux-plan 2026-09-04): a HEADER COMMENT that
    # merely mentions "Commands/SQL/owner actions" used to flip in_owner
    # permanently, hiding every question block after it — Freeze skipped
    # the questions gate. The section keyword must OPEN the comment.
    text = ("# OPEN-QUESTIONS — ui-ux-plan\n"
            "# Owner answers one line per QUESTION. Commands/SQL/owner "
            "actions live only under \"## Owner actions\".\n"
            "\n"
            "1. PROBLEM: stale pointer\n"
            "   QUESTION: Fix it at freeze?\n"
            "   RECOMMEND: Yes.\n"
            "\n"
            "2. PROBLEM: second gap\n"
            "   QUESTION: Approve minsize?\n"
            "   RECOMMEND: 820x600.\n")
    assert len(pc.parse_questions(text)) == 2


def test_owner_section_header_still_suppresses_questions():
    # the anchored match must still treat real section headers as excluded
    for header in ("## Owner actions\n", "# Commands:\n", "# sql\n"):
        text = header + "1. run the migration?\n"
        assert pc.parse_questions(text) == [], header


def test_mention_comment_does_not_swallow_following_questions_after_header():
    # comments never count as questions (even '?'-ending); a real
    # "## Owner actions" header suppresses only its own section —
    # the block BEFORE the header counts
    text = ("# intro — commands and sql live below?\n"
            "1. PROBLEM: a\n"
            "   QUESTION: b?\n"
            "   RECOMMEND: c\n"
            "## Owner actions\n"
            "2. owner-only step?\n")
    assert len(pc.parse_questions(text)) == 1


# ------------------------------------------------ v2.6.3 parse_files guard
def test_parse_files_accepts_valid_paths():
    text = ("<<<FILE: plans/my-plan/PART-01.draft.md>>>\n"
            "body line\n"
            "<<<END>>>\n")
    files, notes = pc.parse_files(text, "my-plan")
    assert files == [("plans/my-plan/PART-01.draft.md", "body line\n")]
    assert notes == ""


def test_parse_files_rejects_escape_paths():
    bad = ("<<<FILE: plans/my-plan/../evil.md>>>\nx\n<<<END>>>\n"
           "<<<FILE: plans/other-plan/file.md>>>\nx\n<<<END>>>\n"
           "<<<FILE: /etc/passwd>>>\nx\n<<<END>>>\n"
           "<<<FILE: C:\\Temp\\evil.txt>>>\nx\n<<<END>>>\n"
           "<<<FILE: plans\\my-plan\\file.md>>>\nx\n<<<END>>>\n")
    files, notes = pc.parse_files(bad, "my-plan")
    assert files == []
    assert notes.count("ignored bad path") == 5


def test_parse_files_body_and_notes():
    text = ("intro note\n"
            "<<<FILE: plans/s/f.md>>>\nline1\n\nline3\n<<<END>>>\n"
            "trailing note\n")
    files, notes = pc.parse_files(text, "s")
    assert files == [("plans/s/f.md", "line1\n\nline3\n")]
    assert "intro note" in notes and "trailing note" in notes


# ------------------------------------------------ v2.6.3 DEFERRED tag rule
def test_deferred_tag_resolves_item():
    assert pc.count_open_recon(
        "- [ ] DEFERRED (owner-approved 2026-09-04): token tables\n") == 0
    assert pc.count_open_recon("- [ ] deferred by owner\n") == 0
    assert pc.count_open_recon("- [ ] (DEFERRED) old check\n") == 0


def test_deferred_mention_does_not_resolve_item():
    # prose merely MENTIONING the word must keep the item open
    assert pc.count_open_recon("- [ ] not DEFERRED yet\n") == 1
    assert pc.count_open_recon("- [ ] what about DEFERRED?\n") == 1


# ------------------------------------------------ v2.6.3 flip_recon_item
def test_flip_recon_item_toggles_only_the_checkbox():
    assert pc.flip_recon_item("- [ ] EXISTS: plan-console.py") == \
        "- [x] EXISTS: plan-console.py"
    assert pc.flip_recon_item("- [x] done") == "- [ ] done"
    assert pc.flip_recon_item("[X] uppercase") == "[ ] uppercase"
    # prose containing '[ ]'/'[x]' after the checkbox is never touched
    line = "- [ ] see the `[ ]` marker [x] example"
    assert pc.flip_recon_item(line) == \
        "- [x] see the `[ ]` marker [x] example"
    assert pc.flip_recon_item("plain prose") is None


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
