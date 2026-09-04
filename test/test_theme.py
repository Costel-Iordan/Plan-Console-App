"""Theme-system tests for the Plan Console (pure — no Tk, no network,
no repo access). Covers PART-01 §A session 1: THEMES completeness,
token hex format validity, and _detect_os_theme fallback behavior.

Run either way:
    py test/test_theme.py
    py -m pytest test/test_theme.py
"""
import importlib.util
import re
import sys
from pathlib import Path

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
    # lockstep with UserGuide.html :root (PART-01 §G)
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
    # verbatim from UserGuide.html :root (PART-01 §G lockstep)
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


def test_high_contrast_defaults_to_true_when_undetectable(monkeypatch):
    # safe default: never fight the OS (PART-01 §G)
    monkeypatch.setattr(pc, "winreg", None)
    assert pc._high_contrast_active() is True


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__]))