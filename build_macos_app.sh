#!/bin/bash
# Build "Android TV Toolkit.app" with PyInstaller (optional — most people
# should just double-click run_toolkit.command).
#
#   ./build_macos_app.sh            → dist/Android TV Toolkit.app
#
# The app is built for this Mac's architecture (Apple Silicon or Intel). It is
# ad-hoc signed, not notarised: it runs on the Mac that built it; copied to
# another Mac, Gatekeeper blocks it until you run
#   xattr -cr "/Applications/Android TV Toolkit.app"
# adb is not bundled — install it with: brew install --cask android-platform-tools
set -euo pipefail
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Reuse the environment run_toolkit.command sets up, and make sure its Python
# has a working Tk 8.6+ — otherwise the app would silently quit on launch.
if ! .venv/bin/python -c 'import tkinter, sys; tkinter.Tcl(); sys.exit(tkinter.TkVersion < 8.6)' >/dev/null 2>&1; then
    echo "No working .venv yet — run ./run_toolkit.command once first (it sets up Python with Tk)." >&2
    exit 1
fi

.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller
rm -rf build "dist/Android TV Toolkit.app"
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed \
    --name "Android TV Toolkit" \
    --osx-bundle-identifier io.github.nasd223.atvtoolkit \
    run_toolkit.py

# PyInstaller ad-hoc signs on Apple Silicon; re-sign the finished bundle so the
# signature covers everything (needed for it to launch on arm64).
codesign --force --deep --sign - "dist/Android TV Toolkit.app"

echo
echo "✅ Built: dist/Android TV Toolkit.app ($(uname -m))"
echo "   Drag it to Applications, or double-click it here."
