#!/bin/bash

set -e

echo -e "\n🚀 Starting setup..."

# Check for Python 3
if ! command -v python3 &> /dev/null; then
  echo -e "\n❌ Python 3 is not installed. Please install it and try again."
  exit 1
fi

# Create virtual environment if it doesn't exist
if [[ ! -d "venv" ]]; then
  echo -e "\n🐍 Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate

# Upgrade pip
echo -e "\n⬆️ Upgrading pip..."
pip install --upgrade pip > /dev/null

# Check and install required packages
required_packages=(pyinstaller textual rich)
missing_packages=()

for pkg in "${required_packages[@]}"; do
  if ! pip show "$pkg" &> /dev/null; then
    missing_packages+=("$pkg")
  fi
done

if [ ${#missing_packages[@]} -ne 0 ]; then
  echo -e "\n📦 Installing missing packages: ${missing_packages[*]}..."
  pip install "${missing_packages[@]}" > /dev/null
fi

# Clean previous builds
echo -e "\n🧹 Cleaning previous builds..."
rm -rf build dist gv_tui gv_cli

# Generate .spec files
echo -e "\n⚙️ Generating .spec files..."
mkdir -p specs

pyi-makespec --onefile --name gv_cli gv_cli.py --specpath specs

DASHBOARD_CSS_PATH="$(realpath dashboard.css)"
pyi-makespec --onefile --name gv_tui gv_tui.py \
  --add-data "${DASHBOARD_CSS_PATH}:." \
  --hidden-import textual.widgets._tab \
  --specpath specs

# Build executables
echo -e "\n🛠  Building executables into project root..."
pyinstaller --distpath . specs/gv_cli.spec
pyinstaller --distpath . specs/gv_tui.spec

# Detect shell config file
SHELL_NAME=$(basename "$SHELL")
case "$SHELL_NAME" in
  zsh)    SHELL_RC=~/.zshrc ;;
  bash)   SHELL_RC=~/.bashrc ;;
  *)      SHELL_RC="your shell's config file" ;;
esac

BIN_DIR="$(pwd)"

echo -e "\n✅ Build complete!"
echo -e "▶️ Run './gv_cli <subcommand>' or './gv_tui'\n"
echo -e "📍 To use these commands globally, add this to your $SHELL_RC:"
echo -e "   export PATH=\"$BIN_DIR:\$PATH\"\n"
echo -e "📌 Then run:"
echo -e "   source $SHELL_RC\n"
