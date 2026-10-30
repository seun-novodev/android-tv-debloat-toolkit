"""adb lookup when packaged with PyInstaller (sys.frozen / sys._MEIPASS)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_toolkit


def _make_adb(folder):
    adb = folder / "adb" / run_toolkit.ADB_NAME
    adb.parent.mkdir(parents=True)
    adb.write_bytes(b"MZ")  # Windows only accepts files that look like programs
    return str(adb)


def test_frozen_finds_adb_bundled_inside(monkeypatch, tmp_path):
    meipass, exe_dir = tmp_path / "meipass", tmp_path / "dist"
    exe_dir.mkdir()
    bundled = _make_adb(meipass)
    monkeypatch.delenv("ADB_PATH", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "run_toolkit.exe"))
    assert run_toolkit._find_adb() == bundled


def test_frozen_finds_adb_next_to_executable(monkeypatch, tmp_path):
    exe_dir = tmp_path / "dist"
    beside = _make_adb(exe_dir)
    monkeypatch.delenv("ADB_PATH", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "empty"), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "run_toolkit.exe"))
    assert run_toolkit._find_adb() == beside
