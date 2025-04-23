# Set your environment
# work_env=true(work setup) or work_env=false(home setup)
work_env=true
job=groq
base=(.aliases .tmux.conf .vimrc .zprofile)
work=(.aliases-$job .zprompt-$job .zshrc-$job)
work_dotfile="$HOME/git/setup/$job"

load_base_env() {
    # .bin stuff
    export PATH="$HOME/.bin:$HOME/.local/bin:$PATH"

    # Colorful grep
    export GREP_COLORS='1;35;40'

    # less command like vim
    export LESS='-F -R -M -i -N -j5 -X'

    # ls command colors
    export LSCOLORS="ExGxxxxxCxxxxxxxxxxxxx"

    export FZF_DEFAULT_OPTS="
    --height=40%
    --layout=reverse
    --border=rounded
    --color=fg:#dcdccc,bg:#1c1c1c,preview-bg:#1c1c1c,border:#5f5faf,header:#af87d7
    --prompt='❯ '
    --marker='✓ '
    --pointer='▶'
    --info=inline
    --preview 'bat --style=plain --color=always --line-range :500 {}'
    "

    # functions for home
    [[ -f "$HOME/.bin/home-functions.sh" ]] && source "$HOME/.bin/home-functions.sh"

    # auto complete
    autoload -Uz compinit
    compinit

    # not sure what i did
    autoload -Uz colors && colors

    # setup fzf key bindings and fuzzy completion
    source <(fzf --zsh)

    # allow prompt updates ie date/time
    setopt PROMPT_SUBST

    # make '#' work in interactive shells
    setopt INTERACTIVE_COMMENTS

    # Load dotfiles:
    for file in "${base[@]}"; do
        [ -r "$file" ] && [ -f "$file" ] && source "$file" 2>/dev/null
    done
    unset file
}

# Load dotfiles based on environment
if [[ $work_env == "true" ]]; then
    for file in "${work[@]}"; do
        [[ -f "$work_dotfile/$file" ]] && source "$work_dotfile/$file"
    done

    load_base_env

elif [[ $work_env == "false" ]]; then
    [[ -f "$HOME/.zprompt" ]] && source "$HOME/.zprompt"
    load_base_env

else
    echo "Unknown value for work_env: '$work_env' — must be 'true' or 'false'"
fi

echo "Loaded $job environment ($([[ $work_env == true ]] && echo work || echo home))"

