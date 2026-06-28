import os
import re
import subprocess
import sys
import PySimpleGUI as sg

# Resolve the adb executable: prefer the bundled adb/ subfolder next to this
# script so users don't need ADB on their system PATH.
def _find_adb():
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    local = os.path.join(script_dir, "adb", "adb.exe")
    return local if os.path.isfile(local) else "adb"

ADB = _find_adb()


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


# Fix 1 & 6: Use subprocess (not os.popen), scope reconnect check to specific device
def run_adb(*args):
    """Run an adb command and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            [ADB, *args],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout, result.stderr, result.returncode
    except FileNotFoundError:
        return "", f"adb not found at '{ADB}'. Make sure the adb/ folder is present next to this script.", 1
    except subprocess.TimeoutExpired:
        return "", "ADB command timed out.", 1


def reconnect_check():
    # Fix 6: scope device check to the connected target, not all devices
    if not state.connected or not state.ip:
        return False
    stdout, _, _ = run_adb("devices")
    if state.target not in stdout:
        stdout, _, rc = run_adb("connect", state.target)
        if rc == 0 and ("connected" in stdout or "already connected" in stdout):
            return True
        state.connected = False
        return False
    return True


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


def connect_to_tv():
    layout = [
        [sg.Text("Enter TV IP Address:")],
        [sg.InputText(key="IP")],
        [sg.Button("Connect"), sg.Button("Cancel")],
    ]
    window = sg.Window("Connect to TV", layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
        if event == "Connect":
            ip = values["IP"].strip()
            # Fix 2: validate IP before using it in any command
            if not is_valid_ip(ip):
                sg.popup("❌ Invalid IP address. Please enter a valid IPv4 address (e.g. 192.168.1.100).")
                continue
            state.ip = ip
            # Fix 1: subprocess with list args — no shell, no injection
            stdout, stderr, rc = run_adb("connect", state.target)
            # Fix 5: check return code, not just string content
            if rc == 0 and ("connected" in stdout or "already connected" in stdout):
                state.connected = True
                sg.popup(f"✅ Connected to {state.target} successfully!")
            else:
                state.connected = False
                detail = stderr.strip() or stdout.strip() or "Unknown error"
                sg.popup(f"❌ Failed to connect.\n\n{detail}\n\nCheck your TV IP and ADB Debugging settings.")
            break
    window.close()


def install_apk():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    layout = [
        [sg.Text("Select APK to install:")],
        [sg.Input(), sg.FileBrowse(file_types=(("APK Files", "*.apk"),))],
        [sg.Button("Install"), sg.Button("Cancel")],
    ]
    window = sg.Window("Install APK", layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
        if event == "Install":
            apk_path = values[0]
            if not apk_path:
                sg.popup("No file selected.")
                continue
            remote_path = f"/sdcard/{os.path.basename(apk_path)}"
            # Fix 1 & 4: subprocess list args; Fix 4: use state.target (consistent port)
            push_out, push_err, push_rc = run_adb("-s", state.target, "push", apk_path, "/sdcard/")
            install_out, install_err, install_rc = run_adb(
                "-s", state.target, "shell", "pm", "install", "-r", remote_path
            )
            # Fix 5: surface errors clearly
            lines = []
            lines.append(f"Push {'✅ OK' if push_rc == 0 else '❌ Failed'}:")
            lines.append(push_out or push_err)
            lines.append(f"\nInstall {'✅ OK' if install_rc == 0 else '❌ Failed'}:")
            lines.append(install_out or install_err)
            sg.popup_scrolled("\n".join(lines), title="APK Install Log", size=(60, 20))
            break
    window.close()


def disable_google_launcher():
    if not reconnect_check():
        sg.popup("❌ TV not connected. Use 'Connect to TV' first.")
        return
    # Fix 1: subprocess list args
    stdout, stderr, rc = run_adb(
        "-s", state.target, "shell", "pm", "disable-user", "--user", "0",
        "com.google.android.tvlauncher"
    )
    # Fix 5: report outcome clearly
    result = stdout or stderr or "No output received."
    title = "✅ Launcher Disabled" if rc == 0 else "❌ Disable Failed"
    sg.popup_scrolled(result, title=title)


def _run_debloat(app_list):
    """Shared debloat logic: disables each package and returns a result string."""
    output_lines = []
    for label, pkg in app_list:
        stdout, stderr, rc = run_adb(
            "-s", state.target, "shell", "pm", "disable-user", "--user", "0", pkg
        )
        # Fix 5: use return code, not fragile string matching
        if rc == 0 and "new state: disabled" in stdout:
            status = "✅ Disabled"
        elif "already" in stdout.lower() or "already" in stderr.lower():
            status = "⚠️ Already disabled"
        elif rc != 0:
            detail = (stderr or stdout).strip()
            status = f"❌ Error — {detail}"
        else:
            status = f"⚠️ Unexpected response — {stdout.strip()}"
        output_lines.append(f"{label} ({pkg}): {status}")
    output_lines.append("\nDebloating complete.")
    return "\n".join(output_lines)


def safe_debloat_checklist():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    checkbox_layout = [
        [sg.Checkbox(label, key=package, default=True)] for label, package in safe_apps
    ]
    layout = [
        [sg.Text("Select the safe apps you want to disable:")],
        [sg.Column(checkbox_layout, scrollable=True, size=(500, 400))],
        [sg.Button("Select All"), sg.Button("Deselect All")],
        [sg.Button("Apply Selected Changes"), sg.Button("Cancel")],
    ]
    window = sg.Window("Safe Debloat (Choose Apps)", layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
        elif event == "Select All":
            for _, package in safe_apps:
                window[package].update(value=True)
        elif event == "Deselect All":
            for _, package in safe_apps:
                window[package].update(value=False)
        elif event == "Apply Selected Changes":
            selected = [(lbl, pkg) for lbl, pkg in safe_apps if values[pkg]]
            if not selected:
                sg.popup("No apps selected.")
                continue
            output = _run_debloat(selected)
            sg.popup_scrolled(output, title="Safe Debloat Result", size=(60, 20))
            break
    window.close()


def advanced_debloat():
    if not reconnect_check():
        sg.popup("❌ Not connected. Use 'Connect to TV' first.")
        return
    checkbox_layout = [
        [sg.Checkbox(f"{risk} {label}", key=package)] for label, package, risk in apps
    ]
    layout = [
        [sg.Text("Legend:  ✅ Safe   ⚠️ Caution   🚫 Critical", text_color="blue")],
        [sg.Column(checkbox_layout, scrollable=True, size=(500, 400))],
        [sg.Button("Select All Safe Apps"), sg.Button("Deselect All")],
        [sg.Button("Apply Selected Changes"), sg.Button("Cancel")],
    ]
    window = sg.Window("Advanced Debloat", layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, "Cancel"):
            break
        elif event == "Select All Safe Apps":
            for label, package, risk in apps:
                if risk == "✅":
                    window[package].update(value=True)
        elif event == "Deselect All":
            for _, package, _ in apps:
                window[package].update(value=False)
        elif event == "Apply Selected Changes":
            selected = [(lbl, pkg) for lbl, pkg, _ in apps if values[pkg]]
            if not selected:
                sg.popup("No apps selected.")
                continue
            output = _run_debloat(selected)
            sg.popup_scrolled(output, title="Advanced Debloat Result", size=(60, 20))
            break
    window.close()


def show_safe_debloat_list():
    lines = ["Apps disabled in Safe Debloat mode:\n"]
    for label, package in safe_apps:
        lines.append(f"  • {label}  ({package})")
    sg.popup_scrolled("\n".join(lines), title="Apps Disabled in Safe Debloat Mode", size=(80, 30))


def main_menu():
    layout = [
        [sg.Button("Connect to TV")],
        [sg.Button("Safe Debloat")],
        [sg.Button("Advanced Debloat")],
        [sg.Button("Install APK")],
        [sg.Button("Disable Google TV Launcher")],
        [sg.Button("View Safe Debloat App List")],
        [sg.Button("Exit")],
    ]
    window = sg.Window("Android TV Toolkit v1.2", layout)
    while True:
        event, _ = window.read()
        if event in (sg.WINDOW_CLOSED, "Exit"):
            break
        elif event == "Connect to TV":
            connect_to_tv()
        elif event == "Safe Debloat":
            safe_debloat_checklist()
        elif event == "Advanced Debloat":
            advanced_debloat()
        elif event == "Install APK":
            install_apk()
        elif event == "Disable Google TV Launcher":
            disable_google_launcher()
        elif event == "View Safe Debloat App List":
            show_safe_debloat_list()
    window.close()


if __name__ == "__main__":
    main_menu()
