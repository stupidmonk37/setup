autoload -Uz colors && colors
setopt PROMPT_SUBST

# Colorful grep
export GREP_OPTIONS='--color=always'
export GREP_COLOR='1;35;40'

# Load dotfiles:
for file in ~/.{zprompt,aliases,private}; do
    [ -r "$file" ] && [ -f "$file" ] && source "$file"
done
unset file

# Always enable colored `grep` output
#alias grep='grep -G'
#alias fgrep='fgrep -G'
#alias egrep='egrep -G'

# List all files colorized in long format, including dot files
alias la="ls -lAhGT"

# ls in color
alias ls="ls -G"
