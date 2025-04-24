#!/usr/bin/env zsh
############################
# This script:
# - Symlinks dotfiles from ~/git/setup to ~/
# - Installs the gruvbox color scheme for vim/bat
# - Optionally runs macOS and Homebrew setup scripts
############################

# dotfiles directory
dotfiledir="${HOME}/git/setup"

# list of files/folders to symlink
files=(.vim .vimrc .zshrc .zprofile .zprompt .aliases .bin .tmux.conf)

# fancy spinning action
spinner() {
  local pid=$!
  local spin='-\|/'
  local i=0
  while kill -0 $pid 2>/dev/null; do
    i=$(( (i+1) %4 ))
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

# create symlinks
echo ""
echo "🔗 Symlinking dotfiles from $dotfiledir into ~/"
for file in "${files[@]}"; do
    src="${dotfiledir}/${file}"
    dest="${HOME}/${file}"
    if [[ -L "$dest" && "$(readlink "$dest")" == "$src" ]]; then
        echo "      ⚠️  $file already linked"
    else
        ln -sf "$src" "$dest" && echo "      ✅ Linked ~/${file}"
    fi
done
echo ""

# install the gruvbox colorscheme for Vim/Bat
echo "🎨 Installing gruvbox color scheme..."
if curl -fLo "${dotfiledir}/.vim/colors/gruvbox.vim" --create-dirs \
    https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim  &> /dev/null; then
    echo "      ✅ gruvbox installed!"
else
    echo "      ❌ Failed to install gruvbox theme!"
fi
echo ""

# optionally run macOS or Homebrew setup scripts
# ./macOS.sh
 ./brew.sh

echo ""
echo "✅ Installation Complete!"
echo ""
echo "🧼 Reloading shell..."
echo ""
exec zsh

