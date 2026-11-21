"""Rev-6 audit regression tests (R-63 … R-97).

Every test here pins a defect found by audits/2026-11-21-full-project-audit-rev6.md.
The theme is the one rev-5 named and rev-6 proved was still open: a
model-authored string or path must not become code execution, secret
exfiltration, a false "done", or silent data loss.

Run either way:
    py test/test_audit_v313.py
    py -m pytest test/test_audit_v313.py
"""
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "plan_console_v313", HERE.parent / "plan-console.py")
pc = importlib.util.module_from_spec(_spec)
sys.modules["plan_console_v313"] = pc
_spec.loader.exec_module(pc)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------- R-63
def test_readonly_command_rejects_argument_mode_subexpressions():
    for bad in ("git log (calc.exe)", "git status @(calc.exe)",
                "git diff (notepad.exe)", "git show HEAD%(calc.exe)",
                "git log @{x=1}", "get-content $(calc)"):
        assert not pc.is_readonly_command(bad), bad
    # the legitimate read-only forms still pass
    for ok in ("git status --porcelain", "git diff --stat",
               "git log --oneline -5", "Select-String -Path x -Pattern 'sk-'"):
        assert pc.is_readonly_command(ok), ok


def test_git_readonly_argv_is_fixed_and_config_neutralized(tmp_path):
    argv = pc._git_readonly_argv("git status --porcelain", tmp_path)
    assert argv is not None
    joined = " ".join(argv)
    assert "--no-pager" in argv
    assert "-C" in argv and str(tmp_path) in argv
    assert "core.fsmonitor=false" in joined
    assert "core.pager=cat" in joined
    assert argv[-2:] == ["status", "--porcelain"]
    # diff-family commands get the external-driver guards
    dargv = pc._git_readonly_argv("git diff --stat", tmp_path)
    assert "--no-ext-diff" in dargv and "--no-textconv" in dargv


def test_git_readonly_argv_allows_revision_ranges(tmp_path):
    argv = pc._git_readonly_argv("git diff HEAD~1..HEAD --stat", tmp_path)
    assert argv is not None and "HEAD~1..HEAD" in argv


def test_git_readonly_argv_rejects_anything_else(tmp_path):
    for bad in ("git commit -m x", "git add .", "git log (calc)",
                "git -c core.fsmonitor=evil status", "git push",
                "git diff --no-index /etc/passwd /etc/passwd",
                "git show C:/Windows/win.ini", "git diff ../outside.md"):
        assert pc._git_readonly_argv(bad, tmp_path) is None, bad


def test_git_resolution_never_falls_back_to_a_bare_name():
    assert pc._resolve_git_exe(which=lambda _: None,
                               isfile=lambda _: False) is None
    assert pc._resolve_git_exe(which=lambda _: r"C:\Git\git.exe",
                               isfile=lambda _: True) == r"C:\Git\git.exe"


def test_git_env_disables_system_and_global_config(monkeypatch):
    env = pc._git_env()
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_GLOBAL"] == pc.os.devnull
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_PAGER"] == "cat"


# ---------------------------------------------------------------- R-64
def _pack_harness():
    app = type("H", (), {})()
    app._said = []
    app.say = lambda target, line: app._said.append((target, line))
    return app


def test_context_pack_denies_secret_directory_components(tmp_path):
    write(tmp_path / "credentials" / "prod.yaml", "password: hunter2")
    write(tmp_path / "src" / "app_main.py", "print('safe')\n")
    app = _pack_harness()
    pack = pc.App._context_pack(app, tmp_path,
                                "credentials prod password app_main")
    assert "prod.yaml" not in pack
    assert "app_main.py" in pack
    assert any("inlined src/app_main.py" in line for _t, line in app._said)


def test_context_pack_denies_env_suffix_and_key_material(tmp_path):
    for name, body in (("prod.env", "DB_PASSWORD=x"),
                       ("id_rsa", "PRIVATE"),
                       ("service-account.json", "{}"),
                       ("store.kdbx", "x"),
                       ("deploy.tfvars", "secret=1")):
        write(tmp_path / name, body)
    write(tmp_path / "README.md", "hello")
    app = _pack_harness()
    pack = pc.App._context_pack(app, tmp_path,
                                "prod env db password id rsa service account "
                                "store deploy readme")
    for banned in ("prod.env", "id_rsa", "service-account.json",
                   "store.kdbx", "deploy.tfvars"):
        assert banned not in pack, banned
    assert "README.md" in pack


def test_context_pack_rejects_non_text_extensions(tmp_path):
    write(tmp_path / "notes.exe", "MZ")
    write(tmp_path / "notes.md", "safe")
    app = _pack_harness()
    pack = pc.App._context_pack(app, tmp_path, "notes")
    assert "notes.md" in pack and "notes.exe" not in pack


def test_context_pack_skips_symlinked_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("SECRET", encoding="utf-8")
    link = repo / "notes.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation not permitted on this machine")
    app = _pack_harness()
    pack = pc.App._context_pack(app, repo, "notes")
    assert "SECRET" not in pack
    assert any("symlink" in line for _t, line in app._said)


def test_context_pack_reads_utf8(tmp_path):
    write(tmp_path / "notes.txt", "café — naïve\n")
    app = _pack_harness()
    pack = pc.App._context_pack(app, tmp_path, "notes")
    assert "café" in pack


# ---------------------------------------------------------------- R-69
def test_parse_files_rejects_ads_and_device_names():
    bad = ("<<<FILE: plans/demo/a:b.md>>>\nx\n<<<END>>>\n"
           "<<<FILE: plans/demo/CON.md>>>\nx\n<<<END>>>\n"
           "<<<FILE: plans/demo/trailing. .md>>>\nx\n<<<END>>>\n"
           "<<<FILE: plans/demo/nul.txt>>>\nx\n<<<END>>>\n")
    files, notes = pc.parse_files(bad, "demo")
    assert files == []
    assert notes.count("ignored bad path") == 4
    ok, _ = pc.parse_files(
        "<<<FILE: plans/demo/PART-01.draft.md>>>\nx\n<<<END>>>\n", "demo")
    assert ok and ok[0][0] == "plans/demo/PART-01.draft.md"


# ---------------------------------------------------------------- R-78
def test_atomic_write_leaves_no_temp_and_concurrent_writes_are_whole(tmp_path):
    p = tmp_path / "target.txt"
    bodies = ["A" * 20000, "B" * 20000, "C" * 20000]

    def worker(i):
        pc.atomic_write_text(p, bodies[i % len(bodies)])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(18)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert p.read_text(encoding="utf-8") in bodies
    assert not list(tmp_path.glob(".*.tmp")), "temp files leaked"


# ---------------------------------------------------------------- R-68
def test_redirect_policy_is_same_host_only():
    assert pc._same_host_redirect("https://openrouter.ai/a",
                                  "https://openrouter.ai/b")
    assert pc._same_host_redirect("https://openrouter.ai/a",
                                  "https://openrouter.ai/a?x=1")
    assert not pc._same_host_redirect("https://openrouter.ai/a",
                                      "https://evil.example/b")
    assert not pc._same_host_redirect("https://openrouter.ai/a",
                                      "http://openrouter.ai/b")
    assert not pc._same_host_redirect("https://openrouter.ai/a",
                                      "https://openrouter.ai.evil/b")


# ---------------------------------------------------------------- R-66
def test_check_is_risky_flags_downloads_and_chains():
    assert not pc.check_is_risky("npm run lint")
    assert not pc.check_is_risky("npx tsc --noEmit")
    for risky in ("curl https://x", "npm install left-pad",
                  "npm run lint && rm -rf x", "iwr x | iex",
                  "powershell -Command x", "git clone x"):
        assert pc.check_is_risky(risky), risky


def test_shell_argv_is_platform_appropriate(monkeypatch):
    monkeypatch.setattr(pc.os, "name", "posix")
    assert pc.shell_argv("npm test") == ["/bin/sh", "-c", "npm test"]
    monkeypatch.setattr(pc.os, "name", "nt")
    argv = pc.shell_argv("npm test")
    assert argv[-2:] == ["-Command", "npm test"]


def test_busy_disable_covers_checks_and_source_load():
    assert "btn_checks" in pc.BUSY_DISABLE
    assert "btn_load_src" in pc.BUSY_DISABLE


# ---------------------------------------------------------------- R-73
def test_owner_answers_lowercase_heading_is_counted():
    text = ("## owner answers\n"
            "- Q: 1. PROBLEM: gap\n  A: yes\n")
    assert pc.count_owner_answers(text) == 1


def test_insert_owner_answer_stays_inside_the_section():
    text = ("## owner answers\n"
            "- Q: old\n  A: old answer\n\n"
            "## Notes\nkeep this section\n")
    out = pc.insert_owner_answer(text, ["1. PROBLEM: new"], "new answer")
    assert out.index("new answer") < out.index("## Notes")
    assert "## Notes\nkeep this section" in out
    assert pc.count_owner_answers(out) == 2


# ---------------------------------------------------------------- R-80
def test_append_owner_action_stays_inside_the_section():
    text = ("## Owner actions\n"
            "- [ ] old action `git status`\n\n"
            "## Notes\nthis is not an action\n")
    out = pc.append_owner_action(text, "- [ ] new action `git diff`")
    assert out.index("new action") < out.index("## Notes")
    assert [a["command"] for a in pc.parse_owner_actions(out)] == [
        "git status", "git diff"]


# ---------------------------------------------------------------- R-88
def test_numbered_owner_steps_are_not_stranded_questions():
    text = ("## Owner actions\n"
            "1. run the first migration\n"
            "2. run the second migration\n")
    assert pc.unaccounted_escalations(text) == []
    real = ("## Owner actions\n"
            "1. PROBLEM: a real gap\n"
            "   QUESTION: decide?\n")
    assert len(pc.unaccounted_escalations(real)) == 1


# ---------------------------------------------------------------- R-71
def test_latest_pass_only_completes_a_session():
    recs = [{"n": 1, "leg": "", "status": "FAIL"},
            {"n": 2, "leg": "", "status": "PASS"},
            {"n": 3, "leg": "a", "status": "PASS"},
            {"n": 3, "leg": "b", "status": "PARTIAL"}]
    passed = pc.latest_passed_keys(recs)
    assert (1, "") not in passed
    assert (2, "") in passed
    assert (3, "a") in passed and (3, "b") not in passed


def test_split_session_needs_both_legs_passed():
    rows = {3: ("scope", "g1", True, True)}
    assert pc.session_completed(rows, [
        {"n": 3, "leg": "a", "status": "PASS"}], 3) is False
    assert pc.session_completed(rows, [
        {"n": 3, "leg": "a", "status": "PASS"},
        {"n": 3, "leg": "b", "status": "PASS"}], 3) is True


def test_next_pending_offers_a_failed_session_again(tmp_path):
    pdir = tmp_path / "plans" / "demo"
    write(pdir / "PART-01 v1.0.md",
          "PART 01\nA. MAP\n 1 | one | g1 | no\n 2 | two | g2 | no\nB. x\n")
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-01-01 | gates: g1 | status: FAIL | P00 v1.0\n")
    assert pc.next_pending_session(pdir)["n"] == 1


# ---------------------------------------------------------------- R-72
class _HealthApp(pc.App):
    def __init__(self):
        pass

    _frozen_file = staticmethod(pc.find_frozen_file)
    _ip_summary = staticmethod(lambda p: (None, 0, "", ""))
    _git_dirty = staticmethod(lambda r: None)


def test_mkhealth_survives_a_section_a_gap(tmp_path):
    pdir = tmp_path / "plans" / "gap"
    write(pdir / "PART-01 v1.0.md",
          "PART 01\nA. MAP\n 1 | one | g1 | no\n 3 | three | g3 | no\n"
          "B. x\n")
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-01-01 | gates: g1 | status: PASS | P00 v1.0\n")
    lines = pc.App._mkhealth(_HealthApp(), tmp_path, "gap")
    assert any("3  " in l or " 3 " in l for l in lines)


def test_mkhealth_survives_an_empty_frozen_file(tmp_path):
    pdir = tmp_path / "plans" / "empty"
    write(pdir / "PART-01 v1.0.md", "")
    lines = pc.App._mkhealth(_HealthApp(), tmp_path, "empty")
    assert lines and "PLAN HEALTH" in lines[0]


def test_mkhealth_deferred_row_is_not_the_next_session(tmp_path):
    pdir = tmp_path / "plans" / "def"
    write(pdir / "PART-01 v1.0.md",
          "PART 01\nA. MAP\n"
          " 1 | done | g1 | no\n"
          " 2 | DEFERRED — not executed in this plan | g2 | no\n"
          "B. x\n")
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-01-01 | gates: g1 | status: PASS | P00 v1.0\n")
    body = "\n".join(pc.App._mkhealth(_HealthApp(), tmp_path, "def"))
    assert "DEFERRED — not executed" in body
    assert "NEXT = session 2" not in body
    assert "ALL SESSIONS PASS" in body


# ---------------------------------------------------------------- R-74
def test_unreadable_plan_files_fail_their_gates(tmp_path, monkeypatch):
    pdir = tmp_path / "plans" / "locked"
    write(pdir / "PART-01.draft.md", "# draft\n")
    write(pdir / "OPEN-QUESTIONS.md", "1. PROBLEM: a\n QUESTION: b?\n")
    write(pdir / "RECON-CHECKLIST.md", "- [ ] open\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    real = Path.read_text

    def fake(self, *a, **k):
        if self.name in ("OPEN-QUESTIONS.md", "RECON-CHECKLIST.md",
                         "PART-01.draft.md"):
            raise OSError("locked")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", fake)
    gates = {g["id"]: g for g in pc.freeze_gate_report(pdir)}
    for gid in ("questions", "owner_actions", "parked", "recon"):
        assert gates[gid]["ok"] is False, gid
        assert "could NOT be read" in gates[gid]["detail"], gid


# ---------------------------------------------------------------- R-83
def test_load_cfg_rejects_a_non_object_json(tmp_path, monkeypatch):
    cfg = tmp_path / "plan-console.json"
    cfg.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(pc, "CFG", cfg)
    assert pc.App._load_cfg() == {}
    assert (tmp_path / "plan-console.json.corrupt").is_file()
    assert "could not be loaded" in pc._CFG_LOAD_NOTE


# ---------------------------------------------------------------- R-84
def test_unknown_log_target_is_named(capsys):
    app = type("H", (), {})()
    app.logs = {}
    pc.App._log_line(app, "typo-target", "hello")
    assert "unknown log target" in capsys.readouterr().out


# ---------------------------------------------------------------- R-81
def test_on_health_reports_before_health_write_failure():
    app = type("H", (), {})()
    app._preflight = lambda: Path(".")
    app._get_slug = lambda first="sessions": "demo"
    app.slug_var = type("V", (), {"get": staticmethod(lambda: "demo")})()
    app._mkhealth = lambda repo, slug: ["PLAN HEALTH — demo"]
    app.say = lambda target, line: app.said.append(line)
    app.said = []

    def boom(*a, **k):
        raise OSError("locked")

    app._log_health = boom
    pc.App.on_health(app)
    assert app.said[0] == "PLAN HEALTH — demo"
    assert any("WARN: HEALTH.md" in l for l in app.said)


# ---------------------------------------------------------------- R-66/R-67
def test_checks_worker_posts_completion(tmp_path, monkeypatch):
    pdir = tmp_path / "plans" / "demo"
    pdir.mkdir(parents=True)
    app = type("H", (), {})()
    app.q = pc.DropOldestQueue(maxsize=10)
    app._busy = lambda on, msg="": None
    app._log_health = lambda *a, **k: None
    pc.App._run_checks_worker(app, tmp_path, "demo", [])
    target, payload = app.q.get_nowait()
    assert target == "__checks_done__"
    assert payload[2] == [] and payload[3] is None


def test_owner_action_worker_posts_completion(tmp_path, monkeypatch):
    import subprocess
    app = type("H", (), {})()
    app.q = pc.DropOldestQueue(maxsize=10)
    app._busy = lambda on, msg="": None
    monkeypatch.setattr(
        pc, "_run_readonly_command",
        lambda cmd, repo: subprocess.CompletedProcess(cmd, 0, "ok", ""))
    action = {"command": "git status", "prose": "check tree"}
    pc.App._owner_action_worker(app, action, tmp_path)
    target, payload = app.q.get_nowait()
    assert target == "__oa_done__"
    assert payload[0] is action and payload[2] is None


def test_after_checks_reports_failures_and_malformed(monkeypatch):
    app = type("H", (), {})()
    app.said = []
    app.say = lambda target, line: app.said.append(line)
    sent = []
    app._send_check_failures = lambda *a: sent.append(a)
    warned = []
    monkeypatch.setattr(pc.messagebox, "showwarning",
                        lambda *a, **k: warned.append(a))
    results = [{"id": "LINT", "command": "npm run lint", "ok": True,
                "code": 0, "output": "", "error": None},
               {"id": "TYPES", "command": "npm run types", "ok": False,
                "code": 2, "output": "bad", "error": None},
               {"id": "BROKEN", "command": None, "ok": None, "code": None,
                "output": "", "error": "no command"}]
    pc.App._after_checks(app, Path("."), "demo", results, None, None)
    assert sent, "a failed check must produce the agent instruction"
    assert warned, "malformed checks must be reported even with failures"
    assert any("1 passed, 1 failed, 1 not run" in l for l in app.said)


def test_session_state_reports_declared_and_reported_gates(tmp_path):
    pdir = tmp_path / "plans" / "state"
    write(pdir / "PART-01 v1.0.md",
          "PART 01\nA. MAP\n 1 | one | g1: a, g2: b | no\nB. x\n")
    write(pdir / "PROGRESS.md",
          "SESSION 1 | 2026-01-01 | gates: g1 | status: PASS | P00 v1.0\n")
    st = pc.App._session_state(_HealthApp(), pdir, 1)
    assert st["declared"] == ["g1", "g2"]
    assert st["gates"] == ["g1"]
    assert any("g2" in n for n in st["notes"])


def test_on_freeze_writes_the_versioned_plan(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    pdir = repo / "plans" / "demo"
    write(pdir / "PART-01.draft.md", "# PART 01 — demo\n\nA. body\n")
    write(pdir / "RECON-CHECKLIST.md", "- [x] done\n")
    write(pdir / "VALIDATION.md", "PART-01 READY")
    app = type("H", (), {})()
    app._preflight = lambda: repo
    app._get_slug = lambda *a: "demo"
    app._frozen_file = lambda p: pc.find_frozen_file(p)
    app._freeze_gates_dialog = lambda *a: None
    app.say = lambda target, line: app.said.append(line)
    app.said = []
    app._strip_refresh = lambda: None
    monkeypatch.setattr(pc.messagebox, "showerror", lambda *a, **k: None)
    pc.App.on_freeze(app)
    frozen = pdir / "PART-01 v1.0.md"
    assert frozen.is_file()
    assert "frozen" in frozen.read_text(encoding="utf-8").splitlines()[0]
    assert (pdir / "PROGRESS.md").is_file()
    assert any("FROZEN v1.0" in line for line in app.said)


def test_license_gate_is_a_noop_once_accepted():
    app = type("H", (), {})()
    app.cfg = {"license_accepted": True}
    assert pc._run_license_gate(app) is True


# ---------------------------------------------------------------- Tk tests
@pytest.fixture()
def app_window(tmp_path, monkeypatch):
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


def _pump(root, n=20):
    for _ in range(n):
        root.update_idletasks()
        root.update()


def _repo(tmp_path):
    repo = tmp_path / "repo"
    write(repo / "PART-00.md", "# PART 00\n")
    write(repo / "commands" / "new-plan.md", "# new-plan\n")
    return repo


def test_restore_ignores_another_repos_source(app_window, tmp_path):
    app, root = app_window
    repo_a = _repo(tmp_path / "a")
    repo_b = _repo(tmp_path / "b")
    src = repo_a / "plans" / "plan-a" / "SOURCE.md"
    write(src, "# SOURCE — plan-a\nType: plan | Captured: x\n\n---\n\n"
               "REPO-A-REPORT-BODY\n")
    app.repo_var.set(str(repo_b))
    app.slug_var.set("plan-a")
    app.cfg["intake_file"] = str(src)
    app.src.delete("1.0", "end")
    app._restore_intake_source()
    _pump(root)
    assert "REPO-A-REPORT-BODY" not in app.src.get("1.0", "end")


def test_proceed_archives_an_existing_source(app_window, tmp_path,
                                             monkeypatch):
    app, root = app_window
    repo = _repo(tmp_path)
    pdir = repo / "plans" / "demo"
    write(pdir / "SOURCE.md", "# old source\n\nOLD-BODY\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("demo")
    app.src.delete("1.0", "end")
    app.src.insert("1.0", "NEW-BODY " * 10)
    monkeypatch.setattr(app, "_intake_chain", lambda *a, **k: None)
    monkeypatch.setattr(pc.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(pc.messagebox, "showerror", lambda *a, **k: None)
    app.on_proceed()
    _pump(root)
    backups = list(pdir.glob("SOURCE.md.*.bak"))
    assert backups, "an existing SOURCE.md must be archived"
    assert "OLD-BODY" in backups[0].read_text(encoding="utf-8")


def test_proceed_reenables_the_button_when_the_write_fails(
        app_window, tmp_path, monkeypatch):
    app, root = app_window
    repo = _repo(tmp_path)
    app.repo_var.set(str(repo))
    app.slug_var.set("demo")
    app.src.delete("1.0", "end")
    app.src.insert("1.0", "NEW-BODY " * 10)
    monkeypatch.setattr(pc.messagebox, "askyesno", lambda *a, **k: True)
    errors = []
    monkeypatch.setattr(pc.messagebox, "showerror",
                        lambda *a, **k: errors.append(a))
    real = pc.atomic_write_text

    def fake(path, text):
        if Path(path).name == "SOURCE.md":
            raise OSError("disk full")
        return real(path, text)

    monkeypatch.setattr(pc, "atomic_write_text", fake)
    app.on_proceed()
    _pump(root)
    assert str(app.btn_proceed.cget("state")) == "normal"
    assert errors, "the failed write must be named"


def test_on_close_preserves_unsaved_answer(app_window, tmp_path,
                                           monkeypatch):
    app, root = app_window
    repo = _repo(tmp_path)
    app.repo_var.set(str(repo))
    app.slug_var.set("demo")
    app.answer.insert("1.0", "a decision I had not saved yet")
    monkeypatch.setattr(app, "_save_cfg",
                        lambda: (_ for _ in ()).throw(OSError("read-only")))
    app.on_close()
    saved = repo / "plans" / "demo" / "ANSWER-DRAFT.txt"
    assert saved.is_file()
    assert "a decision I had not saved yet" in saved.read_text(
        encoding="utf-8")


def test_intake_primary_controls_fit_at_820(app_window):
    app, root = app_window
    root.state("normal")
    root.geometry("820x600")
    app.nb.select(0)
    _pump(root)
    rw = root.winfo_width()
    rx0 = root.winfo_rootx()
    for w in (app.kind, app.slug, app.btn_proceed, app.btn_freeze):
        left = w.winfo_rootx() - rx0
        assert w.winfo_width() > 5
        assert left + w.winfo_width() <= rw + 1, (
            "%r runs off the window at 820px" % w)
    for w in (app.chk_recon, app.chk_validate, app.chk_auto_resolve):
        assert w.winfo_ismapped()
        assert w.winfo_width() > 5


def test_startup_does_not_fetch_models_in_paste_mode(tmp_path, monkeypatch):
    tk = pytest.importorskip("tkinter")
    root = tk.Tk()
    root.withdraw()
    monkeypatch.setattr(pc, "CFG", tmp_path / "cfg.json")
    monkeypatch.setattr(pc, "_high_contrast_active", lambda: False)
    monkeypatch.setattr(pc.App, "_auto_command_check",
                        lambda self, repo=None: None)
    called = []
    monkeypatch.setattr(pc.App, "_fetch_models", lambda self: called.append(1))
    app = pc.App(root)
    try:
        assert app.use_key.get() is False
        assert called == [], "paste mode must not phone home at startup"
    finally:
        root.destroy()


# ------------------------------------------------------------ docs/release
def test_readme_is_current():
    root = HERE.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert pc.APP_VERSION in readme
    assert "100 tests" not in readme
    for feature in ("Run checks", "Load from file"):
        assert feature in readme, feature


def test_userguide_documents_declared_checks():
    txt = (HERE.parent / "UserGuide.txt").read_text(encoding="utf-8")
    html = (HERE.parent / "UserGuide.html").read_text(encoding="utf-8")
    for body in (txt, html):
        assert "Run checks" in body
        assert "CHECKS.last.md" in body


def test_guides_have_reduced_motion_and_focus_visible_css():
    css = (HERE.parent / "assets" / "console.css").read_text(
        encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_release_artifacts_match_the_app_or_are_absent():
    rel = HERE.parent / "rel"
    if not rel.is_dir():
        pytest.skip("release tree not built in this checkout")

    def same_bytes(a, b):
        return (a.read_bytes().replace(b"\r\n", b"\n")
                == b.read_bytes().replace(b"\r\n", b"\n"))

    for name in ("plan-console.py", "README.md", "UserGuide.txt",
                 "UserGuide.html", "no-api-key-guide.html",
                 "pyproject.toml", "test/test_audit_v313.py"):
        assert same_bytes(rel / name, HERE.parent / name), (
            "rel/%s is stale — rebuild the release tree" % name)
    assert not list(rel.rglob("__pycache__"))
    assert not (rel / "plan-console.json").exists()
    assert (rel / "test" / "test_audit_v313.py").is_file()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
