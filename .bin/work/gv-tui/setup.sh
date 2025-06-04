#!/bin/bash

set -e

# Python version check
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Please install it and try again."
    exit 1
fi

# Create venv if it doesn't exist
if [[ ! -d "gv_tui_venv" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv gv_tui_venv
fi

source gv_tui_venv/bin/activate

pip install --upgrade pip &> /dev/null

echo "Installing python requirements..."
pip install -r requirements.txt &> /dev/null

echo ""
echo "Setup complete. Run the app with:"
echo ""
echo "source gv_tui_venv/bin/activate && python3 gv_tui.py"
