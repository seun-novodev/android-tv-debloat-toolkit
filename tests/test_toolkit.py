import io
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run_toolkit


@pytest.fixture(autouse=True)
def reset_state():
    run_toolkit.state.connected = False
    run_toolkit.state.ip = ""
    run_toolkit.state.port = "5555"
    yield
    run_toolkit.state.connected = False
    run_toolkit.state.ip = ""
    run_toolkit.state.port = "5555"


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("1.2.3.4", True),
        ("192.168.86.102", True),
        ("0.0.0.0", True),
        ("255.255.255.255", True),
        ("256.1.1.1", False),
        ("999.1.1.1", False),
        ("1.2.3", False),
        ("1.2.3.4.5", False),
        ("1.2.3.a", False),
        ("", False),
        (" 1.2.3.4", False),
        ("1.2.3.4 ", False),
    ],
)
def test_is_valid_ip(ip, expected):
    assert run_toolkit.is_valid_ip(ip) is expected


@pytest.mark.parametrize(
    ("port", "expected"),
    [
        ("0", False),
        ("1", True),
        ("65535", True),
        ("65536", False),
        ("", False),
        ("abc", False),
        (" 5", False),
    ],
)
def test_is_valid_port(port, expected):
    assert run_toolkit.is_valid_port(port) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1.2.3.4", ("1.2.3.4", "5555")),
        ("1.2.3.4:5555", ("1.2.3.4", "5555")),
        ("1.2.3.4:39903", ("1.2.3.4", "39903")),
        ("1.2.3.4:0", None),
        ("1.2.3.4:abc", None),
        ("999.1.1.1", None),
        (" 1.2.3.4 ", ("1.2.3.4", "5555")),
    ],
)
def test_parse_target(text, expected):
    assert run_toolkit.parse_target(text) == expected


@pytest.mark.parametrize(
    ("stdout", "target", "expected"),
    [
        ("connected to 192.168.86.102:39903", "192.168.86.102:39903", True),
        ("already connected to 1.2.3.4:5555", "1.2.3.4:5555", True),
        ("failed to connect to '127.0.0.1:5599': Connection refused", "127.0.0.1:5599", False),
        ("cannot connect to 1.2.3.4:5555: No route to host", "1.2.3.4:5555", False),
        ("connected to 1.2.3.4:5555", "1.2.3.4:9999", False),
    ],
)
def test_connect_succeeded(stdout, target, expected):
    assert run_toolkit.connect_succeeded(stdout, target) is expected


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("Successfully paired to 1.2.3.4:37000 [guid=adb-x]", True),
        ("Failed: Wrong password or connection was dropped.", False),
        ("error: protocol fault (couldn't read status message): Undefined error: 0", False),
    ],
)
def test_pair_succeeded(stdout, expected):
    assert run_toolkit.pair_succeeded(stdout) is expected


@pytest.mark.parametrize(
    ("devices_stdout", "target", "expected"),
    [
        ("List of devices attached\n1.2.3.4:5555\tdevice\n", "1.2.3.4:5555", True),
        ("List of devices attached\n1.2.3.4:5555\toffline\n", "1.2.3.4:5555", False),
        ("List of devices attached\n1.2.3.4:5555\tunauthorized\n", "1.2.3.4:5555", False),
        ("List of devices attached\n1.2.3.4:55555\tdevice\n", "1.2.3.4:5555", False),
        ("List of devices attached\n", "1.2.3.4:5555", False),
        ("", "1.2.3.4:5555", False),
    ],
)
def test_device_online(devices_stdout, target, expected):
    assert run_toolkit.device_online(devices_stdout, target) is expected


@pytest.mark.parametrize(
    ("stdout", "expected"),
    [
        ("package:com.example.one\npackage:com.example.two\n", {"com.example.one", "com.example.two"}),
        ("  package:com.foo.bar  \n\nother:ignored\n", {"com.foo.bar"}),
        ("", set()),
    ],
)
def test_parse_packages(stdout, expected):
    assert run_toolkit.parse_packages(stdout) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Exception occurred while executing 'disable-user':\n"
            "java.lang.IllegalArgumentException: Unknown package: com.example.x\n"
            "\tat com.android.server.pm.PackageManagerService.setEnabledSettings(PackageManagerService.java:3931)",
            "Unknown package: com.example.x",
        ),
        (
            "java.lang.SecurityException: Shell cannot change component state for null to 3",
            "Shell cannot change component state for null to 3",
        ),
        ("Error: foo", "Error: foo"),
        ("Performing Streamed Install\nFailure [INSTALL_FAILED_OLDER_SDK]", "Failure [INSTALL_FAILED_OLDER_SDK]"),
        ("", "Unknown error"),
    ],
)
def test_first_error_line(text, expected):
    assert run_toolkit.first_error_line(text) == expected


@pytest.mark.parametrize(
    ("text", "expected_substring"),
    [
        (
            "error: protocol fault (couldn't read status message): Undefined error: 0",
            "The pairing service didn't complete the handshake.",
        ),
        (
            "failed to connect to '127.0.0.1:5599': Connection refused",
            "The TV refused the connection.",
        ),
        (
            "cannot connect to 1.2.3.4:5555: No route to host",
            "The TV didn't answer.",
        ),
        (
            "Error: something else failed",
            "Error: something else failed",
        ),
    ],
)
def test_friendly_adb_error(text, expected_substring):
    result = run_toolkit.friendly_adb_error(text)
    assert expected_substring in result


def test_run_adb_strips_daemon_lines_and_passes_timeout(monkeypatch):
    recorded = {}

    def fake_run(cmd, *, capture_output, text, timeout, **kwargs):
        recorded["cmd"] = cmd
        recorded["timeout"] = timeout
        stderr = (
            "* daemon not running; starting now at tcp:5037\n"
            "* daemon started successfully\n"
            "real error line"
        )
        return subprocess.CompletedProcess(cmd, 0, stdout="ok\n", stderr=stderr)

    monkeypatch.setattr(run_toolkit.subprocess, "run", fake_run)
    stdout, stderr, rc = run_toolkit.run_adb("devices", timeout=42)
    assert stdout == "ok\n"
    assert stderr == "real error line"
    assert rc == 0
    assert recorded["cmd"] == [run_toolkit.ADB, "devices"]
    assert recorded["timeout"] == 42


@pytest.mark.parametrize(
    ("exc", "expected_msg"),
    [
        (FileNotFoundError("no such file"), "adb not found"),
        (PermissionError("permission denied"), "Could not run adb"),
        (subprocess.TimeoutExpired(cmd="adb", timeout=15), "ADB command timed out."),
    ],
)
def test_run_adb_exceptions(monkeypatch, exc, expected_msg):
    def fake_run(*args, **kwargs):
        raise exc

    monkeypatch.setattr(run_toolkit.subprocess, "run", fake_run)
    stdout, stderr, rc = run_toolkit.run_adb("devices")
    assert stdout == ""
    assert rc == 1
    assert expected_msg in stderr


def test_find_adb_env_override(monkeypatch, tmp_path):
    adb_file = tmp_path / "custom_adb"
    adb_file.write_text("", encoding="utf-8")
    monkeypatch.setenv("ADB_PATH", str(adb_file))
    assert run_toolkit._find_adb() == str(adb_file)

    adb_dir = tmp_path / "platform-tools"
    adb_dir.mkdir()
    monkeypatch.setenv("ADB_PATH", str(adb_dir))
    assert run_toolkit._find_adb() == str(adb_dir / run_toolkit.ADB_NAME)

    monkeypatch.setenv("ADB_PATH", "~/my_adb_binary")
    assert run_toolkit._find_adb() == os.path.expanduser("~/my_adb_binary")

    missing = str(tmp_path / "nonexistent" / "adb")
    monkeypatch.setenv("ADB_PATH", missing)
    assert run_toolkit._find_adb() == missing


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX chmod executable bit semantics")
def test_find_adb_extra_dirs_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("ADB_PATH", raising=False)
    empty_app_dir = tmp_path / "app"
    empty_app_dir.mkdir()
    monkeypatch.setattr(run_toolkit, "_app_dirs", lambda: [str(empty_app_dir)])

    empty_path_dir = tmp_path / "empty_path"
    empty_path_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_path_dir))

    extra_dir = tmp_path / "extra_bin"
    extra_dir.mkdir()
    fake_adb = extra_dir / "adb"
    fake_adb.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_adb.chmod(0o755)
    monkeypatch.setattr(run_toolkit, "EXTRA_ADB_DIRS", [str(extra_dir)])

    assert run_toolkit._find_adb() == str(fake_adb)


def test_find_adb_skips_windows_placeholder(monkeypatch, tmp_path):
    # Old copies of the repo shipped a 2-byte adb/adb.exe that isn't a program.
    monkeypatch.delenv("ADB_PATH", raising=False)
    monkeypatch.setattr(run_toolkit, "IS_WINDOWS", True)
    monkeypatch.setattr(run_toolkit, "ADB_NAME", "adb.exe")
    monkeypatch.setattr(run_toolkit, "_app_dirs", lambda: [str(tmp_path)])
    monkeypatch.setattr(run_toolkit, "EXTRA_ADB_DIRS", [])
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    (tmp_path / "adb").mkdir()
    local = tmp_path / "adb" / "adb.exe"
    local.write_bytes(b"\r\n")
    assert run_toolkit._find_adb() == "adb"
    local.write_bytes(b"MZ" + b"\0" * 64)
    assert run_toolkit._find_adb() == str(local)


@pytest.fixture
def no_adb(monkeypatch):
    """adb can't be found; records popups and download attempts."""
    calls = []
    monkeypatch.delenv("ADB_PATH", raising=False)
    monkeypatch.setattr(run_toolkit, "ADB", run_toolkit.ADB)  # ensure_adb reassigns it
    monkeypatch.setattr(run_toolkit, "_find_adb", lambda: "adb")
    monkeypatch.setattr(run_toolkit.shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(run_toolkit.sg, "popup", lambda *a, **k: calls.append(("popup", k.get("title"))))
    monkeypatch.setattr(run_toolkit, "download_adb", lambda: calls.append(("download", None)) or True)
    return calls


def test_ensure_adb_windows_offers_download(monkeypatch, no_adb):
    monkeypatch.setattr(run_toolkit, "IS_WINDOWS", True)
    monkeypatch.setattr(run_toolkit.sg, "popup_yes_no", lambda *a, **k: "No")
    run_toolkit.ensure_adb()
    assert no_adb == []

    monkeypatch.setattr(run_toolkit.sg, "popup_yes_no", lambda *a, **k: "Yes")
    run_toolkit.ensure_adb()
    assert no_adb == [("download", None), ("popup", "ADB Installed")]


def test_ensure_adb_elsewhere_shows_install_hint(monkeypatch, no_adb):
    monkeypatch.setattr(run_toolkit, "IS_WINDOWS", False)
    run_toolkit.ensure_adb()
    assert no_adb == [("popup", "ADB Missing")]


def test_ensure_adb_quiet_when_adb_path_set(monkeypatch, no_adb):
    monkeypatch.setattr(run_toolkit, "IS_WINDOWS", True)
    monkeypatch.setenv("ADB_PATH", "C:/missing/adb.exe")
    run_toolkit.ensure_adb()
    assert no_adb == []


def test_ensure_adb_quiet_when_local_adb_not_executable(monkeypatch, no_adb, tmp_path):
    # run_adb reports "can't run" for this; it isn't "missing".
    local = tmp_path / "adb"
    local.write_text("", encoding="utf-8")
    monkeypatch.setattr(run_toolkit, "IS_WINDOWS", False)
    monkeypatch.setattr(run_toolkit, "_find_adb", lambda: str(local))
    run_toolkit.ensure_adb()
    assert no_adb == []


class _FakeResponse(io.BytesIO):
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _platform_tools_zip(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name in names:
            z.writestr(f"platform-tools/{name}", b"MZ" + name.encode())
    return buf.getvalue()


def test_download_adb_extracts_files(monkeypatch, tmp_path):
    monkeypatch.setattr(run_toolkit, "ADB_DIR", str(tmp_path / "adb"))
    data = _platform_tools_zip(run_toolkit.ADB_FILES)
    monkeypatch.setattr(run_toolkit.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(data))
    assert run_toolkit.download_adb() is True
    assert sorted(p.name for p in (tmp_path / "adb").iterdir()) == sorted(run_toolkit.ADB_FILES)
    assert (tmp_path / "adb" / "adb.exe").read_bytes() == b"MZadb.exe"


def test_download_adb_failure_leaves_no_adb_exe(monkeypatch, tmp_path):
    monkeypatch.setattr(run_toolkit, "ADB_DIR", str(tmp_path / "adb"))
    data = _platform_tools_zip(["adb.exe", "AdbWinApi.dll"])  # AdbWinUsbApi.dll missing
    monkeypatch.setattr(run_toolkit.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(data))
    with pytest.raises(KeyError):
        run_toolkit.download_adb()
    assert not (tmp_path / "adb" / "adb.exe").exists()


def test_reconnect_check_not_connected_initially(monkeypatch):
    calls = []
    monkeypatch.setattr(run_toolkit, "run_adb", lambda *a, **kw: calls.append(a))
    assert run_toolkit.reconnect_check() is False
    assert calls == []


def test_reconnect_check_already_online(monkeypatch):
    run_toolkit.state.connected = True
    run_toolkit.state.ip = "1.2.3.4"
    calls = []

    def fake_run_adb(*args, **kwargs):
        calls.append(args)
        return ("List of devices attached\n1.2.3.4:5555\tdevice\n", "", 0)

    monkeypatch.setattr(run_toolkit, "run_adb", fake_run_adb)
    assert run_toolkit.reconnect_check() is True
    assert calls == [("devices",)]
    assert run_toolkit.state.connected is True


def test_reconnect_check_offline_then_connect_succeeds(monkeypatch):
    run_toolkit.state.connected = True
    run_toolkit.state.ip = "1.2.3.4"
    calls = []
    responses = [
        ("List of devices attached\n1.2.3.4:5555\toffline\n", "", 0),
        ("connected to 1.2.3.4:5555\n", "", 0),
        ("List of devices attached\n1.2.3.4:5555\tdevice\n", "", 0),
    ]

    def fake_run_adb(*args, **kwargs):
        calls.append(args)
        return responses.pop(0)

    monkeypatch.setattr(run_toolkit, "run_adb", fake_run_adb)
    assert run_toolkit.reconnect_check() is True
    assert calls == [
        ("devices",),
        ("connect", "1.2.3.4:5555"),
        ("devices",),
    ]
    assert run_toolkit.state.connected is True


def test_reconnect_check_unauthorized_and_connect_fails(monkeypatch):
    run_toolkit.state.connected = True
    run_toolkit.state.ip = "1.2.3.4"
    calls = []
    responses = [
        ("List of devices attached\n1.2.3.4:5555\tunauthorized\n", "", 0),
        ("failed to connect to '1.2.3.4:5555': Connection refused\n", "", 0),
        ("", "", 0),  # disconnect
    ]

    def fake_run_adb(*args, **kwargs):
        calls.append(args)
        return responses.pop(0)

    monkeypatch.setattr(run_toolkit, "run_adb", fake_run_adb)
    assert run_toolkit.reconnect_check() is False
    # The stale transport is dropped so the next attempt re-handshakes.
    assert calls == [("devices",), ("connect", "1.2.3.4:5555"), ("disconnect", "1.2.3.4:5555")]
    assert run_toolkit.state.connected is False


def test_run_debloat_already_disabled_and_not_installed(monkeypatch):
    calls = []
    monkeypatch.setattr(run_toolkit, "shell", lambda *a, **kw: calls.append(a))
    out = run_toolkit._run_debloat(
        [("App A", "pkg.disabled"), ("App B", "pkg.missing")],
        enabled={"pkg.enabled"},
        disabled={"pkg.disabled"},
    )
    assert calls == []
    assert "App A (pkg.disabled): ⚠️ Already disabled" in out
    assert "App B (pkg.missing): ⏭️ Not installed — skipped" in out


def test_run_debloat_outcomes(monkeypatch):
    calls = []
    responses = {
        "pkg.ok": ("Package pkg.ok new state: disabled-user\n", "", 0),
        "pkg.sec": (
            "",
            "java.lang.SecurityException: Shell cannot change component state for null to 3\n",
            255,
        ),
        "pkg.err": (
            "",
            "Exception occurred while executing 'disable-user':\n"
            "java.lang.IllegalArgumentException: Unknown package: pkg.err\n"
            "\tat com.android.server.pm.PackageManagerService.setEnabledSettings(PackageManagerService.java:3931)\n",
            255,
        ),
    }

    def fake_shell(*args, **kwargs):
        calls.append(args)
        return responses[args[-1]]

    monkeypatch.setattr(run_toolkit, "shell", fake_shell)
    app_list = [
        ("OK App", "pkg.ok"),
        ("Protected App", "pkg.sec"),
        ("Broken App", "pkg.err"),
    ]
    out = run_toolkit._run_debloat(
        app_list,
        enabled={"pkg.ok", "pkg.sec", "pkg.err"},
        disabled=set(),
    )
    assert len(calls) == 3
    assert "OK App (pkg.ok): ✅ Disabled" in out
    assert "Protected App (pkg.sec): 🔒 Protected by Android" in out
    assert "Broken App (pkg.err): ❌ Error — Unknown package: pkg.err" in out
    assert "at com.android" not in out


def test_package_state(monkeypatch):
    calls = []

    def fake_shell(*args, **kwargs):
        calls.append(args)
        if "-e" in args:
            return ("package:a\npackage:b\n", "", 0)
        if "-d" in args:
            return ("package:c\n", "", 0)
        raise AssertionError(f"Unexpected args: {args}")

    monkeypatch.setattr(run_toolkit, "shell", fake_shell)
    enabled, disabled = run_toolkit.package_state()
    assert enabled == {"a", "b"}
    assert disabled == {"c"}
    assert calls == [
        ("pm", "list", "packages", "-e", "--user", "0"),
        ("pm", "list", "packages", "-d", "--user", "0"),
    ]


# Real `cmd package query-activities --brief ... HOME` output (Android 14, Google TV).
HOME_QUERY = (
    "2 activities found:\n"
    "  Activity #0:\n"
    "    priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n"
    "    com.glasshome.tv/.MainActivity\n"
    "  Activity #1:\n"
    "    priority=-1000 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n"
    "    com.android.tv.settings/.system.FallbackHome\n"
)
LAUNCHERX = "com.google.android.apps.tv.launcherx"


def _launcher_env(monkeypatch, home_output, answer="Yes"):
    """Connected TV with launcherx enabled; records popups and disable calls."""
    run_toolkit.state.connected = True
    run_toolkit.state.ip = "1.2.3.4"
    popups, disabled_calls = [], []
    monkeypatch.setattr(run_toolkit, "reconnect_check", lambda: True)
    monkeypatch.setattr(run_toolkit, "package_state", lambda: ({LAUNCHERX, "com.glasshome.tv"}, set()))

    def fake_shell(*args, **kwargs):
        if args[:2] == ("cmd", "package"):
            return (home_output, "", 0)
        disabled_calls.append(args)
        return (f"Package {args[-1]} new state: disabled-user\n", "", 0)

    monkeypatch.setattr(run_toolkit, "shell", fake_shell)
    monkeypatch.setattr(run_toolkit.sg, "popup", lambda *a, **k: popups.append(a[0]))
    monkeypatch.setattr(run_toolkit.sg, "popup_scrolled", lambda *a, **k: popups.append(a[0]))
    monkeypatch.setattr(run_toolkit.sg, "popup_yes_no", lambda *a, **k: popups.append(a[0]) or answer)
    return popups, disabled_calls


def test_home_activities_parses_packages(monkeypatch):
    monkeypatch.setattr(run_toolkit, "shell", lambda *a, **k: (HOME_QUERY, "", 0))
    assert run_toolkit._home_activities() == {"com.glasshome.tv", "com.android.tv.settings"}


def test_disable_launcher_refuses_without_alternative(monkeypatch):
    only_fallback = HOME_QUERY.replace("com.glasshome.tv/.MainActivity", f"{LAUNCHERX}/.home.HomeActivity")
    popups, disabled_calls = _launcher_env(monkeypatch, only_fallback)
    run_toolkit.disable_google_launcher()
    assert disabled_calls == []
    assert "No other launcher is installed" in popups[-1]


def test_disable_launcher_needs_confirmation(monkeypatch):
    popups, disabled_calls = _launcher_env(monkeypatch, HOME_QUERY, answer="No")
    run_toolkit.disable_google_launcher()
    assert disabled_calls == []
    assert "com.glasshome.tv" in popups[-1]


def test_disable_launcher_disables_launcherx(monkeypatch):
    popups, disabled_calls = _launcher_env(monkeypatch, HOME_QUERY, answer="Yes")
    run_toolkit.disable_google_launcher()
    assert disabled_calls == [("pm", "disable-user", "--user", "0", LAUNCHERX)]
    assert f"({LAUNCHERX}): ✅ Disabled" in popups[-1]


@pytest.mark.parametrize(
    ("devices_stdout", "expected"),
    [
        ("List of devices attached\n1.2.3.4:5555\tunauthorized\n", "unauthorized"),
        ("List of devices attached\n1.2.3.4:5555\tdevice product:x model:y\n", "device"),
        ("List of devices attached\n", None),
    ],
)
def test_device_status(devices_stdout, expected):
    assert run_toolkit.device_status(devices_stdout, "1.2.3.4:5555") == expected


def _scripted_run_adb(monkeypatch, responses):
    calls = []

    def fake_run_adb(*args, **kwargs):
        calls.append(args)
        return responses[args[0]]

    monkeypatch.setattr(run_toolkit, "run_adb", fake_run_adb)
    return calls


def test_adb_connect_online(monkeypatch):
    calls = _scripted_run_adb(monkeypatch, {
        "connect": ("connected to 1.2.3.4:5555\n", "", 0),
        "devices": ("List of devices attached\n1.2.3.4:5555\tdevice\n", "", 0),
    })
    assert run_toolkit.adb_connect("1.2.3.4:5555") == (True, "connected to 1.2.3.4:5555")
    assert ("disconnect", "1.2.3.4:5555") not in calls


def test_adb_connect_unauthorized_is_not_success(monkeypatch):
    # Before the TV's prompt is accepted adb still says "already connected".
    calls = _scripted_run_adb(monkeypatch, {
        "connect": ("already connected to 1.2.3.4:5555\n", "", 0),
        "devices": ("List of devices attached\n1.2.3.4:5555\tunauthorized\n", "", 0),
        "disconnect": ("disconnected 1.2.3.4:5555\n", "", 0),
    })
    ok, detail = run_toolkit.adb_connect("1.2.3.4:5555")
    assert ok is False
    assert detail == run_toolkit.AUTH_HINT
    assert calls[-1] == ("disconnect", "1.2.3.4:5555")


def test_adb_connect_failed_to_authenticate(monkeypatch):
    _scripted_run_adb(monkeypatch, {
        "connect": ("failed to authenticate to 1.2.3.4:5555\n", "", 0),
        "disconnect": ("", "", 0),
    })
    assert run_toolkit.adb_connect("1.2.3.4:5555") == (False, run_toolkit.AUTH_HINT)


def test_package_state_raises_when_query_fails(monkeypatch):
    monkeypatch.setattr(run_toolkit, "shell", lambda *a, **k: ("", "error: closed", 1))
    with pytest.raises(run_toolkit.AdbError, match="error: closed"):
        run_toolkit.package_state()


def test_package_state_raises_on_empty_list(monkeypatch):
    monkeypatch.setattr(run_toolkit, "shell", lambda *a, **k: ("", "", 0))
    with pytest.raises(run_toolkit.AdbError):
        run_toolkit.package_state()


class _FakeWindow:
    def __init__(self, busy):
        self.metadata = busy


@pytest.mark.parametrize(
    ("event", "busy", "expected"),
    [
        ("Cancel", False, True),
        (run_toolkit.sg.WINDOW_CLOSED, False, True),
        (run_toolkit.sg.WINDOW_CLOSE_ATTEMPTED_EVENT, False, True),
        (run_toolkit.sg.WINDOW_CLOSE_ATTEMPTED_EVENT, True, False),  # X ignored mid-job
        ("Install", False, False),
    ],
)
def test_should_close(event, busy, expected):
    assert run_toolkit.should_close(event, _FakeWindow(busy)) is expected


FAULT = "error: protocol fault (couldn't read status message): Undefined error: 0"
PAIRED = "Successfully paired to 1.2.3.4:37000 [guid=adb-x]"


@pytest.mark.parametrize(
    ("replies", "expected_calls", "paired"),
    [
        ([("", FAULT), (PAIRED, "")], ["pair", "kill-server", "start-server", "pair"], True),
        ([("", FAULT), ("", FAULT)], ["pair", "kill-server", "start-server", "pair"], False),
        ([("Failed: Wrong password or connection was dropped.", "")], ["pair"], False),
        ([(PAIRED, "")], ["pair"], True),
    ],
)
def test_adb_pair_restarts_server_once_on_protocol_fault(monkeypatch, replies, expected_calls, paired):
    calls, replies = [], list(replies)

    def fake_run_adb(*args, **kwargs):
        calls.append(args[0])
        if args[0] == "pair":
            out, err = replies.pop(0)
            return out, err, 0 if out.startswith("Success") else 1
        return "", "", 0

    monkeypatch.setattr(run_toolkit, "run_adb", fake_run_adb)
    stdout, _ = run_toolkit.adb_pair("1.2.3.4:37000", "123456")
    assert calls == expected_calls
    assert run_toolkit.pair_succeeded(stdout) is paired
