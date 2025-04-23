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

# create symlinks
echo "🔗 Symlinking dotfiles from $dotfiledir into ~/"
for file in "${files[@]}"; do
    echo "  ↪ ${file}"
    ln -sf "${dotfiledir}/${file}" "${HOME}/${file}" && echo "    ✅ Linked ~/${file}"
done

# install the gruvbox colorscheme for Vim/Bat
echo "🎨 Installing gruvbox color scheme..."
curl -fLo "${dotfiledir}/dotfiles/.vim/colors/gruvbox.vim" --create-dirs \
    https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim

# optionally run macOS or Homebrew setup scripts
# ./macOS.sh
# ./brew.sh

echo ""
echo "✅ Installation Complete!"
echo "🧼 Reloading shell..."
exec zsh

