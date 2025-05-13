#!/usr/bin/env zsh

set -e

# ==========================================================================
# =====[ variables ]========================================================
# ==========================================================================
DOTFILE_DIR="$HOME/git/setup"
FILES=(.vim .vimrc .zshrc .zprofile .zprompt .aliases .bin .tmux.conf .p10k.zsh)
GRUVBOX_URL="https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim"
GRUVBOX_PATH="$DOTFILE_DIR/.vim/colors/gruvbox.vim"

# ==========================================================================
# =====[ helpful functions ]================================================
# ==========================================================================
warn() { echo "     ⚠️  $1"; }
fail() { echo "     ❌ $1"; }
pass() { echo "     ✅  $1"; }
header() { print "\n🛠️  $1"; }

#spinner() {
#  local pid=$!
#  local spin='-\|/'
#  local i=0
#  while kill -0 $pid 2>/dev/null; do
#    i=$(( (i + 1) % 4 ))
#    printf " \r     %s" "${spin:$i:1}"
#    sleep 0.1
#  done
#  printf "\r     ✅\n"
#}

run_with_spinner_69() {
  local msg="$1"
  shift
  echo -n "        $msg..."
  "$@" &> /dev/null &
  spinner
}

run_with_spinner() {
  local msg="$1"
  shift
  echo -n "        $msg..."

  "$@" &> /dev/null &
  local pid=$!
  local spin='-\|/'
  local i=0
  while kill -0 $pid 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf " \r     %s" "${spin:$i:1}"
    sleep 0.1
  done
  wait $pid
  local exit_status=$?
  if [ $exit_status -eq 0 ]; then
    printf "\r     ✅\n"
  else
    printf "\r     ❌ Command failed\n"
  fi
}

# ==========================================================================
# =====[ symlink setup ]====================================================
# ==========================================================================
symlink_setup() {
    header "Linking dotfiles from ~/git/setup → ~/"
    for file in "${FILES[@]}"; do
        src="${DOTFILE_DIR}/${file}"
        dest="${HOME}/${file}"

        if [[ ! -e "$src" ]]; then
            warn "$file not found in $DOTFILE_DIR — skipping."
            continue
        fi

        if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
            warn "$file already linked"
        else
            ln -sf "$src" "$dest" && pass " Linked $file"
        fi
    done
}

# ==========================================================================
# =====[ install vim/bat theme ]============================================
# ==========================================================================
install_vim_theme() {
    header "Installing gruvbox theme for Vim/Bat"
    if curl -fLo "$GRUVBOX_PATH" --create-dirs "$GRUVBOX_URL" &> /dev/null; then
        pass "Gruvbox theme installed!"
    else
        fail "Could not download gruvbox — check internet or URL."
    fi
}

# ==========================================================================
# =====[ run brew.sh ]======================================================
# ==========================================================================
run_brew() {
    header "Running Homebrew setup..."
    brew_script="${DOTFILE_DIR}/brew.sh"
    if [[ -x "$brew_script" ]]; then
        "$brew_script"
    else
        warn "brew.sh not found or not executable at $brew_script"
    fi
}

# ==========================================================================
# =====[ install fzf-tab ]==================================================
# ==========================================================================
install_fzf_tab() {
    fzf_tab="$HOME/.fzf-tab"
    if [[ ! -d "$fzf_tab" ]]; then
        header "Installing fzf-tab..."
        git clone https://github.com/Aloxaf/fzf-tab "$fzf_tab"
        pass "fzf-tab installed!"
    fi
}

# ==========================================================================
# =====[ all done ]=========================================================
# ==========================================================================
print_done() {
    pass "Installation Complete!"
    echo ""
    echo "🧼 Reloading shell..."
    exec zsh
}

# ==========================================================================
# =====[ main script ]======================================================
# ==========================================================================
symlink_setup
install_vim_theme
run_brew
install_fzf_tab
print_done

