#!/bin/bash

set -e

# Python version check
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install it and try again."
    exit 1
fi

# Create venv if it doesn't exist
if [[ ! -d "venv" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

pip install --upgrade pip > /dev/null
pip install rich textual > /dev/null

# Install pyinstaller if not installed
if ! pip show pyinstaller &> /dev/null; then
  echo "🔧 Installing pyinstaller..."
  pip install pyinstaller > /dev/null
fi

rm -rf build gv_tui.spec gv_cli.spec gv_tui gv_cli

pyinstaller --onefile --name gv_cli --distpath . gv_cli.py
pyinstaller --onefile --name gv_tui --distpath . --add-data "dashboard.css:." --hidden-import textual.widgets._tab gv_tui.py

echo ""
echo "✅ Build complete! You can now run ./gv_cli or ./gv_tui"
echo ""
