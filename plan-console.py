#!/usr/bin/env python3
"""Plan Console — paste-to-plan intake + session lifecycle manager.
v2.0 — Owner-pass hardening + versioned freeze (built on the real v1.9):
  * Strict question parser: only numbered ("1. …") or '?'-ending lines
    OUTSIDE "## Owner actions" sections and code fences count as
    questions. Prose, SQL drafts and resolution summaries never
    inflate the counter or block Freeze.
  * Owner pass: full question text shown above the answer box; every
    answer flattened to one line; every removal archived to
    plans/<slug>/owner-pass.log with an OPEN-QUESTIONS.md.bak snapshot;
    answers are refused (not lost) if the draft is missing.
  * Freeze writes the frozen plan as "PART-01 v1.0.md" (version in the
    filename) and now gates on VALIDATION.md == "PART-01 READY".
    Legacy PART-01.md files (freeze header present) are still fully
    supported everywhere — run "Update command files" once after
    installing so agents know both names.
  * Sessions: better "not frozen" diagnostics (lists the folder,
    reminds that the Slug field takes the PLAN slug), deploy note
    mentions the PART-01 §G agent-deploy override.
v2.1 — richer open questions: every question is a three-line block
  (PROBLEM / QUESTION / RECOMMEND) so the owner sees problem context
  and a recommendation with each decision. Parser is block-aware
  (one count per block; legacy one-liners still count); owner pass
  shows and archives whole blocks. Run "Update command files" once
  per repo after installing.
v2.2 — interruption safety (IN-PROGRESS handshake):
  * commands/session.md: the agent writes plans/<slug>/IN-PROGRESS.md
    before working, appends a "stopped" line when halting without
    finishing, and on the next run RECONCILES partial work (git diff)
    instead of redoing blindly. PROGRESS.md stays the sole completion
    record (canonical line appended FIRST, marker deleted after; a
    marker left over after completion is stale and gets removed).
  * Started repos are checked automatically (startup + first action,
    once per repo per app run): if command files predate the built-in
    versions, the console offers to apply them — no hunting for the
    "Update command files" button.
  * Status / Plan health / Copy-session-instruction surface the
    interrupted state (◔ RUNNING, resume verdicts, stale-marker note).
  * Freeze self-heals a missing PROGRESS.md in the already-frozen
    branch; the owner pass refuses a duplicate answer if a crash left
    a question answered-but-still-listed.
v2.3 — standing orders for execution agents (AGENT-ORDERS.md): the
  console reads them and prepends them to every session instruction —
  the document's own placement rule ("before every session block").
  Customization without touching code: the active file is
  AGENT-ORDERS.md next to this script (auto-created from the built-in
  default on first use; never auto-overwritten afterwards), or a
  per-repo override at <repo>/AGENT-ORDERS.md (that wins for that
  repo). An empty file or one containing just "OFF" disables them.
  "Agent orders…" (top bar) opens the active file for editing. Init /
  Update-command-files never touch these files. No command files
  changed in v2.3 — existing v2.2 repos need nothing.
v2.4 — BLOCKED resolution made explicit: commands/session.md now
  instructs the agent to close a resolved incident by appending a
  "resolved <date> — how" line and RENAMING BLOCKED.md →
  BLOCKED-resolved.md (never deleting it — it is the audit record of
  the failure and its fix; the console flags "blocked" on the file's
  existence and clears on the rename). The Status line states the
  rename convention. Existing repos: "Update command files" once
  (session.md changed).
v2.5 — gates are actually reported in Plan health: PROGRESS.md records
  are parsed LENIENTLY, read-only (the file is agent-owned per PART-01
  §F — the console never rewrites it). The reader accepts the format
  drift agents produce: 'Gates:'/'gates ='/missing label, ids
  G1/g-1/g_1, ids carrying their §A descriptions, bracketed lists,
  ranges g1-g3, 'all' (expanded from the §A session row), 'none', bare
  '1, 2' lists, records split across several lines, prose addenda
  after a real record (the record with content wins). Non-canonical
  records are flagged (⚠) in the output instead of silently reporting
  no gates. Applies everywhere the console reads progress: Plan
  health, Session report, Status, session-sequence guard.
  commands/session.md now spells out the canonical PROGRESS line with
  a worked example — existing repos: "Update command files" once
  (session.md changed; the v2.2 auto-check offers it). No other
  starter files changed.
v2.6.3 — audit hardening: DEFERRED must be a tag (prose like 'not
  DEFERRED' no longer resolves a recon item); checkbox toggling flips
  the anchored bracket only; EXISTS auto-verify is repo-relative only;
  model favorites accept real model ids only; the <<<FILE>>> path
  guard is module-level (parse_files) and unit-tested; the auto-update
  dialog text comes from COMMAND_UPDATE_NOTE; socket timeouts are
  caught on Python 3.9 too.
v2.6.4 — the Owner-pass status line now checks the third Freeze gate
  (VALIDATION.md) too: "ready to Freeze" only appears when the report
  exists and reads exactly "PART-01 READY", so a stale validation
  report can no longer make the counter contradict the Freeze button.

Works with ANY coding agent (e.g. Zoo Code in VS Codium):
  - Intake scaffolding runs via the OpenRouter API if you tick
    "Use API key" (and have a key stored); otherwise the console copies
    a ready-made instruction for your agent.
  - Sessions always run in YOUR agent (instruction copied for you).
  - Freeze, Status, Session report, Plan health, Show validation report,
    Owner pass are pure Python — instant, no model, no API.

One-time: point "Repo folder" at your project folder and click
"Init starter repo" to create PART-00.md, templates/ and commands/.
Existing repo: "Update command files" refreshes commands/ only.

Settings are stored in plan-console.json next to this script.
"""
import json, os, queue, re, socket, subprocess, threading, time
import urllib.request, urllib.error
from datetime import date, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
try:
    import winreg                    # Windows registry (theme detection)
except ImportError:                  # non-Windows: guarded fallbacks below
    winreg = None

HERE = Path(__file__).resolve().parent
CFG = HERE / "plan-console.json"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MODELS_URL = "https://openrouter.ai/api/v1/models"
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"

# v2.1 — block-aware question parsing (owner pass + freeze + status)
Q_LINE_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
# v2.6.2 — anchored: a comment line counts as the START of an owner-
# actions/commands/SQL section only when the section keyword OPENS the
# comment ("## Owner actions", "# Commands:"). A comment that merely
# MENTIONS these words (e.g. OPEN-QUESTIONS.md header prose "Commands/
# SQL/owner actions live only under...") must not poison the rest of
# the file — the unanchored variant silently hid every question block
# after it (freeze skipped the questions gate entirely).
OWNER_SECTION_RE = re.compile(r"^#+\s*(?:owner\s+actions|commands?|sql)\b", re.I)
# v2.6.1 — recon checkbox lines are recognized only at line start
# (optional bullet), so prose that merely MENTIONS `- [ ]` (e.g. the
# RECON-CHECKLIST.md header explaining the format) is never counted.
RECON_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s*)?\[( |x|X)\]")
# v2.6.3 — DEFERRED counts as resolved only when it is a TAG: it opens
# the item text (right after the checkbox) or sits in a bracketed note
# like '(DEFERRED …)'. Prose that merely MENTIONS the word ('not
# DEFERRED yet', 'what about DEFERRED?') no longer silently resolves
# an open item.
DEFERRED_START_RE = re.compile(r"^DEFERRED\b", re.I)
DEFERRED_BRACKET_RE = re.compile(r"[\[(]\s*DEFERRED\b", re.I)

# ------------------------------------------------------------- v3.0 theme
# Semantic token system — mirrors the guides' CSS token names/values
# (UserGuide.html :root palette; assets/console.css keeps them in
# lockstep, PART-01 §G). This module-level dict is the ONLY place hex
# color literals may live (PART-01 §E grep gate).
THEMES = {
    "light": {
        "bg-main": "#f8fafc",
        "bg-card": "#ffffff",
        "bg-accent": "#e2e8f0",
        "text-main": "#0f172a",
        "text-muted": "#475569",
        "accent-cyan": "#0284c7",
        "accent-green": "#16a34a",
        "accent-orange": "#ea580c",
        "accent-red": "#dc2626",
        "border-color": "#cbd5e1",
    },
    "dark": {
        "bg-main": "#0f172a",
        "bg-card": "#1e293b",
        "bg-accent": "#334155",
        "text-main": "#f8fafc",
        "text-muted": "#94a3b8",
        "accent-cyan": "#38bdf8",
        "accent-green": "#4ade80",
        "accent-orange": "#fb923c",
        "accent-red": "#f87171",
        "border-color": "#475569",
    },
}
# persisted selector values (PART-01 §E): "light" | "dark" | "system"
THEME_SETTINGS = ("light", "dark", "system")
THEME_LABELS = {"light": "Light", "dark": "Dark", "system": "Follow OS"}
THEME_SETTING_BY_LABEL = {v: k for k, v in THEME_LABELS.items()}


def _detect_os_theme():
    """'light' or 'dark' — best-effort OS theme detection. Windows reads
    HKCU\\...\\Themes\\Personalize → AppsUseLightTheme; anything else
    (non-Windows, winreg missing, key unreadable) falls back to 'light'
    without crashing (PART-01 §G)."""
    if winreg is not None and os.name == "nt":
        try:
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion"
                    r"\Themes\Personalize") as key:
                return ("dark" if winreg.QueryValueEx(key,
                        "AppsUseLightTheme")[0] == 0 else "light")
        except OSError:
            pass
    return "light"


def _high_contrast_active():
    """True when Windows high-contrast mode is on — or when the check
    cannot be performed (non-Windows, winreg missing, key unreadable):
    skipping custom colors is the safe default, never fight the OS
    (PART-01 §G)."""
    if winreg is None or os.name != "nt":
        return True
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Control Panel\Accessibility"
                            r"\HighContrast") as key:
            return bool(int(winreg.QueryValueEx(key, "Flags")[0]) & 1)
    except OSError:
        return True


def apply_theme(root, style, name):
    """Apply the named token set ('light' or 'dark') to the whole app:
    ttk styling via 'clam' (fallback 'default' when clam is missing,
    §G) plus a walk over classic tk widgets, which ttk.Style cannot
    restyle (§G). Returns True when colors were applied, False when
    skipped because Windows high-contrast mode is active (or cannot be
    ruled out)."""
    if _high_contrast_active():
        return False
    t = THEMES[name]
    style.theme_use("clam" if "clam" in style.theme_names() else "default")
    style.configure(".", background=t["bg-main"], foreground=t["text-main"],
                    fieldbackground=t["bg-card"],
                    bordercolor=t["border-color"],
                    lightcolor=t["bg-card"], darkcolor=t["bg-card"],
                    troughcolor=t["bg-card"],
                    selectbackground=t["bg-accent"],
                    selectforeground=t["text-main"])
    style.configure("TFrame", background=t["bg-main"])
    style.configure("TLabel", background=t["bg-main"],
                    foreground=t["text-main"])
    style.configure("TLabelframe", background=t["bg-main"],
                    foreground=t["text-main"],
                    bordercolor=t["border-color"])
    style.configure("TLabelframe.Label", background=t["bg-main"],
                    foreground=t["text-main"])
    style.configure("TNotebook", background=t["bg-main"],
                    bordercolor=t["border-color"])
    style.configure("TNotebook.Tab", background=t["bg-card"],
                    foreground=t["text-muted"], padding=(10, 4))
    style.map("TNotebook.Tab", background=[("selected", t["bg-card"])],
              foreground=[("selected", t["text-main"])])
    style.configure("TButton", background=t["bg-card"],
                    foreground=t["text-main"],
                    bordercolor=t["border-color"])
    style.map("TButton",
              background=[("pressed", t["bg-accent"]),
                          ("active", t["bg-card"])],
              foreground=[("disabled", t["text-muted"])])
    style.configure("TEntry", fieldbackground=t["bg-card"],
                    foreground=t["text-main"],
                    insertbackground=t["text-main"],
                    bordercolor=t["border-color"])
    style.map("TEntry", fieldbackground=[("readonly", t["bg-card"])])
    style.configure("TCombobox", fieldbackground=t["bg-card"],
                    foreground=t["text-main"],
                    bordercolor=t["border-color"])
    style.map("TCombobox", fieldbackground=[("readonly", t["bg-card"])],
              foreground=[("readonly", t["text-main"])])
    style.configure("TCheckbutton", background=t["bg-main"],
                    foreground=t["text-main"])
    style.map("TCheckbutton", background=[("active", t["bg-main"])])
    style.configure("TSpinbox", fieldbackground=t["bg-card"],
                    foreground=t["text-main"],
                    insertbackground=t["text-main"],
                    bordercolor=t["border-color"])
    style.configure("TScrollbar", background=t["bg-card"],
                    troughcolor=t["bg-main"],
                    bordercolor=t["border-color"])
    # v3.1 — status pills (tab status lines, owner-pass status line)
    style.configure("Pill.TLabel", background=t["bg-accent"],
                    foreground=t["text-main"], padding=(10, 3))
    root.configure(bg=t["bg-main"])
    _walk_classic_widgets(root, t)
    return True


def _walk_classic_widgets(widget, t):
    """Recolor classic tk widgets (ttk.Style cannot reach them, §G).
    Toplevels are skipped: popups always use the theme active at their
    creation time (accepted exception, §G)."""
    for child in widget.winfo_children():
        if isinstance(child, tk.Toplevel):
            continue
        cls = child.winfo_class()
        if cls == "Text":
            child.configure(bg=t["bg-card"], fg=t["text-main"],
                            insertbackground=t["text-main"],
                            selectbackground=t["bg-accent"],
                            selectforeground=t["text-main"])
        elif cls == "Listbox":
            child.configure(bg=t["bg-card"], fg=t["text-main"],
                            selectbackground=t["bg-accent"],
                            selectforeground=t["text-main"])
        _walk_classic_widgets(child, t)


def recon_item_state(line):
    """'done', 'open', or None (not a checkbox item line)."""
    m = RECON_ITEM_RE.match(line)
    if not m:
        return None
    return "done" if m.group(1).lower() == "x" else "open"


def is_deferred(line):
    """True when the owner marked this recon item DEFERRED (v2.0 rule,
    tightened v2.6.3 — see DEFERRED_START_RE above)."""
    m = RECON_ITEM_RE.match(line)
    rest = line[m.end():].strip() if m else line.strip()
    return bool(DEFERRED_START_RE.match(rest)
                or DEFERRED_BRACKET_RE.search(rest))


def flip_recon_item(line):
    """Toggle the CHECKBOX of a recon item line (v2.6.3): flips the
    bracket the anchor matched, never the first '[ ]'/'[x]' occurring
    anywhere in the prose after it. None when the line is not a
    checkbox item."""
    m = RECON_ITEM_RE.match(line)
    if not m:
        return None
    a, b = m.start(1), m.end(1)
    return line[:a] + ("x" if m.group(1) == " " else " ") + line[b:]


def count_open_recon(text):
    """Unresolved `- [ ]` items in a RECON-CHECKLIST body: real checkbox
    lines only; owner-marked DEFERRED lines count as resolved (v2.0 rule)."""
    return sum(1 for l in text.splitlines()
               if recon_item_state(l) == "open"
               and not is_deferred(l))
# continuation lines of a v2.1 question block: indented, or explicitly
# labelled QUESTION:/RECOMMEND:/RECOMMENDATION:
Q_CONT_RE = re.compile(r"^\s*(QUESTION|RECOMMEND(?:ATION)?)\s*:", re.I)


def _is_continuation(line):
    """True if `line` continues the question block above it (v2.1):
    indented, or labelled QUESTION:/RECOMMEND:/RECOMMENDATION:.
    Blank lines, headings, code fences, numbered lines and flush-left
    prose are NOT continuations."""
    s = line.strip()
    if (not s or s.startswith("#") or line.lstrip().startswith("```")
            or Q_LINE_RE.match(line)):
        return False
    return line[:1] in (" ", "\t") or bool(Q_CONT_RE.match(line))


def parse_questions(text):
    """[(lineno, line)] of REAL questions only — block-aware (v2.1).

    A question is either a v2.1 three-line block:
        1. PROBLEM: <the gap/risk that raises the question>
           QUESTION: <the decision needed>?
           RECOMMEND: <suggested answer + why>
    (the numbered PROBLEM header counts ONCE; continuation lines are
    absorbed, never double-counted) — or a legacy one-liner: a numbered
    line, or any '?'-ending line. Flush-left prose after a question is
    NOT absorbed (legacy files keep their exact v2.0 behavior). Lines
    in Owner-actions/commands/SQL sections and ``` fences never count.
    """
    out, in_owner, in_fence, in_block = [], False, False, False
    for i, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            in_block = False
            continue
        s = line.strip()
        if not s:
            in_block = False
            continue
        if s.startswith("#"):
            in_owner = bool(OWNER_SECTION_RE.search(s))
            in_block = False
            continue
        if in_owner or in_fence:
            continue
        if Q_LINE_RE.match(line):
            out.append((i, line))
            in_block = True          # numbered header opens a block
            continue
        if in_block and _is_continuation(line):
            continue                 # QUESTION:/RECOMMEND: absorbed
        in_block = False
        if s.endswith("?"):
            out.append((i, line))
    return out


def question_block(text, lineno):
    """Full text of the question whose header sits at `lineno`: the
    header plus its continuation lines, up to the first blank line,
    heading, code fence, numbered line or flush-left prose. Legacy
    one-liners return just themselves. The owner pass displays,
    archives and removes whole blocks with this."""
    lines = text.splitlines()
    if not 0 <= lineno < len(lines):
        return ""
    block = [lines[lineno]]
    for j in range(lineno + 1, len(lines)):
        if _is_continuation(lines[j]):
            block.append(lines[j])
        else:
            break
    return "\n".join(block)


def recommend_line(text, lineno):
    """The RECOMMEND: line of the question block at `lineno`, stripped of
    its label, or "" when the block has none (legacy one-liners)."""
    for ln in question_block(text, lineno).splitlines():
        m = re.match(r"\s*RECOMMEND\s*:\s*(.*)$", ln, re.I)
        if m:
            return m.group(1).strip()
    return ""


def count_owner_answers(text):
    """v2.7 — leftover Q/A pairs under '## OWNER ANSWERS' in a PART-01
    draft. The section is a TEMPORARY inbox: per the owner-pass rule
    (commands/owner-resolve.md) every answered pair must be integrated
    into §A–§G and removed; only pairs marked NEEDS CLARIFICATION may
    stay. A '- Q:' line opens a pair; a line of the pair containing
    'NEEDS CLARIFICATION' exempts it. Pairs outside the section never
    count. Console-side twin of the validate-plan leftover check, so
    the Freeze gate and the Owner-pass tab see the same number the
    validator reports."""
    pos = text.find("## OWNER ANSWERS")
    if pos == -1:
        return 0
    leftover, in_pair, flagged = 0, False, False
    for line in text[pos:].splitlines()[1:]:
        s = line.strip()
        if s.startswith("#"):
            break                      # a later heading ends the section
        if line.startswith("- Q:"):
            if in_pair and not flagged:
                leftover += 1
            in_pair, flagged = True, False
        elif in_pair and "NEEDS CLARIFICATION" in s:
            flagged = True
    if in_pair and not flagged:
        leftover += 1
    return leftover


# ----------------------------------------------------------------------------
# v2.5 — lenient PROGRESS.md parsing (Plan health / Session report /
# Status / session-sequence guard). The canonical record (PART-00
# SESSION MECHANICS):
#   SESSION <n> | <YYYY-MM-DD> | gates: <gN ids> |
#   status: PASS|PARTIAL|FAIL|BLOCKED[ — reason] | P00 v<version>
# Agents emit near-misses: 'gates: passed g1,g2', 'Gates: g1 g2',
# 'gates: [g1: pytest green]', 'gates: 1, 2', 'gates: all', fields on
# separate lines, no 'gates:' label at all … — and the old strict
# whole-line parse then silently reported NO gates. Policy (matches
# the app's ownership rules, PART-01 §F):
#   - READ-ONLY: PROGRESS.md is agent-owned; the console never
#     rewrites it. Leniency lives entirely on the read side.
#   - FLAG, DON'T HIDE: records that deviate from the canonical shape
#     are parsed anyway and marked non-canonical, so drift stays
#     visible in the health output instead of invisible.
# ----------------------------------------------------------------------------
PROG_SESSION_RE = re.compile(r"\bSESSION\s*[:#.]?\s*(\d+)\b", re.I)
PROG_SESSION_START_RE = re.compile(r"^\s*[-*•>✓»#]*\s*SESSION\s*[:#.]?\s*(\d+)",
                                   re.I)
PROG_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
PROG_P00_RE = re.compile(r"\bP\s*00\s*v[\w.]+", re.I)
PROG_GATES_LABEL_RE = re.compile(r"\bgates?\b\s*[:=]?", re.I)
PROG_GATES_LABEL_STRICT_RE = re.compile(r"\bgates?\b\s*[:=]", re.I)
PROG_STATUS_LBL_VAL_RE = re.compile(r"\bstatus\b\s*[:=]?\s*"
                                     r"(PASS|PARTIAL|FAIL|BLOCK)\w*", re.I)
PROG_STATUS_VAL_RE = re.compile(r"\b(PASS|PARTIAL|FAIL|BLOCKED|BLOCK)\b", re.I)
PROG_GATE_TOKEN_RE = re.compile(r"\bg[-_ ]?(\d+)\b", re.I)
PROG_GATE_RANGE_RE = re.compile(r"\bg[-_]?(\d+)\s*[-–~]\s*g?[-_]?\s*(\d+)\b",
                                re.I)
PROG_ALL_RE = re.compile(r"^[\s(\[{]*(?:all(?:\s+gates?)?(?:\s+passed)?)"
                         r"[\s)\]}]*$", re.I)
PROG_NONE_RE = re.compile(r"^(?:none|n/?a|-{1,2}|no gates|0|\[\]|"
                          r"\(\s*none\s*\)|not applicable|empty)$", re.I)
PROG_CANON_RE = re.compile(
    r"^SESSION\s+(\d+)\s+\|\s+(\d{4}-\d{2}-\d{2})\s+\|\s+gates:\s*"
    r"(g\d+(?:\s*,\s*g\d+)*)?\s*\|\s+status:\s+"
    r"(PASS|PARTIAL|FAIL|BLOCKED)(?:\s+[—-]\s*[^|]*)?\s*\|\s+P00\s+v[\w.]+\s*$")
PROG_CONT_RE = re.compile(r"\b(?:gates?|status)\b\s*[:=]?|\bP\s*00\b", re.I)
PROG_SECTION_RE = re.compile(r"^\s*#*\s*[A-G][.)]\s")
# a physical line ending in one of these continues on the next line
PROG_HANG_END = (":", "|", ",", ";", "—", "-")


def _gnum(g):
    return int(g[1:])


def parse_gates_field(raw):
    """(ids, all_flag) — normalized 'gN' ids from any gates text.

    Tolerates what agents actually emit: separators , ; whitespace | /;
    case/prefix variants G1 g1 g-1 g_1; ids carrying their §A
    descriptions ('g1: pytest green', 'g2 (parity)'); bracketed lists;
    ranges g1-g3 (expanded); 'all' → all_flag=True (caller expands
    against the §A session row); 'none' '-' 'n/a' → ([], False); bare
    number lists ('1, 2') accepted only when no g-prefixed id appears
    anywhere in the field."""
    if not raw:
        return [], False
    t0 = raw.strip().strip("()[]{}\"'. ")
    if PROG_ALL_RE.match(t0):
        return [], True
    if not t0 or PROG_NONE_RE.match(t0):
        return [], False
    ids = set()
    s = raw.replace("|", " ").replace("/", " ")

    def _expand(m):
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < a <= b <= 99:
            ids.update("g%d" % k for k in range(a, b + 1))
        return " "

    s = PROG_GATE_RANGE_RE.sub(_expand, s)
    for m in PROG_GATE_TOKEN_RE.finditer(s):
        ids.add("g" + m.group(1))
    if ids:
        return sorted(ids, key=_gnum), False
    bare = s.replace(" and ", " ").replace(",", " ").replace(";", " ")
    if re.fullmatch(r"[\d\s]+", bare):
        nums = re.findall(r"\d+", bare)
        if nums and all(1 <= int(x) <= 99 for x in nums):
            return sorted(("g%s" % x for x in nums), key=_gnum), False
    return [], False


def _gates_field_text(text):
    """Raw gates text when a 'gates' label appears in the record HEAD
    (everything before the status value and the P00 tag), else None.
    Restricting the search to the head keeps the word 'gates' inside a
    status note from hijacking the field, and lets gate descriptions
    contain words like 'passed' without truncating the field."""
    head_end = len(text)
    for stop in (PROG_STATUS_LBL_VAL_RE, PROG_P00_RE):
        m = stop.search(text)
        if m:
            head_end = min(head_end, m.start())
    head = text[:head_end]
    m = PROG_GATES_LABEL_RE.search(head)
    if not m:
        return None
    return head[m.end():].strip(" \t\n,;|")


def _gates_field_after_status(text):
    """Field of a 'gates:' label placed AFTER the status value
    (reordered fields) — requires the colon so prose in the status
    note never matches. Runs to the P00 tag or end of text."""
    sm = (PROG_STATUS_LBL_VAL_RE.search(text)
          or PROG_STATUS_VAL_RE.search(text))
    if not sm:
        return None
    m = PROG_GATES_LABEL_STRICT_RE.search(text, sm.end())
    if not m:
        return None
    start = m.end()
    end = len(text)
    pm = PROG_P00_RE.search(text, start)
    if pm:
        end = pm.start()
    return text[start:end].strip(" \t\n,;|") or None


def _guess_gates_field(text):
    """Gates text when no 'gates' label exists anywhere: the first
    '|'-chunk of the head that parses to gate ids, else the whole head
    (its gN token scan picks up any ids anywhere in it)."""
    head_end = len(text)
    for stop in (PROG_STATUS_LBL_VAL_RE, PROG_P00_RE):
        m = stop.search(text)
        if m:
            head_end = min(head_end, m.start())
    head = text[:head_end]
    for chunk in head.split("|"):
        chunk = chunk.strip()
        if (not chunk or PROG_SESSION_RE.search(chunk)
                or PROG_DATE_RE.fullmatch(chunk)
                or re.fullmatch(r"\d+", chunk)):
            continue
        ids, _ = parse_gates_field(chunk)
        if ids:
            return chunk
    return head.strip() or None


def parse_progress_record(text):
    """Leniently parse ONE PROGRESS.md record (a single line, or
    several folded lines) into a dict — or None when no 'SESSION <n>'
    token is present. Keys: n · date · gates (normalized gN ids) ·
    gates_all (True for 'all' — expand via session_row_gates) ·
    status · note (the status reason) · p00 · canonical (exactly the
    PART-00 shape) · raw."""
    ms = PROG_SESSION_RE.search(text)
    if not ms:
        return None
    dm = PROG_DATE_RE.search(text)
    pm = PROG_P00_RE.search(text)
    sm = PROG_STATUS_LBL_VAL_RE.search(text)
    if sm is None:            # no 'status:' label → the LAST status
        for m in PROG_STATUS_VAL_RE.finditer(text):   # word wins
            sm = m
    status, note = "UNKNOWN", ""
    if sm:
        status = sm.group(1).upper()
        if status == "BLOCK":
            status = "BLOCKED"
        after = text[sm.end():]
        p2 = PROG_P00_RE.search(after)
        if p2:
            after = after[:p2.start()]
        note = after.strip(" \t\n|—-;,")
    gates_raw = _gates_field_text(text)
    if gates_raw is None:
        gates_raw = _gates_field_after_status(text)
    if gates_raw is None:
        gates_raw = _guess_gates_field(text)
    gates, gates_all = parse_gates_field(gates_raw)
    one_line = "\n" not in text.strip()
    return {"n": int(ms.group(1)),
            "date": dm.group(1) if dm else "",
            "gates": gates, "gates_all": gates_all,
            "status": status, "note": note,
            "p00": pm.group(0) if pm else "",
            "canonical": one_line and bool(PROG_CANON_RE.match(text.strip())),
            "raw": text.strip()}


def read_progress(path):
    """All session records in PROGRESS.md, in file order (v2.5).

    Folds records agents split across lines ('SESSION 3 | …' followed
    by 'gates: …' / 'status: …' lines, or values wrapped after a
    trailing ':', '|', ',' or '—'); skips headers, comments and
    unrelated prose. '# SESSION n' and bulleted session lines count as
    record starts (the v2.4 parser accepted them too)."""
    entries, buf = [], []

    def _flush():
        if buf:
            rec = parse_progress_record("\n".join(buf))
            if rec:
                entries.append(rec)
            del buf[:]

    if not path.is_file():
        return entries
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        if PROG_SESSION_START_RE.match(line):
            _flush()          # '# SESSION n' / bulleted headers count too —
            buf.append(line)  # the v2.4 parser allowed them
            continue
        if line.lstrip().startswith("#"):
            continue          # other comments never fold into a record
        if buf and (PROG_CONT_RE.search(line)
                    or buf[-1].rstrip().endswith(PROG_HANG_END)):
            buf.append(line)
        else:
            _flush()
    _flush()
    return entries


def latest_sessions(records):
    """({n: record}, duplicated_ns) — the LAST record per session
    number wins (agents occasionally append a corrective second line);
    duplicated_ns lists sessions recorded more than once."""
    out, dups = {}, []
    for rec in records:
        if rec["n"] in out:
            dups.append(rec["n"])
        out[rec["n"]] = rec
    return out, sorted(set(dups))


def session_row_gates(plan_text, n):
    """Gate ids PART-01 §A defines for session `n`: scans the §A
    section (falls back to the whole file when no section headings are
    found), handling template table rows ('3 | scope | g1: pytest
    green, g2: lint | no') and loose rows ('3. scope — gates g1, g2 —
    deploy: no'). [] when the session or its gates are not defined —
    used by Plan health to compute 'missing' gates."""
    lines = plan_text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        if re.match(r"^\s*#*\s*A[.)]\s", ln):
            start = i
            break
    if start is None:
        sec = lines                     # no §A heading → whole file
    else:
        end = len(lines)
        for j in range(start + 1, len(lines)):
            if PROG_SECTION_RE.match(lines[j]):
                end = j
                break
        sec = lines[start:end]
    want = str(n)
    for line in sec:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) >= 3 and cells[0].rstrip(".):") == want:
            ids, _ = parse_gates_field(cells[2])
            if ids:
                return ids
            ids, _ = parse_gates_field(" ".join(cells))
            if ids:
                return ids
            continue
        m = re.match(r"^\s*%s[.):]?\s+(.*)$" % re.escape(want), line)
        if m:
            ids, _ = parse_gates_field(m.group(1))
            if ids:
                return ids
    return []


class _Cancelled(Exception):
    pass


FILE_RULES = """

OUTPUT PROTOCOL — MANDATORY:
Every file you produce must appear in your reply as:

<<<FILE: plans/<slug>/<name>.md>>>
<complete file content>
<<<END>>>

Rules:
- Paths must stay inside plans/<slug>/ of the repo.
- Emit complete files — never diffs or placeholders.
- Anything outside <<<FILE>>> blocks is treated as notes for the log.
- Notes outside blocks: at most 10 lines, terse.
- Do NOT invent facts to fill gaps — leave sections empty instead.
"""
RETRY_NOTE = ("\n\nYour previous reply had no valid <<<FILE>>> blocks. "
              "Re-answer, outputting every file in the mandated format.")

# v2.6.3 — the one-line description of the NEWEST command-file change,
# shown in the auto-update dialog. Bump this together with the command
# files so the dialog text never goes stale.
COMMAND_UPDATE_NOTE = ("session.md spells out the canonical PROGRESS.md "
                       "line with a worked example — gates report "
                       "cleanly in Plan health")


def parse_files(text, slug):
    """(files, notes) from an agent reply: every <<<FILE: …>>> block
    with the path guard applied — only paths INSIDE plans/<slug>/
    (no '..', no backslashes, no absolute paths) are returned for
    writing; everything else lands in the notes as ignored. Module
    level since v2.6.3 so the guard is unit-testable without Tk."""
    files, notes, cur = [], [], None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("<<<FILE:") and s.endswith(">>>"):
            cur = (s[len("<<<FILE:"):-3].strip(), [])
        elif s == "<<<END>>>" and cur:
            path, body = cur
            if (path.startswith("plans/%s/" % slug) and ".." not in path
                    and "\\" not in path and not path.startswith("/")):
                files.append((path, "\n".join(body).rstrip() + "\n"))
            else:
                notes.append("(ignored bad path: %s)" % path)
            cur = None
        elif cur is not None:
            cur[1].append(line)
        else:
            notes.append(line)
    return files, "\n".join(notes)

# ----------------------------------------------------------------------------
# v2.3 — standing orders for execution agents (attached to session
# instructions). Deliberately OUTSIDE STARTER_FILES: "Update command
# files" overwrites anything that differs from the built-ins, which
# would destroy user customizations. Precedence when loading:
#   1. <repo>/AGENT-ORDERS.md   (per-repo override — wins for that repo)
#   2. AGENT-ORDERS.md here     (app-level, user-editable, auto-created
#                                from the default below on first use,
#                                then NEVER auto-overwritten again)
# A file that is empty or contains only "OFF" disables the orders for
# everything it governs. Init / Update-command-files never touch these.
# ----------------------------------------------------------------------------
AGENT_ORDERS_NAME = "AGENT-ORDERS.md"
AGENT_ORDERS_DEFAULT = """# AGENT-ORDERS.md

STANDING ORDERS — EXECUTION AGENT (permanent; paste after global
configuration, before every session block given to this agent. Where
stricter than global config, this block wins.)

## WHO YOU ARE

You are a software execution agent. You are tasked with implementing,
remediating, and maintaining systems according to explicit
specifications. Your work is expected to be verifiable, strictly
scoped, and free of regressions. These orders establish permanent
constraints to ensure high-quality, auditable execution. Future audits
should find nothing.

## FAILURE MODES TO AVOID (permanent context — never repeat)

FM1 Silent spec deviation — implementing different semantics than the
spec and telling no one.
FM2 Unauthorized payload change — deleting or modifying data/fields
under an explicit "change NOTHING else."
FM3 Dead references shipped — inventing keys, IDs, or variables present
in none of the required target files.
FM4 Transcribed a spec sketch's flaws verbatim instead of implementing
its intent.
FM5 Misreported your own work — progress reports contradicting your own
change list.
FM6 Dead speculative code — introducing unused variables, exports, or
future-proofing structures.
FM7 Skipped a required gate — failing to run tests, linters, or build
checks.

## THE CONTRACT

C1 Deviations are never silent. If a spec seems wrong or ambiguous:
follow it as written and file ADJUDICATION-REQUESTED in the session
notes, or BLOCKED.md if proceeding is unsafe. You never substitute your
own version. FM1 is unforgivable twice.
C2 Every change is diffable. After each change, paste the git diff or
grep proving the delta equals exactly what was authorized. No paste =
not done.
C3 Sketches are intent, not gospel. Copying an obvious flaw is failure;
"improving" beyond scope is failure. Correct move: implement intent,
log flaws as OBSERVED-NOT-FIXED.
C4 No orphaned references. New keys, strings, or fields require entries
in ALL applicable target files (e.g., locale files, schemas, database
migrations) in the same session. If a session's scope forbids touching
those files, that session ships ZERO new references. Dead keys and dead
fields are banned.
C5 Gates always run, always pasted. Run the project's standard
type-checker, linter, and test suite. Plus any session-specific
harnesses. Paste actual output.
C6 Reports are verifiable or marked UNVERIFIED-OWNER. Every claim
carries the command that proves it. A false progress line on record
ends your tenure on this project.
C7 Scope is law. The session block lists authorized files; anything
else voids the session. Out-of-scope observations get one-line
OBSERVED-NOT-FIXED entries. "Harmless" unrequested edits are still
violations.
C8 Nothing speculative. No dead exports, no future-proofing, no unused
anything.

## ESCALATION LADDER — your only three escape valves; guessing is not one:

ADJUDICATION-REQUESTED   spec doubt; proceed as written, flag it
OBSERVED-NOT-FIXED       out-of-scope issue; one line, move on
BLOCKED.md               failed verification (one retry) or missing
                         access, with the exact owner command/SQL

## OUTPUT SHAPE

Change table with file:line · pasted gate outputs · pasted scope diff ·
proof for every verifiable claim · no narrative, no conclusions. One
pass, gates, stop.

## ENV FACTS

Session specs dictate the authorized files and scope. Refer to the
project's standard build, lint, and test commands. Global agent
configuration governs everything not restated here.
"""

# ----------------------------------------------------------------------------
# Starter repo files (created by "Init starter repo" — never overwrite existing)
# ----------------------------------------------------------------------------
STARTER_FILES = {
"PART-00.md": """PART 00 — SESSION PROTOCOL (universal; loaded every session)
Version 1.1 — Owner-only edits, version bump required. PROGRESS.md records
the version executed. This file contains PROCESS rules only. All project
facts live in the plan's frozen PART-01 file (e.g. "PART-01 v1.0.md").

SESSION MECHANICS
- One session = one numbered unit of work, executed to completion.
- Only session(s) named in PART-01 §A may deploy or touch production.
- Never modify/rename/delete assets in PART-01 §A "legacy inventory"
  unless this session is explicitly scoped to do so.
- End every session: append ONE line to PROGRESS.md, canonical form:
  SESSION <n> | <YYYY-MM-DD> | gates: <passed gN ids, comma-separated> |
  status: PASS|PARTIAL|FAIL|BLOCKED[ — one-line reason] | P00 v<version>
- A failed verification gets ONE fix attempt. Second failure →
  BLOCKED.md (exact repro + what you tried) and STOP.
- Never resolve ambiguity by guessing. BLOCKED.md is a correct outcome.
- Missing credential/access for a step? Do NOT stall: write the exact
  command/SQL for the owner into BLOCKED.md and continue with everything
  that IS possible.

SOURCE-OF-TRUTH HIERARCHY
1. CODE — request/response shapes verbatim (snake_case stays snake_case).
2. The doc named "source of truth" in PART-01 §F.
3. Other §F artifacts.
Exceptions only where PART-01 §G explicitly overrides.

DEFAULT CONTRACTS (apply unless PART-01 §E overrides)
- Status codes: 400 unknown task/bad input/missing config row; 401 auth;
  402 metering; 500 unexpected; 502 provider exhausted (refund); 503 disabled.
- Metering: cost per invocation from §E. Consume BEFORE external calls;
  402 on insufficient balance; REFUND when the paid operation provably
  failed after consumption.
- Failover: on network error / timeout / 429 / 404 / 5xx → fallback
  provider. Both providers fail → 502 + refund. NO failover after first
  byte of a stream. Timeouts per §E.
- Streaming (only tasks listed in §E): normalized frames on the wire,
  ping comment frames at §E cadence, metering consumed before the stream
  opens.
- Runtime model policy in §E governs configured provider/model VALUES,
  not which coding agent executes sessions.
- Provider quirks (JSON-mode syntax, auth-header handling, capability
  limits) come from §G — never assume them.

PART-01 COMPLETENESS (hard gate)
The frozen PART-01 file ("PART-01 v1.0.md" — or a legacy PART-01.md with
a freeze header) must define sections A–F (G optional if empty). If a
section missing, stale-dated, or contradictory affects this session →
BLOCKED.md citing the section. The agent NEVER invents project facts.

ECONOMY RULES
- Be terse. Artifacts and verification output only. No prose about what
you're about to do, no concluding essays.
- Targeted reads: grep to locate, then read only needed line ranges.
  Never re-read content already extracted into plan artifacts.
- Never echo PART-00, PART-01, or large files — reference by path/section.
- One pass: do the work, run the gates, stop. No unsolicited review or
  refactoring outside session scope.
""",

"templates/PART-01.md": """PART 01 — PROJECT CONTEXT: <plan-slug>
Owner-maintained. Freeze as "PART-01 v1.0" (file "PART-01 v1.0.md",
written by the Plan Console "Freeze" button) before Session 1; edits
require a version bump + owner approval. Sections A–F mandatory; G
recommended.

A. MISSION & SCOPE
   Mission: <one paragraph>
   Session budget: <N> sessions.
   Session map (gates column: use stable ids — "g1: pytest green, g2: parity vs RECON §4"):
     # | one-line scope | gates | deploy?
     1 | ...            | ...   | no
     ... (last = deploy session, owner-supervised unless §G overrides)
   Legacy inventory: <existing assets that stay frozen — paths, URLs, names>
   Out of scope: <explicit non-goals>

B. VERIFIED INFRASTRUCTURE FACTS   (every line: fact — verified YYYY-MM-DD)
   Hosts, versions, endpoints, auth schemes, env vars, hardware limits,
   capability constraints (e.g. "model X has no vision — date").

C. TARGET STRUCTURE
   Final file/function tree, paths only, one line each.

D. ROUTING / CONFIG TABLE   (the ONLY place task→provider→model lives)
   task | primary provider | model | fallback provider | model | cost
   Exact model IDs may live in a §F reference doc (e.g. PROVIDERS.md);
   never duplicated inline anywhere else.

E. BUSINESS RULES   (state only DELTAS from PART-00 defaults)
   Metering: <cost per task; refund semantics>
   Timeouts: <per provider class, e.g. local 90s / cloud 45s>
   Streaming: <which tasks; frame format; ping cadence>
   Runtime model policy: <allow/deny lists for configured VALUES>
   Error-code deltas: <if any>

F. ARTIFACTS MAP
   Source of truth: <path, e.g. RECON.md>
   Agent-appended: PROGRESS.md, BLOCKED.md
   Console-appended (agent never edits): HEALTH.md (Plan-health audit trail)
   Reference docs: <paths>
   Owner-only (agent never touches): <paths, e.g. BUDGET.md>

G. KNOWN QUIRKS & EXCEPTIONS
   Version-specific provider quirks (e.g. JSON-mode string form),
   response-shape exceptions, verbatim-header rules, anything that
   contradicts §C/§D expectations. Deploy-execution overrides
   (agent-executed deploys instead of owner-supervised) belong here.
""",

"commands/new-plan.md": """---
description: Intake a ready-made plan, brainstorm, or audit report into a new plan
argument-hint: <plan|brainstorm|audit> <source-path> <slug>
---
Load PART-00.md and follow its economy rules. INTAKE pass — no code
changes, no deploys, write only inside plans/<slug>/.

Arguments: $ARGUMENTS → parse as TYPE SOURCE SLUG
TYPE: plan | brainstorm | audit. SOURCE: path to the source doc.
SLUG: kebab-case.

1. mkdir plans/SLUG
2. If SOURCE is not already at plans/SLUG/SOURCE.md, copy it there.
   Never overwrite an existing SOURCE.md.
3. Read SOURCE.md fully. Treat every factual claim as UNVERIFIED —
   plans rot, brainstorms speculate, audits go stale.
4. Copy templates/PART-01.md → plans/SLUG/PART-01.draft.md; fill from
   SOURCE per TYPE below.

Question format (MANDATORY — the Plan Console counts and archives
whole blocks): every question in OPEN-QUESTIONS.md is a THREE-LINE
block, exactly this shape:

1. PROBLEM: <one sentence — the gap, contradiction or risk that
   raises the question>
   QUESTION: <the decision needed, phrased as a question>?
   RECOMMEND: <one line — the recommended answer, and why>

Format rules: the PROBLEM line carries the number ("1.", "2." …) and
never ends with '?'; the QUESTION line ends with '?' and is never
numbered; the RECOMMEND line never ends with '?'; separate blocks
with one blank line; never split a part across lines. The owner's
ANSWER stays one line. Commands/SQL/owner actions NEVER appear among
questions — they live only under a "## Owner actions" heading at the
end. Prose summaries and resolution notes go under '#' comment lines
(the console ignores those).

TYPE=plan (a ready-made, already-structured plan):
- Normalize the plan into the template §A–G structure: map its own
  sections onto the template sections (mission/scope → §A, stated
  facts → §B, target structure → §C, config/routing → §D, business
  rules → §E, references → §F, quirks/exceptions → §G). Never discard
  content that has no clean home — place it in the closest section or
  §G. The template's structure WINS; the plan's CONTENT wins.
- If the plan contains a phase/session/work breakdown: convert it into
  the §A session map table with gN gate ids and a deploy column (last
  session = deploy, owner-supervised unless §G overrides). If it has
  none: propose a session map from its work items, marked PROPOSED.
- RECON-CHECKLIST.md — every claim the plan depends on (versions,
  paths, env vars, dependencies, commands): `- [ ]` items; use the
  `EXISTS: <repo-relative path>` form for pure file/dir existence
  checks. Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — gaps only the owner can settle: missing
  sections, undated facts, work items without a clear gate, scope
  decisions. Three-line blocks per the question-format rule above.
- No TRIAGE.md (nothing to triage in a plan).

TYPE=brainstorm also produces:
- RECON-CHECKLIST.md — one item per UNVERIFIED §B fact, rendered as
  `- [ ]` checkbox lines: check | where to run | expected shape (use
  `EXISTS:` form for pure file/dir existence checks).
  Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — max 10, each answerable by the owner in one
  line, as three-line blocks per the question-format rule above.
- §A session map marked PROPOSED (dependencies ordered, deploy last).
  Use gN gate ids in the gates column.

TYPE=audit also produces:
- TRIAGE.md — every finding gets an ID (A1…) and verdict
  FIX-IN-PLAN | DEFER | ACCEPT with a one-line reason.
- RECON-CHECKLIST.md — re-verification checks ONLY for evidence sessions
  depend on (existence, line numbers, config rows), as `- [ ]` lines
  (use `EXISTS:` form for pure file/dir existence checks).
  Order: blocks Session 1 first.
- OPEN-QUESTIONS.md — triage disputes the owner must settle, one
  three-line block each per the question-format rule above.
- §A session map groups FIX-IN-PLAN findings into coherent deployable
  sessions; each session line lists its finding IDs. Use gN gate ids.

Never invent facts to fill gaps — gaps stay blank and surface in
OPEN-QUESTIONS.md. Emit every file you created.

Next: commands/recon.md <slug> — verify the draft's claims; then the
owner answers OPEN-QUESTIONS.md in the console Owner pass tab.
""",

"commands/owner-resolve.md": """---
description: Integrate owner answers, finish agent-runnable recon, sharpen
             unclear questions (never answer them)
argument-hint: <slug>
---
Arguments: $ARGUMENTS → SLUG

Load PART-00.md. Work only inside plans/SLUG/.

Inputs:
- plans/SLUG/PART-01.draft.md — the section "## OWNER ANSWERS" holds Q/A
  pairs supplied by the owner. Owner answers are AUTHORITATIVE FACTS.
  If a Q's text is a three-line block (PROBLEM/QUESTION/RECOMMEND),
  its RECOMMEND line is the agent's earlier suggestion — context
  only, NEVER an owner answer; integrate only the owner's answer.
- plans/SLUG/OPEN-QUESTIONS.md — questions still awaiting the owner.
- plans/SLUG/RECON-CHECKLIST.md — `- [ ]` / `- [x]` items.

Execute in order:

1. INTEGRATE OWNER ANSWERS. For each Q/A pair under ## OWNER ANSWERS:
   - Move the answer's content into the correct draft section: scope or
     session-map decisions → §A; checkable facts → §B (mark
     "VERIFIED <today> — owner-confirmed" ONLY if the answer asserts a
     concrete fact); structure → §C; routing/config → §D; business
     rules → §E; artifact references → §F; quirks/exceptions → §G.
   - After integrating a pair, remove it from ## OWNER ANSWERS.
   - If an answer is ambiguous, incomplete, or contradicts the draft:
     do NOT guess its meaning. Add a NEW question to OPEN-QUESTIONS.md
     asking precisely what is unclear (quote the answer, state what
     decision is needed), and leave that pair in ## OWNER ANSWERS
     marked "NEEDS CLARIFICATION".

2. SHARPEN REMAINING QUESTIONS. For every item in OPEN-QUESTIONS.md the
   owner has not answered: if the question is vague or answerable in
   several ways, rewrite it to be concrete and one-line-answerable
   (what decision, what format, which options). You may NOT answer any
   question yourself — rewording is allowed, answering is not.
   Rewritten questions MUST keep the three-line block form
   (1. PROBLEM: … / QUESTION: …? / RECOMMEND: …); sharpen the PROBLEM
   and RECOMMEND lines too — the RECOMMEND stays a suggestion, not an
   answer. Legacy one-line questions you rewrite must be converted to
   the block form. Resolution summaries and owner commands/SQL go
   under "## Owner actions" or '#' comment lines — never as loose
   prose (the Plan Console counts one numbered block per question,
   plus legacy '?'-ending one-liners, outside "## Owner actions" and
   code fences; loose prose would break its counter).

3. FINISH AGENT-RUNNABLE RECON. Execute every RECON-CHECKLIST.md item
   you can verify locally (file/dir existence, grep, reading
   code/config, counts). Tick `- [x]` and record the actual output.
   Promote matching §B draft lines to VERIFIED <today> where the check
   passed. Failures stay `- [ ]` with a note. OWNER-ONLY items (need
   credentials/DB/dashboards/SSH): never run, never stall — ensure the
   exact command/SQL for each is listed under "## Owner actions" in
   OPEN-QUESTIONS.md.

4. Emit every file you changed (PART-01.draft.md, OPEN-QUESTIONS.md,
   RECON-CHECKLIST.md — full files). End your notes with exactly one
   line: answers integrated X / need clarification Y / questions
   sharpened Z / checklist ticked W / owner-only V.

Next: commands/validate-plan.md <slug> — validation is the step after
integration; Freeze only unlocks on "PART-01 READY".
""",

"commands/recon.md": """---
description: Run the agent-runnable items of a plan's RECON-CHECKLIST
argument-hint: <slug>
---
Load PART-00.md. Read plans/$ARGUMENTS/RECON-CHECKLIST.md first.

Classify each item:
- AGENT-RUNNABLE: file/dir existence, grep, reading code/config, counts
- OWNER-ONLY: anything needing credentials, DB, dashboards, SSH, live
  external calls

Pure file/directory existence checks: emit them in the exact form
`- [ ] EXISTS: <repo-relative path>` — the Plan Console Owner-pass tab
can auto-verify and tick those in local Python.

Execute every AGENT-RUNNABLE item; record actual output next to it and
tick it `- [x]`. Promote matching PART-01.draft.md §B lines to
VERIFIED <today> ONLY where the check passed. Failures stay UNVERIFIED
with a note.

OWNER-ONLY items: append exact commands/SQL to OPEN-QUESTIONS.md under
"## Owner actions" — do not stall on them.

Emit every file you changed (RECON-CHECKLIST.md, PART-01.draft.md,
OPEN-QUESTIONS.md if touched). End with one line in your notes:
verified X / pending-owner Y / failed Z.

Next: the owner answers OPEN-QUESTIONS.md in the Plan Console Owner
pass tab (answers land in PART-01.draft.md ## OWNER ANSWERS — a
TEMPORARY inbox), then commands/owner-resolve.md <slug> integrates
them into the draft.
""",

"commands/validate-plan.md": """---
description: Pre-freeze gap report for a plan
argument-hint: <slug>
---
Load PART-00.md. Validate plans/$ARGUMENTS/PART-01.draft.md (or the
frozen "PART-01 v1.0.md" / legacy PART-01.md if no draft) against
templates/PART-01.md. Check ONLY:
- missing mandatory sections (A–F)
- §B lines lacking verification dates
- provider/model IDs appearing outside §D
- contradictions: §D vs §G, §E vs PART-00 defaults, §A map vs §C tree
- session-map gaps: sessions without gates, deploy not last, gates
  lacking gN ids
- unanswered questions in OPEN-QUESTIONS.md (open = numbered question
  blocks, counted once per block, or legacy '?'-ending one-liners,
  outside "## Owner actions" and code fences — the Plan Console counts
  the same way)
- unresolved `- [ ]` items in RECON-CHECKLIST.md (owner-marked DEFERRED
  items count as resolved)
- leftover Q/A pairs in "## OWNER ANSWERS" (integrated or marked
  NEEDS CLARIFICATION only)

Write the findings to plans/$ARGUMENTS/VALIDATION.md (one line per
finding, overwrite previous). Each finding line MUST end with the
remediation as the exact next command to run, e.g. "→ run
owner-resolve <slug>" or "→ fix in the draft, then re-validate" —
findings read as instructions, never as puzzles. If none: write
exactly "PART-01 READY". Findings only — no fixes, no rewrites.

Next: "PART-01 READY" → commands/freeze-plan.md <slug> (or the
console Freeze button); otherwise fix the findings and re-run this
command before Freezing.
""",

"commands/freeze-plan.md": """---
description: Promote a validated draft to frozen PART-01 v1.0
          (agent fallback — the Plan Console "Freeze" button does this
          automatically and is the normal path)
argument-hint: <slug>
---
Load PART-00.md. Target: plans/$ARGUMENTS/

Preconditions (stop and report if any fail — never auto-resolve):
1. PART-01.draft.md exists and no "PART-01 v*.md" is present yet
2. OPEN-QUESTIONS.md has no open questions (numbered question blocks,
   counted once per block, or legacy '?'-ending one-liners, outside
   "## Owner actions" and code fences; the console counts the same way)
3. RECON-CHECKLIST.md has no unresolved `- [ ]` items (or
   owner-marked DEFERRED)
4. plans/SLUG/VALIDATION.md says "PART-01 READY" (run
   commands/validate-plan.md if missing)

If all pass:
- Write "PART-01 v1.0.md" = draft + header "PART 01 — <slug> | v1.0
  frozen <date>" (the version lives IN the filename)
- Keep the draft as history; create PROGRESS.md with header
  "# PROGRESS — <slug> | PART-01 v1.0 | <date>"
- Report "FROZEN v1.0 — N sessions mapped, deploy = session N"

Next: commands/session.md <slug> 1 — sessions execute against the
frozen file, in §A order.
""",

"commands/session.md": """---
description: Execute a numbered session of a plan
argument-hint: <slug> <session-number>
---
Arguments: $ARGUMENTS → SLUG N

Load: PART-00.md → the frozen plan in plans/SLUG/ ("PART-01 v1.0.md",
or whichever "PART-01 v*.md" exists; a legacy PART-01.md with a freeze
header is also valid — drafts are NOT executable) →
plans/SLUG/PROGRESS.md → plans/SLUG/RECON.md only if this session
needs it.

Guards (stop if any fail):
- the frozen PART-01 file exists (see naming above)
- PROGRESS.md shows sessions 1..N-1 complete
- N exists in the §A session map

IN-PROGRESS HANDSHAKE (interruption safety — binding):
START, before any work:
- If plans/SLUG/IN-PROGRESS.md exists:
  * If PROGRESS.md already shows this session complete, the marker is
    stale — delete it and proceed normally.
  * Otherwise a previous run was interrupted: read IN-PROGRESS.md
    fully, run `git status` and `git diff`, and RECONCILE — keep and
    finish work that is correct, cleanly revert work that is wrong.
    Never redo blindly, never guess.
- Write plans/SLUG/IN-PROGRESS.md exactly:
  IN PROGRESS — session <N> | started <YYYY-MM-DD> | scope: <§A row>
  worktree at start: <git status --porcelain output, or "clean">
- Then do the session work.
STOPPING WITHOUT FINISHING (owner needed, context exhausted, blocked):
- Append one line to IN-PROGRESS.md: "stopped <date> — <reason; what
  remains>". Write BLOCKED.md if the BLOCKED protocol applies. Stop.
END, after gates pass:
- Append the canonical PROGRESS.md line FIRST, THEN delete
  IN-PROGRESS.md. (If interrupted between the two, the next run sees
  both — PROGRESS.md wins; delete the stale marker.)

Scope and gates come from §A session N. If N is a deploy session:
owner-supervised; gates before AND after deploy; never proceed past a
failed post-deploy gate. EXCEPTION: if PART-01 §G explicitly assigns
deploys to the agent (e.g. authenticated Supabase CLI in the agent's
environment), the agent may execute them itself — still with gates
before and after, and ordering constraints from §G.

BLOCKED PROTOCOL (restated from PART-00 — binding):
- A failed verification gets ONE fix attempt. If the second attempt
  also fails: write plans/SLUG/BLOCKED.md containing (a) exact
  reproduction steps, (b) what you tried and what failed, (c) what you
  need from the owner (command, credential, decision) — then STOP.
  Do NOT guess around it. BLOCKED.md is a correct outcome, not a
  failure of the session.
- If BLOCKED.md already exists at session start, read it first — it is
  the record of the previous stop; resolve or ask before redoing work.
- When blocked, still append the canonical PROGRESS line with
  status: BLOCKED — one-line reason.
- RESOLUTION: when the owner fixes the cause and the session re-runs
  to PASS, close the incident by appending one line to BLOCKED.md
  ("resolved <YYYY-MM-DD> — <how it was fixed>") and RENAMING the file
  to BLOCKED-resolved.md. NEVER delete BLOCKED.md — it is the audit
  record of the failure and its fix. The Plan Console flags "blocked"
  while the file exists and clears it on the rename; the file
  BLOCKED-resolved.md triggers nothing.

Close by appending exactly ONE canonical PROGRESS.md line (format per
PART-00 SESSION MECHANICS):
SESSION N | YYYY-MM-DD | gates: <passed gN ids> | status: PASS|PARTIAL|FAIL|BLOCKED — reason | P00 v<version>
Worked example (fill in your values):
SESSION 3 | 2025-06-01 | gates: g1, g2 | status: PASS | P00 v1.1
The Plan Console reads this line to report gates in Plan health, so
keep it strictly canonical: ONE physical line; lowercase 'gates:' and
'status:' labels with colons; gate ids in gN form ('g1, g2') — never
bare numbers, never 'all'; list ONLY the gates that passed (a PARTIAL
line lists the passed subset; the reason field explains the rest). The
console parses leniently and flags non-canonical lines, but canonical
is what reports cleanly. Gate IDs come from PART-01 §A session N.
Execute per PART-00. Stop after gates pass and the PROGRESS line is
appended.

Next: the next session number (Plan health shows it), or
commands/plan-status.md <slug> after the last session.
""",

"commands/plan-status.md": """---
description: Report what a plan needs next
argument-hint: <slug>
---
Read plans/$ARGUMENTS/ only. Report in ≤6 lines:
- stage: intake | recon | owner-pass (answers → owner-resolve
  integration) | validation | frozen | in-progress | done
- last PROGRESS.md line
- interrupted: IN-PROGRESS.md exists → re-run the session command (it resumes)
- blockers: unanswered questions, owner answers not yet integrated
  (## OWNER ANSWERS in PART-01.draft.md), unresolved recon items
- next action as the exact command to run
No fixes, no rewrites.
""",

}
class App:
    def __init__(self, root):
        self.root, self.q = root, queue.Queue()
        self.logs, self.status = {}, {}
        self.cfg = self._load_cfg()
        self._cancel_events = set()   # live cancel Events, one per API call
        self._cancel_lock = threading.Lock()
        self._n_busy = 0
        self._cmd_checked = set()   # v2.2 — repos already auto-checked
        # v3.0 — theme: persisted setting ("light"|"dark"|"system", §E)
        # + effective token set for creation-time widget colors
        self.theme_setting = (self.cfg["theme"]
                              if self.cfg.get("theme") in THEME_SETTINGS
                              else "system")
        self._theme_effective = (self.theme_setting
                                 if self.theme_setting != "system"
                                 else _detect_os_theme())
        self._tokens = (None if _high_contrast_active()
                        else THEMES[self._theme_effective])
        self.style = ttk.Style(root)
        root.title("Plan Console")
        # v3.1 — resizable window, size remembered in cfg, minsize 820x600
        # (below that the three-tab layout clips — PART-01 §C)
        try:
            geo = "%dx%d" % (int(self.cfg.get("win_w", 1020)),
                             int(self.cfg.get("win_h", 800)))
        except (TypeError, ValueError):
            geo = "1020x800"
        root.geometry(geo)
        root.minsize(820, 600)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._topbar()
        self._tabs()
        self._apply_theme_setting()
        self._fetch_models()
        root.after(100, self._drain)
        # v2.2 — started repos: offer new command-file protocols at startup
        root.after(400, self._auto_command_check)

    @staticmethod
    def _load_cfg():
        """plan-console.json → dict. A corrupt or undecodable file is
        backed up as plan-console.json.corrupt and settings restart
        empty, instead of crashing the app at startup."""
        if not CFG.exists():
            return {}
        try:
            return json.loads(CFG.read_text(encoding="utf-8"))
        except Exception:
            try:
                CFG.replace(CFG.with_name("plan-console.json.corrupt"))
            except Exception:
                pass
            return {}

    def on_close(self):
        """v3.1 — WM_DELETE_WINDOW handler: remember the window size in
        cfg (PART-01 §C), then close."""
        self.cfg["win_w"] = max(820, self.root.winfo_width())
        self.cfg["win_h"] = max(600, self.root.winfo_height())
        self._save_cfg()
        self.root.destroy()

    # ------------------------------------------------------------------ UI
    def _topbar(self):
        top = ttk.Frame(self.root); top.pack(fill="x", padx=10, pady=(6, 0))
        top.columnconfigure(1, weight=1)
        # Row 0: repo folder
        ttk.Label(top, text="Repo folder").grid(row=0, column=0, sticky="w")
        self.repo = ttk.Entry(top)
        self.repo.insert(0, self.cfg.get("repo", str(Path.cwd())))
        self.repo.grid(row=0, column=1, sticky="we", padx=4)
        ttk.Button(top, text="Browse…", command=self._browse_repo)\
            .grid(row=0, column=2, padx=(4, 0))
        ttk.Button(top, text="Init starter repo",
                   command=self.on_init_repo).grid(row=0, column=3, padx=(12, 4))
        ttk.Button(top, text="Update command files",
                   command=self.on_update_commands).grid(row=0, column=4,
                                                         padx=(4, 0))
        # Row 1: model picker + its own reload button
        ttk.Label(top, text="OpenRouter model").grid(row=1, column=0, sticky="w",
                                                     pady=(6, 0))
        self.model_cb = ttk.Combobox(top, width=36, state="normal")
        self._all_models = list(self.cfg.get("favorites", []))
        self.model_cb["values"] = self._all_models
        if self.cfg.get("model"):
            self.model_cb.set(self.cfg["model"])
        self.model_cb.grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        self.model_cb.bind("<KeyRelease>", self._filter_models)
        self.model_cb.bind("<<ComboboxSelected>>", self._on_model_picked)
        self.model_cb.bind("<Return>", self._on_model_picked)
        self.model_cb.bind("<FocusOut>", self._on_model_picked)
        ttk.Button(top, text="Reload models",
                   command=self._fetch_models)\
            .grid(row=1, column=2, padx=(16, 0), pady=(6, 0))
        # v2.3 — edit the standing orders attached to session instructions
        ttk.Button(top, text="Agent orders…",
                   command=self.on_edit_agent_orders)\
            .grid(row=1, column=3, padx=(8, 0), pady=(6, 0))
        # Row 2: API key + use-key checkbox
        ttk.Label(top, text="API key (optional)").grid(row=2, column=0, sticky="w",
                                                       pady=(6, 0))
        self.key = ttk.Entry(top, show="*", width=34)
        # security: the key is never restored from plan-console.json —
        # session-only field, or the OPENROUTER_API_KEY env variable
        self.key.insert(0, os.environ.get("OPENROUTER_API_KEY", ""))
        self.key.grid(row=2, column=1, sticky="w", padx=4, pady=(6, 0))
        self.use_key = tk.BooleanVar(value=self.cfg.get("use_key", False))
        # Row 3: hint under the key field + PDF link (visible when unchecked)
        self._key_hint = ttk.Label(
            top, text="Works faster WITHOUT a key — the console hands "
                      "ready-made instructions to your agent instead.",
            wraplength=680, justify="left")
        self._key_hint.grid(row=3, column=1, sticky="w", padx=4)
        self._pdf_link = ttk.Label(
            top, text="How to use without a key (PDF guide) »",
            cursor="hand2")
        self._pdf_link.grid(row=3, column=2, padx=(16, 0))
        self._pdf_link.bind("<Button-1>", lambda _e: self._open_nokey_pdf())

        def _toggle_key():
            # checked = API mode → key field editable, link hidden;
            # unchecked = paste mode → key field grayed, PDF link shown
            self.key.configure(state="normal" if self.use_key.get()
                               else "disabled")
            if self.use_key.get():
                self._pdf_link.grid_remove()
            else:
                self._pdf_link.grid()

        ttk.Checkbutton(top, text="Use API key",
                        variable=self.use_key,
                        command=_toggle_key)\
            .grid(row=2, column=2, sticky="w", padx=(16, 0), pady=(6, 0))
        _toggle_key()      # apply saved state right now (startup)
        # Row 4: live progress + cancel
        self.prog = ttk.Label(top, text="")
        self.prog.grid(row=4, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Button(top, text="Cancel API call",
                   command=self.on_cancel_api)\
            .grid(row=4, column=2, padx=(16, 0), pady=(6, 0))
        # v3.0 — theme selector (Light / Dark / Follow OS), persisted §E
        ttk.Label(top, text="Theme").grid(row=4, column=3, sticky="e",
                                          padx=(16, 4), pady=(6, 0))
        self.theme_var = tk.StringVar(value=THEME_LABELS[self.theme_setting])
        self.theme_cb = ttk.Combobox(top, textvariable=self.theme_var,
                                     values=tuple(THEME_LABELS[s] for s
                                                  in THEME_SETTINGS),
                                     state="readonly", width=10)
        self.theme_cb.grid(row=4, column=4, sticky="w", pady=(6, 0))
        self.theme_cb.bind("<<ComboboxSelected>>", self.on_theme_change)

    # ---------------------------------------------------------- v3.0 theme
    def on_theme_change(self, _event=None):
        """Theme selector callback: resolve the new setting, apply it to
        the whole app, and persist the raw setting in plan-console.json
        (PART-01 §E)."""
        self.theme_setting = THEME_SETTING_BY_LABEL.get(
            self.theme_cb.get(), "system")
        self._apply_theme_setting()
        self.cfg["theme"] = self.theme_setting
        self._save_cfg()

    def _apply_theme_setting(self):
        """Apply the current theme setting to the whole app (no
        persistence — on_theme_change persists)."""
        self._theme_effective = (self.theme_setting
                                 if self.theme_setting != "system"
                                 else _detect_os_theme())
        applied = apply_theme(self.root, self.style, self._theme_effective)
        self._tokens = THEMES[self._theme_effective] if applied else None
        self._tint_labels()

    def _tint_labels(self):
        """Re-color the token-driven labels (hints, link, full-question
        text) for the current effective theme. No-op when high-contrast
        mode is active — never fight the OS (§G)."""
        t = self._tokens
        if not t:
            return
        for w in (self._key_hint, self._flow_hint, self._agent_hint):
            w.configure(foreground=t["text-muted"])
        self._pdf_link.configure(foreground=t["accent-cyan"])
        self.q_full.configure(foreground=t["text-main"])

    @staticmethod
    def _open_path(path):
        """Open a file with the OS default app (Windows startfile, with
        macOS/Linux fallback). True on success, False on failure."""
        try:
            os.startfile(str(path))            # Windows
            return True
        except AttributeError:                 # non-Windows fallback
            import platform
            opener = "open" if platform.system() == "Darwin" else "xdg-open"
            subprocess.Popen([opener, str(path)])
            return True
        except Exception:
            return False

    def _open_nokey_pdf(self):
        """Open the 'how to use without a key' PDF next to the app."""
        pdf = HERE / "no-api-key-guide.pdf"
        if not pdf.is_file():
            messagebox.showinfo("Guide not found",
                "Expected:\n%s\n\nExport the guide as a PDF with exactly "
                "this name, in the same folder as plan-console.py." % pdf)
            return
        if not self._open_path(pdf):
            messagebox.showinfo("Guide", "Open manually:\n%s" % pdf)

    # --------------------------------------------- v2.3 standing orders
    def _agent_orders(self, repo=None):
        """The active standing-orders text ("" = disabled).

        Precedence — the first existing file wins, content verbatim:
        1. <repo>/AGENT-ORDERS.md  (per-repo override)
        2. AGENT-ORDERS.md next to this script (app-level, user-editable)
        3. the built-in default — materialized as the app-level file on
           first use, so future customizations edit a real file.
        A file that is empty or contains only 'OFF' disables the orders
        for everything it governs (that repo, or all repos). Never
        written by Init / Update-command-files — created here, once,
        only when absent."""
        cands = []
        if repo is not None:
            cands.append(Path(repo) / AGENT_ORDERS_NAME)
        cands.append(HERE / AGENT_ORDERS_NAME)
        for f in cands:
            if f.is_file():
                body = f.read_text(encoding="utf-8").strip()
                if body and body.upper() != "OFF":
                    return body
                return ""          # explicit OFF / empty → disabled
        sidecar = HERE / AGENT_ORDERS_NAME
        try:
            sidecar.write_text(AGENT_ORDERS_DEFAULT, encoding="utf-8")
        except Exception:
            pass                   # read-only location → default in memory
        return AGENT_ORDERS_DEFAULT.strip()

    def on_edit_agent_orders(self):
        """v2.3 — open the ACTIVE AGENT-ORDERS.md for editing: the
        per-repo override if present, else the app-level file next to
        the script (created from the built-in default when missing).
        Edits apply to the NEXT session instruction you copy; nothing
        is ever overwritten automatically afterwards."""
        repo = self.repo_path()
        f = repo / AGENT_ORDERS_NAME
        which = "per-repo override — wins for this repo only"
        if not f.is_file():
            f = HERE / AGENT_ORDERS_NAME
            which = "app-level — applies to every repo"
            if not f.is_file():
                try:
                    f.write_text(AGENT_ORDERS_DEFAULT, encoding="utf-8")
                except Exception:
                    pass
        if not self._open_path(f):
            messagebox.showinfo("Agent orders", "Open manually:\n%s" % f)
            return
        self.say("intake", "agent orders: editing %s (%s). Set the content "
                 "to just 'OFF' (or empty) to disable; delete the repo file "
                 "to fall back to the app-level file. Changes apply to the "
                 "next session instruction you copy." % (f, which))

    def _tabs(self):
        nb = ttk.Notebook(self.root); nb.pack(fill="both", expand=True,
                                              pady=(2, 6))
        f1, f2, f3 = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        self._intake_tab(f1); self._session_tab(f2); self._owner_tab(f3)
        nb.add(f1, text="Intake"); nb.add(f2, text="Sessions")
        nb.add(f3, text="Owner pass")

    def _mklog(self, parent, name, height):
        st = ttk.Label(parent, text="idle", style="Pill.TLabel")
        st.pack(anchor="w", padx=10, pady=(4, 0))
        t = self._tokens
        log_kw = ({"bg": t["bg-card"], "fg": t["text-main"],
                   "insertbackground": t["text-main"]} if t else {})
        log = scrolledtext.ScrolledText(parent, height=height, wrap="word",
                                        state="disabled", **log_kw)
        log.pack(fill="both", expand=True, padx=10, pady=(4, 8))
        self.logs[name], self.status[name] = log, st

    def _intake_tab(self, f):
        top = ttk.Frame(f); top.pack(fill="x", padx=10, pady=(6, 0))
        ttk.Label(top, text="Type").grid(row=0, column=0)
        self.kind = ttk.Combobox(top, values=("plan", "brainstorm", "audit"),
                                 state="readonly", width=10)
        self.kind.set(self.cfg.get("kind", "plan"))
        self.kind.grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Slug").grid(row=0, column=2)
        self.slug = ttk.Entry(top, width=20); self.slug.grid(row=0, column=3, padx=4)
        self.auto_recon = tk.BooleanVar(value=False)
        self.auto_validate = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="auto recon",
                        variable=self.auto_recon).grid(row=0, column=4, padx=4)
        ttk.Checkbutton(top, text="auto validate",
                        variable=self.auto_validate).grid(row=0, column=5, padx=4)
        self.btn_proceed = ttk.Button(top, text="Proceed", command=self.on_proceed)
        self.btn_proceed.grid(row=0, column=6, padx=8)
        self.btn_freeze = ttk.Button(top, text="Freeze", command=self.on_freeze)
        self.btn_freeze.grid(row=0, column=7)
        rowb = ttk.Frame(f); rowb.pack(anchor="w", padx=10, pady=(6, 0))
        ttk.Button(rowb, text="Run recon",
                   command=self.on_recon).pack(side="left")
        ttk.Button(rowb, text="Validate draft",
                   command=self.on_validate).pack(side="left", padx=6)
        ttk.Button(rowb, text="Show validation report",
                   command=self.on_show_validation).pack(side="left")
        ttk.Label(f, text="Paste a plan, brainstorm, or audit report below:")\
            .pack(anchor="w", padx=10, pady=(2, 0))
        self.src = scrolledtext.ScrolledText(f, height=8, wrap="word")
        self.src.pack(fill="x", padx=10, pady=4)
        self._mklog(f, "intake", 14)

    def _session_tab(self, f):
        top = ttk.Frame(f); top.pack(fill="x", padx=10, pady=(6, 0))
        ttk.Label(top, text="Slug").grid(row=0, column=0)
        self.sslug = ttk.Entry(top, width=20); self.sslug.grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Session #").grid(row=0, column=2)
        self.snum = ttk.Spinbox(top, from_=1, to=99, width=5)
        self.snum.set("1"); self.snum.grid(row=0, column=3, padx=4)
        self.btn_copy = ttk.Button(top, text="Copy session instruction",
                                   command=self.on_copy_instr)
        self.btn_copy.grid(row=0, column=4, padx=6)
        ttk.Button(top, text="Status", command=self.on_status).grid(row=0, column=5, padx=4)
        ttk.Button(top, text="Session report",
                   command=self.on_report).grid(row=0, column=6, padx=4)
        ttk.Button(top, text="Plan health",
                   command=self.on_health).grid(row=0, column=7, padx=4)
        self._mklog(f, "sessions", 22)

    # ---------------------------------------------------------- owner pass
    def _owner_tab(self, f):
        top = ttk.Frame(f); top.pack(fill="x", padx=10, pady=(6, 0))
        ttk.Label(top, text="Slug").grid(row=0, column=0)
        self.oslug = ttk.Entry(top, width=20)
        self.oslug.grid(row=0, column=1, padx=4)
        ttk.Button(top, text="Refresh",
                   command=self.on_owner_refresh).grid(row=0, column=2, padx=4)
        # v2.6 — P1: read-only dry-run of the Freeze gates, on this tab
        ttk.Button(top, text="What's blocking Freeze?",
                   command=self.on_freeze_dry_run).grid(row=0, column=3, padx=4)
        self.owner_status = ttk.Label(top, text="enter slug and click Refresh",
                                      style="Pill.TLabel")
        self.owner_status.grid(row=0, column=4, padx=10)
        # v2.0 — flow hint so the next step is always visible
        self._flow_hint = ttk.Label(
            f, text="Flow: Refresh → answer every question (saved to "
                    "PART-01.draft.md ## OWNER ANSWERS) → 'Agent: finish "
                    "owner pass' → paste to agent → Refresh → tick recon → "
                    "Validate → Freeze. Nothing you answer or remove is "
                    "ever lost (owner-pass.log + .bak).",
            wraplength=780, justify="left")
        self._flow_hint.pack(anchor="w", padx=10, pady=(2, 0))
        body = ttk.Frame(f); body.pack(fill="both", expand=True, padx=10, pady=6)
        # left: open questions
        lq = ttk.Labelframe(body, text="Open questions — select, type answer below")
        lq.pack(side="left", fill="both", expand=True, padx=(0, 5))
        self.oq_list = tk.Listbox(lq, height=10, activestyle="dotbox")
        self.oq_list.pack(fill="both", expand=True, padx=6, pady=6)
        # v2.0 — full question text above the answer box (no 120-char guesswork)
        self.q_full = ttk.Label(lq, text="(select a question to read it in full)",
                                wraplength=380, justify="left")
        self.q_full.pack(fill="x", padx=6, pady=(4, 0))
        self.oq_list.bind("<<ListboxSelect>>", self._show_full_question)
        self.answer = scrolledtext.ScrolledText(lq, height=3, wrap="word")
        self.answer.pack(fill="x", padx=6)
        barq = ttk.Frame(lq); barq.pack(fill="x", padx=6, pady=6)
        ttk.Button(barq, text="Save answer → draft + remove",
                   command=self.on_answer_save).pack(side="left")
        # v2.5 — one-click accept of the selected block's RECOMMEND line
        ttk.Button(barq, text="Accept recommendation",
                   command=self.on_recommend_accept).pack(side="left", padx=6)
        # v2.1 — archives the WHOLE question block, never just the header
        ttk.Button(barq, text="Archive question (keep log)",
                   command=self.on_question_remove).pack(side="left", padx=6)
        # right: recon checklist
        rc = ttk.Labelframe(body, text="Recon checklist")
        rc.pack(side="left", fill="both", expand=True, padx=(5, 0))
        self.rc_list = tk.Listbox(rc, height=10)
        self.rc_list.pack(fill="both", expand=True, padx=6, pady=6)
        barr = ttk.Frame(rc); barr.pack(fill="x", padx=6, pady=6)
        ttk.Button(barr, text="Tick/untick selected",
                   command=self.on_tick_toggle).pack(side="left")
        ttk.Button(barr, text="Verify EXISTS items",
                   command=self.on_verify_exists).pack(side="left", padx=6)
        # bottom: hand the rest to the agent
        bar2 = ttk.Frame(f); bar2.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Button(bar2, text="Agent: finish owner pass",
                   command=self.on_owner_resolve).pack(side="left")
        self._agent_hint = ttk.Label(
            bar2, text="Answer questions above first — then this hands "
                       "the rest to your agent: it integrates your "
                       "answers, ticks what it can verify locally, and "
                       "rewrites unclear questions instead of guessing.",
            wraplength=680, justify="left")
        self._agent_hint.pack(side="left", padx=8)
        self._oq_items, self._rc_items = [], []
        self._oq_file = self._rc_file = None
        self._oq_text = ""      # v2.1 — raw text for full-block display

    def _owner_paths(self):
        slug = self._get_slug("owner")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Owner pass", "Enter the slug first (kebab-case).")
            return None
        return slug, self.repo_path() / "plans" / slug

    # v2.0 — frozen-plan locator: "PART-01 v*.md" or legacy PART-01.md
    def _frozen_file(self, pdir):
        if not pdir.is_dir():
            return None
        def _vkey(p):
            # numeric version sort — lexicographic would rank v1.10 < v1.2
            m = re.search(r"v(\d+)\.(\d+)", p.name)
            return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
        vers = sorted(pdir.glob("PART-01 v*.md"), key=_vkey)
        if vers:
            return vers[-1]
        legacy = pdir / "PART-01.md"
        if legacy.is_file():
            head = "\n".join(legacy.read_text(encoding="utf-8")
                             .splitlines()[:3]).lower()
            if "frozen" in head:
                return legacy
        return None

    def _in_progress(self, pdir):
        """v2.2 — (path, session_number) of an interrupted session per
        commands/session.md, or (None, None). The marker file lives at
        plans/<slug>/IN-PROGRESS.md while the agent works."""
        f = pdir / "IN-PROGRESS.md"
        if not f.is_file():
            return None, None
        try:
            body = f.read_text(encoding="utf-8")
        except Exception:
            return f, None       # undecodable marker → unreadable, not a crash
        m = re.search(r"(?i)session\s+(\d+)", body)
        return f, (int(m.group(1)) if m else None)

    def on_owner_refresh(self):
        got = self._owner_paths()
        if got is None: return
        slug, pdir = got
        self._oq_items, self._rc_items = [], []
        self._oq_text = ""      # v2.1 — raw text for full-block display
        self._oq_file, self._rc_file = (pdir / "OPEN-QUESTIONS.md",
                                        pdir / "RECON-CHECKLIST.md")
        self.oq_list.delete(0, "end"); self.rc_list.delete(0, "end")
        if hasattr(self, "q_full"):
            self.q_full.configure(text="(select a question to read it in full)")
        if not pdir.is_dir():
            self.owner_status.configure(text="plans/%s not found" % slug)
            return
        if self._oq_file.is_file():
            # v2.1 — keep the raw text so whole blocks can be shown/archived
            self._oq_text = self._oq_file.read_text(encoding="utf-8")
            self._oq_items = parse_questions(self._oq_text)
            for n, (lineno, _line) in enumerate(self._oq_items, 1):
                # list shows the QUESTION: line (the scannable decision);
                # the full block appears below when selected
                self.oq_list.insert("end", "Q%d: %s" % (n, self._q_label(lineno)))
        if self._rc_file.is_file():
            for i, line in enumerate(
                    self._rc_file.read_text(encoding="utf-8").splitlines()):
                state = recon_item_state(line)
                if state:
                    self._rc_items.append((i, line))
                    mark = "[x]" if state == "done" else "[ ]"
                    self.rc_list.insert("end", "%s %s"
                                        % (mark, line.strip().lstrip("- ").strip()[:108]))
        nq = len(self._oq_items)
        # v2.6.1 — same counting as the Freeze gate: real checkbox lines
        # only, DEFERRED counts as resolved (so "ready to Freeze" is true)
        nu = sum(1 for _, l in self._rc_items
                 if recon_item_state(l) == "open"
                 and not is_deferred(l))
        # v2.7 — answers parked in ## OWNER ANSWERS awaiting the
        # owner-resolve integration: the section is a TEMPORARY inbox,
        # not a final home, so the count is surfaced here explicitly
        na = 0
        draft = pdir / "PART-01.draft.md"
        if draft.is_file():
            na = count_owner_answers(draft.read_text(encoding="utf-8"))
        # v2.6.4 — third Freeze gate surfaced here too: the status line
        # checks VALIDATION.md (missing or != "PART-01 READY") so it can
        # never say "ready to Freeze" while the Freeze button would fail
        # on a stale validation report (same condition as _freeze_blockers).
        val = pdir / "VALIDATION.md"
        if not val.is_file():
            vnote = " — VALIDATION.md not found — click 'Validate draft' first"
        elif val.read_text(encoding="utf-8").strip() != "PART-01 READY":
            vnote = " — VALIDATION.md is not 'PART-01 READY' — re-validate"
        else:
            vnote = ""
        # v2.0 — the status line states the NEXT action; v2.7 — answers
        # awaiting integration outrank recon ticks: the owner has
        # answered, but the plan body does not know yet
        if nq:
            hint = " — next: answer questions, then 'Agent: finish owner pass'"
        elif na:
            hint = (" — next: 'Agent: finish owner pass' — integrates %d "
                    "answered question(s) into the draft" % na)
        elif nu:
            hint = " — next: tick recon items"
        elif vnote:
            hint = vnote
        else:
            hint = " — ready to Freeze"
        self.owner_status.configure(
            text=("%d open question(s), %d answer(s) awaiting integration, "
                  "%d unchecked item(s)%s" % (nq, na, nu, hint)))
        if (nq == 0 and na == 0 and nu == 0 and not vnote
                and (self._oq_file.is_file() or self._rc_file.is_file())):
            self.say("intake", "owner pass: everything resolved — Freeze "
                     "is unblocked.")

    def on_answer_save(self, tag="ANSWERED"):
        got = self._owner_paths()
        if got is None: return
        slug, pdir = got
        sel = self.oq_list.curselection()
        if not sel:
            messagebox.showerror("Owner pass", "Select a question first.")
            return
        if not self._oq_file or not self._oq_file.is_file():
            messagebox.showerror("Owner pass", "Click Refresh first.")
            return
        # v2.0 — flatten to ONE line so the Q/A pair stays parseable
        ans = " ".join(self.answer.get("1.0", "end").split())
        if not ans:
            messagebox.showerror("Owner pass",
                                 "Type the answer in the box below the "
                                 "question list.")
            return
        lineno, hdr = self._oq_items[sel[0]]
        qtext = self._oq_file.read_text(encoding="utf-8")
        lines = qtext.splitlines()
        # v2.1 — content-aware stale-index guard (file may have been
        # rewritten by the agent since the last Refresh)
        if (not 0 <= lineno < len(lines)
                or lines[lineno].strip() != hdr.strip()):
            messagebox.showerror("Owner pass",
                                 "OPEN-QUESTIONS.md changed since the last "
                                 "Refresh — click Refresh, re-select and "
                                 "re-answer (nothing was written).")
            return
        # 1) answer goes into the draft (→ frozen PART-01 → sessions see it)
        draft = pdir / "PART-01.draft.md"
        if not draft.is_file():
            # v2.0 — refuse instead of silently dropping the answer
            messagebox.showerror("Owner pass",
                                 "plans/%s/PART-01.draft.md not found — the "
                                 "answer would be lost. Run intake first, "
                                 "then re-answer." % slug)
            return
        # v2.1 — grab the WHOLE question block (problem + question +
        # recommendation), not just its header line
        qlines = [l.strip() for l in question_block(qtext, lineno)
                  .strip().splitlines()]
        text = draft.read_text(encoding="utf-8")
        # v2.2 — crash-window guard: this question already answered in the
        # draft but still listed (a save was interrupted between the two
        # writes) → refuse instead of duplicating the Q/A pair
        marker = "- Q: %s" % qlines[0]
        pos = text.find("## OWNER ANSWERS")
        if pos != -1 and any(l.strip() == marker
                              for l in text[pos:].splitlines()):
            messagebox.showerror("Owner pass",
                "This question is already answered in the draft "
                "(## OWNER ANSWERS in PART-01.draft.md) but is still "
                "listed in OPEN-QUESTIONS.md — a previous save was "
                "interrupted.\n\nUse 'Archive question (keep log)' to "
                "remove the stale listing (the answer stays in the "
                "draft), or edit the draft manually.")
            return
        if "## OWNER ANSWERS" not in text:
            # v2.7 — self-labeling inbox: the header states what the
            # section is and which command empties it, so "answered but
            # not integrated" can never look like a final state
            text = text.rstrip() + (
                "\n\n## OWNER ANSWERS (appended %s — TEMPORARY inbox: "
                "run commands/owner-resolve.md to integrate these "
                "answers into §A–§G, then delete this section)\n"
                % date.today())
        else:
            text = text.rstrip() + "\n"
        # v2.1 — the Q side keeps the full block, so the agent integrating
        # the answer sees the problem and recommendation as context
        text += "- Q: %s\n" % qlines[0]
        for cont in qlines[1:]:
            text += "      %s\n" % cont
        text += "  A: %s\n" % ans
        draft.write_text(text, encoding="utf-8")
        # 2) whole question block removed from OPEN-QUESTIONS.md — archived first
        self._oq_backup()
        self._oq_archive(pdir, tag, "\n".join(qlines), ans)
        end = lineno + len(qlines)
        if end < len(lines) and not lines[end].strip():
            end += 1          # take the block's separator blank line too
        del lines[lineno:end]
        self._oq_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.answer.delete("1.0", "end")
        self.say("intake", "owner pass: answer stored in PART-01.draft.md "
                 "(## OWNER ANSWERS — full question block kept with it); "
                 "question archived to owner-pass.log; snapshot at "
                 "OPEN-QUESTIONS.md.bak")
        self.on_owner_refresh()

    def on_recommend_accept(self):
        """v2.5 — one-click accept: prefill the answer box with the
        block's RECOMMEND line + provenance, then run the normal save
        path — every on_answer_save guard (stale-index, crash-window
        duplicate, draft refusal) applies unchanged. RECOMMEND is
        context only, never an owner answer (PART-01 §G), so this is
        always an explicit, confirmed owner action."""
        got = self._owner_paths()
        if got is None: return
        if not self._oq_file or not self._oq_file.is_file():
            messagebox.showerror("Owner pass", "Click Refresh first.")
            return
        sel = self.oq_list.curselection()
        if not sel:
            messagebox.showerror("Owner pass", "Select a question first.")
            return
        lineno, _hdr = self._oq_items[sel[0]]
        qtext = self._oq_file.read_text(encoding="utf-8")
        rec = recommend_line(qtext, lineno)
        if not rec:
            # legacy one-line questions carry no RECOMMEND → graceful error
            messagebox.showerror("Owner pass",
                                 "This question has no RECOMMEND line — "
                                 "type the answer in the box instead.")
            return
        if not messagebox.askyesno("Owner pass",
                "Accept this recommendation as the answer?\n\n%s"
                % rec[:400]):
            return
        self.answer.delete("1.0", "end")
        self.answer.insert("1.0", "%s [recommendation accepted %s]"
                           % (rec, date.today()))
        self.on_answer_save(tag="ANSWERED (recommendation accepted)")

    def on_question_remove(self):
        got = self._owner_paths()
        if got is None: return
        slug, pdir = got
        sel = self.oq_list.curselection()
        if not sel:
            messagebox.showerror("Owner pass", "Select a question first.")
            return
        if not self._oq_file or not self._oq_file.is_file():
            messagebox.showerror("Owner pass", "Click Refresh first.")
            return
        lineno, hdr = self._oq_items[sel[0]]
        qtext = self._oq_file.read_text(encoding="utf-8")
        lines = qtext.splitlines()
        # v2.1 — content-aware stale-index guard
        if (not 0 <= lineno < len(lines)
                or lines[lineno].strip() != hdr.strip()):
            messagebox.showerror("Owner pass",
                                 "OPEN-QUESTIONS.md changed since the last "
                                 "Refresh — click Refresh and re-select.")
            return
        # v2.1 — archive/remove the WHOLE block, not just the header line
        qblock = question_block(qtext, lineno)
        if not messagebox.askyesno("Owner pass",
                "Archive this whole question (kept in owner-pass.log, "
                "snapshot .bak)?\n\n%s" % qblock.strip()[:400]):
            return
        self._oq_backup()
        self._oq_archive(pdir, "REMOVED (no answer)", qblock)
        end = lineno + len(qblock.strip().splitlines())
        if end < len(lines) and not lines[end].strip():
            end += 1
        del lines[lineno:end]
        self._oq_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.on_owner_refresh()

    # ------------------------------------------------- v2.0 owner helpers
    def _show_full_question(self, _e=None):
        sel = self.oq_list.curselection()
        if sel and sel[0] < len(self._oq_items):
            # v2.1 — full PROBLEM/QUESTION/RECOMMEND block, not just the header
            self.q_full.configure(
                text=question_block(self._oq_text,
                                    self._oq_items[sel[0]][0]).strip())
        else:
            self.q_full.configure(text="")

    def _q_label(self, lineno):
        """One-line label for the question list: the QUESTION: line of a
        v2.1 block when present, else the (legacy) header line itself.
        v2.5 — blocks carrying a RECOMMEND line get a ' ·has rec' suffix
        (nothing else consumes these listbox labels)."""
        blines = question_block(self._oq_text, lineno).splitlines()
        if not blines:
            return "(stale — click Refresh)"
        label = None
        for ln in blines:
            m = re.match(r"\s*QUESTION\s*:\s*(.*)$", ln, re.I)
            if m:
                label = m.group(1).strip()[:100]
                break
        if label is None:
            label = blines[0].strip()[:100]
        if recommend_line(self._oq_text, lineno):
            label += " ·has rec"
        return label

    def _oq_backup(self):
        """Snapshot OPEN-QUESTIONS.md before any modification."""
        if self._oq_file and self._oq_file.is_file():
            try:
                bak = self._oq_file.parent / (self._oq_file.name + ".bak")
                bak.write_text(self._oq_file.read_text(encoding="utf-8"),
                               encoding="utf-8")
            except Exception:
                pass

    def _oq_archive(self, pdir, tag, qtext, ans=""):
        """Append removed questions/answers to the append-only owner-pass
        log. v2.1: qtext may be a multi-line question block — continuation
        lines are indented to stay visually under the Q:."""
        try:
            qlines = [l.strip() for l in qtext.strip().splitlines()]
            with (pdir / "owner-pass.log").open("a", encoding="utf-8") as f:
                f.write("[%s] %s\n    Q: %s\n"
                        % (datetime.now().strftime("%Y-%m-%d %H:%M"),
                           tag, qlines[0] if qlines else "(empty)"))
                for cont in qlines[1:]:
                    f.write("        %s\n" % cont)
                if ans:
                    f.write("    A: %s\n" % ans)
        except Exception:
            pass

    def on_tick_toggle(self):
        got = self._owner_paths()
        if got is None: return
        slug, pdir = got
        sel = self.rc_list.curselection()
        if not sel:
            messagebox.showerror("Owner pass", "Select a checklist item first.")
            return
        if not self._rc_file or not self._rc_file.is_file():
            messagebox.showerror("Owner pass", "Click Refresh first.")
            return
        lineno, line = self._rc_items[sel[0]]
        new = flip_recon_item(line)
        if new is None:
            messagebox.showerror("Owner pass",
                                 "Selected line is not a checkbox item.")
            return
        lines = self._rc_file.read_text(encoding="utf-8").splitlines()
        lines[lineno] = new
        self._rc_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.on_owner_refresh()

    def on_verify_exists(self):
        """Auto-tick `- [ ] EXISTS: <path>` items whose path exists."""
        got = self._owner_paths()
        if got is None: return
        slug, pdir = got
        if not self._rc_file or not self._rc_file.is_file():
            messagebox.showerror("Owner pass",
                                 "No checklist loaded — click Refresh.")
            return
        repo = self.repo_path()
        lines = self._rc_file.read_text(encoding="utf-8").splitlines()
        verified, remaining = 0, 0
        for i, line in enumerate(lines):
            m = re.match(r"\s*-\s*\[\s*\]\s*EXISTS:?\s*(.+)$", line,
                         re.IGNORECASE)
            if not m:
                continue
            path = m.group(1).strip()
            # v2.6.3 — repo-relative ONLY: the old CWD fallback
            # (Path(path).exists()) auto-ticked items from files that
            # merely shared a name outside the repo
            if (repo / path).exists():
                lines[i] = flip_recon_item(line)
                verified += 1
            else:
                remaining += 1
        if verified:
            self._rc_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.say("intake", "owner pass: EXISTS auto-verify — %d ticked, "
                 "%d not found" % (verified, remaining))
        self.on_owner_refresh()

    def on_owner_resolve(self):
        """Hand the rest of the owner pass to the agent (paste-instruction
        mode only — the agent must read the repo locally, so there is no
        API lane for this step)."""
        got = self._owner_paths()
        if got is None: return
        slug, pdir = got
        repo = self.repo_path()
        draft = pdir / "PART-01.draft.md"
        if not draft.is_file():
            messagebox.showerror("Owner pass",
                                 "plans/%s/PART-01.draft.md not found — run "
                                 "intake first." % slug)
            return
        body = draft.read_text(encoding="utf-8")
        na = count_owner_answers(body)
        if "## OWNER ANSWERS" not in body:
            if not messagebox.askyesno("Owner pass",
                    "No answers recorded yet (## OWNER ANSWERS is empty).\n"
                    "The agent will still tick what it can verify and "
                    "sharpen the remaining questions.\n\nContinue?"):
                return
        self._show_instruction(
            "Owner-resolve instruction — %s" % slug,
            self._instruction(repo, "owner-resolve.md", slug),
            pdir / "instructions" / "owner-resolve.txt")
        self.say("intake", "owner pass: instruction copied — paste into your "
                 "agent (repo open as workspace). It will integrate your "
                 "%d answer(s) into the draft body (§A–§G) and delete the "
                 "## OWNER ANSWERS inbox, tick locally-verifiable checklist "
                 "items, and rewrite unclear questions (NEEDS CLARIFICATION) "
                 "instead of guessing. When it finishes, click Refresh here, "
                 "then 'Show validation report' → Freeze." % na)

    # ------------------------------------------------------- small helpers
    def _browse_repo(self):
        d = filedialog.askdirectory(title="Choose your repo folder")
        if d:
            self.repo.delete(0, "end"); self.repo.insert(0, d)

    def repo_path(self):
        return Path(self.repo.get().strip()).expanduser().resolve()

    def _get_slug(self, first="intake"):
        """First non-empty slug across the three slug fields (Intake /
        Sessions / Owner pass), stripped. `first` selects the priority —
        the tab the user is working in. Replaces the fallback chain that
        was copy-pasted into eight handlers."""
        order = {"intake": (self.slug, self.sslug, self.oslug),
                 "sessions": (self.sslug, self.slug, self.oslug),
                 "owner": (self.oslug, self.slug, self.sslug)}
        for f in order[first]:
            v = f.get().strip()
            if v:
                return v
        return ""

    def _or_key_value(self):
        if not self.use_key.get():
            return ""           # checkbox off → never use any key
        return self.key.get().strip() or os.environ.get("OPENROUTER_API_KEY", "")

    def _save_cfg(self):
        # security: the API key is deliberately NOT persisted. It lives
        # in the entry field for this session only, or in the
        # OPENROUTER_API_KEY environment variable.
        self.cfg.update(repo=str(self.repo_path()),
                        model=self.model_cb.get().strip(),
                        use_key=self.use_key.get(),
                        kind=self.kind.get(),
                        theme=self.theme_setting)
        self.cfg.pop("or_key", None)
        CFG.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")

    def say(self, target, line):
        self.q.put((target, line))

    # ---- instruction delivery: clipboard + popup + backup file ----------
    def _show_instruction(self, title, text, save_path=None):
        """Copy an instruction to the clipboard AND make it impossible to
        miss: shows a popup (Copy-again button) and saves a backup file.
        Safe to call from any thread."""
        saved = None
        if save_path is not None:
            try:
                p = Path(save_path)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
                saved = str(p)
            except Exception:
                saved = None
        self.q.put(("__popup__", (title, text, saved)))

    def _instruction_popup(self, title, text, saved):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("700x440+%d+%d"
                     % (self.root.winfo_x() + 60, self.root.winfo_y() + 120))
        ttk.Label(win,
                  text="COPIED TO CLIPBOARD — paste this into your agent "
                       "(repo open as workspace):",
                  font=("", 10, "bold"), wraplength=660, justify="left")\
            .pack(anchor="w", padx=10, pady=(8, 2))
        t = self._tokens   # popups use the theme active at creation (§G)
        if saved:
            lbl_kw = {"foreground": t["text-muted"]} if t else {}
            ttk.Label(win, text="Backup copy saved to: %s" % saved,
                      wraplength=660, justify="left", **lbl_kw)\
                .pack(anchor="w", padx=10)
        txt_kw = ({"bg": t["bg-card"], "fg": t["text-main"],
                   "insertbackground": t["text-main"]} if t else {})
        txt = scrolledtext.ScrolledText(win, wrap="word", **txt_kw)
        txt.insert("1.0", text)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True, padx=10, pady=6)
        bar = ttk.Frame(win); bar.pack(fill="x", padx=10, pady=(0, 10))

        def copy_again():
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            btn.configure(text="Copied ✓")

        btn = ttk.Button(bar, text="Copy again", command=copy_again)
        btn.pack(side="left")
        ttk.Button(bar, text="Close", command=win.destroy).pack(side="right")
        win.attributes("-topmost", True)   # stays visible while you switch apps
        win.lift()

    def _drain(self):
        while not self.q.empty():
            target, payload = self.q.get()
            if target == "__models__":
                self._apply_models(payload)
            elif target == "__models_failed__":
                self._log_line("intake",
                               "model list fetch failed (%s) — you can type a "
                               "model id by hand." % payload)
            elif target == "__prog__":
                self.prog.configure(text=payload)
            elif target == "__popup__":
                title, text, saved = payload
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                self._instruction_popup(title, text, saved)
            elif target == "__busy__":
                on, msg = payload
                if on:
                    self._n_busy += 1
                else:
                    self._n_busy = max(0, self._n_busy - 1)
                busy_now = self._n_busy > 0
                for b in (getattr(self, "btn_proceed", None),
                          getattr(self, "btn_freeze", None),
                          getattr(self, "btn_copy", None)):
                    if b:
                        b.configure(state="disabled" if busy_now else "normal")
                for st in self.status.values():
                    st.configure(text=(msg or "working …") if busy_now else "idle")
                if not busy_now:
                    self.prog.configure(text="")
            else:
                self._log_line(target, payload)
        self.root.after(100, self._drain)

    def _log_line(self, target, line):
        w = self.logs.get(target)
        if w:
            w.configure(state="normal"); w.insert("end", line + "\n")
            w.see("end"); w.configure(state="disabled")

    def _busy(self, on, msg=""):
        self.q.put(("__busy__", (on, msg)))

    def on_cancel_api(self):
        # every live _api_call owns its own Event; set them all — a
        # parallel call starting can no longer reset the cancel (v2.5 fix)
        with self._cancel_lock:
            active = list(self._cancel_events)
        for ev in active:
            ev.set()
        self.say("intake", "cancel requested — aborting current API call …")

    # ------------------------------------------------------------ starter
    def on_init_repo(self):
        repo = self.repo_path()
        missing = [p for p in STARTER_FILES if not (repo / p).is_file()]
        if not missing:
            messagebox.showinfo("Init", "Repo already has all starter files.")
            return
        if not messagebox.askyesno("Init starter repo",
                "Create %d starter files in\n%s ?" % (len(missing), repo)):
            return
        repo.mkdir(parents=True, exist_ok=True)
        for p in missing:
            f = repo / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(STARTER_FILES[p], encoding="utf-8")
        self.say("intake", "initialized starter files: " + ", ".join(missing))

    # ------------------------------------------- v2.2 command-file updates
    def _stale_commands(self, repo):
        """Command files that differ from (or are missing vs) the built-in
        versions. None = repo has no command files at all (not a started
        repo — the auto-check stays silent there)."""
        cmds = {p: c for p, c in STARTER_FILES.items()
                if p.startswith("commands/")}
        if not any((repo / p).is_file() for p in cmds):
            return None
        return [p for p, c in cmds.items()
                if not (repo / p).is_file()
                or (repo / p).read_text(encoding="utf-8") != c]

    def _apply_command_update(self, repo, stale):
        """Overwrite the listed command files with built-in versions
        (PART-00.md, templates/ and plans/ are never touched)."""
        repo.mkdir(parents=True, exist_ok=True)
        for p in stale:
            f = repo / p
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(STARTER_FILES[p], encoding="utf-8")
        self.say("intake", "updated command files: " + ", ".join(stale))

    def _auto_command_check(self, repo=None):
        """v2.2 — started repos: offer the current command-file protocols
        once per repo per app run (startup + first action). Declining is
        remembered for this run only — use the manual button anytime."""
        repo = repo or self.repo_path()
        if not repo.is_dir() or str(repo) in self._cmd_checked:
            return
        self._cmd_checked.add(str(repo))
        stale = self._stale_commands(repo)
        if not stale:
            return
        # v2.5 — dialog names the current change (was: v2.4 BLOCKED rename)
        if messagebox.askyesno("Command files out of date",
                "This repo's command files predate the current console "
                "version (newest: %s).\n\n"
                "Update %d file(s) now?\n%s\n\n(Not asked again this run; "
                "PART-00.md, templates/ and plans/ are never touched.)"
                % (COMMAND_UPDATE_NOTE, len(stale), "\n".join(stale))):
            self._apply_command_update(repo, stale)

    def on_update_commands(self):
        """Refresh commands/ with the built-in versions (nothing else)."""
        repo = self.repo_path()
        stale = self._stale_commands(repo)
        if stale is None:
            # no command files at all — the manual button still creates them
            if not messagebox.askyesno("Update command files",
                    "No command files found in\n%s\n\nCreate the current "
                    "built-in command files now?" % repo):
                return
            self._apply_command_update(
                repo, [p for p in STARTER_FILES if p.startswith("commands/")])
            return
        if not stale:
            messagebox.showinfo("Update command files",
                                "All command files are already up to date.")
            return
        if not messagebox.askyesno("Update command files",
                "Overwrite %d command file(s) with the current built-in "
                "versions?\n\n%s\n\n(PART-00.md, templates/ and plans/ are "
                "never touched.)" % (len(stale), "\n".join(stale))):
            return
        self._apply_command_update(repo, stale)

    def _preflight(self):
        repo = self.repo_path()
        need = [p for p in ("PART-00.md", "commands/new-plan.md")
                if not (repo / p).is_file()]
        if need:
            if messagebox.askyesno("Not a plan repo",
                    "%s is missing starter files (%s).\nInitialize them now?"
                    % (repo, ", ".join(need))):
                repo.mkdir(parents=True, exist_ok=True)
                for p, c in STARTER_FILES.items():
                    f = repo / p
                    if not f.is_file():
                        f.parent.mkdir(parents=True, exist_ok=True)
                        f.write_text(c, encoding="utf-8")
            else:
                return None
        self._auto_command_check(repo)   # v2.2 — once per repo per run
        return repo

    # -------------------------------------------------------------- intake
    def on_proceed(self):
        repo = self._preflight()
        if repo is None: return
        slug = self.slug.get().strip()
        text = self.src.get("1.0", "end").strip()
        if not SLUG_RE.match(slug):
            messagebox.showerror("Slug", "Slug must be kebab-case, e.g. payments-v2")
            return
        if len(text) < 40:
            messagebox.showerror("Source", "Paste the plan, brainstorm, or "
                                 "audit report first.")
            return
        pdir = repo / "plans" / slug
        if self._frozen_file(pdir):   # v2.0 — any frozen name blocks re-intake
            messagebox.showerror("Frozen", "plans/%s is already frozen — pick a new slug." % slug)
            return
        if pdir.exists() and any(pdir.iterdir()) and not messagebox.askyesno(
                "Exists", "plans/%s already has files — continue anyway?" % slug):
            return
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "SOURCE.md").write_text(
            "# SOURCE — %s\nType: %s | Captured: %s (plan-console)\n\n---\n\n%s\n"
            % (slug, self.kind.get(), date.today(), text), encoding="utf-8")
        self._save_cfg()
        self.say("intake", "[%s] plans/%s/SOURCE.md written (%s)"
                 % (date.today(), slug, self.kind.get()))
        ui = {"kind": self.kind.get(), "recon": self.auto_recon.get(),
              "validate": self.auto_validate.get(),
              "model": self.model_cb.get().strip(), "key": self._or_key_value()}
        threading.Thread(target=self._intake_chain, args=(repo, slug, ui),
                         daemon=True).start()

    def _intake_chain(self, repo, slug, ui):
        self._busy(True, "intake running …")
        try:
            pdir = repo / "plans" / slug
            p00 = (repo / "PART-00.md").read_text(encoding="utf-8")
            tmpl = (repo / "templates" / "PART-01.md").read_text(encoding="utf-8")
            src = (pdir / "SOURCE.md").read_text(encoding="utf-8")
            if not ui["key"]:
                steps = [("new-plan.md",
                          "%s plans/%s/SOURCE.md %s" % (ui["kind"], slug, slug))]
                if ui["recon"]: steps.append(("recon.md", slug))
                if ui["validate"]: steps.append(("validate-plan.md", slug))
                lines = ["Working directory: %s" % repo, "",
                         "Execute these command files in this repo, in order:"]
                for i, (cmd, a) in enumerate(steps, 1):
                    lines.append("%d. commands/%s — arguments: %s" % (i, cmd, a))
                lines += ["", "Follow PART-00.md economy rules. "
                          "Write only inside plans/%s/." % slug]
                self._show_instruction("Intake instruction — %s" % slug,
                                       "\n".join(lines),
                                       pdir / "instructions" / "intake.txt")
                self.say("intake", "NO API KEY — intake instruction copied to "
                         "clipboard (popup + backup file in plans/%s/"
                         "instructions/). Paste it into your agent with the "
                         "repo open as the workspace folder, then do the "
                         "owner pass and click Freeze." % slug)
                return
            ok = self._run_api(repo, "intake", "new-plan.md",
                               "%s plans/%s/SOURCE.md %s" % (ui["kind"], slug, slug),
                               slug, [("PART-00.md", p00),
                                      ("plans/%s/SOURCE.md" % slug, src),
                                      ("templates/PART-01.md", tmpl)],
                               ui["model"], ui["key"])
            if ok and (pdir / "PART-01.draft.md").is_file():
                draft = pdir / "PART-01.draft.md"
                jobs = []
                if ui["recon"] and (pdir / "RECON-CHECKLIST.md").is_file():
                    rc = (pdir / "RECON-CHECKLIST.md").read_text(encoding="utf-8")
                    extra = [("PART-00.md", p00),
                             ("plans/%s/RECON-CHECKLIST.md" % slug, rc),
                             ("plans/%s/PART-01.draft.md" % slug,
                              draft.read_text(encoding="utf-8")),
                             ("REPO CONTEXT — PARTIAL: only some matching files "
                              "inlined; items not verifiable from it are "
                              "OWNER-ONLY",
                              self._context_pack(repo, rc))]
                    jobs.append(("recon.md", extra))
                if ui["validate"]:
                    extra = [("PART-00.md", p00),
                             ("plans/%s/PART-01.draft.md" % slug,
                              draft.read_text(encoding="utf-8")),
                             ("templates/PART-01.md", tmpl)]
                    for aux in ("OPEN-QUESTIONS.md", "RECON-CHECKLIST.md"):
                        f = pdir / aux
                        if f.is_file():
                            extra.append(("plans/%s/%s" % (slug, aux),
                                          f.read_text(encoding="utf-8")))
                    jobs.append(("validate-plan.md", extra))
                if jobs:
                    if len(jobs) > 1:
                        self.say("intake", "running recon + validate in "
                                 "parallel …")
                    threads = [threading.Thread(
                        target=self._run_api,
                        args=(repo, "intake", cmd, slug, slug, extra,
                              ui["model"], ui["key"]), daemon=True)
                        for cmd, extra in jobs]
                    for t in threads:
                        t.start()
                    for t in threads:
                        t.join()
                if ui["validate"]:
                    self._echo_validation(pdir)
            self._after_intake(repo, slug)
        except Exception as exc:
            self.say("intake", "ERROR: %s" % exc)
        finally:
            self._busy(False)

    def _echo_validation(self, pdir):
        val = pdir / "VALIDATION.md"
        if val.is_file():
            self.say("intake", "\n===== VALIDATION =====\n%s"
                     % val.read_text(encoding="utf-8").strip())

    def on_recon(self):
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("intake")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Recon", "Enter the slug first (kebab-case).")
            return
        pdir = repo / "plans" / slug
        rc = pdir / "RECON-CHECKLIST.md"
        if not rc.is_file():
            messagebox.showerror("Recon", "plans/%s/RECON-CHECKLIST.md not "
                                 "found — run intake first." % slug)
            return
        ui = {"model": self.model_cb.get().strip(), "key": self._or_key_value()}

        def work():
            self._busy(True, "recon running …")
            try:
                if not ui["key"]:
                    self._show_instruction(
                        "Recon instruction — %s" % slug,
                        self._instruction(repo, "recon.md", slug),
                        pdir / "instructions" / "recon.txt")
                    self.say("intake", "NO API KEY — recon instruction copied "
                             "(popup + backup file). Fastest path: your agent "
                             "reads the repo locally.")
                    return
                p00 = (repo / "PART-00.md").read_text(encoding="utf-8")
                checklist = rc.read_text(encoding="utf-8")
                extra = [("PART-00.md", p00),
                         ("plans/%s/RECON-CHECKLIST.md" % slug, checklist)]
                draft = pdir / "PART-01.draft.md"
                if draft.is_file():
                    extra.append(("plans/%s/PART-01.draft.md" % slug,
                                  draft.read_text(encoding="utf-8")))
                extra.append(("REPO CONTEXT — PARTIAL: only some matching files "
                              "inlined; items not verifiable from it are "
                              "OWNER-ONLY",
                              self._context_pack(repo, checklist)))
                self._run_api(repo, "intake", "recon.md", slug, slug, extra,
                              ui["model"], ui["key"])
            finally:
                self._busy(False)
        threading.Thread(target=work, daemon=True).start()

    def on_validate(self):
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("intake")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Validate", "Enter the slug first (kebab-case).")
            return
        pdir = repo / "plans" / slug
        draft = pdir / "PART-01.draft.md"
        if not draft.is_file():
            if pdir.is_dir():
                have = ", ".join(sorted(p.name for p in pdir.iterdir())) or "(empty)"
                hint = ("Only SOURCE.md listed? The draft hasn't been created yet:\n"
                        "- no API key: paste the copied intake instruction into\n"
                        "  your agent — IT creates the draft, then this works.\n"
                        "- with a key: read the Intake log for ERROR lines, or\n"
                        "  wait — intake can take a few minutes.")
            else:
                have = "(folder does not exist)"
                hint = ("Slug typo, or the top-bar Repo folder points to the "
                        "wrong place.")
            messagebox.showerror("Validate",
                "plans/%s/PART-01.draft.md not found.\n\n"
                "Files in plans/%s/: %s\n\n%s" % (slug, slug, have, hint))
            return
        ui = {"model": self.model_cb.get().strip(), "key": self._or_key_value()}

        def work():
            self._busy(True, "validating …")
            try:
                if not ui["key"]:
                    self._show_instruction(
                        "Validate instruction — %s" % slug,
                        self._instruction(repo, "validate-plan.md", slug),
                        pdir / "instructions" / "validate.txt")
                    self.say("intake", "NO API KEY — validate instruction copied "
                             "(popup + backup file). The agent writes the report "
                             "to plans/%s/VALIDATION.md — then click 'Show "
                             "validation report'." % slug)
                    return
                extra = [("PART-00.md", (repo / "PART-00.md").read_text(encoding="utf-8")),
                         ("plans/%s/PART-01.draft.md" % slug, draft.read_text(encoding="utf-8")),
                         ("templates/PART-01.md", (repo / "templates" / "PART-01.md").read_text(encoding="utf-8"))]
                for aux in ("OPEN-QUESTIONS.md", "RECON-CHECKLIST.md"):
                    f = pdir / aux
                    if f.is_file():
                        extra.append(("plans/%s/%s" % (slug, aux),
                                      f.read_text(encoding="utf-8")))
                self._run_api(repo, "intake", "validate-plan.md", slug, slug,
                              extra, ui["model"], ui["key"])
                self._echo_validation(pdir)
            finally:
                self._busy(False)
        threading.Thread(target=work, daemon=True).start()

    def on_show_validation(self):
        """Pure Python: display plans/<slug>/VALIDATION.md in the log."""
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("intake")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Validation report",
                                 "Enter the slug first (kebab-case).")
            return
        val = repo / "plans" / slug / "VALIDATION.md"
        if not val.is_file():
            messagebox.showerror("Validation report",
                "plans/%s/VALIDATION.md not found.\n\nRun 'Validate draft' "
                "first — with a key it takes a minute; without a key, paste "
                "the validate instruction into your agent and let it write "
                "the report." % slug)
            return
        body = val.read_text(encoding="utf-8")
        mtime = datetime.fromtimestamp(val.stat().st_mtime)\
                  .strftime("%Y-%m-%d %H:%M")
        self.say("intake", "\n===== VALIDATION — plans/%s/VALIDATION.md "
                 "(written %s) =====\n%s"
                 % (slug, mtime, body.strip()))
        if "PART-01 READY" in body:
            self.say("intake", "→ report says READY — you can Freeze.")
        else:
            self.say("intake", "→ findings listed above — resolve them in the "
                     "draft, then Validate again before Freezing.")

    def _after_intake(self, repo, slug):
        pdir = repo / "plans" / slug
        for name in ("OPEN-QUESTIONS.md", "RECON-CHECKLIST.md"):
            f = pdir / name
            if f.is_file() and f.read_text(encoding="utf-8").strip():
                self.say("intake", "\n===== %s — owner pass =====\n%s"
                         % (name, f.read_text(encoding="utf-8").strip()))
        self.say("intake", "\nNext: 1) Owner pass tab — answer each question "
                 "(saved into the draft), 2) click 'Agent: finish owner pass' "
                 "to hand the rest to your agent — or tick items yourself, "
                 "3) 'Validate draft', 4) Freeze. Paste-instructions are also "
                 "saved under plans/%s/instructions/." % slug)

    # ------------------------------------------------------ OpenRouter API
    def _fetch_models(self):
        def work():
            try:
                with urllib.request.urlopen(MODELS_URL, timeout=15) as r:
                    ids = sorted(m["id"] for m in json.load(r)["data"])
                self.q.put(("__models__", ids))
            except Exception as exc:
                self.q.put(("__models_failed__", str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _apply_models(self, ids):
        fav = self.cfg.get("favorites", [])
        self._all_models = fav + [i for i in ids if i not in fav]
        self.model_cb["values"] = self._all_models
        cur = self.model_cb.get().strip()
        if cur:
            self._remember_model(cur)
        elif fav:
            self.model_cb.set(fav[0])

    def _remember_model(self, model):
        fav = [m for m in self.cfg.get("favorites", []) if m != model]
        self.cfg["favorites"] = [model] + fav[:7]
        CFG.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")

    def _filter_models(self, event):
        """Type-to-filter for the model dropdown. Navigation keys pass
        through so ↑/↓ open and walk the list normally."""
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab",
                            "Left", "Right", "Home", "End",
                            "Shift_L", "Shift_R", "Control_L", "Control_R",
                            "Alt_L", "Alt_R"):
            return
        typed = self.model_cb.get().strip().lower()
        if typed:
            self.model_cb["values"] = [m for m in self._all_models
                                       if typed in m.lower()]
        else:
            self.model_cb["values"] = self._all_models

    def _on_model_picked(self, _event):
        picked = self.model_cb.get().strip()
        # v2.6.3 — remember only REAL model ids: typed filters ('glm',
        # 'nvidia') used to be saved as favorites on FocusOut/Return and
        # polluted the dropdown. A hand-typed vendor/model id (contains
        # '/') is still allowed — the model list may have failed to
        # load, and the log invites typing an id by hand.
        if picked and (picked in self._all_models or "/" in picked):
            self._remember_model(picked)
    def _api_call(self, prompt, model, key, timeout=360):
        """Streaming OpenRouter call: live progress ticker, cancellation,
        low reasoning effort (auto-retry without it if rejected).

        Each call gets its own threading.Event, registered for the life
        of the call — so cancelling one request can no longer be wiped
        by a parallel call starting (intake runs recon+validate in
        parallel threads)."""
        ev = threading.Event()
        with self._cancel_lock:
            self._cancel_events.add(ev)
        try:
            return self._api_call_body(prompt, model, key, timeout, ev)
        finally:
            with self._cancel_lock:
                self._cancel_events.discard(ev)

    def _api_call_body(self, prompt, model, key, timeout, ev):
        t0 = time.time()
        payload = {"model": model, "stream": True,
                   "messages": [{"role": "user", "content": prompt}]}
        attempts = [json.dumps({**payload, "reasoning": {"effort": "low"}})
                    .encode("utf-8"),
                    json.dumps(payload).encode("utf-8")]
        resp = None
        for i, body in enumerate(attempts):
            try:
                resp = urllib.request.urlopen(
                    urllib.request.Request(CHAT_URL, data=body, headers={
                        "Authorization": "Bearer " + key,
                        "Content-Type": "application/json"}), timeout=60)
                break
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    err = json.loads(e.read().decode("utf-8", "replace"))\
                          .get("error", {})
                    if isinstance(err, dict) and err.get("message"):
                        detail = " — " + str(err["message"])[:200]
                except Exception:
                    pass
                if e.code == 400 and i == 0:
                    continue        # provider may reject 'reasoning' — retry plain
                hints = {401: " — check your OpenRouter API key",
                         402: " — insufficient credits on OpenRouter",
                         429: " — rate limited; wait a bit or pick another model"}
                raise RuntimeError("OpenRouter HTTP %d%s%s"
                                   % (e.code, hints.get(e.code, ""), detail))
            except urllib.error.URLError as e:
                raise RuntimeError("network problem reaching OpenRouter (%s)"
                                   % e.reason)
        if resp is None:
            raise RuntimeError("request could not be started")
        parts, err_msg = [], None
        chars, last_report = 0, time.time()
        try:
            for raw in resp:
                if ev.is_set():
                    raise _Cancelled()
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                except ValueError:
                    continue
                if isinstance(chunk, dict) and chunk.get("error"):
                    e0 = chunk["error"]
                    err_msg = (e0.get("message", e0) if isinstance(e0, dict)
                               else e0)
                    break
                try:
                    delta = chunk["choices"][0]["delta"].get("content") or ""
                except (KeyError, IndexError, TypeError, AttributeError):
                    delta = ""
                if delta:
                    parts.append(delta)
                    chars += len(delta)
                now = time.time()
                if now - last_report >= 1.0:
                    last_report = now
                    self.q.put(("__prog__",
                                "generating… %ds · %s chars — Cancel stops it"
                                % (int(now - t0), "{:,}".format(chars))))
                if now - t0 > timeout:
                    raise RuntimeError("timed out after %ds — try a smaller/"
                                       "faster model" % timeout)
        except (TimeoutError, socket.timeout):
            # socket.timeout IS TimeoutError on Python 3.10+, but only
            # an OSError subclass before that — catch both so the
            # friendly 'connection stalled' message survives on 3.9 too
            raise RuntimeError("connection stalled (no data for 60s) — model "
                               "queue too long; retry or pick another model")
        except _Cancelled:
            raise RuntimeError("cancelled by user")
        finally:
            try:
                resp.close()
            except Exception:
                pass
        if err_msg:
            raise RuntimeError("OpenRouter refused the request: %s — often a "
                               "free-model rate/capacity limit; try another "
                               "model or wait a minute" % str(err_msg)[:250])
        text = "".join(parts)
        if not text.strip():
            raise RuntimeError("model replied with empty content — free models "
                               "do this under load; retry or pick another model")
        return text

    def _run_api(self, repo, target, cmd_file, args, slug, extra, model, key):
        """Run one command file through the API. Returns True if it ran."""
        cpath = repo / "commands" / cmd_file
        if not cpath.is_file():
            self.say(target, "ERROR: commands/%s not found — click "
                     "'Init starter repo'." % cmd_file)
            return False
        if not model:
            self.say(target, "ERROR: no model selected — pick one in the top bar.")
            return False
        prompt = cpath.read_text(encoding="utf-8").replace("$ARGUMENTS", args)
        prompt += FILE_RULES + "".join(
            "\n\n===== INLINED FILE: %s =====\n%s" % (l, c) for l, c in extra)
        self.say(target, "----- %s via %s -----" % (cmd_file, model))
        try:
            text = self._api_call(prompt, model, key)
            files, notes = parse_files(text, slug)
            if not files:
                self.say(target, "reply had no <<<FILE>>> blocks — retrying once …")
                text = self._api_call(prompt + RETRY_NOTE, model, key)
                files, notes = parse_files(text, slug)
        except Exception as exc:
            self.say(target, "ERROR: %s" % exc)
            self.say(target, "Fix the cause if needed, then retry this step "
                     "(for intake: click Proceed again and answer Yes).")
            return False
        for path, content in files:
            f = repo / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content, encoding="utf-8")
            self.say(target, "wrote %s" % path)
        if not files:
            self.say(target, "still no files — run this step manually in your "
                     "agent: commands/%s with arguments: %s" % (cmd_file, args))
            return False
        if notes.strip():
            self.say(target, "agent notes: " + notes.strip()[:600])
        return True

    def _context_pack(self, repo, checklist, max_files=8, max_bytes=4000):
        words = {w.lower() for w in re.findall(r"[A-Za-z_]{5,}", checklist)}
        skip = {".git", "node_modules", "plans", ".venv", "venv",
                "__pycache__", ".vscode", "dist", "build"}
        picked = []
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in skip]
            for name in files:
                if len(picked) >= max_files:
                    break
                p = Path(root) / name
                rel = p.relative_to(repo).as_posix()
                if any(w in rel.lower() for w in words):
                    try:
                        if p.stat().st_size < max_bytes:
                            picked.append("----- %s -----\n%s"
                                          % (rel, p.read_text(errors="replace")))
                    except OSError:
                        pass
            if len(picked) >= max_files:
                break
        return "\n\n".join(picked) if picked else "(no matching files found)"

    # -------------------------------------------------------------- freeze
    def _freeze_blockers(self, pdir):
        """v2.6 — P1: the on_freeze() gate checks, read-only. Returns the
        list of things that would block Freeze right now (empty = clear).
        Mutates nothing — the real Freeze keeps its own flow, including
        the already-frozen self-heal."""
        out = []
        if not (pdir / "PART-01.draft.md").is_file():
            out.append("PART-01.draft.md not found — run intake first")
        frozen = self._frozen_file(pdir)
        if frozen:
            out.append("already frozen (%s)" % frozen.name)
        oq = pdir / "OPEN-QUESTIONS.md"
        if oq.is_file():
            qs = parse_questions(oq.read_text(encoding="utf-8"))
            if qs:
                out.append("%d open question(s) in OPEN-QUESTIONS.md — "
                           "answer them in the Owner pass tab" % len(qs))
        draft = pdir / "PART-01.draft.md"
        if draft.is_file():
            # v2.7 — owner-resolve gate: answers parked in ## OWNER
            # ANSWERS are not yet part of the plan body
            na = count_owner_answers(draft.read_text(encoding="utf-8"))
            if na:
                out.append("%d owner answer(s) parked in ## OWNER ANSWERS "
                           "— run 'Agent: finish owner pass' "
                           "(owner-resolve) to integrate them, then "
                           "re-validate" % na)
        rc = pdir / "RECON-CHECKLIST.md"
        if rc.is_file():
            # v2.0 — owner-marked DEFERRED items no longer block Freeze;
            # v2.6.1 — anchored checkbox matching (prose mentioning `- [ ]`
            # in the header is not an item)
            n = count_open_recon(rc.read_text(encoding="utf-8"))
            if n:
                out.append("%d unchecked item(s) in RECON-CHECKLIST.md — "
                           "tick them in the Owner pass tab or mark the "
                           "line DEFERRED" % n)
        val = pdir / "VALIDATION.md"
        if not val.is_file():
            out.append("VALIDATION.md not found — click 'Validate draft' "
                       "first (paste the copied instruction to your agent)")
        elif val.read_text(encoding="utf-8").strip() != "PART-01 READY":
            out.append("VALIDATION.md is not 'PART-01 READY' — resolve the "
                       "findings, re-validate")
        return out

    def on_freeze_dry_run(self):
        """v2.6 — P1: print what would block Freeze right now; owner no
        longer has to guess or switch tabs."""
        got = self._owner_paths()
        if got is None: return
        _slug, pdir = got
        blockers = self._freeze_blockers(pdir)
        if not blockers:
            self.say("owner", "freeze dry-run: nothing blocking — Freeze "
                     "is unblocked.")
            return
        self.say("owner", "freeze dry-run — %d blocker(s):" % len(blockers))
        for b in blockers:
            self.say("owner", "  - " + b)

    def _pending_questions(self, f):
        # v2.1 — block-aware parser: one count per question block,
        # prose/SQL never count
        return len(parse_questions(f.read_text(encoding="utf-8")))

    def on_freeze(self):
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("intake")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Freeze", "Enter the slug first (kebab-case).")
            return
        pdir = repo / "plans" / slug
        draft = pdir / "PART-01.draft.md"
        if not draft.is_file():
            messagebox.showerror("Freeze", "plans/%s/PART-01.draft.md not found — "
                                 "run intake first." % slug)
            return
        frozen_existing = self._frozen_file(pdir)
        if frozen_existing:
            # v2.2 — self-heal the freeze crash window: the frozen file was
            # written but PROGRESS.md wasn't (interrupted between the two
            # writes) → create the missing header now, dated/versioned from
            # the frozen file itself
            prog = pdir / "PROGRESS.md"
            healed = ""
            if not prog.is_file():
                head = "\n".join(frozen_existing.read_text(encoding="utf-8")
                                 .splitlines()[:3])
                dm = re.search(r"\d{4}-\d{2}-\d{2}", head)
                vm = re.search(r"v\d+\.\d+", frozen_existing.name)
                prog.write_text("# PROGRESS — %s | PART-01 %s | %s\n"
                                % (slug, vm.group(0) if vm else "v1.0",
                                   dm.group(0) if dm else date.today()),
                                encoding="utf-8")
                healed = ("\n\n(Created the missing PROGRESS.md header — a "
                          "previous freeze was interrupted between the two "
                          "writes.)")
            messagebox.showerror("Freeze", "plans/%s is already frozen (%s).%s"
                                 % (slug, frozen_existing.name, healed))
            return
        oq = pdir / "OPEN-QUESTIONS.md"
        if oq.is_file():
            oq_text = oq.read_text(encoding="utf-8")
            qs = parse_questions(oq_text)
            if qs:
                # v2.1 — show the QUESTION line (the decision), not the
                # PROBLEM header; full blocks live in the Owner pass tab
                shown = []
                for lineno, _hdr in qs[:6]:
                    blk = [l.strip() for l in
                           question_block(oq_text, lineno).strip().splitlines()]
                    qline = next((l for l in blk
                                  if re.match(r"QUESTION\s*:", l, re.I)),
                                 blk[0] if blk else "")
                    shown.append(qline[:90])
                messagebox.showerror("Freeze",
                    "OPEN-QUESTIONS.md still has %d open question(s):\n\n%s\n\n"
                    "Answer them in the Owner pass tab (answering removes the "
                    "whole PROBLEM/QUESTION/RECOMMEND block; loose prose/SQL "
                    "lines do not count as questions)."
                    % (len(qs), "\n".join(shown)))
                return
        # v2.7 — owner-resolve gate (matches _freeze_blockers): answers
        # parked in ## OWNER ANSWERS are a TEMPORARY inbox — they must
        # be integrated into §A–§G before the plan is frozen
        na = count_owner_answers(draft.read_text(encoding="utf-8"))
        if na:
            messagebox.showerror("Freeze",
                "PART-01.draft.md still parks %d owner answer(s) in "
                "## OWNER ANSWERS (a TEMPORARY inbox — they are not yet "
                "part of the plan body).\n\nClick 'Agent: finish owner "
                "pass' so they are integrated into §A–§G, then "
                "re-validate and Freeze." % na)
            return
        rc = pdir / "RECON-CHECKLIST.md"
        if rc.is_file():
            # v2.0 — owner-marked DEFERRED items no longer block Freeze;
            # v2.6.1 — anchored checkbox matching (prose mentioning `- [ ]`
            # in the header is not an item)
            n = count_open_recon(rc.read_text(encoding="utf-8"))
            if n:
                messagebox.showerror("Freeze", "RECON-CHECKLIST.md has %d unchecked "
                                     "item(s) — tick them in the Owner pass tab "
                                     "or mark the line DEFERRED." % n)
                return
        # v2.0 — validation gate (matches commands/freeze-plan.md preconditions)
        val = pdir / "VALIDATION.md"
        if not val.is_file():
            messagebox.showerror("Freeze", "VALIDATION.md not found — click "
                                 "'Validate draft' first (paste the copied "
                                 "instruction to your agent), then Freeze.")
            return
        vbody = val.read_text(encoding="utf-8").strip()
        if vbody != "PART-01 READY":
            messagebox.showerror("Freeze",
                                 "VALIDATION.md is not 'PART-01 READY':\n\n%s\n\n"
                                 "Resolve the findings, re-validate, then "
                                 "Freeze." % vbody[:500])
            return
        body = draft.read_text(encoding="utf-8")
        # v2.0 — versioned filename: PART-01 v1.0.md
        frozen = pdir / "PART-01 v1.0.md"
        frozen.write_text(
            "PART 01 — %s | v1.0 frozen %s\n\n%s" % (slug, date.today(), body),
            encoding="utf-8")
        prog = pdir / "PROGRESS.md"
        if not prog.is_file():
            prog.write_text("# PROGRESS — %s | PART-01 v1.0 | %s\n"
                            % (slug, date.today()), encoding="utf-8")
        self.say("intake", "FROZEN v1.0 — plan ready as 'plans/%s/"
                 "PART-01 v1.0.md' (draft kept as history). Go to the Sessions "
                 "tab, enter the slug, and click 'Copy session instruction' "
                 "for session 1." % slug)

    # ------------------------------------------------------------ sessions
    def _session_guards(self):
        repo = self._preflight()
        if repo is None: return None
        # v2.0 — slug falls back to Intake/Owner-pass fields too
        slug = (self.sslug.get().strip() or self.slug.get().strip()
                or self.oslug.get().strip())
        if not SLUG_RE.match(slug):
            messagebox.showerror("Slug", "kebab-case slug required (e.g. payments-v2)")
            return None
        try:
            n = int(self.snum.get())
        except ValueError:
            messagebox.showerror("Session", "Session number must be a whole number.")
            return None
        if n < 1:
            messagebox.showerror("Session", "Session number must be 1 or higher.")
            return None
        pdir = repo / "plans" / slug
        # v2.0 — any frozen name (PART-01 v1.0.md or legacy PART-01.md)
        part01 = self._frozen_file(pdir)
        if part01 is None:
            # v2.0 — diagnose instead of a bare "not found"
            extra = ""
            if pdir.is_dir():
                names = sorted(p.name for p in pdir.iterdir())
                extra = "\n\nFiles in plans/%s/: %s" % (
                    slug, ", ".join(names[:12]) or "(empty)")
                if any("draft" in x.lower() for x in names):
                    extra += ("\n→ only a DRAFT exists: finish the owner pass, "
                              "Validate, then Freeze.")
            elif any(SLUG_RE.match(s) for s in (
                    self.slug.get().strip(), self.oslug.get().strip())):
                extra = ("\n→ Slug field takes the PLAN slug (e.g. "
                         "'translation-audit'); the session number goes in the "
                         "'Session #' spinbox.")
            messagebox.showerror("Not frozen",
                "No frozen plan in plans/%s/ — freeze first (Intake tab).%s"
                % (slug, extra))
            return None
        blocked = pdir / "BLOCKED.md"
        if blocked.is_file() and not messagebox.askyesno("BLOCKED on record",
                "BLOCKED.md exists:\n\n%s\n\nRun this session anyway?"
                % blocked.read_text(encoding="utf-8")[:400]):
            return None
        prog = pdir / "PROGRESS.md"
        done = set()
        if prog.is_file():
            # v2.5 — lenient reader (read_progress): a drifting PROGRESS
            # line ('Session #2 …', fields on separate lines) can no
            # longer hide a completed predecessor session
            done = {rec["n"] for rec in read_progress(prog)}
        missing = [i for i in range(1, n) if i not in done]
        if missing:
            messagebox.showerror("Sequence", "PROGRESS.md doesn't show session(s) "
                                 "%s as complete — run sessions in order." % missing)
            return None
        return repo, slug, n

    def _instruction(self, repo, cmd_file, args):
        return ("Working directory: %s\n\n"
                "Read the file commands/%s in this repo and execute it exactly "
                "as written,\nwith arguments: %s" % (repo, cmd_file, args))

    def on_copy_instr(self):
        g = self._session_guards()
        if g is None: return
        repo, slug, n = g
        row = self._session_map(repo / "plans" / slug).get(n)
        deploy = bool(row and row[2])
        # v2.3 — standing orders (AGENT-ORDERS.md) prepended ahead of the
        # session block, per the orders' own placement rule ("after global
        # configuration, before every session block"). The separator maps
        # the orders' "session spec / authorized files" language to the
        # plan system: scope and gates come from PART-01 §A via
        # commands/session.md.
        orders = self._agent_orders(repo)
        body = self._instruction(repo, "session.md", "%s %d" % (slug, n))
        if orders:
            text = (orders
                    + "\n\n===== SESSION BLOCK (the session spec that "
                      "follows) — the standing orders above apply. "
                      "Authorized scope, gates and deploy rules come from "
                      "PART-01 §A via commands/session.md. =====\n\n"
                    + body)
        else:
            text = body
        self._show_instruction(
            "Session %d instruction — %s" % (n, slug),
            text,
            repo / "plans" / slug / "instructions" / ("session-%d.txt" % n))
        self.say("sessions", "instruction copied — paste into your agent with %s "
                 "open as the workspace folder." % repo)
        if orders:
            src = ("per-repo AGENT-ORDERS.md (wins for this repo)"
                   if (repo / AGENT_ORDERS_NAME).is_file()
                   else "app-level AGENT-ORDERS.md next to the console")
            self.say("sessions", "agent orders: attached ahead of the session "
                     "block (%s). Customize via 'Agent orders…' — changes "
                     "apply from the next copy; per-repo file wins; content "
                     "'OFF' or empty disables." % src)
        else:
            self.say("sessions", "agent orders: disabled (missing file is "
                     "created on first use — or content is empty/'OFF'); "
                     "session block only.")
        # v2.2 — resume awareness: a live IN-PROGRESS marker means partial
        # work exists; the instruction's handshake reconciles it
        ip_f, ip_n, ip_sum = self._ip_summary(repo / "plans" / slug)
        if ip_f is not None:
            who = ("session %d (%s)" % (ip_n, ip_sum)
                   if ip_n is not None else (ip_sum or "unreadable marker"))
            self.say("sessions", "◔ IN-PROGRESS.md exists — %s. The handshake "
                     "in the copied instruction makes the agent reconcile "
                     "partial work (read the marker, git status/diff, "
                     "keep-or-revert) instead of redoing blindly; a stale "
                     "marker (session already complete) is deleted by the "
                     "agent." % who)
        self.say("sessions", "BLOCKED protocol: if a gate fails twice, the agent "
                 "writes BLOCKED.md and stops. You fix the cause, rename "
                 "BLOCKED.md → BLOCKED-resolved.md, and re-run the session.")
        if deploy:
            # v2.0 — §G can legitimately assign deploys to the agent
            self.say("sessions", "⚠ DEPLOY session (per §A): supervise it — "
                     "unless PART-01 §G explicitly assigns deploys to the "
                     "agent (e.g. authenticated Supabase CLI). Gates BEFORE "
                     "and AFTER deploy; never continue past a failed "
                     "post-deploy gate.")
        self.say("sessions", "When the agent finishes, click 'Session report'.")

    def _ip_summary(self, pdir):
        """v2.2 — (path, session_number, one-line summary) from the
        IN-PROGRESS.md marker (commands/session.md handshake), or
        (None, None, ""). Summary = 'started <date>' plus the last
        'stopped …' line if the agent halted without finishing."""
        f, n = self._in_progress(pdir)
        if f is None:
            return None, None, ""
        try:
            body = f.read_text(encoding="utf-8")
        except Exception:
            return f, n, "(marker unreadable)"
        m = re.search(r"(?i)started\s+(\d{4}-\d{2}-\d{2})", body)
        summary = "started %s" % (m.group(1) if m else "?")
        for line in body.splitlines():
            if re.match(r"(?i)^\s*stopped\b", line):
                summary += " — " + line.strip()[:60]
        return f, n, summary

    def on_status(self):
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("sessions")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Status", "Enter the slug first (kebab-case).")
            return
        pdir = repo / "plans" / slug
        if not pdir.is_dir():
            self.say("sessions", "STATUS — plans/%s not found" % slug)
            return
        frozen = self._frozen_file(pdir)   # v2.0 — any frozen name
        if frozen:
            stage = "frozen (%s)" % frozen.name
        elif (pdir / "PART-01.draft.md").is_file():
            stage = "intake (draft exists, not frozen)"
        else:
            stage = "empty"
        prog = pdir / "PROGRESS.md"
        tail = "-"
        if prog.is_file():
            lines = [l for l in prog.read_text(encoding="utf-8").splitlines() if l.strip()]
            if lines:
                tail = lines[-1]
        oq = pdir / "OPEN-QUESTIONS.md"
        q = self._pending_questions(oq) if oq.is_file() else 0
        # v2.2 — interrupted-session state from the IN-PROGRESS marker
        ip_f, ip_n, ip_sum = self._ip_summary(pdir)
        if ip_f is None:
            inprog = "no"
        elif ip_n is None:
            inprog = "marker present (session number unreadable — see IN-PROGRESS.md)"
        else:
            inprog = ("session %d (%s) — re-run its session instruction; "
                      "it resumes" % (ip_n, ip_sum or "?"))
        # v2.4 — the Status line teaches the resolution convention
        blocked = ("YES — resolve, then rename BLOCKED.md → "
                   "BLOCKED-resolved.md"
                   if (pdir / "BLOCKED.md").is_file() else "no")
        self.say("sessions", "STATUS — %s | stage: %s | in progress: %s | last "
                 "progress: %s | open questions: %d | blocked: %s"
                 % (slug, stage, inprog, tail, q, blocked))

    # --------------------------------------------- shared session analysis
    def _session_map(self, pdir):
        rows = {}
        part01 = self._frozen_file(pdir)   # v2.0 — any frozen name
        if part01 is None:
            return rows
        for line in part01.read_text(encoding="utf-8").splitlines():
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 3 and cells[0].isdigit():
                d = cells[3].lower() if len(cells) >= 4 else ""
                deploy = d.startswith(("y", "d")) or "deploy" in d or "supervis" in d
                rows[int(cells[0])] = (cells[1], cells[2], deploy)
        return rows

    def _session_state(self, pdir, n, rows=None, records=None,
                       part01_text=None):
        """v2.5 — PROGRESS.md is read through the lenient reader
        (module-level read_progress): agent format drift ('Gates:',
        'gates =', ids with descriptions, 'all', bare numbers, records
        folded across lines, missing label) no longer erases gates.
        Returns the v2.4 dict shape (plus 'lenient') so _verdict /
        _mkreport / _mkhealth keep working. PROGRESS.md is never
        rewritten here — drift is reported, not repaired (agent-owned
        file, PART-01 §F).
        Optional pre-parsed inputs (rows = §A session map, records =
        read_progress list, part01_text = frozen plan text) let Plan
        health parse each file ONCE instead of once per session."""
        if rows is None:
            rows = self._session_map(pdir)
        row = rows.get(n)
        declared_raw = row[1] if row else ""
        part01 = self._frozen_file(pdir)
        if part01_text is None:
            part01_text = (part01.read_text(encoding="utf-8")
                           if part01 is not None else "")
        declared = session_row_gates(part01_text, n) if part01_text else []
        raw, gates, status, notes = None, [], "", []
        when, lenient = "", False
        rec = None
        prog = pdir / "PROGRESS.md"
        if records is None and prog.is_file():
            records = read_progress(prog)      # v2.5 — lenient reader
        if records:
            for r in records:
                if r["n"] == n:
                    # v2.5 — prefer the LAST record with real content
                    # (gates or status parsed) over prose addenda like
                    # 'Session 3 addendum: …'; fall back to the last.
                    if (r["gates"] or r["gates_all"]
                            or r["status"] != "UNKNOWN"):
                        rec = r
                    elif rec is None:
                        rec = r
        if rec is None:
            notes.append("no PROGRESS entry — session unfinished or not run")
        else:
            raw = rec["raw"]
            when = rec["date"]
            lenient = not rec["canonical"]
            gates = list(rec["gates"])
            if rec["gates_all"]:
                if declared:
                    gates = list(declared)     # 'all' → expand from §A
                else:
                    notes.append("'all' gates reported but the §A row has "
                                 "no gN ids to expand")
            if rec["status"] == "UNKNOWN":
                notes.append("no status parsed — PROGRESS line unreadable")
            else:
                status = rec["status"]
                if rec["note"]:
                    status = "%s — %s" % (rec["status"], rec["note"])
        word = status.split()[0].upper() if status else ""
        if declared and gates:
            pset = {g.lower() for g in gates}
            miss = [g for g in declared if g.lower() not in pset]
            extra = sorted(pset - {g.lower() for g in declared})
            if miss: notes.append("declared gate(s) not reported: " + ", ".join(miss))
            if extra: notes.append("reported but not in §A: " + ", ".join(extra))
        elif declared and raw and not gates:
            notes.append("no gates parsed — compare vs §A: " + declared_raw)
        elif gates and raw and not declared:
            notes.append("session row not found in §A map (or gates lack gN ids)")
        if word and word != "PASS":
            notes.append("status " + status)
        return {"n": n, "declared": declared, "declared_raw": declared_raw,
                "deploy": row[2] if row else False, "raw": raw, "gates": gates,
                "status": status, "word": word, "when": when, "notes": notes,
                "lenient": lenient,
                "blocked": (pdir / "BLOCKED.md").is_file()}

    def _verdict(self, st):
        if st["blocked"] or st["word"] == "BLOCKED":
            return "✖ BLOCKED — resolve, rename BLOCKED.md → BLOCKED-resolved.md, re-run"
        if not st["raw"]:
            return "✖ INCOMPLETE — no PROGRESS entry for session %d" % st["n"]
        if not st["notes"] and st["word"] == "PASS":
            # v2.5 — recovered-but-drifted lines are still OK; the tag
            # keeps the drift visible without nagging
            tag = (" (PROGRESS line non-canonical — gates parsed "
                   "leniently)") if st["lenient"] else ""
            return "OK — session %d complete%s" % (st["n"], tag)
        return "⚠ CHECK — " + "; ".join(st["notes"])

    # ------------------------------------------------------ session report
    def on_report(self):
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("sessions")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Slug", "kebab-case slug required.")
            return
        try:
            n = int(self.snum.get())
        except ValueError:
            messagebox.showerror("Session", "Session number must be a whole number.")
            return
        if n < 1:
            messagebox.showerror("Session", "Session number must be 1 or higher.")
            return
        lines = self._mkreport(repo, slug, n)
        for line in lines:
            self.say("sessions", line)
        verdict = next((l for l in lines if l.startswith("VERDICT")), "")
        # v2.6 — P1: on an OK verdict, advance the session number so the
        # daily loop is "click report → click copy → paste" — but only
        # when the next session exists in the §A map (advancing past the
        # deploy session would be wrong; owner answer #3).
        if verdict.startswith("VERDICT: OK"):
            rows = self._session_map(repo / "plans" / slug)
            if (n + 1) in rows:
                self.snum.set(str(n + 1))
                self.say("sessions", "session # advanced to %d (next "
                         "session exists in §A)" % (n + 1))
        # v2.6 — P1: a CHECK verdict's fix hint goes to the clipboard so
        # the round-trip to the agent is copy-paste, not re-type
        hint = next((l.split("fix: ", 1)[1] for l in lines
                     if "fix: " in l), None)
        if hint:
            self.root.clipboard_clear()
            self.root.clipboard_append(hint)
            self.say("sessions", "fix hint copied to clipboard")

    def _mkreport(self, repo, slug, n):
        pdir = repo / "plans" / slug
        st = self._session_state(pdir, n)
        out = ["===== SESSION REPORT — %s / session %d =====" % (slug, n)]
        out.append("progress line : %s" % (st["raw"] or "— none found —"))
        # v2.2 — interrupted? the marker (if any) explains the gap
        ip_f, ip_n, ip_sum = self._ip_summary(pdir)
        if ip_f is not None and (ip_n is None or ip_n == n):
            out.append("in progress   : YES (%s) — interrupted; re-run the "
                       "session instruction to resume" % (ip_sum or "?"))
        out.append("declared (§A) : %s" % (", ".join(st["declared"])
                                           or st["declared_raw"] or "—"))
        out.append("reported      : %s" % (", ".join(st["gates"]) or "—"))
        dirty = self._git_dirty(repo)
        out.append("worktree      : %s" % ("not a git repo" if dirty is None
                    else "clean" if not dirty
                    else "%d modified paths" % len(dirty)))
        verdict = self._verdict(st)
        # v2.5 — the canonical-fix hint fires only on PARSE failures
        # (no gates / no status recovered), never on drifted-but-
        # recovered lines
        if st["raw"] and any(x.startswith(("no gates parsed",
                                           "no status parsed"))
                             for x in st["notes"]):
            verdict += (" | fix: append canonical line — SESSION %d | %s | gates: … "
                        "| status: PASS | P00 v…" % (n, date.today()))
        out.append("VERDICT       : %s" % verdict)
        return out

    # ---------------------------------------------------------- plan health
    def on_health(self):
        repo = self._preflight()
        if repo is None: return
        slug = self._get_slug("sessions")
        if not SLUG_RE.match(slug):
            messagebox.showerror("Slug", "kebab-case slug required.")
            return
        lines = self._mkhealth(repo, slug)
        self._log_health(repo / "plans" / slug, slug, lines)
        for line in lines:
            self.say("sessions", line)

    def _mkhealth(self, repo, slug):
        pdir = repo / "plans" / slug
        part01 = self._frozen_file(pdir)   # v2.0 — any frozen name
        if part01 is None:
            return ["PLAN HEALTH — %s: not frozen (no PART-01 v*.md / "
                    "PART-01.md with freeze header)" % slug]
        rows = self._session_map(pdir)
        if not rows:
            return ["PLAN HEALTH — %s: no session rows in PART-01 §A" % slug]
        N = max(rows)
        part01_text = part01.read_text(encoding="utf-8")
        prog = pdir / "PROGRESS.md"
        records = read_progress(prog) if prog.is_file() else []
        out = ["===== PLAN HEALTH — %s | %s | %d sessions ====="
               % (slug, part01_text.splitlines()[0].strip(), N)]
        # v2.2 — interrupted-session marker (commands/session.md handshake)
        ip_f, ip_n, ip_sum = self._ip_summary(pdir)
        passed = next_n = 0
        next_mark = ""
        drifted = []                     # v2.5 — non-canonical records
        for n in range(1, N + 1):
            st = self._session_state(pdir, n, rows=rows, records=records,
                                     part01_text=part01_text)
            if st["lenient"]:
                drifted.append(n)
            if st["word"] == "BLOCKED":
                mark, detail = "✖ BLOCKED", st["status"][:45]
            elif not st["raw"]:
                if ip_n == n:
                    # v2.2 — marker says this session started but never
                    # appended a PROGRESS line → interrupted, resumable
                    mark = "◔ RUNNING"
                    detail = ip_sum[:45] if ip_sum else "IN-PROGRESS.md"
                else:
                    mark, detail = "— not run", "declared: " + (st["declared_raw"][:38] or "?")
            elif st["word"] == "PASS" and not st["notes"]:
                mark = "OK"
                detail = ",".join(st["gates"]) or "gates n/a"
                if st["lenient"]:
                    # v2.5 — gates counted from a drifting line:
                    # reported AND flagged, never silently dropped
                    detail += " — ⚠ non-canonical line"
                passed += 1
            else:
                mark = "⚠ " + (st["word"] or "CHECK")
                g = ",".join(st["gates"])
                # v2.5 — gates show on ⚠ rows too (that was the bug:
                # any drift made the whole gates column vanish)
                detail = ((g + " | ") if g else "") + (st["notes"][0][:45] if st["notes"] else "")
            out.append(" %2d  %-10s %-10s %s%s" % (n, mark, st["when"] or "----------",
                        detail, "  [DEPLOY]" if st["deploy"] else ""))
            if not next_n and mark != "OK":
                next_n, next_mark = n, mark
        dirty = self._git_dirty(repo)
        out.append("blocked: %s | worktree: %s | passed: %d/%d"
                   % ("YES" if (pdir / "BLOCKED.md").is_file() else "no",
                      "not a git repo" if dirty is None else
                      "clean" if not dirty else "%d modified paths" % len(dirty),
                      passed, N))
        if next_n == 0:
            out.append("VERDICT: ALL SESSIONS PASS — close out: append "
                       "'PLAN COMPLETE %s' to PROGRESS.md" % date.today())
        elif next_n == N or rows.get(next_n, ("", "", False))[2]:
            out.append("VERDICT: NEXT = session %d = DEPLOY (supervise — unless "
                       "§G assigns deploys to the agent) — pre-deploy sweep: "
                       "clear every ⚠ / ✖ / ◔ line above first" % next_n)
        elif next_mark.startswith("✖"):
            out.append("VERDICT: NEXT = session %d — blocked: resolve BLOCKED.md, "
                       "rename to BLOCKED-resolved.md, re-run" % next_n)
        elif next_mark.startswith("◔"):
            # v2.2 — interrupted session: resume, don't restart blindly
            out.append("VERDICT: NEXT = RESUME session %d — re-run its session "
                       "instruction; the agent reconciles partial work per "
                       "IN-PROGRESS.md (git diff, keep-or-revert)" % next_n)
        elif next_mark != "— not run":
            out.append("VERDICT: NEXT = session %d — ⚠ entry above needs fixing "
                       "(re-run session or normalize its PROGRESS line)" % next_n)
        else:
            out.append("VERDICT: NEXT = session %d" % next_n)
        # v2.2 — marker sanity notes (unparsable / outside map / stale)
        if ip_f is not None:
            if ip_n is None or not (1 <= ip_n <= N):
                out.append("note: IN-PROGRESS.md present (session %s) but "
                           "unparsable or outside the session map — inspect "
                           "it manually" % (ip_n if ip_n is not None else "?"))
            elif self._session_state(pdir, ip_n, rows=rows,
                                     records=records,
                                     part01_text=part01_text)["raw"]:
                out.append("note: stale IN-PROGRESS.md — session %d already "
                           "ended (PROGRESS entry exists); the next session "
                           "run deletes the marker per protocol, or remove it "
                           "manually" % ip_n)
        # v2.5 — format-drift hygiene (flag, don't hide): which records
        # were read leniently, and any duplicated session records
        if drifted:
            out.append("note: non-canonical PROGRESS line(s) — session(s) %s: "
                       "gates counted anyway; have the agent append a "
                       "canonical corrective line when convenient"
                       % ", ".join(str(x) for x in drifted))
        _, dups = latest_sessions(records)
        if dups:
            out.append("note: session(s) %s recorded more than once — the "
                       "LAST PROGRESS line wins (expected after a BLOCKED "
                       "re-run)" % ", ".join(str(x) for x in dups))
        return out

    def _log_health(self, pdir, slug, lines):
        if not pdir.is_dir():
            return
        f = pdir / "HEALTH.md"
        header = ("# HEALTH — %s | audit trail of Plan-health runs "
                  "(console-appended; agent never edits)\n\n" % slug) \
            if not f.exists() else ""
        stamp = "## %s\n\n" % datetime.now().strftime("%Y-%m-%d %H:%M")
        with f.open("a", encoding="utf-8") as fh:
            fh.write(header + stamp + "```\n" + "\n".join(lines) + "\n```\n\n")

    # ----------------------------------------------------------------- git
    def _git_dirty(self, repo):
        try:
            r = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                return None
            return [l for l in r.stdout.splitlines() if l.strip()]
        except Exception:
            return None


if __name__ == "__main__":
    _root = tk.Tk()
    App(_root)
    _root.mainloop()
