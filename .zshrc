PROMPT='%(?.%F{green}⏺.%F{red}⏺)%f %2~/ > '
RPROMPT="%t"

#original prompt
#PROMPT='%n@%m %1~ %# '

autoload -Uz colors && colors
setopt PROMPT_SUBST

# Colorful grep
export GREP_COLOR='1;35;40'

# Load dotfiles:
for file in ~/.{zprompt,aliases,private}; do
    [ -r "$file" ] && [ -f "$file" ] && source "$file"
done
unset file

# ls in color
export LSCOLORS="ExGxxxxxCxxxxxxxxxxxxx"

