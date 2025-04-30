#! /bin/bash

# tm - create new tmux session, or switch to existing one. Works from within tmux too. (@bag-man)
# `tm` will allow you to select your tmux session via fzf.
# `tm irc` will attach to the irc session (if it exists), else it will create it.

kctx() {
  local context
  context=$(kubectl config get-contexts -o name | fzf --prompt="K8s Context > ")
  [[ -n "$context" ]] && kubectl config use-context "$context"
}

k8s-switch() {
  echo "🔍 Select a Kubernetes context:"
  local context=$(kubectl config get-contexts -o name | fzf --prompt="Context > ")
  [[ -z "$context" ]] && echo "❌ No context selected." && return

  kubectl config use-context "$context"

  echo "📦 Fetching namespaces for context: $context"
  local namespace=$(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n' | fzf --prompt="Namespace > ")
  [[ -z "$namespace" ]] && echo "⚠️ No namespace selected — keeping default." && return

  kubectl config set-context --current --namespace="$namespace"

  echo "✅ Switched to context: $context with namespace: $namespace"
}

tw () {
	[[ -n "$TMUX" ]] && change="switch-client" || change="attach-session"

	if [[ "$1" == "-ls" ]]; then
		tmux list-sessions
		return
	fi

	if [[ -n "$1" ]]; then
		# Try to attach/switch; if session doesn't exist, create it (detached), but do NOT switch
		if ! tmux has-session -t "$1" 2>/dev/null; then
			tmux new-session -d -s "$1" -n "$1"
			echo "🆕 Created new detached session: $1"
		else
			tmux $change -t "$1"
		fi
		return
	fi

	local target session window
	target=$(tmux list-windows -a -F "#{session_name}:#{window_index}:::#{session_name}  #{window_name}#{window_flags}" | \
		sed 's/-//g' | \
		fzf --exit-0 --with-nth=2 --delimiter=":::" \
			--preview='
				session_window=$(echo {} | cut -d":" -f1,2)
				tmux list-panes -t "$session_window" -F "│ #{pane_index}: #{pane_current_command} (#{pane_current_path})"
			' \
			--preview-window=right:70%:wrap) || return

	session="${target%%:*}"
	window="${target%%:::*}"

	if [[ -n "$TMUX" ]]; then
		tmux switch-client -t "$session"
		tmux select-window -t "$window"
	else
		tmux attach-session -t "$session" \; select-window -t "$window"
	fi
}

tkill () {
	if [[ "$1" == "--all" ]]; then
		read -q "REPLY?⚠️  Kill ALL tmux sessions? [y/N] " || {
			echo "\n❌ Aborted."
			return 1
		}
		echo "\n🔪 Killing all tmux sessions..."
		tmux list-sessions -F '#S' | while read -r session; do
			tmux kill-session -t "$session"
			echo "☠️  Killed $session"
		done
		return
	fi

	local sessions
	sessions="$(tmux ls | fzf --exit-0 --multi)" || return $?

	local i
	for i in "${(f@)sessions}"; do
		[[ $i =~ '([^:]*):.*' ]] && {
			echo "Killing $match[1]"
			tmux kill-session -t "$match[1]"
		}
	done
}


fvfind() {
  local file
  file=$(fzf-tmux -p 80%,60% --preview 'bat --theme="gruvbox" --plain --color=always {}' --preview-window=right:70%)
  [ -n "$file" ] && vim "$file"
}

fbfind() {
  local file
  file=$(fzf-tmux -p 80%,60% --preview 'bat --theme="gruvbox-dark" --plain --color=always {}' --preview-window=right:70%)
  [ -n "$file" ] && bat --theme="gruvbox-dark" --plain --color=always "$file"
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
  bat --theme="gruvbox-dark" --plain "$(find ~/git/setup/groq/notes-groq -type f 2> /dev/null | fzf-tmux -p 70%,50% --preview 'bat --theme="gruvbox-dark" --plain --color=always --style=numbers {}' --preview-window=right:70%)"
}

