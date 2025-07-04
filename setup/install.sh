#!/usr/bin/env zsh

set -e
sudo -v

source "$HOME/git/setup/dotfiles/.bin/home-functions.sh"

WORK_ENV=false
JOB=groq
SETUP_DIR="$HOME/git/setup"
DOTFILE_FILE=(.vim .vimrc .zshrc .zprofile .aliases .bin .tmux.conf .p10k.zsh)
DOTFILE_DIR="$SETUP_DIR/dotfiles"
WORK_FILE=(.aliases-$JOB .zshrc-$JOB)
WORK_DIR="$SETUP_DIR/$JOB" 
GRUVBOX_URL="https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim"
GRUVBOX_PATH="$DOTFILE_DIR/.vim/colors/gruvbox.vim"


warn() { echo "     ⚠️  $1"; }
fail() { echo "     ❌ $1"; }
pass() { echo "     ✅  $1"; }
header() { print "\n🛠️  $1"; }

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

create_work_dir() {
    if $WORK_ENV ; then
        mkdir -p "${WORK_DIR}"
        for file in "${WORK_FILE[@]}" ; do
            touch "${WORK_DIR}/${file}"
        done
    fi
}

symlink_setup() {
    header "Linking dotfiles from ~/git/setup → ~/"
    for file in "${DOTFILE_FILE[@]}"; do
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

install_vim_theme() {
    header "Installing gruvbox theme for Vim/Bat"
    if curl -fLo "$GRUVBOX_PATH" --create-dirs "$GRUVBOX_URL" &> /dev/null; then
        pass "Gruvbox theme installed!"
    else
        fail "Could not download gruvbox — check internet or URL."
    fi
}

install_fzf_tab() {
    fzf_tab="$HOME/.fzf-tab"
    if [[ ! -d "$fzf_tab" ]]; then
        header "Installing fzf-tab..."
        run_with_spinner "Cloning fzf-tab" git clone https://github.com/Aloxaf/fzf-tab "$fzf_tab"
        pass "fzf-tab installed!"
    fi
}

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
# =====[ MAIN SCRIPT ]======================================================
# ==========================================================================
#git clone https://github.com/tmux-plugins/tpm ~/git/setup/dotfiles/.tmux/plugins/tpm
create_work_dir
symlink_setup
install_vim_theme
install_fzf_tab
run_brew

printf "\n🎉 Installation Complete!\n"
printf "🧼 Reloading shell...\n"
exec zsh
