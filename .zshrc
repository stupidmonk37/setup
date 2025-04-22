#################################
########### GROQ ################
#################################
# silence sft if it's not installed
if ! command -v sft >/dev/null; then
  sft() { :; }
fi

# groq suggestions
sft ssh-config >> ~/.ssh/config

# regex for something I don't remember right now...
export nova_ncp_reg="N[0-9]/C[0-9]/P[0-9]+ <-> N[0-9]/C[0-9]/P[0-9]+"

#function small_simp {
#    imgcat -W 25px -H 10px -s ~/git/setup/groq/groq-logo.png
#}

function big_simp {
    imgcat -W 400px -H 150px -s ~/git/setup/groq/groq-logo.png
}

big_simp
#small_simp

#source ~/.bin/functions.sh

##################################
############ k8s #################
##################################
# context and namespace in prompt
source /opt/homebrew/opt/kube-ps1/share/kube-ps1.sh
kubeoff

# auto complete
autoload -Uz compinit
compinit

# easy context switching
source <(switcher init zsh)
source <(switcher completion zsh)

# k8s command completion
source <(kubectl completion zsh)

###################################
############ HOME #################
###################################
# .bin stuff
PATH="$HOME/.bin:$PATH"

# functions for home
source ~/.bin/home-functions.sh

# auto complete
autoload -Uz compinit
compinit

# setup fzf key bindings and fuzzy completion
source <(fzf --zsh)

# not sure what i did
autoload -Uz colors && colors

# less command like vim
export LESS='-F -R -M -i -N -j5 -X'

# allow prompt updates ie date/time
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

export PATH="/Users/jjensen/.local/bin:$PATH"

export FZF_DEFAULT_OPTS="
  --height=40%
  --layout=reverse
  --border=rounded
  --color=fg:#dcdccc,bg:#1c1c1c,preview-bg:#1c1c1c,border:#5f5faf,header:#af87d7
  --prompt='❯ '
  --marker='✓ '
  --pointer='▶'
  --info=inline
  --preview 'bat --style=numbers --color=always --line-range :500 {}'
  "
#export FZF_DEFAULT_OPTS="$FZF_DEFAULT_OPTS --preview 'bat --style=numbers --color=always --line-range :500 {}'"


