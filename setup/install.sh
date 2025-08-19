#!/usr/bin/env zsh

sudo -v

# =====================[ Config ]=====================
WORK_ENV=false
JOB=groq
SETUP_DIR="$HOME/git/setup"
DOTFILE_FILE=(.vim .vimrc .zshrc .zprofile .aliases .bin .tmux.conf .p10k.zsh)
DOTFILE_DIR="$SETUP_DIR/dotfiles"
WORK_FILE=(.aliases-$JOB .zshrc-$JOB)
WORK_DIR="$SETUP_DIR/$JOB"

HOME_PACKAGES=(yq bash zsh tree watch tmux bat fzf powerlevel10k pipx parallel zsh-autosuggestions zsh-syntax-highlighting)
WORK_PACKAGES=(k9s ipmitool pdsh)
HOME_APPS=(visual-studio-code rectangle chatgpt iterm2 font-meslo-for-powerlevel10k font-symbols-only-nerd-font)
WORK_APPS=()

FAILED_TASKS=()

# =====================[ Colors / Helpers ]=====================
warn()  { echo "     ⏩ $1"; }
fail()  { echo "     ❌ $1"; FAILED_TASKS+=("$1"); }
pass()  { echo "     ✅ $1"; }
header(){ print "\n🛠️ $1"; }

# =====================[ Spinner ]=====================
run_spinner() {
  if [ -n "$ZSH_VERSION" ]; then
    emulate -L zsh
    setopt NO_MONITOR
  fi

  local msg="$1"
  shift

  local output_file
  output_file=$(mktemp)
  "$@" &> "$output_file" &
  local pid=$!
  local spin='-\|/'
  local i=0

  while kill -0 $pid 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r    [%s] %s" "${spin:$i:1}" "$msg"
    sleep 0.1
  done

  wait $pid
  run_spinner_status=$?
  run_spinner_output=$(<"$output_file")
  rm -f "$output_file"

  printf "\r\033[K"
}

# =====================[ Setup Functions ]=====================
create_work_dir() {
    header "Creating work directory"
    if [[ "$WORK_ENV" == true ]]; then
        mkdir -p "$WORK_DIR"
        for file in "${WORK_FILE[@]}"; do
            touch "$WORK_DIR/$file"
        done
        pass "Work directory created at $WORK_DIR"
    else
        warn "WORK_ENV disabled — skipping"
    fi
}

symlink_setup() {
    header "Linking dotfiles from $DOTFILE_DIR → ~/"
    for file in "${DOTFILE_FILE[@]}"; do
        local src="$DOTFILE_DIR/$file"
        local dest="$HOME/$file"

        if [[ ! -e "$src" ]]; then
            warn "$file not found — skipping."
            continue
        fi

        run_spinner "Linking $file" ln -sf "$src" "$dest"
        if [[ $run_spinner_status -eq 0 ]]; then
            pass "Linked $file"
        else
            fail "Failed to link $file"
        fi
    done
}

install_brew() {
    header "Checking Homebrew installation"
    if ! command -v brew &>/dev/null; then
        run_spinner "Installing Homebrew" /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [[ $run_spinner_status -eq 0 ]]; then
            pass "Homebrew installed"
            export PATH="/opt/homebrew/bin:$PATH"
        else
            fail "Homebrew installation failed"
            return 1
        fi
    else
        warn "Homebrew already installed"
    fi
}

configure_zsh_shell() {
    header "Setting Homebrew zsh as default shell"
    local BREW_ZSH="$(brew --prefix)/bin/zsh"
    if [[ "$SHELL" != "$BREW_ZSH" ]]; then
        if ! grep -Fxq "$BREW_ZSH" /etc/shells; then
            run_spinner "Adding $BREW_ZSH to allowed shells" echo "$BREW_ZSH" | sudo tee -a /etc/shells > /dev/null
            [[ $run_spinner_status -eq 0 ]] && pass "Shell added to /etc/shells" || fail "Failed to add shell"
        fi
        run_spinner "Changing default shell" chsh -s "$BREW_ZSH"
        [[ $run_spinner_status -eq 0 ]] && pass "Shell changed to Homebrew zsh" || fail "Failed to change shell"
    else
        warn "Homebrew zsh is already default"
    fi
}

homebrew_update() {
    header "Updating Homebrew"
    local cmds=("brew update" "brew upgrade" "brew upgrade --cask" "brew cleanup")
    for cmd in "${cmds[@]}"; do
        run_spinner "$cmd" zsh -c "$cmd"
        [[ $run_spinner_status -eq 0 ]] && pass "$cmd" || fail "$cmd"
    done
}

install_packages() {
    header "Installing CLI packages"
    local PACKAGES=("${HOME_PACKAGES[@]}")
    [[ "$WORK_ENV" == true ]] && PACKAGES+=("${WORK_PACKAGES[@]}")

    for pkg in "${PACKAGES[@]}"; do
        if brew list --formula | grep -qx "$pkg"; then
            warn "$pkg already installed"
        else
            run_spinner "Installing $pkg" brew install "$pkg"
            if [[ $run_spinner_status -eq 0 ]]; then
                pass "$pkg installed"
            elif grep -qE "already installed|is keg-only" <<< "$run_spinner_output"; then
                warn "$pkg already installed (skipping)"
            else
                fail "$pkg installation failed"
                FAILURES+=("Package: $pkg")
            fi
        fi
    done
}

install_apps() {
    header "Installing GUI apps"
    local APPS=("${HOME_APPS[@]}")
    [[ "$WORK_ENV" == true ]] && APPS+=("${WORK_APPS[@]}")

    for app in "${APPS[@]}"; do
        if brew list --cask | grep -qx "$app"; then
            warn "$app already installed"
        else
            run_spinner "Installing $app" brew install --cask "$app"
            if [[ $run_spinner_status -eq 0 ]]; then
                pass "$app installed"
            elif grep -qE "already a Font|already an App" <<< "$run_spinner_output"; then
                warn "$app already installed (skipping existing files)"
            else
                fail "$app installation failed"
                FAILURES+=("App: $app")
            fi
        fi
    done
}

install_vim_theme() {
    local theme_name="Gruvbox"
    local theme_path="$DOTFILE_DIR/.vim/colors/gruvbox.vim"
    local theme_url="https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim"

    header "Installing $theme_name theme for Vim/Bat"
    if [[ -f "$theme_path" ]]; then
        warn "$theme_name already installed"
        return
    fi

    run_spinner "Downloading $theme_name" curl -fsSL -o "$theme_path" --create-dirs "$theme_url"
    [[ $run_spinner_status -eq 0 ]] && pass "$theme_name installed" || fail "Could not download $theme_name"
}

install_fzf_tab() {
    local repo_url="https://github.com/Aloxaf/fzf-tab"
    local install_dir="$HOME/.fzf-tab"

    if [[ -d "$install_dir" ]]; then
        warn "fzf-tab already installed"
        return
    fi

    header "Installing fzf-tab"
    run_spinner "Cloning fzf-tab" git clone --depth 1 "$repo_url" "$install_dir"
    [[ $run_spinner_status -eq 0 ]] && pass "fzf-tab installed" || fail "Failed to install fzf-tab"
}

install_tpm() {
    local repo_url="https://github.com/tmux-plugins/tpm"
    local install_dir="$DOTFILE_DIR/.tmux/plugins/tpm"

    if [[ -d "$install_dir" ]]; then
        warn "TPM already installed"
        return
    fi

    header "Installing Tmux Plugin Manager"
    run_spinner "Cloning TPM" git clone --depth 1 "$repo_url" "$install_dir"
    [[ $run_spinner_status -eq 0 ]] && pass "TPM installed" || fail "Failed to install TPM"
}

# =====================[ Main ]=====================
create_work_dir
symlink_setup
install_brew
configure_zsh_shell
homebrew_update
install_packages
install_apps
install_vim_theme
install_fzf_tab
install_tpm

# =====================[ Failures Summary ]=====================
if (( ${#FAILED_TASKS[@]} > 0 )); then
  print "\n🚨 The following tasks failed:"
  for task in "${FAILED_TASKS[@]}"; do
    echo "   - $task"
  done
  print "\nCheck the above errors and re-run the script as needed."
else
  print "\n🎉 Installation Complete with no errors!"
fi

print "🧼 Reloading shell...\n"
exec zsh
