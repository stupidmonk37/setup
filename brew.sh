#!/usr/bin/env zsh

set -e

### 💬 Functions ###
print_header() {
  echo "\n🛠️ $1\n"
}

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

run_with_spinner() {
  local msg="$1"
  shift
  echo -n "      ⏳ $msg..."
  "$@" &> /dev/null &
  spinner
}

install_brew_if_needed() {
  print_header "Checking for Homebrew"
  if ! command -v brew &>/dev/null; then
    echo "      🛠️ Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo "      ✅ Homebrew installed!"

    # Configure PATH
    if [[ -x "/opt/homebrew/bin/brew" ]]; then
      export PATH="/opt/homebrew/bin:$PATH"
    fi
  else
    echo "      ✅ Homebrew already installed."
  fi

  eval "$(/opt/homebrew/bin/brew shellenv)"
  if ! command -v brew &>/dev/null; then
    echo "      ❌ Failed to configure Homebrew in PATH. Please check manually."
    exit 1
  fi
}

configure_zsh_shell() {
  print_header "Setting Homebrew zsh as default"
  local BREW_ZSH="$(brew --prefix)/bin/zsh"
  if [[ "$SHELL" != "$BREW_ZSH" ]]; then
    if ! grep -Fxq "$BREW_ZSH" /etc/shells; then
      echo "      🛠️ Adding $BREW_ZSH to allowed shells..."
      echo "$BREW_ZSH" | sudo tee -a /etc/shells > /dev/null
    fi
    chsh -s "$BREW_ZSH"
    echo "      ✅ Shell changed to Homebrew zsh."
  else
    echo "      ✅ Homebrew zsh is already the default."
  fi
}

update_homebrew() {
  print_header "Updating and cleaning Homebrew"
  run_with_spinner "Updating brew" brew update
  run_with_spinner "Upgrading brew" brew upgrade
  run_with_spinner "Upgrading casks" brew upgrade --cask
  run_with_spinner "Cleaning up" brew cleanup
}

install_packages() {
  local packages=(
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

  print_header "Installing CLI tools"
  for pkg in "${packages[@]}"; do
    if brew list --formula | grep -qx "$pkg"; then
      echo "      ✅ $pkg already installed"
    else
      echo "      🛠️ Installing $pkg"
      brew install "$pkg"
    fi
  done
}

install_apps() {
  local apps=(
    "sublime-text"
    "visual-studio-code"
    "rectangle"
    "chatgpt"
    "iterm2"
  )

  print_header "Installing GUI apps"
  for app in "${apps[@]}"; do
    if brew list --cask | grep -qx "$app"; then
      echo "      ✅ $app already installed"
    else
      echo "      🛠️ Installing $app"
      brew install --cask "$app"
    fi
  done
}

### 🚀 Main Script ###
install_brew_if_needed
configure_zsh_shell
update_homebrew
install_packages
install_apps

echo "\n🎉 Brew setup complete!\n"

