"""Open every window for real (adb faked) to catch layout/Tk errors per platform.

Needs a display, so it only runs when ATV_GUI_TESTS=1 (CI sets it; Linux CI
runs under xvfb).
"""
import functools
import os
import sys
import tkinter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_toolkit

pytestmark = pytest.mark.skipif(os.environ.get("ATV_GUI_TESTS") != "1",
                                reason="set ATV_GUI_TESTS=1 to open real windows")

sg = run_toolkit.sg
ALL_PACKAGES = ({pkg for _, pkg in run_toolkit.safe_apps}
                | {pkg for _, pkg, _ in run_toolkit.apps}
                | {pkg for _, pkg in run_toolkit.GOOGLE_LAUNCHERS})
_shared_tcl = functools.lru_cache(maxsize=None)(tkinter.Tcl)


@pytest.fixture
def rendered(monkeypatch):
    """Each window renders once, then closes; returns the titles shown."""
    titles = []
    real_read = sg.Window.read

    def read_once(self, timeout=None, **kwargs):
        real_read(self, timeout=100)
        titles.append(self.Title)
        return sg.WINDOW_CLOSED, {}

    monkeypatch.setattr(sg.Window, "read", read_once)
    # FreeSimpleGUI creates a throwaway Tcl interpreter for every window just to
    # read the version. Creating dozens in one process intermittently fails on
    # Windows CI ("Can't find a usable init.tcl ... No error"; see
    # actions/setup-python#1102, python/cpython#126549), so reuse one.
    monkeypatch.setattr(tkinter, "Tcl", _shared_tcl)
    for name in ("popup", "popup_scrolled"):
        monkeypatch.setattr(sg, name, lambda *a, **k: None)
    monkeypatch.setattr(sg, "popup_yes_no", lambda *a, **k: "No")

    # A connected TV where half the known apps are enabled and half disabled.
    pkgs = sorted(ALL_PACKAGES)
    enabled, disabled = set(pkgs[::2]), set(pkgs[1::2])
    run_toolkit.state.ip, run_toolkit.state.port, run_toolkit.state.connected = "192.0.2.1", "5555", True
    monkeypatch.setattr(run_toolkit, "reconnect_check", lambda: True)
    monkeypatch.setattr(run_toolkit, "ADB", run_toolkit.ADB)  # main_menu runs ensure_adb
    monkeypatch.setattr(run_toolkit, "package_state", lambda: (enabled, disabled))
    monkeypatch.setattr(run_toolkit, "run_adb", lambda *a, **k: ("", "", 0))
    yield titles
    run_toolkit.state.connected = False


@pytest.mark.parametrize("dialog", [
    "main_menu", "connect_to_tv", "pair_and_connect", "install_apk",
    "safe_debloat_checklist", "advanced_debloat", "reenable_apps",
])
def test_window_opens(rendered, dialog):
    getattr(run_toolkit, dialog)()
    assert len(rendered) == 1
