#!/bin/bash
# macOS launcher: double-click in Finder (or run ./run_toolkit.command).
# First run creates a private Python environment in .venv and installs the
# requirements; later runs start straight away.
set -euo pipefail
cd "$(dirname "$0")"

# Finder starts .command files with a minimal PATH; add Homebrew's.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

fail() {
    echo
    echo "❌ $1"
    echo
    # Keep the Terminal window open so the message can be read.
    if [[ -t 0 ]]; then read -r -p "Press Return to close this window." _ || true; fi
    exit 1
}

# A Python 3.8+ whose Tk is 8.6 or newer and whose Tcl runtime actually loads
# (Apple's /usr/bin/python3 has Tk 8.5, which freezes; Homebrew's python needs
# python-tk installed).
tk_ok() {
    "$1" -c 'import sys, tkinter; tkinter.Tcl(); sys.exit(not (sys.version_info >= (3, 8) and tkinter.TkVersion >= 8.6))' >/dev/null 2>&1
}

find_python() {
    local name py
    local names=(python3.14 python3.13 python3.12 python3.11 python3.10 python3.9 python3.8 python3)
    # python.org's installer first, then every match on PATH (not just the first,
    # so a Tk-less Homebrew python can't hide a working one later on PATH).
    for py in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
              $(for name in "${names[@]}"; do type -a -P "$name" 2>/dev/null || true; done); do
        [[ -x "$py" && "$py" != "$PWD/.venv/"* ]] || continue
        if tk_ok "$py"; then
            echo "$py"
            return 0
        fi
    done
    return 1
}

# The environment is healthy if its Python runs with Tk and still has pip
# (a Python upgrade or a moved folder can break it).
venv_ok() {
    [[ -x .venv/bin/python ]] && tk_ok .venv/bin/python && .venv/bin/python -m pip --version >/dev/null 2>&1
}

if ! venv_ok; then
    PY=$(find_python) || fail "No Python with Tk 8.6+ found.
   Install Python from https://www.python.org/downloads/ (includes Tk),
   or with Homebrew run:  brew install python python-tk"
    echo "Setting up the toolkit's Python environment using $PY ..."
    rm -rf .venv
    "$PY" -m venv .venv || fail "Couldn't create the Python environment."
fi

# Install requirements on first run, whenever requirements.txt changes, or if
# the library has gone missing.
if ! cmp -s requirements.txt .venv/.requirements-installed 2>/dev/null \
   || ! .venv/bin/python -c 'import FreeSimpleGUI' >/dev/null 2>&1; then
    echo "Installing requirements ..."
    .venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt \
        || fail "Couldn't install the requirements (are you online?)."
    cp requirements.txt .venv/.requirements-installed
fi

# Same places the app looks (see _find_adb in run_toolkit.py).
if [[ -z "${ADB_PATH:-}" ]] && ! command -v adb >/dev/null 2>&1 \
   && [[ ! -x "$HOME/Library/Android/sdk/platform-tools/adb" && ! -x adb/adb ]]; then
    echo "⚠️  adb not found. Install it with:  brew install --cask android-platform-tools"
    echo "   (The toolkit will open, but can't talk to your TV until adb is installed.)"
fi

exec .venv/bin/python run_toolkit.py
