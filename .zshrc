# Set your environment
# work_env=true(work setup) or work_env=false(home setup)
work_env=false
job=groq
base_file=(.aliases .tmux.conf .vimrc .zprofile)
base_dir="$HOME/git/setup"
work_file=(.aliases-$job .zprompt-$job .zshrc-$job)
work_dir="$HOME/git/setup/$job"

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
    --bind 'tab:down,shift-tab:up'
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
    for file in "${base_file[@]}"; do
        [ -r "$base_dir/$file" ] && [ -f "$base_dir/$file" ] && source "$base_dir/$file" 2>/dev/null
    done
    unset file
}

# Load dotfiles based on environment
if [[ $work_env == "true" ]]; then
    for file in "${work_file[@]}"; do
        [[ -f "$work_dir/$file" ]] && source "$work_dir/$file"
    done

    # functions for home
    [[ -f "$HOME/.bin/functions.sh" ]] && source "$HOME/.bin/functions.sh"

    load_base_env

    echo "✅ Loaded $job (work environment)"

elif [[ $work_env == "false" ]]; then
    [[ -f "$base_dir/.zprompt" ]] && source "$base_dir/.zprompt"

    load_base_env

    echo "🏠 Loaded home environment"

else
    echo "⚠️ Unknown value for work_env: '$work_env' — must be 'true' or 'false'"
fi


