# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# Set your environment
# work_env=true(work setup) or work_env=false(home setup)
work_env=false
job=groq
base_file=(.aliases .tmux.conf .vimrc .zprofile)
base_dir="$HOME/git/setup"
work_file=(.aliases-$job .zprompt-$job .zshrc-$job)
work_dir="$HOME/git/setup/$job"

fzf_setup() {
    # fzf
    if command -v fzf >/dev/null; then
        source <(fzf --zsh)
    else
        echo "⚠️ fzf not found! Consider installing via brew install fzf"
    fi

    # fzf-tab
    #local fzf_tab="$HOME/.fzf-tab"
    #if [[ ! -d "$fzf_tab" ]]; then
    #    echo "📦 Installing fzf-tab..."
    #    git clone https://github.com/Aloxaf/fzf-tab "$fzf_tab"
    #fi
    source "$HOME/.fzf-tab/fzf-tab.plugin.zsh"

    # fzf-tab config
    zstyle ':completion:*:descriptions' format '[%d]'
    zstyle ':completion:*' menu select
    zstyle ':fzf-tab:*' fzf-command fzf
    zstyle ':fzf-tab:*' fzf-bindings 'tab:down,shift-tab:up'
    zstyle ':fzf-tab:complete:cd:*' fzf-preview 'ls -l --color=always $realpath'

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
}

load_base_env() {
    # .bin stuff
    export PATH="$HOME/.bin:$HOME/.local/bin:$PATH"

    # Colorful grep
    export GREP_COLORS='1;35;40'

    # less command like vim
    export LESS='-F -R -M -i -N -j5 -X'

    # ls command colors
    export LSCOLORS="ExGxxxxxCxxxxxxxxxxxxx"

    # functions for home
    [[ -f "$HOME/.bin/home-functions.sh" ]] && source "$HOME/.bin/home-functions.sh"

    # auto complete
    autoload -Uz compinit
    compinit

    # not sure what i did
    autoload -Uz colors && colors
    
    # load fzf function
    fzf_setup

    # allow prompt updates ie date/time
    setopt PROMPT_SUBST

    # make '#' work in interactive shells
    setopt INTERACTIVE_COMMENTS

    # Load dotfiles:
    for file in "${base_file[@]}"; do
        [[ -r "$base_dir/$file" ]] && [[ -f "$base_dir/$file" ]] && source "$base_dir/$file" 2>/dev/null
    done
    unset file

    source /opt/homebrew/share/zsh-autosuggestions/zsh-autosuggestions.zsh

    if type brew &>/dev/null; then
        FPATH=$(brew --prefix)/share/zsh-completions:$FPATH
    fi
    
    HISTFILE=~/.zsh_history
    HISTSIZE=10000
    SAVEHIST=10000
    setopt INC_APPEND_HISTORY SHARE_HISTORY
    
    # If you receive "zsh compinit: insecure directories" warnings when attempting
    # to load these completions, you may need to run these commands:
    #chmod go-w '/opt/homebrew/share'
    #chmod -R go-w '/opt/homebrew/share/zsh'

    # To configure todo-txt, copy the default config to your HOME and edit it:
    #cp /opt/homebrew/Cellar/todo-txt/2.13.0/todo.cfg ~/.todo.cfg

}

# Load dotfiles based on environment
if [[ $work_env == "true" ]]; then
    for file in "${work_file[@]}"; do
        [[ -f "$work_dir/$file" ]] && source "$work_dir/$file"
    done

    # functions for home
    [[ -f "$HOME/.bin/functions.sh" ]] && source "$HOME/.bin/functions.sh"

    load_base_env

    #echo "✅ Loaded $job (work environment)"

elif [[ $work_env == "false" ]]; then
    #[[ -f "$base_dir/.zprompt" ]] && source "$base_dir/.zprompt"

    load_base_env

else
    echo "⚠️ Unknown value for work_env: '$work_env' — must be 'true' or 'false'"
fi


source /opt/homebrew/share/powerlevel10k/powerlevel10k.zsh-theme

source /opt/homebrew/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
