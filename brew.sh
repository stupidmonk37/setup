#!/usr/bin/env zsh

set -e

sudo -v

# =========================================================================
# =====[ variables ]=======================================================
# =========================================================================
work_env=false
HOME_PACKAGES=(bash zsh tree watch midnight-commander tmux bat fzf powerlevel10k todo-txt zsh-autosuggestions zsh-syntax-highlighting zsh-completions)
WORK_PACKAGES=(kube-ps1 k9s)
HOME_APPS=(sublime-text visual-studio-code rectangle chatgpt iterm2 font-meslo-lg-nerd-font)
WORK_APPS=()

# =========================================================================
# =====[ helpful functions ]==============================================
# =========================================================================
warn() { echo "     ⚠️  $1"; }
fail() { echo "     ❌ $1"; }
pass() { echo "     ✅ $1"; }
header() { print "\n🛠️ $1"; }

spinner() {
  local pid=$!
  local spin='-\|/'
  local i=0
  while kill -0 $pid 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf " \r     %s" "${spin:$i:1}"
    sleep 0.1
  done
  printf "\r     ✅\n"
}

run_with_spinner() {
  local msg="$1"
  shift
  echo -n "        $msg..."
  "$@" &> /dev/null &
  spinner
}

# =========================================================================
# =====[ install homebrew if needed ]=====================================
# =========================================================================
install_brew_if_needed() {
  header "Checking if Homebrew is installed"
  if ! command -v brew &>/dev/null; then
    run_with_spinner "Installing Homebrew" /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    pass " Homebrew installed!"

    # Configure PATH
    if [[ -x "/opt/homebrew/bin/brew" ]]; then
      export PATH="/opt/homebrew/bin:${PATH}"
    fi
  else
    warn "Homebrew already installed!"
  fi

  eval "$(/opt/homebrew/bin/brew shellenv)"
  if ! command -v brew &>/dev/null; then
    fail "Failed to configure Homebrew in PATH. Please check manually."
    exit 1
  fi
}

# =========================================================================
# =====[ set shell ]======================================================
# =========================================================================
configure_zsh_shell() {
  header "Setting Homebrew zsh as default shell"
  local BREW_ZSH="$(brew --prefix)/bin/zsh"
  if [[ "$SHELL" != "$BREW_ZSH" ]]; then
    if ! grep -Fxq "$BREW_ZSH" /etc/shells; then
      run_with_spinner "Adding $BREW_ZSH to allowed shells" echo "$BREW_ZSH" | sudo tee -a /etc/shells > /dev/null
    fi
    chsh -s "$BREW_ZSH"
    pass " Shell changed to Homebrew zsh."
  else
    warn "Homebrew zsh is already the default!"
  fi
}

# =========================================================================
# =====[ updating homebrew ]===============================================
# =========================================================================
update_homebrew() {
  header "Updating and cleaning Homebrew"
  run_with_spinner " Updating brew" brew update
  run_with_spinner " Upgrading brew" brew upgrade
  run_with_spinner " Upgrading casks" brew upgrade --cask
  run_with_spinner " Cleaning up" brew cleanup
}

# =========================================================================
# =====[ brew install packages ]===========================================
# =========================================================================
install_packages() {
  header "Installing CLI tools"

  # Set PACKAGES depending on whether it's a work environment
  if [ "$work_env" = true ]; then
    PACKAGES=("${HOME_PACKAGES[@]}" "${WORK_PACKAGES[@]}")
  else
    PACKAGES=("${HOME_PACKAGES[@]}")
  fi

  for pkg in "${PACKAGES[@]}"; do
    if brew list --formula | grep -qx "$pkg"; then
      warn "$pkg already installed!"
    else
      run_with_spinner " Installing $pkg" brew install "$pkg"
    fi
  done
}

# =========================================================================
# =====[ brew install cask (apps) ]========================================
# =========================================================================
install_apps() {
  header "Installing GUI apps"

  # Set APPS depending on whether it's a work environment
  if [ "$work_env" = true ]; then
    APPS=("${HOME_APPS[@]}" "${WORK_APPS[@]}")
  else
    APPS=("${HOME_APPS[@]}")
  fi

  for app in "${APPS[@]}"; do
    if brew list --cask | grep -qx "$app"; then
      warn "$app already installed!"
    else
     run_with_spinner " Installing $app" brew install --cask "$app"
    fi
  done
}

# =========================================================================
# =====[ main script ]=====================================================
# =========================================================================
install_brew_if_needed
configure_zsh_shell
update_homebrew
install_packages
install_apps

echo "\n🎉 HomeBrew setup complete!\n"

