"""Theme-system tests for the Plan Console. Covers PART-01 §A session 1:
THEMES completeness, token hex format validity, _detect_os_theme fallback
behavior, and (v3.5.2) the theme-change flow on the real widgets —
display update, persistence, and combobox/popdown restyling. Everything
except the flow tests is pure (no Tk, no network, no repo access); the
flow tests build a real (withdrawn) Tk window and skip when no display
is available.

Run either way:
    py test/test_theme.py
    py -m pytest test/test_theme.py
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "plan_console_theme", HERE.parent / "plan-console.py")
pc = importlib.util.module_from_spec(_spec)
sys.modules["plan_console_theme"] = pc
_spec.loader.exec_module(pc)


# ----------------------------------------------------------- THEMES shape
def test_both_themes_define_the_same_token_keys():
    assert set(pc.THEMES) == {"light", "dark"}
    keys = list(pc.THEMES["light"])
    assert keys, "token table must not be empty"
    assert list(pc.THEMES["dark"]) == keys, \
        "both themes must define the same token keys, in the same order"


def test_token_names_mirror_the_guide_palette():
    # lockstep with assets/console.css :root (UserGuide.html links it;
    # PART-01 §G)
    expected = ("bg-main", "bg-card", "bg-accent", "text-main",
                "text-muted", "accent-cyan", "accent-green",
                "accent-orange", "accent-red", "border-color")
    for name, theme in pc.THEMES.items():
        assert tuple(theme) == expected, \
            "%s tokens drift from the guide palette" % name


def test_every_token_is_a_valid_hex_color():
    hex_re = re.compile(r"^#[0-9a-fA-F]{6}$")
    for name, theme in pc.THEMES.items():
        for token, value in theme.items():
            assert hex_re.match(value), \
                "%s.%s = %r is not a #rrggbb hex color" % (name, token, value)


def test_dark_tokens_match_the_guide_values():
    # verbatim from assets/console.css :root (PART-01 §G lockstep)
    assert pc.THEMES["dark"] == {
        "bg-main": "#0f172a", "bg-card": "#1e293b",
        "bg-accent": "#334155", "text-main": "#f8fafc",
        "text-muted": "#94a3b8", "accent-cyan": "#38bdf8",
        "accent-green": "#4ade80", "accent-orange": "#fb923c",
        "accent-red": "#f87171", "border-color": "#475569"}


def test_theme_settings_and_labels_cover_the_same_values():
    assert pc.THEME_SETTINGS == ("light", "dark", "system")
    assert set(pc.THEME_SETTING_BY_LABEL.values()) == set(pc.THEME_SETTINGS)
    assert set(pc.THEME_SETTING_BY_LABEL) == set(pc.THEME_LABELS.values())


# ------------------------------------------- _detect_os_theme fallback (§G)
class _FakeKey:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class _FakeWinreg:
    HKEY_CURRENT_USER = "HKCU"

    def __init__(self, apps_use_light):
        self._value = apps_use_light

    def OpenKey(self, *_a):
        return _FakeKey()

    def QueryValueEx(self, _key, _name):
        return (self._value, "REG_DWORD")


class _BrokenWinreg:
    HKEY_CURRENT_USER = "HKCU"

    def OpenKey(self, *_a):
        raise OSError("registry unreadable")


def test_detect_os_theme_without_winreg_falls_back_to_light(monkeypatch):
    monkeypatch.setattr(pc, "winreg", None)
    assert pc._detect_os_theme() == "light"


def test_detect_os_theme_registry_error_falls_back_to_light(monkeypatch):
    monkeypatch.setattr(pc, "winreg", _BrokenWinreg())
    monkeypatch.setattr(pc.os, "name", "nt")
    assert pc._detect_os_theme() == "light"


def test_detect_os_theme_dark_when_appsuselighttheme_zero(monkeypatch):
    monkeypatch.setattr(pc, "winreg", _FakeWinreg(0))
    monkeypatch.setattr(pc.os, "name", "nt")
    assert pc._detect_os_theme() == "dark"


def test_detect_os_theme_light_when_appsuselighttheme_one(monkeypatch):
    monkeypatch.setattr(pc, "winreg", _FakeWinreg(1))
    monkeypatch.setattr(pc.os, "name", "nt")
    assert pc._detect_os_theme() == "light"


def test_high_contrast_false_on_non_windows(monkeypatch):
    # v3.5.1 audit fix — non-Windows has no high-contrast check to
    # perform; custom themes must APPLY there (was: permanently True,
    # which disabled dark mode on macOS/Linux)
    monkeypatch.setattr(pc, "winreg", None)
    monkeypatch.setattr(pc.os, "name", "posix")
    assert pc._high_contrast_active() is False


def test_high_contrast_defaults_to_true_when_windows_registry_unreadable(
        monkeypatch):
    # safe default on Windows itself: never fight the OS (PART-01 §G)
    monkeypatch.setattr(pc, "winreg", _BrokenWinreg())
    monkeypatch.setattr(pc.os, "name", "nt")
    assert pc._high_contrast_active() is True


# ------------------------------------------- theme-change flow (v3.5.2 fix)
@pytest.fixture()
def app_window(tmp_path, monkeypatch):
    """A real (withdrawn) Plan Console App on a temp config, offline.
    Skips the test when no Tk display is available."""
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no Tk display available")
    root.withdraw()
    monkeypatch.setattr(pc, "_high_contrast_active", lambda: False)
    monkeypatch.setattr(pc, "CFG", tmp_path / "plan-console.json")
    monkeypatch.setattr(pc.App, "_fetch_models", lambda self: None)
    app = pc.App(root)
    root.update()
    yield app, root
    root.destroy()


def _select(root, cb, label):
    """Deliver a selection the way the Tk core does after the user picks
    from the popdown: set the value, then fire <<ComboboxSelected>>."""
    cb.set(label)
    cb.event_generate("<<ComboboxSelected>>")
    root.update()


def test_theme_change_updates_display_and_persists(app_window):
    """Screenshot regression: after picking a theme, the dropdown must
    DISPLAY the new selection and the choice must reach the config."""
    app, root = app_window
    cb = app.theme_cb
    for label, setting in (("Dark", "dark"), ("Light", "light"),
                           ("Follow OS", "system")):
        _select(root, cb, label)
        assert cb.get() == label, "dropdown must show the new selection"
        assert app.theme_setting == setting
        assert app.cfg["theme"] == setting
    assert pc.CFG.is_file(), "theme changes must be persisted"
    assert '"theme": "system"' in pc.CFG.read_text(encoding="utf-8")


def test_theme_change_restyles_existing_combobox_popdown(app_window):
    """Screenshot regression: a dropdown opened under one theme kept the
    old palette after switching (option_add only reaches popdowns created
    later). _refresh_comboboxes must restyle the existing popdown."""
    import tkinter as tk
    app, root = app_window
    cb = app.theme_cb
    # create the popdown listbox exactly where ttk creates it
    popdown = tk.Toplevel(cb, name="popdown")
    lb = tk.Listbox(popdown)
    lb.pack()
    root.update()
    dark_card, light_card = pc.THEMES["dark"]["bg-card"], \
        pc.THEMES["light"]["bg-card"]
    _select(root, cb, "Dark")
    assert lb.cget("bg") == dark_card, \
        "existing popdown must follow the theme switch"
    _select(root, cb, "Light")
    assert lb.cget("bg") == light_card, \
        "popdown must restyle back to light"
    popdown.destroy()


def test_theme_change_forces_combobox_repaint_without_clobbering(app_window):
    """The repaint pass re-sets every combobox value identically — no
    display value may be lost or changed (model picker included)."""
    app, root = app_window
    app.model_cb.set("test/vendor")
    _select(root, app.theme_cb, "Dark")
    assert app.model_cb.get() == "test/vendor"
    assert app.theme_cb.get() == "Dark"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))