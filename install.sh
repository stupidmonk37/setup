#!/usr/bin/env zsh

set -e

# ==========================================================================
# variables
# ==========================================================================
DOTFILE_DIR="$HOME/git/setup"
FILES=(.vim .vimrc .zshrc .zprofile .zprompt .aliases .bin .tmux.conf)
GRUVBOX_URL="https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim"
GRUVBOX_PATH="$DOTFILE_DIR/.vim/colors/gruvbox.vim"

# ==========================================================================
# helpful functions
# ==========================================================================
warn() { echo "     ⚠️  $1"; }
fail() { echo "     ❌ $1"; }
pass() { echo "     ✅ $1"; }
#divider() { print "\n------------------------------\n"; }
header() { print "\n🛠️  $1"; }

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

# ==========================================================================
# symlink setup
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
            ln -sf "$src" "$dest" && echo "     ✅ Linked $file"
        fi
    done
}

# ==========================================================================
# install vim/bat theme
# ==========================================================================
install_vim_theme() {
    header "Installing gruvbox theme for Vim/Bat"
    if curl -fLo "$GRUVBOX_PATH" --create-dirs "$GRUVBOX_URL" &> /dev/null; then
        pass " Gruvbox theme installed!"
    else
        fail "Could not download gruvbox — check internet or URL."
    fi
}

# ==========================================================================
# run brew.sh
# ==========================================================================
run_brew() {
    header "Running Homebrew setup"
    if [[ -x "./brew.sh" ]]; then
        ./brew.sh
    else
        warn "brew.sh not found or not executable."
    fi
}

# ==========================================================================
# install fzf-tab
# ==========================================================================
install_fzf_tab() {
    fzf_tab="$HOME/.fzf-tab"
    if [[ ! -d "$fzf_tab" ]]; then
        echo "📦 Installing fzf-tab..."
        git clone https://github.com/Aloxaf/fzf-tab "$fzf_tab"
    fi
}

# ==========================================================================
# all done
# ==========================================================================
print_done() {
    echo "✅ Installation Complete!"
    echo ""
    echo "🧼 Reloading shell..."
    exec zsh
}

# ==========================================================================
# main script
# ==========================================================================
symlink_setup
install_vim_theme
run_brew
install_fzf_tab
print_done

