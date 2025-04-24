#!/usr/bin/env zsh

# Spinner function
spinner() {
  local pid=$!
  local spin='-\|/'
  local i=0
  while kill -0 $pid 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r      ⏳ %s" "${spin:$i:1}"
    sleep 0.1
  done
  printf "\r      ✅ Done\n"
}

# Run with spinner wrapper
run_with_spinner() {
  local msg="$1"
  shift
  echo -n "      ⏳ $msg..."
  "$@" &> /dev/null &
  spinner
}

echo "🍺 Setting up Homebrew..."
# Install Homebrew if it isn't already installed
if ! command -v brew &>/dev/null; then
    echo "      🛠️ Homebrew not installed. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo "      ✅ Homebrew installed!"

    # Attempt to set up Homebrew PATH automatically for this session
    if [ -x "/opt/homebrew/bin/brew" ]; then
        # For Apple Silicon Macs
        echo "      🛠️ Configuring Homebrew in PATH for Apple Silicon Mac..."
        export PATH="/opt/homebrew/bin:$PATH"
        echo "      ✅ Homebrew is in path /opt/homebrew/bin:$PATH"
    fi
else
    echo "      ✅ Homebrew is already installed."
fi

# Run these commands in your terminal to add Homebrew to your PATH:
#    echo >> $HOME/.zprofile
#    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> $HOME/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"

# Verify brew is now accessible
if ! command -v brew &>/dev/null; then
    echo "      ❌ Failed to configure Homebrew in PATH. Please add Homebrew to your PATH manually."
    exit 1
fi

# Get the path to Homebrew's zsh
BREW_ZSH="$(brew --prefix)/bin/zsh"
# Check if Homebrew's zsh is already the default shell
if [ "$SHELL" != "$BREW_ZSH" ]; then
    echo "      🛠️  Changing default shell to Homebrew zsh"
    # Check if Homebrew's zsh is already in allowed shells
    if ! grep -Fxq "$BREW_ZSH" /etc/shells; then
        echo "      🛠️  Adding Homebrew zsh to allowed shells..."
        echo "      $BREW_ZSH" | sudo tee -a /etc/shells >/dev/null
    fi
    # Set the Homebrew zsh as default shell
    chsh -s "$BREW_ZSH"
    echo "      ✅ Default shell changed to Homebrew zsh."
else
    echo "      ✅ Homebrew zsh is already the default shell. Skipping configuration."
fi

# Update Homebrew and Upgrade any already-installed formulae
echo "      🛠️ Updating homebrew"
 brew update &> /dev/null
echo "      ✅ Homebrew updated!"
echo "      🛠️ Upgrading homebrew"
brew upgrade &> /dev/null
echo "      ✅ Homebrew upgraded!"
echo "      🛠️ Upgrading homebrew cask"
brew upgrade --cask &> /dev/null
echo "      ✅ Homebrew cask upgraded!"
echo "      🛠️ Cleaning up homebrew"
brew cleanup &> /dev/null
echo "      ✅ Homebrew cleaned!"
echo ""

# Define an array of packages to install using Homebrew.
packages=(
    "bash"
    "zsh"
    "tree"
    "watch"
    "midnight-commander"
    "kube-ps1"
    "k9s"
    "tmux"
    "bat"
    "fzf"
)

# Loop over the array to install each application.
echo "📦 Installing CLI packages..."
for package in "${packages[@]}"; do
    if brew list --formula | grep -q "^$package\$"; then
        echo "      ✅ $package is already installed. Skipping..."
    else
        echo "      🛠️ Installing $package..."
        brew install "$package"
        echo "      ✅ $package installed!"
    fi
done
echo ""

# Define an array of applications to install using Homebrew Cask.
apps=(
    "sublime-text"
    "visual-studio-code"
    "rectangle"
    "chatgpt"
    "iterm2"
)

# Loop over the array to install each application.
echo "🖥️ Installing GUI applications..."
for app in "${apps[@]}"; do
    if brew list --cask | grep -q "^$app\$"; then
        echo "      ✅ $app is already installed. Skipping..."
    else
        echo "      🛠️ Installing $app..."
        brew install --cask "$app"
        echo "      ✅ $app installed!"
    fi
done
echo ""
