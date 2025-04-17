#! /bin/bash

# tm - create new tmux session, or switch to existing one. Works from within tmux too. (@bag-man)
# `tm` will allow you to select your tmux session via fzf.
# `tm irc` will attach to the irc session (if it exists), else it will create it.

ts() {
  [[ -n "$TMUX" ]] && change="switch-client" || change="attach-session"
  if [ $1 ]; then
    tmux $change -t "$1" 2>/dev/null || (tmux new-session -d -s $1 && tmux $change -t "$1"); return
  fi
  session=$(tmux list-sessions -F "#{session_name}" 2>/dev/null | fzf --exit-0) &&  tmux $change -t "$session" || echo "No sessions found."
}

# zsh; needs setopt re_match_pcre. You can, of course, adapt it to your own shell easily.
tks () {
    local sessions
    sessions="$(tmux ls|fzf --exit-0 --multi)"  || return $?
    local i
    for i in "${(f@)sessions}"
    do
        [[ $i =~ '([^:]*):.*' ]] && {
            echo "Killing $match[1]"
            tmux kill-session -t "$match[1]"
        }
    done
}

fvfind() {
  local file
  file=$(fzf-tmux -p 80%,60% --preview 'bat --theme="TwoDark" --plain --color=always {}' --preview-window=right:70%)
  [ -n "$file" ] && vim "$file"
}

fbfind() {
  local file
  file=$(fzf-tmux -p 80%,60% --preview 'bat --theme="TwoDark" --plain --color=always {}' --preview-window=right:70%)
  [ -n "$file" ] && bat "$file"
}


# In tmux.conf
# bind-key 0 run "tmux split-window -l 12 'bash -ci ftpane'"


fcd() {
  cd "$(find ${1:-.} -type d 2> /dev/null | fzf-tmux -p 70%,50% --preview 'ls -alhG {}' --preview-window=right:70%)"
}

fh() {
  eval "$(history | fzf | sed 's/ *[0-9]* *//')"
}

fnotes() {
  bat --theme="TwoDark" --plain "$(find ~/git/setup/notes-groq -type f 2> /dev/null | fzf-tmux -p 70%,50% --preview 'bat --theme="TwoDark" --plain --color=always --style=numbers {}' --preview-window=right:70%)"
}

