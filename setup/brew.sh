#!/usr/bin/env zsh

set -e
sudo -v

source "$HOME/git/setup/dotfiles/.bin/home-functions.sh"

work_env=false
HOME_PACKAGES=(yq bash zsh tree watch tmux bat fzf powerlevel10k pipx parallelzsh-autosuggestions zsh-syntax-highlighting)
WORK_PACKAGES=(k9s ipmitool pdsh)
HOME_APPS=(visual-studio-code rectangle chatgpt iterm2 font-meslo-for-powerlevel10k font-symbols-only-nerd-font)
WORK_APPS=()

# =========================================================================
# =====[ HELPFUL FUNCTIONS ]===============================================
# =========================================================================
warn() { echo "     ⚠️  $1"; }
fail() { echo "     ❌ $1"; }
pass() { echo "     ✅  $1"; }
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

install_brew() {
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

configure_zsh_shell() {
  header "Setting Homebrew zsh as default shell"
  local BREW_ZSH="$(brew --prefix)/bin/zsh"
  if [[ "$SHELL" != "$BREW_ZSH" ]]; then
    if ! grep -Fxq "$BREW_ZSH" /etc/shells; then
      run_with_spinner "Adding $BREW_ZSH to allowed shells" echo "$BREW_ZSH" | sudo tee -a /etc/shells > /dev/null
    fi
    chsh -s "$BREW_ZSH"
    pass "Shell changed to Homebrew zsh."
  else
    warn "Homebrew zsh is already the default!"
  fi
}

update_homebrew() {
  header "Updating and cleaning Homebrew"
  run_with_spinner " Updating brew" brew update
  run_with_spinner " Upgrading brew" brew upgrade
  run_with_spinner " Upgrading casks" brew upgrade --cask
  run_with_spinner " Cleaning up" brew cleanup
}

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
# =====[ MAIN SCRIPT ]=====================================================
# =========================================================================
install_brew
configure_zsh_shell
update_homebrew
install_packages
install_apps

echo "\n🎉 HomeBrew setup complete!\n"

