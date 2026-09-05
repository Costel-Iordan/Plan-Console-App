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


# --------------------------------------- v2.7 count_owner_answers
def test_count_owner_answers_empty_and_absent():
    # no section at all → 0
    assert pc.count_owner_answers("A. MISSION\n    text\n") == 0
    # section present but empty (integrated + deleted note only) → 0
    text = ("## OWNER ANSWERS\n"
            "(All answers integrated; section intentionally empty.)\n")
    assert pc.count_owner_answers(text) == 0


def test_count_owner_answers_counts_pairs():
    text = ("F. ARTIFACTS\n"
            "    body\n"
            "\n"
            "## OWNER ANSWERS (appended 2026-09-04)\n"
            "- Q: 1. PROBLEM: gap\n"
            "      QUESTION: decide?\n"
            "  A: yes\n"
            "- Q: 2. PROBLEM: gap\n"
            "  A: no\n")
    assert pc.count_owner_answers(text) == 2


def test_count_owner_answers_needs_clarification_exempt():
    text = ("## OWNER ANSWERS\n"
            "- Q: 1. PROBLEM: gap\n"
            "  A: unclear — NEEDS CLARIFICATION\n"
            "- Q: 2. PROBLEM: gap\n"
            "  A: plain answer\n")
    # the flagged pair may stay; only the plain one is leftover
    assert pc.count_owner_answers(text) == 1


def test_count_owner_answers_stops_at_next_heading():
    text = ("## OWNER ANSWERS\n"
            "- Q: 1. PROBLEM: gap\n"
            "  A: yes\n"
            "\n"
            "## LATER HEADING\n"
            "- Q: this is another section, never counted\n")
    assert pc.count_owner_answers(text) == 1


# ------------------------------- v2.8 parse_validation_findings
def test_validation_ready_report():
    f = pc.parse_validation_findings("PART-01 READY\n")
    assert f["ready"] and f["n"] == 0


def test_validation_ready_with_banner():
    f = pc.parse_validation_findings(
        "===== VALIDATION =====\nPART-01 READY\n")
    assert f["ready"] and f["n"] == 0


def test_validation_owner_resolve_classification():
    text = ("1. §G:130 multi-deploy deviation → run owner-resolve "
            "new-mistral\n"
            "2. §OWNER ANSWERS — 7 pairs → run owner-resolve new-mistral\n")
    f = pc.parse_validation_findings(text)
    assert f["n"] == 2
    assert f["owner_resolve"] == ["new-mistral"]
    assert f["fix_draft"] == [] and f["other"] == []


def test_validation_fix_draft_classification():
    text = ("1. §B:57-59 — three lines marked UNVERIFIED → fix in the "
            "draft, then re-validate\n"
            "2. §E Streaming omits ping cadence → fix in the draft, then "
            "re-validate\n")
    f = pc.parse_validation_findings(text)
    assert f["n"] == 2
    assert len(f["fix_draft"]) == 2
    assert f["owner_resolve"] == [] and f["other"] == []


def test_validation_mixed_and_summary_line_ignored():
    text = ("# VALIDATION — new-mistral (validate-plan run 2026-09-04)\n"
            "1. §B:57 placeholder model-IDs → fix in the draft, then "
            "re-validate\n"
            "2. OQ 1 answered but not integrated → run owner-resolve "
            "new-mistral\n"
            "3. §A session map gap → fix in the draft, then re-validate\n"
            "→ findings listed above — resolve them in the draft, then "
            "Validate again before Freezing.\n")
    f = pc.parse_validation_findings(text)
    assert f["n"] == 3
    assert len(f["fix_draft"]) == 2
    assert f["owner_resolve"] == ["new-mistral"]
    assert f["other"] == []


def test_validation_unrecognized_suffix_lands_in_other():
    text = "1. mystery finding → consult the oracle\n"
    f = pc.parse_validation_findings(text)
    assert f["n"] == 1 and len(f["other"]) == 1
    assert f["owner_resolve"] == [] and f["fix_draft"] == []


def test_validation_unnumbered_prose_counts_nothing():
    f = pc.parse_validation_findings("go fix the draft\n")
    assert f["n"] == 0 and not f["ready"]


# ------------------------------------------------------- merge_slug_values
# Regression: v3.3.1 cross-repo slug leakage. recent_slugs is global
# (plan-console.json) — a slug from repo A must never appear in
# repo B's plan dropdown.
# v3.3.2: a directory under plans/ counts as a plan only when it holds
# a plan marker file (is_plan_dir), so misplaced kebab-case dirs
# (commands/, templates/, archives) never appear in the dropdown.

def _mk_plan(plans, slug, marker="SOURCE.md"):
    d = plans / slug
    d.mkdir(parents=True)
    if marker is not None:
        (d / marker).write_text("x", encoding="utf-8")
    return d


def test_foreign_recent_slug_never_leaks(tmp_path):
    repo = Path(tmp_path) / "repoB"
    for s in ("plan-b1", "plan-b2", "plan-b3"):
        _mk_plan(repo / "plans", s)
    vals = pc.merge_slug_values(repo, ["plan-from-repo-a"])
    assert vals == ["plan-b1", "plan-b2", "plan-b3"], (
        "the foreign plan must NOT appear in repo B's list")


def test_recent_slug_kept_when_it_exists_in_repo(tmp_path):
    repo = Path(tmp_path) / "repoB"
    _mk_plan(repo / "plans", "alpha")
    _mk_plan(repo / "plans", "beta")
    vals = pc.merge_slug_values(repo, ["beta"])
    assert vals == ["beta", "alpha"], "recent order kept, then disk order"


def test_recent_slug_invalid_or_malformed_ignored(tmp_path):
    repo = Path(tmp_path) / "repoB"
    _mk_plan(repo / "plans", "alpha")
    vals = pc.merge_slug_values(repo, ["Not_Kebab", "", None, 42])
    assert vals == ["alpha"]


def test_repo_without_plans_dir_yields_nothing(tmp_path):
    vals = pc.merge_slug_values(Path(tmp_path) / "empty", ["x", "y"])
    assert vals == []


def test_limit_caps_the_dropdown(tmp_path):
    repo = Path(tmp_path) / "repoB"
    for i in range(15):
        _mk_plan(repo / "plans", "p%d" % i)
    vals = pc.merge_slug_values(repo, [])
    assert len(vals) == 10


def test_scan_plan_slugs_ignores_files_and_non_slugs(tmp_path):
    repo = Path(tmp_path) / "repoB"
    plans = repo / "plans"
    _mk_plan(plans, "good-slug")
    (plans / "Not_Kebab").mkdir()
    (plans / "Not_Kebab" / "SOURCE.md").write_text("x", encoding="utf-8")
    (plans / "loose-file.md").write_text("x", encoding="utf-8")
    assert pc.scan_plan_slugs(repo) == ["good-slug"]


def test_reproduction_real_shape_four_becomes_three(tmp_path):
    # exact incident shape: repo B with 3 plans, config remembering
    # repo A's single plan → UI showed 4. Fixed: 3.
    repoB = Path(tmp_path) / "repoB"
    for s in ("console-audit-1", "quiet-workbench-theme", "ui-ux-plan"):
        _mk_plan(repoB / "plans", s)
    vals = pc.merge_slug_values(repoB, ["new-mistral"])
    assert vals == ["console-audit-1", "quiet-workbench-theme", "ui-ux-plan"]
    assert len(vals) == 3
    assert "new-mistral" not in vals


# ------------------------------------------- non-plan dirs under plans/
# Regression: v3.3.2 — commands/, templates/ and archive copies placed
# (or cloned) under plans/ passed the bare kebab-case filter and were
# listed as plans. They carry no plan marker and must be excluded.

def test_command_and_template_dirs_excluded(tmp_path):
    repo = Path(tmp_path) / "repoB"
    plans = repo / "plans"
    _mk_plan(plans, "new-mistral")
    cmd = plans / "commands"
    cmd.mkdir(parents=True)
    (cmd / "freeze-plan.md").write_text("x", encoding="utf-8")
    tpl = plans / "templates"
    tpl.mkdir()
    (tpl / "PART-01.md").write_text("x", encoding="utf-8")
    assert pc.scan_plan_slugs(repo) == ["new-mistral"]


def test_archive_dir_without_markers_excluded(tmp_path):
    repo = Path(tmp_path) / "repoB"
    plans = repo / "plans"
    _mk_plan(plans, "real-plan")
    old = plans / "plans-old-structure"
    old.mkdir(parents=True)
    (old / "PART-00.md").write_text("x", encoding="utf-8")
    (old / "plans").mkdir()
    (old / "commands").mkdir()
    assert pc.scan_plan_slugs(repo) == ["real-plan"]


def test_empty_kebab_dir_not_a_plan(tmp_path):
    repo = Path(tmp_path) / "repoB"
    (repo / "plans" / "ghost-plan").mkdir(parents=True)
    assert pc.scan_plan_slugs(repo) == [], (
        "a plans/ dir without any plan marker is not a plan")


def test_every_marker_file_qualifies(tmp_path):
    repo = Path(tmp_path) / "repoB"
    plans = repo / "plans"
    for m in pc.PLAN_MARKER_FILES:
        _mk_plan(plans, "plan-" + m.split(".")[0].lower(), marker=m)
    _mk_plan(plans, "plan-frozen", marker="PART-01 v1.0.md")
    _mk_plan(plans, "plan-frozen-legacy", marker="PART-01.draft.md")
    assert pc.scan_plan_slugs(repo) == sorted(
        p.name for p in plans.iterdir()), (
        "every recognized marker (incl. PART-01 v*.md / .draft.md) "
        "marks a real plan")


def test_legacy_frozen_part01_md_is_a_plan(tmp_path):
    # a legacy frozen PART-01.md (freeze header: "frozen" in the first
    # 3 lines — same rule _frozen_file() applies) still lists.
    repo = Path(tmp_path) / "repoB"
    _mk_plan(repo / "plans", "legacy-plan",
             marker="PART-01.md")
    (repo / "plans" / "legacy-plan" / "PART-01.md").write_text(
        "PART 01 — legacy-plan | v1.0 frozen 2026-08-31\n",
        encoding="utf-8")
    assert pc.scan_plan_slugs(repo) == ["legacy-plan"]


def test_template_part01_md_without_freeze_header_not_a_plan(tmp_path):
    # templates/PART-01.md (no freeze header) must NOT qualify — this
    # is the exact false positive seen in C:\Temp\Resume\resume-app.
    repo = Path(tmp_path) / "repoB"
    plans = repo / "plans"
    _mk_plan(plans, "real-plan")
    tpl = plans / "templates"
    tpl.mkdir(parents=True)
    (tpl / "PART-01.md").write_text(
        "PART 01 — PROJECT CONTEXT: <plan-slug>\n", encoding="utf-8")
    assert pc.scan_plan_slugs(repo) == ["real-plan"]


def test_source_md_only_is_a_plan_v32_fresh_scaffold(tmp_path):
    # the console's own contract: a fresh scaffold contains ONLY
    # SOURCE.md — it must still be listed.
    repo = Path(tmp_path) / "repoB"
    _mk_plan(repo / "plans", "fresh-scaffold")
    assert pc.scan_plan_slugs(repo) == ["fresh-scaffold"]


def test_recent_slug_pointing_at_non_plan_dir_dropped(tmp_path):
    repo = Path(tmp_path) / "repoB"
    plans = repo / "plans"
    _mk_plan(plans, "real-plan")
    (plans / "commands").mkdir()
    vals = pc.merge_slug_values(repo, ["commands", "real-plan"])
    assert vals == ["real-plan"], (
        "a remembered slug whose dir has no plan marker must not resurface")


# ------------------------------------------------------- slug_feedback (v3.4)
def test_slug_feedback_empty_shows_editability_hint():
    text, kind = pc.slug_feedback("", False)
    assert kind == "hint"
    assert "type" in text and "pick" in text, (
        "the empty state must invite BOTH typing and picking")


def test_slug_feedback_invalid_chars_explains_rule():
    for bad in ("Not_Kebab", "UPPER", "double--dash", "trailing-", "a b"):
        text, kind = pc.slug_feedback(bad, False)
        assert kind == "invalid", bad
        assert "kebab" in text.lower(), bad


def test_slug_feedback_new_vs_exists():
    text_new, kind_new = pc.slug_feedback("fresh-idea", False)
    text_ex, kind_ex = pc.slug_feedback("fresh-idea", True)
    assert kind_new == "new" and "creates" in text_new
    assert kind_ex == "exists" and "reuse" in text_ex


def test_slug_feedback_valid_slug_passes_slug_re():
    _, kind = pc.slug_feedback("payments-v2", False)
    assert pc.SLUG_RE.match("payments-v2") and kind == "new"


# --------------------------------------------------------- owner actions v3.5
OA_BODY = (
    "# OPEN-QUESTIONS — demo\n"
    "\n"
    "1. PROBLEM: gap\n"
    "   QUESTION: proceed?\n"
    "   RECOMMEND: yes\n"
    "\n"
    "## Owner actions\n"
    "- [ ] plan-console.json is owner-only; confirm the API-key half:\n"
    "  `Select-String -Path plan-console.json -Pattern 'sk-'` "
    "(expect: no matches)\n"
    "  → verifies §B \"plan-console.json contains no API key\"\n"
    "- [x] already handled: `git status` — check tree\n"
    "- prose only bullet, no command\n"
    "\n"
    "## Notes\n"
    "- [ ] a checkbox OUTSIDE the section never counts\n"
)


def test_parse_owner_actions_finds_section_bullets():
    acts = pc.parse_owner_actions(OA_BODY)
    assert len(acts) == 3, "only bullets under '## Owner actions' count"
    assert acts[0]["checked"] is False
    assert acts[0]["command"] == \
        "Select-String -Path plan-console.json -Pattern 'sk-'"
    assert acts[0]["expect"] == "no matches"
    assert acts[0]["verifies"] == "plan-console.json contains no API key"
    # multi-line bullet: continuation lines joined, lineno = bullet line
    assert acts[0]["lineno"] == 8


def test_parse_owner_actions_checked_and_commandless():
    acts = pc.parse_owner_actions(OA_BODY)
    assert acts[1]["checked"] is True
    assert acts[1]["command"] == "git status"
    assert acts[2]["command"] is None
    assert acts[2]["verifies"] is None and acts[2]["expect"] is None


def test_parse_owner_actions_no_section():
    assert pc.parse_owner_actions("# nothing here\n- [ ] `git status`\n") == []


def test_parse_owner_actions_ignores_code_fences():
    text = ("## Owner actions\n"
            "```\n"
            "- [ ] `git commit` inside a fence never counts\n"
            "```\n")
    assert pc.parse_owner_actions(text) == []


def test_count_open_owner_actions():
    assert pc.count_open_owner_actions(OA_BODY) == 2
    assert pc.count_open_owner_actions("## Owner actions\n(nothing)\n") == 0


def test_is_readonly_command_default_deny():
    for ok in ("Select-String -Path x -Pattern y", "  git status --porcelain",
               "Test-Path README.md", "Get-Content plan-console.json",
               "git diff --stat", "git log -1"):
        assert pc.is_readonly_command(ok), ok
    for bad in ("git commit -m x", "git add .", "Remove-Item x",
                "python -m pytest", "del file", "curl http://x"):
        assert not pc.is_readonly_command(bad), bad
    assert not pc.is_readonly_command("")


def test_is_readonly_command_rejects_shell_separators():
    # v3.5.1 audit fix — a whitelisted prefix followed by a separator
    # executes a SECOND, arbitrary command; must be copy-only
    for bad in ("git status; remove-item x",
                "select-string x -path y; calc",
                "git status & del file",
                "get-content foo | out-file evil.txt",
                "get-content foo | set-content evil.txt",
                "git log `n calc",
                "git status $(calc)",
                "git diff > evil.txt",
                "select-string x < input.txt",
                "git status\nremove-item x",
                "git diff --output=evil.txt",
                "git show --out=evil.txt",
                "get-content foo | foreach { calc }",
                "git status | tee-object evil.txt",
                "git log | start-process calc",
                "git status | invoke-expression x",
                "git status | iex x"):
        assert not pc.is_readonly_command(bad), bad


def test_is_readonly_command_still_allows_plain_pipes_in_args():
    # legitimate read-only usage must keep working after the hardening
    for ok in ("Select-String -Path x -Pattern 'sk-'",
               "git status --porcelain=v1",
               "Get-Content plan-console.json -TotalCount 3",
               "git log --oneline -5"):
        assert pc.is_readonly_command(ok), ok


def test_mark_sb_verified_promotes_matching_line():
    draft = ("A. MISSION\n"
             "B. FACTS\n"
             "   - plan-console.json contains no API key; session-only "
             "— UNVERIFIED (owner-only per §F)\n"
             "   - other fact — VERIFIED 2026-09-05\n"
             "C. TREE\n")
    new, line = pc.mark_sb_verified(draft, "plan-console.json contains",
                                    "2026-09-06", "Select-String …")
    assert new is not None
    assert "VERIFIED 2026-09-06 (owner-run: Select-String …)" in new
    assert "UNVERIFIED" not in new
    assert line.startswith("- plan-console.json contains")


def test_parse_owner_actions_legacy_plain_bullets():
    # pre-v3.5 plans write plain bullets with no checkbox and no colon
    # in the expect tag — they must still parse (regression guard)
    legacy = ("## Owner actions\n"
              "- plan-console.json is owner-only; confirm the key half:\n"
              "  `Select-String -Path plan-console.json -Pattern 'sk-'` "
              "(expect no matches)\n"
              "- If you prefer to commit personally, run:\n"
              "  `git add plan-console.py && git commit -m x`\n")
    acts = pc.parse_owner_actions(legacy)
    assert len(acts) == 2
    assert all(not a["checked"] for a in acts), \
        "legacy plain bullets count as unchecked"
    assert acts[0]["command"].startswith("Select-String")
    assert acts[0]["expect"] == "no matches", "colon-less expect parses"
    assert acts[1]["command"].startswith("git add")
    assert pc.count_open_owner_actions(legacy) == 2


def test_mark_sb_verified_never_touches_verified_or_outside_b():
    draft = ("A. MISSION\n"
             "   - plan-console.json claim — UNVERIFIED (outside §B)\n"
             "B. FACTS\n"
             "   - already good — VERIFIED 2026-09-05\n"
             "C. TREE\n")
    new, line = pc.mark_sb_verified(draft, "already good", "2026-09-06")
    assert new is None and line is None, \
        "an already-verified §B line is never rewritten"
    new2, _ = pc.mark_sb_verified(draft, "plan-console.json claim",
                                  "2026-09-06")
    assert new2 is None, "§A lines never match — only the §B region"


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
