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

# =====================[ Colors / Helpers ]=====================
warn()  { echo "     ⏩ $1"; }
fail()  { echo "     ❌ $1"; }
pass()  { echo "     ✅  $1"; }
header(){ print "\n🛠️  $1"; }

# Spinner that returns exit status to caller
run_with_spinner() {
  local msg="$1"; shift
  echo -n "        $msg..."
  "$@" &>/dev/null &
  local pid=$!
  local spin='-\|/'
  local i=0
  while kill -0 $pid 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf " \r     %s" "${spin:$i:1}"
    sleep 0.1
  done
  wait $pid
  local status=$?
  if [[ $status -eq 0 ]]; then
    printf "\r     ✅\n"
  else
    printf "\r     ❌ Command failed\n"
  fi
  return $status
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
    local all_ok=true
    for file in "${DOTFILE_FILE[@]}"; do
        local src="$DOTFILE_DIR/$file"
        local dest="$HOME/$file"

        if [[ ! -e "$src" ]]; then
            warn "$file not found in $DOTFILE_DIR — skipping."
            all_ok=false
            continue
        fi

        if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
            warn "$file already linked"
            continue
        fi

        if ln -sf "$src" "$dest"; then
            pass "Linked $file"
        else
            fail "Failed to link $file"
            all_ok=false
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

    if curl -fsSL -o "$theme_path" --create-dirs "$theme_url"; then
        pass "$theme_name installed at $theme_path"
    else
        fail "Could not download $theme_name"
    fi
}

install_fzf_tab() {
    local repo_url="https://github.com/Aloxaf/fzf-tab"
    local install_dir="$HOME/.fzf-tab"

    if [[ -d "$install_dir" ]]; then
        warn "fzf-tab already installed"
        return
    fi

    header "Installing fzf-tab"
    if run_with_spinner "Cloning fzf-tab" git clone --depth 1 "$repo_url" "$install_dir"; then
        pass "fzf-tab installed"
    else
        fail "Failed to install fzf-tab"
    fi
}

install_tpm() {
    local repo_url="https://github.com/tmux-plugins/tpm"
    local install_dir="$DOTFILE_DIR/.tmux/plugins/tpm"

    if [[ -d "$install_dir" ]]; then
        warn "TPM already installed"
        return
    fi

    header "Installing Tmux Plugin Manager"
    if git clone --depth 1 "$repo_url" "$install_dir" &>/dev/null; then
        pass "TPM installed"
    else
        fail "Failed to install TPM"
    fi
}

run_brew() {
    header "Running Homebrew setup"
    local brew_script="$SETUP_DIR/setup/brew.sh"

    if [[ -x "$brew_script" ]]; then
        if "$brew_script"; then
            pass "Homebrew setup completed"
        else
            fail "Homebrew setup script errors"
        fi
    else
        warn "brew.sh not found or not executable"
    fi
}

# =====================[ Main ]=====================
create_work_dir
symlink_setup
install_vim_theme
install_fzf_tab
install_tpm
run_brew

print "\n🎉 Installation Complete!"
print "🧼 Reloading shell...\n"
exec zsh
