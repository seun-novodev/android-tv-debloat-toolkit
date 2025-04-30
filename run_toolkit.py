import os
import PySimpleGUI as sg

connected = False
tv_ip = ""

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
    ("Freeview On Now", "uk.co.freeview.onnow")
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
    ("TCL Framework Core", "com.tcl.framework.custom", "🚫")
]

def connect_to_tv():
    global connected, tv_ip
    layout = [[sg.Text('Enter TV IP Address:')], [sg.InputText(key='IP')],
              [sg.Button('Connect'), sg.Button('Cancel')]]
    window = sg.Window('Connect to TV', layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        if event == 'Connect':
            tv_ip = values['IP']
            result = os.popen(f'adb connect {tv_ip}').read()
            if "connected" in result or "already connected" in result:
                connected = True
                sg.popup('✅ Connected successfully!')
            else:
                sg.popup('❌ Failed to connect. Check your TV IP and ADB Debugging settings.')
            break
    window.close()

def install_apk():
    if not connected:
        sg.popup('Connect to a TV first!')
        return
    layout = [[sg.Text('Select APK to install:')], [sg.Input(), sg.FileBrowse(file_types=(("APK Files", "*.apk"),))],
              [sg.Button('Install'), sg.Button('Cancel')]]
    window = sg.Window('Install APK', layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        if event == 'Install':
            apk_path = values[0]
            if not apk_path:
                sg.popup('No file selected.')
                continue
            push_result = os.popen(f'adb -s {tv_ip}:5555 push "{apk_path}" /sdcard/').read()
            install_result = os.popen(f'adb -s {tv_ip}:5555 shell pm install /sdcard/{os.path.basename(apk_path)}').read()
            result_text = f"Push Result:\n{push_result}\n\nInstall Result:\n{install_result}"
            sg.popup_scrolled(result_text, title="APK Install Log", size=(60, 20))
            break
    window.close()

def disable_google_launcher():
    if not connected:
        sg.popup('Connect to a TV first!')
        return
    result = os.popen(f'adb connect {tv_ip} && adb shell pm disable-user --user 0 com.google.android.tvlauncher').read()
    sg.popup_scrolled(result, title="Disable Launcher Result")

def safe_debloat_checklist():
    if not connected:
        sg.popup('Connect to a TV first!')
        return
    checkbox_layout = [[sg.Checkbox(label, key=package, default=True)] for label, package in safe_apps]
    layout = [
        [sg.Text('Select the safe apps you want to disable:')],
        [sg.Column(checkbox_layout, scrollable=True, size=(500, 400))],
        [sg.Button('Select All'), sg.Button('Deselect All')],
        [sg.Button('Apply Selected Changes'), sg.Button('Cancel')]
    ]
    window = sg.Window('Safe Debloat (Choose Apps)', layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        elif event == 'Select All':
            for _, package in safe_apps:
                window[package].update(value=True)
        elif event == 'Deselect All':
            for _, package in safe_apps:
                window[package].update(value=False)
        elif event == 'Apply Selected Changes':
            selected = [pkg for _, pkg in safe_apps if values[pkg]]
            if not selected:
                sg.popup('No apps selected.')
                continue
            output = ''
            for label, pkg in safe_apps:
                if pkg in selected:
                    result = os.popen(f'adb shell pm disable-user --user 0 {pkg}').read()
                    status = '✅ Success' if 'new state: disabled-user' in result else '⚠️ Already Disabled or Error'
                    output += f"Disabling {label} ({pkg})... {status}\n\n"
            output += "\nDebloating Completed!"
            sg.popup_scrolled(output, title="Safe Debloat Result", size=(60, 20))
            break
    window.close()

def advanced_debloat():
    if not connected:
        sg.popup('Connect to a TV first!')
        return
    checkbox_layout = [[sg.Checkbox(f'{risk} {label}', key=package)] for label, package, risk in apps]
    layout = [
        [sg.Text('Legend:  ✅ Safe   ⚠️ Caution   🚫 Critical', text_color='blue')],
        [sg.Column(checkbox_layout, scrollable=True, size=(500, 400))],
        [sg.Button('Select All Safe Apps'), sg.Button('Deselect All')],
        [sg.Button('Apply Selected Changes'), sg.Button('Cancel')]
    ]
    window = sg.Window('Advanced Debloat', layout)
    while True:
        event, values = window.read()
        if event in (sg.WINDOW_CLOSED, 'Cancel'):
            break
        elif event == 'Select All Safe Apps':
            for label, package, risk in apps:
                if risk == '✅':
                    window[package].update(value=True)
        elif event == 'Deselect All':
            for _, package, _ in apps:
                window[package].update(value=False)
        elif event == 'Apply Selected Changes':
            selected = [pkg for _, pkg, _ in apps if values[pkg]]
            if not selected:
                sg.popup('No apps selected.')
                continue
            output = ''
            for label, pkg, _ in apps:
                if pkg in selected:
                    result = os.popen(f'adb shell pm disable-user --user 0 {pkg}').read()
                    status = '✅ Success' if 'new state: disabled-user' in result else '⚠️ Already Disabled or Error'
                    output += f"Disabling {label} ({pkg})... {status}\n\n"
            output += "\nDebloating Completed!"
            sg.popup_scrolled(output, title="Advanced Debloat Result", size=(60, 20))
            break
    window.close()

def show_safe_debloat_list():
    safe_list = (
        "Apps disabled in Safe Debloat mode:\n"
        "- Android TV Recommendations\n"
        "- Google Play Movies\n"
        "- TCL Gallery, Dashboard, and Boot Ads\n"
        "- Netflix TV App\n"
        "- Chromecast receiver\n"
        "- TCL/Freeview region bloat\n"
        "...and more.\n"
    )
    sg.popup_scrolled(safe_list, title="Apps Disabled in Safe Debloat Mode", size=(80, 30))

def main_menu():
    layout = [
        [sg.Button('Connect to TV')],
        [sg.Button('Safe Debloat')],
        [sg.Button('Advanced Debloat')],
        [sg.Button('Install APK')],
        [sg.Button('Disable Google TV Launcher')],
        [sg.Button('View Safe Debloat App List')],
        [sg.Button('Exit')]
    ]
    window = sg.Window('Android TV Toolkit v1.1', layout)
    while True:
        event, _ = window.read()
        if event in (sg.WINDOW_CLOSED, 'Exit'):
            break
        elif event == 'Connect to TV':
            connect_to_tv()
        elif event == 'Safe Debloat':
            safe_debloat_checklist()
        elif event == 'Advanced Debloat':
            advanced_debloat()
        elif event == 'Install APK':
            install_apk()
        elif event == 'Disable Google TV Launcher':
            disable_google_launcher()
        elif event == 'View Safe Debloat App List':
            show_safe_debloat_list()
    window.close()

if __name__ == '__main__':
    main_menu()
