import http.client
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import zlib

# The GUI needs Tk 8.6+. Some Python builds ship without Tk (Homebrew's on
# macOS) or with the old Tk 8.5 that hangs on modern macOS (Apple's
# /usr/bin/python3), so fail with a fix instead of a traceback or a freeze.
def _tk_problem():
    try:
        import tkinter
    except ImportError:
        return "This Python has no Tk (tkinter) support, which the toolkit needs."
    if tkinter.TkVersion < 8.6:
        return f"This Python uses Tk {tkinter.TkVersion}; the toolkit needs Tk 8.6 or newer."
    try:
        tkinter.Tcl()  # loads the Tcl runtime without opening a window
    except tkinter.TclError as e:
        return f"This Python's Tcl/Tk installation is broken ({e})."
    return None

_problem = _tk_problem()
if _problem:
    if sys.platform == "darwin":
        hint = ("Install Python from python.org (includes Tk), or with Homebrew run:\n"
                "  brew install python-tk")
    elif sys.platform.startswith("linux"):
        hint = "Install your distro's Tk package, e.g.: sudo apt install python3-tk"
    else:
        hint = "Reinstall Python from python.org and tick 'tcl/tk and IDLE'."
    sys.exit(f"{_problem}\n{hint}")

import FreeSimpleGUI as sg

IS_WINDOWS = sys.platform == "win32"
ADB_NAME = "adb.exe" if IS_WINDOWS else "adb"

# Common adb install locations that may be missing from PATH, e.g. when the
# app is launched from Finder/Dock on macOS (which uses a minimal PATH).
if IS_WINDOWS:
    EXTRA_ADB_DIRS = [
        os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~/AppData/Local")),
                     "Android", "Sdk", "platform-tools"),        # Android Studio
    ]
else:
    EXTRA_ADB_DIRS = [
        "/opt/homebrew/bin",                                        # Homebrew, Apple Silicon
        "/usr/local/bin",                                           # Homebrew, Intel Mac
        os.path.expanduser("~/Library/Android/sdk/platform-tools"),  # Android Studio, macOS
        os.path.expanduser("~/Android/Sdk/platform-tools"),          # Android Studio, Linux
    ]


def _app_dirs():
    """Folders that may hold a bundled adb/ folder."""
    if getattr(sys, "frozen", False):
        # PyInstaller: data bundled with --add-data unpacks to _MEIPASS; also
        # allow an adb/ folder placed next to the executable.
        return [d for d in (getattr(sys, "_MEIPASS", None),
                            os.path.dirname(os.path.abspath(sys.executable))) if d]
    return [os.path.dirname(os.path.abspath(__file__))]


# Resolve the adb executable, in order: ADB_PATH env var, the bundled adb/
# subfolder next to this script, then PATH plus common install locations.
def _find_adb():
    override = os.environ.get("ADB_PATH", "").strip()
    if override:
        override = os.path.expanduser(override)
        if os.path.isdir(override):
            override = os.path.join(override, ADB_NAME)
        # Use it even if it doesn't exist, so the error names the bad ADB_PATH.
        return override
    for app_dir in _app_dirs():
        local = os.path.join(app_dir, "adb", ADB_NAME)
        # On Windows also check it is a real program (old copies of this repo
        # shipped a 2-byte placeholder adb.exe).
        if os.path.isfile(local) and (not IS_WINDOWS or _is_windows_executable(local)):
            return local
    search_path = os.pathsep.join(p for p in [os.environ.get("PATH"), *EXTRA_ADB_DIRS] if p)
    return shutil.which("adb", path=search_path) or "adb"


def _adb_missing_hint():
    if sys.platform == "darwin":
        return "Install it with:  brew install --cask android-platform-tools"
    if IS_WINDOWS:
        return "Restart the toolkit to download it from Google, or put adb.exe in the adb/ folder next to it."
    return "Install it with your package manager, e.g.: sudo apt install adb"


PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
PLATFORM_TOOLS_PAGE = "https://developer.android.com/tools/releases/platform-tools"
ADB_FILES = ("adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll")
# Where a downloaded adb goes: next to the script, or next to the .exe when frozen.
ADB_DIR = os.path.join(_app_dirs()[-1], "adb")


def _is_windows_executable(path):
    # Every valid Windows executable starts with the "MZ" signature.
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


ADB = _find_adb()


def download_adb():
    """Download Google's Platform Tools and extract adb into the adb/ folder. Returns False if cancelled."""
    buffer = io.BytesIO()
    with urllib.request.urlopen(PLATFORM_TOOLS_URL, timeout=30) as response:
        total = int(response.headers.get("Content-Length", 0))
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            buffer.write(chunk)
            done = buffer.tell()
            if total and not sg.one_line_progress_meter(
                "Downloading ADB", done, total,
                f"Downloading ADB from Google... {done / 1e6:.1f} / {total / 1e6:.1f} MB",
                key="adb_download", orientation="h", keep_on_top=True,
            ) and done < total:
                return False

    os.makedirs(ADB_DIR, exist_ok=True)
    # Extract to temporary names and only then move into place, so a failed
    # download never leaves a half-written adb.exe that looks installed.
    with zipfile.ZipFile(buffer) as archive:
        for name in ADB_FILES:
            with archive.open(f"platform-tools/{name}") as src, open(os.path.join(ADB_DIR, name + ".part"), "wb") as dst:
                shutil.copyfileobj(src, dst)
    for name in ADB_FILES[::-1]:  # adb.exe last
        os.replace(os.path.join(ADB_DIR, name + ".part"), os.path.join(ADB_DIR, name))
    return True


def ensure_adb():
    """Offer a one-click ADB download when no working adb is available."""
    global ADB
    ADB = _find_adb()
    # A bad ADB_PATH is reported when adb is first used, naming the path.
    # (A file that exists but can't run is reported by run_adb, not as missing.)
    if os.path.isfile(ADB) or shutil.which(ADB) or os.environ.get("ADB_PATH", "").strip():
        return
    if not IS_WINDOWS:
        sg.popup(f"ADB was not found.\n\n{_adb_missing_hint()}", title="ADB Missing")
        return
    choice = sg.popup_yes_no(
        "This toolkit needs ADB, Google's official tool to talk to your TV.\n\n"
        "Download it now from Google (about 8 MB)?",
        title="ADB Required",
    )
    if choice != "Yes":
        return
    try:
        if not download_adb():
            return
    except (OSError, zipfile.BadZipFile, zlib.error, http.client.HTTPException, KeyError) as e:
        sg.one_line_progress_meter_cancel(key="adb_download")
        sg.popup(
            f"❌ ADB download failed: {e}\n\n"
            f"You can download Platform Tools manually from:\n{PLATFORM_TOOLS_PAGE}\n\n"
            "Then copy adb.exe, AdbWinApi.dll and AdbWinUsbApi.dll into the adb/ folder next to this toolkit.",
            title="Download Failed",
        )
        return
    ADB = _find_adb()
    sg.popup("✅ ADB is ready.", title="ADB Installed")


# Fix 3: Replace global mutable state with a simple state container
class TVConnection:
    def __init__(self):
        self.connected = False
        self.ip = ""
        self.port = "5555"

    @property
    def target(self):
        return f"{self.ip}:{self.port}"


state = TVConnection()


# Fix 2: IP address validation
def is_valid_ip(ip):
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip)) and all(
        0 <= int(p) <= 255 for p in ip.split(".")
    )


def is_valid_port(port):
    return port.isdigit() and 1 <= int(port) <= 65535


def parse_target(text, default_port="5555"):
    """Parse 'IP' or 'IP:port' into (ip, port), or None if invalid."""
    ip, _, port = text.strip().partition(":")
    port = port or default_port
    if is_valid_ip(ip) and is_valid_port(port):
        return ip, port
    return None


# --- adb output parsing -------------------------------------------------------
# adb's exit code is unreliable: `adb connect` exits 0 even when it fails, so
# these helpers read the output text instead.

def connect_succeeded(stdout, target):
    out = stdout.lower()
    if any(word in out for word in ("failed", "unable", "cannot", "refused")):
        return False
    return f"connected to {target}".lower() in out


def pair_succeeded(stdout):
    return "successfully paired to" in stdout.lower()


def device_status(devices_stdout, target):
    """State `adb devices` lists for target ('device', 'offline', 'unauthorized', ...), or None."""
    for line in devices_stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == target:
            return parts[1]
    return None


def device_online(devices_stdout, target):
    """True if `adb devices` lists target as 'device' (not offline/unauthorized)."""
    return device_status(devices_stdout, target) == "device"


def parse_packages(pm_list_stdout):
    """Parse `pm list packages` output into a set of package names."""
    return {
        line.strip()[len("package:"):]
        for line in pm_list_stdout.splitlines()
        if line.strip().startswith("package:")
    }


def first_error_line(text):
    """Pick the meaningful line out of adb/pm output, skipping Java stack frames."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if line.startswith(("at ", "Exception occurred while executing", "Performing ")):
            continue
        # "java.lang.IllegalArgumentException: Unknown package: x" -> "Unknown package: x"
        m = re.match(r"^(?:[\w$]+\.)+[\w$]*(?:Exception|Error): (.+)$", line)
        return m.group(1) if m else line
    return "Unknown error"


def adb_pair(target, code):
    """Pair with a Wireless debugging pairing port; returns (stdout, stderr).

    A long-running adb server sometimes fails every pairing attempt with
    "protocol fault (couldn't read status message)" until it is restarted, so
    restart it and try once more. The pairing code stays valid after a failure.
    """
    stdout, stderr, _ = run_adb("pair", target, code, timeout=30)
    if not pair_succeeded(stdout) and "protocol fault" in (stderr + stdout).lower():
        run_adb("kill-server")
        run_adb("start-server", timeout=30)
        stdout, stderr, _ = run_adb("pair", target, code, timeout=30)
    return stdout, stderr


def friendly_adb_error(text):
    """Explain common adb connection/pairing errors in plain words."""
    detail = first_error_line(text)
    low = text.lower()
    if "protocol fault" in low:
        return (f"{detail}\n\nThe pairing service didn't complete the handshake. Check the pairing "
                "port: it and the code change every time you open the pairing screen on the TV.")
    if "connection refused" in low:
        return f"{detail}\n\nThe TV refused the connection. Check that debugging is on and the port is right."
    if "timed out" in low or "no route to host" in low:
        return f"{detail}\n\nThe TV didn't answer. Check the IP and that both devices are on the same network."
    return detail


# Fix 1 & 6: Use subprocess (not os.popen), scope reconnect check to specific device
def run_adb(*args, timeout=15):
    """Run an adb command and return (stdout, stderr, returncode)."""
    # Without this, each adb call flashes a console window when run windowless on Windows.
    extra = {"creationflags": subprocess.CREATE_NO_WINDOW} if IS_WINDOWS else {}
    try:
        result = subprocess.run(
            [ADB, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            **extra,
        )
        # Drop adb's "* daemon not running; starting now" chatter.
        stderr = "\n".join(l for l in result.stderr.splitlines() if not l.startswith("* daemon"))
        return result.stdout, stderr, result.returncode
    except FileNotFoundError:
        return "", f"adb not found at '{ADB}'. {_adb_missing_hint()}", 1
    except OSError as e:
        # e.g. not executable, or wrong architecture
        return "", f"Could not run adb at '{ADB}': {e}", 1
    except subprocess.TimeoutExpired:
        return "", "ADB command timed out.", 1


AUTH_HINT = ("The TV hasn't authorised this computer yet. Accept the 'Allow debugging?' "
             "prompt on the TV (tick 'Always allow'), then connect again.")


def adb_connect(target):
    """Connect to target; returns (ok, detail). Allows for adb server cold start."""
    stdout, stderr, _ = run_adb("connect", target, timeout=30)
    if connect_succeeded(stdout, target):
        status = device_status(run_adb("devices")[0], target)
        if status == "device":
            return True, stdout.strip()
    else:
        status = None
    # adb keeps unauthorized/offline transports and then just says "already
    # connected", so drop it to force a fresh handshake on the next attempt.
    run_adb("disconnect", target)
    if status == "unauthorized" or "authenticate" in (stdout + stderr).lower():
        return False, AUTH_HINT
    if status:
        return False, f"The TV is listed as '{status}'. Check the TV is on and try again."
    return False, friendly_adb_error(stderr or stdout)


def reconnect_check():
    # Fix 6: scope device check to the connected target, not all devices
    if not state.connected or not state.ip:
        return False
    stdout, _, _ = run_adb("devices", timeout=30)
    if device_online(stdout, state.target):
        return True
    ok, _ = adb_connect(state.target)  # also confirms the device is online
    state.connected = ok
    return ok


def shell(*args, timeout=15):
    return run_adb("-s", state.target, "shell", *args, timeout=timeout)


class AdbError(Exception):
    pass


def package_state():
    """Return (enabled, disabled) package-name sets for user 0 on the connected TV.

    Raises AdbError if the TV can't be queried, so callers never mistake a
    failed query for "nothing installed".
    """
    sets = []
    for flag in ("-e", "-d"):
        stdout, stderr, rc = shell("pm", "list", "packages", flag, "--user", "0")
        if rc != 0:
            raise AdbError(f"Couldn't read the TV's app list: {first_error_line(stderr or stdout)}")
        sets.append(parse_packages(stdout))
    if not sets[0]:
        raise AdbError("Couldn't read the TV's app list: the TV reported no enabled apps.")
    return sets[0], sets[1]


safe_apps = [
    ("Android TV Recommendations", "com.google.android.tvrecommendations"),
    ("Google Shop Row", "com.google.android.leanbacklauncher.recommendations"),
    ("Chromecast Built-In", "com.google.android.gms.cast.receiver"),
    ("Google Backdrop", "com.google.android.backdrop"),
    ("Google Play Movies & TV", "com.google.android.videos"),
    ("Google Play Games", "com.google.android.play.games"),
    ("Google Mediashell", "com.google.android.apps.mediashell"),
    ("Google Smart Connect", "com.google.android.apps.nbu.smartconnect.tv"),
    ("Google Feedback", "com.google.android.feedback"),
    ("One-Time Initializer", "com.google.android.onetimeinitializer"),
    ("Calendar Sync Adapter", "com.google.android.syncadapters.calendar"),
    ("Google Partner Setup", "com.google.android.partnersetup"),
    ("Android Easter Egg", "com.android.egg"),
    ("Print Spooler", "com.android.printspooler"),
    ("TalkBack (Accessibility)", "com.google.android.marvin.talkback"),
    ("Android Screensaver", "com.android.dreams.basic"),
    ("Calendar Provider", "com.android.providers.calendar"),
    ("Contacts Provider", "com.android.providers.contacts"),
    ("User Dictionary", "com.android.providers.userdictionary"),
    ("TCL Gallery", "com.tcl.gallery"),
    ("TCL Notes & Reminders", "com.tcl.notereminder"),
    ("TCL MessageBox", "com.tcl.messagebox"),
    ("TCL Antivirus (Guard)", "com.tcl.guard"),
    ("TCL Antivirus Overlay", "com.tcl.tvweishi"),
    ("TCL App Market", "com.tcl.appmarket2"),
    ("TCL Stickers", "com.tcl.esticker"),
    ("TCL PVR Player", "com.tcl.pvr.pvrplayer"),
    ("TCL Video Player", "com.tcl.videoplayer"),
    ("TCL Overseas App Ads", "com.tcl.overseasappshow"),
    ("TCL Boot Ads", "com.tcl.bootadservice"),
    ("TCL Dashboard", "com.tcl.dashboard"),
    ("Netflix TV App", "com.netflix.ninja"),
    ("AOS TV", "com.aos.aostv"),
    ("Freeview Explore", "uk.co.freeview.explore"),
    ("Freeview On Now", "uk.co.freeview.onnow"),
]

apps = [
    ("Chromecast Built-In", "com.google.android.gms.cast.receiver", "✅"),
    ("Google Play Movies & TV", "com.google.android.videos", "✅"),
    ("Android TV Recommendations", "com.google.android.tvrecommendations", "✅"),
    ("TCL Launcher", "com.tcl.usercenter2", "✅"),
    ("TCL User Center", "com.tcl.usercenter", "✅"),
    ("TCL Web Browser", "com.tcl.browser", "✅"),
    ("Notes and Reminders", "com.tcl.notereminder", "✅"),
    ("Gallery App", "com.tcl.gallery", "✅"),
    ("Netflix TV App", "com.netflix.ninja", "✅"),
    ("Freeview Explore", "uk.co.freeview.explore", "✅"),
    ("AOS TV", "com.aos.aostv", "✅"),
    ("Google Assistant", "com.google.android.googlequicksearchbox", "⚠️"),
    ("Google Play Store", "com.android.vending", "⚠️"),
    ("YouTube for Android TV", "com.google.android.youtube.tv", "⚠️"),
    ("TCL HDMI Service", "com.tcl.tv", "⚠️"),
    ("TCL Setup Wizard", "com.tcl.initsetup", "⚠️"),
    ("TCL Multiscreen Interaction", "com.tcl.MultiScreenInteraction_TV", "⚠️"),
    ("System UI", "com.android.systemui", "🚫"),
    ("Google Play Services", "com.google.android.gms", "🚫"),
    ("TCL Framework Core", "com.tcl.framework.custom", "🚫"),
]


CRITICAL = "🚫"

# Home-screen apps this toolkit can disable, by platform.
GOOGLE_LAUNCHERS = [
    ("Google TV Home", "com.google.android.apps.tv.launcherx"),   # Google TV / Chromecast
    ("Android TV Home", "com.google.android.tvlauncher"),         # classic Android TV
]
# HOME handlers that are system fallbacks, not usable replacement launchers.
NON_LAUNCHER_HOMES = {
    "com.android.tv.settings",
    "com.android.settings",
    "com.google.android.tungsten.setupwraith",
    "com.google.android.apps.tv.launcherx",
    "com.google.android.tvlauncher",
}

DONE = "-ADB-DONE-"


def run_in_background(window, fn, status_key, message):
    """Run fn off the UI thread so the window stays responsive; result arrives as DONE."""
    for el in window.element_list():
        if isinstance(el, sg.Button):
            el.update(disabled=True)
    window[status_key].update(message)
    window.metadata = True  # busy: see should_close()
    window.perform_long_operation(fn, DONE)


def should_close(event, window):
    """Close on Cancel/X, but ignore the X while a background job is running."""
    if event == sg.WINDOW_CLOSE_ATTEMPTED_EVENT and window.metadata:
        return False
    return event in (sg.WINDOW_CLOSED, sg.WINDOW_CLOSE_ATTEMPTED_EVENT, "Cancel")


def pair_and_connect():
    """Android 11+ / Chromecast: pair with a code first, then connect."""
    layout = [
        [sg.Text("Step 1 — Pairing (TV: Developer options → Wireless debugging → Pair device with pairing code)")],
        [sg.Text("TV IP Address:"), sg.InputText(key="IP", size=(20, 1))],
        [sg.Text("Pairing Port: "), sg.InputText(key="PAIR_PORT", size=(10, 1))],
        [sg.Text("Pairing Code: "), sg.InputText(key="PAIR_CODE", size=(15, 1))],
        [sg.HorizontalSeparator()],
        [sg.Text("Step 2 — Connection port (shown under 'IP address & Port' on the Wireless debugging screen)")],
        [sg.Text("Debug Port:   "), sg.InputText(key="DEBUG_PORT", size=(10, 1))],
        [sg.Button("Pair & Connect"), sg.Button("Cancel")],
    ]
    window = sg.Window("Pair & Connect (Android 11+ / Chromecast)", layout, modal=True)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
        if event == "Pair & Connect":
            ip = values["IP"].strip()
            pair_port = values["PAIR_PORT"].strip()
            pair_code = values["PAIR_CODE"].strip()
            debug_port = values["DEBUG_PORT"].strip()

            if not is_valid_ip(ip):
                sg.popup("❌ Invalid IP address. Enter a valid IPv4 address (e.g. 192.168.1.100).")
                continue
            if not is_valid_port(pair_port) or not is_valid_port(debug_port):
                sg.popup("❌ Enter both ports as numbers between 1 and 65535.\n\n"
                         "Wireless debugging uses a different, random port for pairing and for connecting.")
                continue
            if not pair_code:
                sg.popup("❌ Pairing code cannot be empty.")
                continue

            # Step 1: pair
            stdout, stderr = adb_pair(f"{ip}:{pair_port}", pair_code)
            if not pair_succeeded(stdout):
                sg.popup(f"❌ Pairing failed.\n\n{friendly_adb_error(stderr or stdout)}\n\n"
                         "Check the IP, port, and code shown on your TV.")
                continue

            # Step 2: connect
            state.ip, state.port = ip, debug_port
            ok, detail = adb_connect(state.target)
            state.connected = ok
            if ok:
                sg.popup(f"✅ Paired and connected to {state.target} successfully!")
            else:
                sg.popup(f"⚠️ Paired OK but connection failed.\n\n{detail}\n\n"
                         "Check the debug port shown under 'IP address & Port' on your TV.")
            break
    window.close()


def connect_to_tv():
    layout = [
        [sg.Text("Enter TV IP Address (add :port if it isn't 5555, e.g. 192.168.1.100:5555):")],
        [sg.InputText(key="IP")],
        [sg.Button("Connect"), sg.Button("Cancel")],
    ]
    window = sg.Window("Connect to TV", layout, modal=True)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
        if event == "Connect":
            # Fix 2: validate IP before using it in any command
            parsed = parse_target(values["IP"])
            if not parsed:
                sg.popup("❌ Invalid address. Enter an IPv4 address (e.g. 192.168.1.100), "
                         "optionally with a port (e.g. 192.168.1.100:5555).")
                continue
            # Always set the port too, so one from an earlier Pair & Connect isn't reused.
            state.ip, state.port = parsed
            ok, detail = adb_connect(state.target)
            state.connected = ok
            if ok:
                sg.popup(f"✅ Connected to {state.target} successfully!")
            else:
                sg.popup(f"❌ Failed to connect.\n\n{detail}\n\n"
                         "If the TV shows an 'Allow USB debugging?' prompt, accept it and try again.")
            break
    window.close()


def install_apk():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    layout = [
        [sg.Text("Select APK to install:")],
        [sg.Input(key="APK"), sg.FileBrowse(file_types=(("APK Files", "*.apk"),))],
        [sg.Text("", key="-STATUS-", size=(50, 1))],
        [sg.Button("Install"), sg.Button("Cancel")],
    ]
    window = sg.Window("Install APK", layout, modal=True, enable_close_attempted_event=True)
    while True:
        event, values = window.read()
        if should_close(event, window):
            break
        if event == "Install":
            apk_path = values["APK"].strip()
            if not apk_path:
                sg.popup("No file selected.")
                continue
            if not os.path.isfile(apk_path):
                sg.popup(f"❌ File not found:\n{apk_path}")
                continue
            # `adb install` streams the APK from this computer. The old push to
            # /sdcard + `pm install` fails on Android 11+ and broke on spaces.
            run_in_background(
                window,
                lambda: run_adb("-s", state.target, "install", "-r", apk_path, timeout=600),
                "-STATUS-", "Installing… large APKs can take a few minutes over Wi-Fi.")
        elif event == DONE:
            stdout, stderr, rc = values[DONE]
            if rc == 0 and "Success" in stdout:
                sg.popup_scrolled(stdout.strip(), title="✅ APK Installed", size=(60, 10))
            else:
                sg.popup_scrolled(first_error_line(stderr or stdout), title="❌ APK Install Failed", size=(60, 10))
            break
    window.close()


def _home_activities():
    """Packages that can act as the Home screen on the connected TV."""
    stdout, _, _ = shell("cmd", "package", "query-activities", "--brief",
                         "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME")
    return {line.strip().split("/")[0] for line in stdout.splitlines() if "/" in line}


def disable_google_launcher():
    if not reconnect_check():
        sg.popup("❌ TV not connected. Use 'Connect to TV' first.")
        return
    enabled, disabled = package_state()
    targets = [(label, pkg) for label, pkg in GOOGLE_LAUNCHERS if pkg in enabled]
    if not targets:
        sg.popup("ℹ️ No enabled Google launcher found — it may already be disabled.")
        return
    # Refuse unless another launcher is installed, so the TV isn't left without a Home screen.
    alternatives = sorted(_home_activities() - NON_LAUNCHER_HOMES)
    if not alternatives:
        sg.popup("❌ No other launcher is installed.\n\n"
                 "Install a launcher such as FLauncher first (Install APK), otherwise "
                 "the TV will have no Home screen.")
        return
    names = "\n".join(f"  • {label} ({pkg})" for label, pkg in targets)
    if sg.popup_yes_no(f"This will disable:\n{names}\n\nOther launcher(s) found:\n  • "
                       + "\n  • ".join(alternatives)
                       + "\n\nYou can undo this with 'Re-enable Apps'. Continue?",
                       title="Disable Google Launcher") != "Yes":
        return
    output = _run_debloat(targets, enabled, disabled)
    sg.popup_scrolled(output, title="Disable Google Launcher Result", size=(60, 10))


def _run_debloat(app_list, enabled, disabled):
    """Shared debloat logic: disables each package and returns a result string.

    enabled/disabled come from package_state(), read once before the run.
    """
    output_lines = []
    for label, pkg in app_list:
        if pkg in disabled:
            status = "⚠️ Already disabled"
        elif pkg not in enabled:
            status = "⏭️ Not installed — skipped"
        else:
            stdout, stderr, rc = shell("pm", "disable-user", "--user", "0", pkg)
            if rc == 0 and "new state: disabled" in stdout:
                status = "✅ Disabled"
            elif "SecurityException" in stderr + stdout:
                status = "🔒 Protected by Android — can't be disabled over ADB"
            else:
                status = f"❌ Error — {first_error_line(stderr or stdout)}"
        output_lines.append(f"{label} ({pkg}): {status}")
    output_lines.append("\nDebloating complete.")
    return "\n".join(output_lines)


def _debloat_window(title, header, entries, preselect):
    """Checklist of (label, pkg, risk) that disables the selected packages.

    preselect(risk) -> bool decides each installed app's initial tick.
    """
    enabled, disabled = package_state()

    def suffix(pkg):
        if pkg in disabled:
            return "  (already disabled)"
        if pkg not in enabled:
            return "  (not installed)"
        return ""

    def available(pkg):
        return pkg in enabled

    checkbox_layout = [
        [sg.Checkbox(f"{risk + ' ' if risk else ''}{label}{suffix(pkg)}", key=pkg,
                     default=available(pkg) and preselect(risk), disabled=not available(pkg))]
        for label, pkg, risk in entries
    ]
    layout = [
        *header,
        [sg.Column(checkbox_layout, scrollable=True, vertical_scroll_only=True, size=(500, 400))],
        [sg.Button("Select All Safe Apps"), sg.Button("Deselect All")],
        [sg.Text("", key="-STATUS-", size=(50, 1))],
        [sg.Button("Apply Selected Changes"), sg.Button("Cancel")],
    ]
    window = sg.Window(title, layout, modal=True, enable_close_attempted_event=True,
                       size=(560, 500), resizable=True)
    while True:
        event, values = window.read()
        if should_close(event, window):
            break
        elif event == "Select All Safe Apps":
            for _, pkg, risk in entries:
                if available(pkg):
                    window[pkg].update(value=risk in ("", "✅"))
        elif event == "Deselect All":
            for _, pkg, _ in entries:
                window[pkg].update(value=False)
        elif event == "Apply Selected Changes":
            selected = [(lbl, pkg) for lbl, pkg, _ in entries if values.get(pkg)]
            if not selected:
                sg.popup("No apps selected.")
                continue
            critical = [lbl for lbl, pkg, risk in entries if values.get(pkg) and risk == CRITICAL]
            if critical and sg.popup_yes_no(
                    "⚠️ You selected CRITICAL system apps:\n  • " + "\n  • ".join(critical)
                    + "\n\nDisabling these can stop the TV from working. Continue anyway?",
                    title="Critical apps selected") != "Yes":
                continue
            run_in_background(window, lambda: _run_debloat(selected, enabled, disabled),
                              "-STATUS-", f"Disabling {len(selected)} app(s)…")
        elif event == DONE:
            sg.popup_scrolled(values[DONE], title=f"{title} Result", size=(60, 20))
            break
    window.close()


def safe_debloat_checklist():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    _debloat_window(
        "Safe Debloat (Choose Apps)",
        [[sg.Text("Select the safe apps you want to disable:")]],
        [(label, pkg, "") for label, pkg in safe_apps],
        preselect=lambda risk: True,
    )


def advanced_debloat():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    _debloat_window(
        "Advanced Debloat",
        [[sg.Text("Legend:  ✅ Safe   ⚠️ Caution   🚫 Critical")]],
        apps,
        preselect=lambda risk: False,
    )


def reenable_apps():
    """List disabled packages and re-enable the selected ones (undo for debloat)."""
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    _, disabled = package_state()
    if not disabled:
        sg.popup("ℹ️ No disabled apps found on this TV.")
        return
    known = {pkg: label for label, pkg in safe_apps}
    known.update({pkg: label for label, pkg, _ in apps})
    known.update({pkg: label for label, pkg in GOOGLE_LAUNCHERS})
    ordered = sorted(disabled, key=lambda p: (p not in known, p))

    def name(pkg):
        return f"{known[pkg]} ({pkg})" if pkg in known else pkg

    checkbox_layout = [[sg.Checkbox(name(pkg), key=pkg)] for pkg in ordered]
    layout = [
        [sg.Text("Disabled apps on this TV (apps this toolkit knows are listed first):")],
        [sg.Column(checkbox_layout, scrollable=True, vertical_scroll_only=True, size=(560, 400))],
        [sg.Text("", key="-STATUS-", size=(50, 1))],
        [sg.Button("Re-enable Selected"), sg.Button("Cancel")],
    ]
    window = sg.Window("Re-enable Apps", layout, modal=True, enable_close_attempted_event=True)

    def enable(pkgs):
        lines = []
        for pkg in pkgs:
            stdout, stderr, rc = shell("pm", "enable", "--user", "0", pkg)
            if rc == 0 and "new state: enabled" in stdout:
                status = "✅ Enabled"
            elif "SecurityException" in stderr + stdout:
                status = "🔒 Protected by Android — disabled by the system, can't be changed over ADB"
            else:
                status = f"❌ Error — {first_error_line(stderr or stdout)}"
            lines.append(f"{name(pkg)}: {status}")
        return "\n".join(lines)

    while True:
        event, values = window.read()
        if should_close(event, window):
            break
        if event == "Re-enable Selected":
            selected = [pkg for pkg in ordered if values.get(pkg)]
            if not selected:
                sg.popup("No apps selected.")
                continue
            run_in_background(window, lambda: enable(selected), "-STATUS-",
                              f"Re-enabling {len(selected)} app(s)…")
        elif event == DONE:
            sg.popup_scrolled(values[DONE], title="Re-enable Result", size=(60, 20))
            break
    window.close()


def reboot_tv():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    if sg.popup_yes_no(f"Reboot the TV at {state.target} now?", title="Reboot TV") != "Yes":
        return
    _, stderr, rc = run_adb("-s", state.target, "reboot", timeout=30)
    state.connected = False
    if rc == 0:
        sg.popup("✅ Reboot command sent. Reconnect once the TV is back on.\n\n"
                 "Android 11+ / Chromecast: a reboot turns Wireless debugging off and "
                 "changes its port, so turn it back on and use Pair & Connect again.")
    else:
        sg.popup(f"❌ Reboot failed.\n\n{first_error_line(stderr)}")


def show_safe_debloat_list():
    lines = ["Apps disabled in Safe Debloat mode:\n"]
    for label, package in safe_apps:
        lines.append(f"  • {label}  ({package})")
    sg.popup_scrolled("\n".join(lines), title="Apps Disabled in Safe Debloat Mode", size=(80, 30))


def _status_text():
    return f"Connected: {state.target}" if state.connected else "Not connected"


def main_menu():
    ensure_adb()
    actions = {
        "Connect to TV": connect_to_tv,
        "Pair & Connect (Android 11+ / Chromecast)": pair_and_connect,
        "Safe Debloat": safe_debloat_checklist,
        "Advanced Debloat": advanced_debloat,
        "Re-enable Apps": reenable_apps,
        "Install APK": install_apk,
        "Disable Google TV Launcher": disable_google_launcher,
        "Reboot TV": reboot_tv,
        "View Safe Debloat App List": show_safe_debloat_list,
    }
    layout = [
        [sg.Text(_status_text(), key="-CONN-", size=(36, 1))],
        *[[sg.Button(name)] for name in actions],
        [sg.Button("Exit")],
    ]
    window = sg.Window("Android TV Toolkit v1.3", layout, finalize=True)
    # Start the adb server now so the first real command doesn't pay the start-up delay.
    window.perform_long_operation(lambda: run_adb("start-server", timeout=30), "-ADB-READY-")
    while True:
        event, _ = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break
        if event in actions:
            try:
                actions[event]()
            except AdbError as e:
                sg.popup(f"❌ {e}\n\nCheck the TV is still on and connected, then try again.")
        window["-CONN-"].update(_status_text())
    window.close()


if __name__ == "__main__":
    main_menu()
