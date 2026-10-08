"""v3.12 — load-from-file on the Intake tab, with the pane
BOUND to plans/<slug>/SOURCE.md:

  * the button fills the paste box from a markdown file —
    a session-only link, never written to plan-console.json;
  * Proceed binds the pane to the SOURCE.md it writes
    (cfg "intake_file") — the link to the loaded file is
    severed at that moment;
  * a launch restores that SOURCE.md's BODY (unwrapped, so
    re-Proceeding never double-wraps) — and only if it
    exists, else the pane starts empty.

The failure classes these gate:
  * a cancelled dialog must leave the box untouched;
  * an unreadable file must be NAMED — an empty box would
    read as an empty report, the worse failure (convention §1);
  * loading over a slug whose SOURCE.md exists (Proceed
    already ran) must be REFUSED before the picker opens;
  * a FROZEN slug must be refused with the frozen
    message — re-intake is blocked entirely;
  * a restored plan must re-Proceed WITHOUT double-wrapping;
  * a vanished remembered file must start empty, never
    crash the launch.

Run either way:
    py test/test_intake_load.py
    py -m pytest test/test_intake_load.py
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
import json
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

REPORT = ("# AI audit report\n\n" + "\n".join(
    "Finding %03d: latency budget exceeded on the billing path." % i
    for i in range(300)))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_app(tmp_path, monkeypatch, cfg=None):
    """A real (withdrawn) App on a temp config, offline — same
    shape and same Tk-retry discipline as the other suites: a
    transient TclError must not turn into a silent skip."""
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
    cfg_path = tmp_path / "plan-console.json"
    if cfg is not None:
        write(cfg_path, json.dumps(cfg))
    monkeypatch.setattr(pc, "CFG", cfg_path)
    monkeypatch.setattr(pc.App, "_fetch_models", lambda self: None)
    monkeypatch.setattr(pc.App, "_auto_command_check",
                        lambda self, repo=None: None)
    # the orders sidecar is seeded next to the SCRIPT — redirect
    # HERE so a test that triggers seeding cannot write into the
    # real install directory
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    monkeypatch.setattr(pc, "HERE", sidecar)
    app = pc.App(root)
    root.update()
    return app, root


def _repo(tmp_path):
    """A minimal plan repo: _preflight requires PART-00.md and
    commands/new-plan.md to exist, or it opens a dialog."""
    repo = tmp_path / "repo"
    write(repo / "PART-00.md", "# PART 00\n")
    write(repo / "commands" / "new-plan.md", "# new-plan\n$ARGUMENTS\n")
    return repo


def _proceed(app, root, monkeypatch, repo, slug, text=REPORT):
    """Fill the box and click Proceed for real (the intake
    chain is stubbed — no model, no API)."""
    monkeypatch.setattr(pc.messagebox, "showerror",
                        lambda *a, **k: None)
    monkeypatch.setattr(pc.messagebox, "askyesno",
                        lambda *a, **k: True)
    app._intake_chain = lambda *a: None
    app.repo_var.set(str(repo))
    app.kind.set("audit")
    app.slug_var.set(slug)
    app.src.delete("1.0", "end")
    app.src.insert("1.0", text)
    root.update()
    app.on_proceed()
    root.update()
    return (repo / "plans" / slug / "SOURCE.md")


# ------------------------------------------------- the load button
def test_load_from_file_fills_the_box(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    p = tmp_path / "audit.md"
    write(p, REPORT)
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: str(p))
    app.on_load_source()
    root.update()
    assert app.src.get("1.0", "end").strip() == REPORT, \
        "the box must hold the whole file, not a preview of it"
    root.destroy()


def test_load_is_session_only_not_persisted(tmp_path, monkeypatch):
    """The loaded file must NOT be written to plan-console.json:
    the binding happens at Proceed, not at load. Otherwise a
    restart would restore the raw report even after the pane
    was bound to SOURCE.md."""
    app, root = _make_app(tmp_path, monkeypatch)
    p = tmp_path / "audit.md"
    write(p, REPORT)
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: str(p))
    app.on_load_source()
    assert "intake_file" not in app.cfg
    cfg_on_disk = tmp_path / "plan-console.json"
    if cfg_on_disk.is_file():
        on_disk = json.loads(cfg_on_disk.read_text(encoding="utf-8"))
        assert "intake_file" not in on_disk
    root.destroy()


def test_load_replaces_what_was_there(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    app.src.insert("1.0", "old notes")
    p = tmp_path / "report.md"
    write(p, REPORT)
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: str(p))
    app.on_load_source()
    assert app.src.get("1.0", "end").strip() == REPORT
    assert "old notes" not in app.src.get("1.0", "end")
    root.destroy()


def test_cancel_keeps_the_box_untouched(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    app.src.insert("1.0", "hand-typed notes")
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: "")
    app.on_load_source()
    assert "hand-typed notes" in app.src.get("1.0", "end")
    assert "intake_file" not in app.cfg
    root.destroy()


def test_unreadable_file_is_named_not_silent(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    # a directory: read_text raises OSError on every platform
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: str(tmp_path))
    errors = []
    monkeypatch.setattr(pc.App, "_error_dialog",
                        lambda self, t, m: errors.append((t, m)))
    app.on_load_source()
    assert errors, "an unreadable file must be named, not silent"
    assert app.src.get("1.0", "end").strip() == ""
    root.destroy()


def test_error_dialog_builds_a_themed_window(tmp_path, monkeypatch):
    """The themed box must actually build and be
    destroyable — a themed error that crashes on
    open is worse than the native box it replaced.
    Both token states are exercised: the palette
    and the high-contrast no-tokens fallback."""
    tk = pytest.importorskip("tkinter")
    app, root = _make_app(tmp_path, monkeypatch)
    app._error_dialog("Load from file",
                      "plans/demo is already frozen.")
    root.update()
    dls = [w for w in root.winfo_children()
           if isinstance(w, tk.Toplevel)]
    assert dls, "the themed error window must exist"
    dls[0].destroy()
    # high contrast: no palette, must still build
    app._tokens = None
    app._error_dialog("Load from file", "could not read x")
    root.update()
    dls = [w for w in root.winfo_children()
           if isinstance(w, tk.Toplevel)]
    assert dls, "the dialog must build without a palette too"
    dls[0].destroy()
    root.destroy()


# ------------------------------------------------- the SOURCE.md bind
def test_slug_is_taken_marks_proceeded_slugs(tmp_path):
    repo = _repo(tmp_path)
    assert pc.slug_is_taken(repo, "anything") is False
    write(repo / "plans" / "demo" / "SOURCE.md",
          "# SOURCE — demo\n\n---\n\nbody\n")
    assert pc.slug_is_taken(repo, "demo") is True
    # an invalid slug is never "taken" — Proceed is
    # the one that refuses those
    assert pc.slug_is_taken(repo, "Not Kebab!") is False
    assert pc.slug_is_taken(repo, "") is False


def test_load_refused_when_source_md_exists(tmp_path, monkeypatch):
    """The shortcut the button must NOT offer: filling
    the pane over a plan whose Proceed already ran. The
    pane is BOUND to that plan's SOURCE.md."""
    app, root = _make_app(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    src = _proceed(app, root, monkeypatch, repo, "taken-slug")
    assert src.is_file()
    # the owner now tries to load a DIFFERENT file over
    # the same slug — refused before the dialog even opens
    picked = []
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: picked.append(kw) or str(
                            tmp_path / "another-audit.md"))
    errors = []
    monkeypatch.setattr(pc.App, "_error_dialog",
                        lambda self, t, m: errors.append((t, m)))
    app.on_load_source()
    root.update()
    assert errors, "loading over an existing plan must be refused"
    assert errors[0][0] == "Load from file"
    assert "has not been used before" in errors[0][1]
    assert not picked, "a refused slug must not open the picker"
    assert app.src.get("1.0", "end").strip() == REPORT, \
        "a refused load must leave the bound SOURCE.md in the box"
    root.destroy()


def test_load_refused_for_a_frozen_plan(tmp_path, monkeypatch):
    """Re-intake is blocked for frozen plans (the same
    ban on_proceed enforces) — and the refusal says
    WHY, rather than the generic SOURCE.md message."""
    app, root = _make_app(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    pdir = repo / "plans" / "frozen-plan"
    write(pdir / "PART-01 v1.0.md",
          "# PART 01 — demo | v1.0 frozen 2026-10-04\n\n"
          "A. MISSION & SCOPE\n")
    write(pdir / "SOURCE.md",
          "# SOURCE — frozen-plan\n\n---\n\nbody\n")
    app.repo_var.set(str(repo))
    app.slug_var.set("frozen-plan")
    picked = []
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: picked.append(kw) or str(
                            tmp_path / "another-audit.md"))
    errors = []
    monkeypatch.setattr(pc.App, "_error_dialog",
                        lambda self, t, m: errors.append((t, m)))
    app.on_load_source()
    root.update()
    assert errors, "a frozen plan must refuse the load"
    assert errors[0][0] == "Load from file"
    assert "frozen" in errors[0][1]
    assert "has not been used before" in errors[0][1]
    assert not picked, "a refused slug must not open the picker"
    root.destroy()


def test_load_allowed_for_a_fresh_slug(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    app.repo_var.set(str(repo))
    app.slug_var.set("fresh-slug")
    p = tmp_path / "audit.md"
    write(p, REPORT)
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: str(p))
    app.on_load_source()
    assert app.src.get("1.0", "end").strip() == REPORT
    root.destroy()


def test_load_allowed_when_the_repo_has_no_plans_yet(
        tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    repo = tmp_path / "empty-repo"
    repo.mkdir()
    app.repo_var.set(str(repo))
    app.slug_var.set("first-plan")
    p = tmp_path / "audit.md"
    write(p, REPORT)
    monkeypatch.setattr(pc.filedialog, "askopenfilename",
                        lambda **kw: str(p))
    app.on_load_source()
    assert app.src.get("1.0", "end").strip() == REPORT
    root.destroy()


def test_proceed_binds_the_pane_to_source_md(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    src = _proceed(app, root, monkeypatch, repo, "probe-audit")
    assert src.is_file(), "Proceed must write SOURCE.md"
    assert app.cfg["intake_file"] == str(src), \
        "after Proceed the pane is bound to SOURCE.md, not the loaded file"
    on_disk = json.loads(
        (tmp_path / "plan-console.json").read_text(encoding="utf-8"))
    assert on_disk["intake_file"] == str(src)
    root.destroy()


def test_source_body_strips_the_wrapper():
    wrapped = ("# SOURCE — demo\nType: audit | Captured: "
               "2026-10-04 (plan-console)\n\n---\n\n"
               + REPORT + "\n")
    assert pc.source_body(wrapped) == REPORT
    # a report that itself contains a '---' rule survives:
    # the FIRST separator is always the wrapper's
    tricky = ("# SOURCE — demo\nType: plan | Captured: "
              "2026-10-04 (plan-console)\n\n---\n\n"
              "# Section\n\n---\n\nbody text\n")
    assert pc.source_body(tricky) == "# Section\n\n---\n\nbody text"
    # no wrapper at all (a plain report): passes through
    assert pc.source_body("  just a report  \n") == "just a report"


def test_restored_source_md_is_unwrapped(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    src = _proceed(app, root, monkeypatch, repo, "demo-audit")
    # simulate a restart: fresh box, then the launch-time restore
    app.src.delete("1.0", "end")
    app._restore_intake_source()
    root.update()
    assert app.src.get("1.0", "end").strip() == REPORT, \
        "the restore must give the BODY — no header, no wrapper"
    root.destroy()


def test_restored_plan_reproceeds_without_double_wrapping(
        tmp_path, monkeypatch):
    """The bug this gates: restoring the WRAPPED SOURCE.md and
    clicking Proceed again would wrap the wrap, burying the
    report under ever-deeper headers."""
    app, root = _make_app(tmp_path, monkeypatch)
    repo = _repo(tmp_path)
    src = _proceed(app, root, monkeypatch, repo, "demo-audit")
    # restart: the launch-time restore repopulates the box
    app.src.delete("1.0", "end")
    app._restore_intake_source()
    root.update()
    # ... and the owner Proceeds the restored plan again
    src2 = _proceed(app, root, monkeypatch, repo, "demo-audit")
    assert pc.source_body(src2.read_text(encoding="utf-8")) == REPORT, \
        "re-Proceeding a restored plan must not double-wrap"
    root.destroy()


# ------------------------------------------------- restore on launch
def test_vanished_remembered_file_starts_empty(tmp_path, monkeypatch):
    app, root = _make_app(tmp_path, monkeypatch,
                          {"intake_file": str(tmp_path / "gone.md")})
    assert app.src.get("1.0", "end").strip() == ""
    root.destroy()


def test_wrapper_only_source_md_starts_empty(tmp_path, monkeypatch):
    p = tmp_path / "plans" / "empty" / "SOURCE.md"
    write(p, "# SOURCE — empty\nType: audit | Captured: "
             "2026-10-04 (plan-console)\n\n---\n\n\n")
    app, root = _make_app(tmp_path, monkeypatch,
                          {"intake_file": str(p)})
    assert app.src.get("1.0", "end").strip() == ""
    root.destroy()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
