PROMPT='%(?.%F{green}⏺.%F{red}⏺)%f %2~/ > '
RPROMPT="%t"

#original prompt
#PROMPT='%n@%m %1~ %# '

autoload -Uz colors && colors
setopt PROMPT_SUBST

# Colorful grep
export GREP_COLOR='1;35;40'
alias grep="grep --color=auto"
alias egrep="grep --color=auto"
alias fgrep="grep --color=auto"

# Load dotfiles:
for file in ~/.{zprompt,aliases,private}; do
    [ -r "$file" ] && [ -f "$file" ] && source "$file"
done
unset file

# List all files colorized in long format, including dot files
alias ll="ls -alhG"

# ls in color
export LSCOLORS="ExGxxxxxCxxxxxxxxxxxxx"
alias ls="ls -G"

