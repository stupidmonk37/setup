# GROQ
# silence sft if it's not installed
if ! command -v sft >/dev/null; then
  sft() { :; }
fi
sft ssh-config >> ~/.ssh/config
autoload -Uz compinit
compinit
export nova_ncp_reg="N[0-9]/C[0-9]/P[0-9]+ <-> N[0-9]/C[0-9]/P[0-9]+"
source <(kubectl completion zsh)




# HOME
# .bin stuff
PATH="$HOME/.bin:$PATH"
# not sure what i did
autoload -Uz colors && colors
setopt PROMPT_SUBST
# make '#' work in interactive shells
setopt INTERACTIVE_COMMENTS

# Colorful grep
export GREP_COLOR='1;35;40'

# Load dotfiles:
for file in ~/.{zprompt,aliases,private}; do
    [ -r "$file" ] && [ -f "$file" ] && source "$file"
done
unset file

# ls in color
export LSCOLORS="ExGxxxxxCxxxxxxxxxxxxx"

