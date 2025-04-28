import PySimpleGUI as sg
import subprocess
import os

# Set ADB path
adb_path = os.path.join(os.getcwd(), "adb", "adb.exe")

# GUI Layout
layout = [
    [sg.Text('Android TV Toolkit', font=('Arial', 16))],
    [sg.Text('Enter TV IP Address:'), sg.Input(key='-IP-', size=(25,1)), sg.Button('Connect'), sg.Button('Check Connection')],
    [sg.HorizontalSeparator()],
    [sg.Button('Debloat TV - Safe Mode', size=(30,1))],
    [sg.Button('Debloat TV - Remove Recommendations Only', size=(30,1))],
    [sg.Button('Install APK to TV', size=(30,1))],
    [sg.HorizontalSeparator()],
    [sg.Button('Disable Google Launcher', size=(30,1))],
    [sg.Button('Reboot TV', size=(30,1))],
    [sg.HorizontalSeparator()],
    [sg.Output(size=(60,10))],
    [sg.Button('Exit')]
]

# Create window
window = sg.Window('Android TV Toolkit v1.0', layout, size=(500,600))

def adb_command(command):
    full_command = [adb_path] + command
    result = subprocess.run(full_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print(result.stdout)
    if result.stderr:
        print("ERROR:", result.stderr)

# Event Loop
while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED or event == 'Exit':
        break
    if event == 'Connect':
        ip = values['-IP-']
        adb_command(['connect', ip])
    if event == 'Check Connection':
        adb_command(['devices'])
    if event == 'Debloat TV - Safe Mode':
        adb_command(['push', 'scripts/debloat_safe.sh', '/sdcard/'])
        adb_command(['shell', 'sh /sdcard/debloat_safe.sh'])
    if event == 'Debloat TV - Remove Recommendations Only':
        adb_command(['push', 'scripts/debloat_minimal.sh', '/sdcard/'])
        adb_command(['shell', 'sh /sdcard/debloat_minimal.sh'])
    if event == 'Install APK to TV':
        apk_file = sg.popup_get_file('Select APK', file_types=(('APK Files', '*.apk'),))
        if apk_file:
            adb_command(['install', '-r', apk_file])
    if event == 'Disable Google Launcher':
        adb_command(['shell', 'pm', 'disable-user', '--user', '0', 'com.google.android.apps.tv.launcherx'])
        adb_command(['shell', 'pm', 'disable-user', '--user', '0', 'com.google.android.tvlauncher'])
    if event == 'Reboot TV':
        adb_command(['reboot'])

window.close()
