#!/usr/bin/env zsh
############################
# This script creates symlinks from the home directory to any desired dotfiles in $HOME/dotfiles
# And also installs MacOS Software
# And also installs Homebrew Packages and Casks (Apps)
# And also sets up VS Code
# And also sets up Sublime Text
############################

# dotfiles directory
dotfiledir="${HOME}/git/setup"

# list of files/folders to symlink in ${homedir}
files=(vim vimrc zshrc zprofile zprompt aliases bin tmux.conf)

# create symlinks (will overwrite old dotfiles)
for file in "${files[@]}"; do
    echo "Creating symlink to $file in home directory."
    ln -sf "${dotfiledir}/.${file}" "${HOME}/.${file}"
done

# Not sure where to put this yet, so it's going here
# It's the vim/bat colorscheme
curl -fLo "${dotfiledir}.vim/colors/gruvbox.vim" --create-dirs https://raw.githubusercontent.com/morhetz/gruvbox/master/colors/gruvbox.vim


# Run the MacOS Script
#./macOS.sh

# Run the Homebrew Script
#./brew.sh

echo "Installation Complete!"
