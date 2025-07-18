#! /bin/bash

# Run a command in all panes of a tmux session
# (ie tmux_all_panes "kubectl get pods")
tmux_all_panes() {
  local cmd="$*"
  if [ -z "$cmd" ]; then
    echo "❌ No command provided."
    echo "Usage: run_in_all_panes <command>"
    return 1
  fi

  for pane in $(tmux list-panes -F '#P'); do
    tmux send-keys -t "$pane" "$cmd" C-m
  done
}


# Switch to a different Kubernetes context and namespace
# (ie k8s-switch)
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


run_spinner() {
  if [ -n "$ZSH_VERSION" ]; then
    emulate -L zsh
    setopt NO_MONITOR
  fi

   local msg="$1"
   shift

   local output_file
   output_file=$(mktemp)
   "$@" &> "$output_file" &
   local pid=$!
   local spin='-\|/'
   local i=0

   while kill -0 $pid 2>/dev/null; do
     i=$(( (i + 1) % 4 ))
     printf "\r    [%s] %s" "${spin:$i:1}" "$msg"
     sleep 0.1
   done

   wait $pid
   run_spinner_status=$?
   run_spinner_output=$(<"$output_file")
   rm -f "$output_file"

   # Clear the spinner line (no status symbol here)
   printf "\r\033[K"
}

homebrew_update() {
  echo ""
  echo "🍺 Updating Homebrew..."

  # Declare commands and labels
  local cmds=(
    "brew update"
    "brew upgrade"
    "brew upgrade --cask"
    "brew cleanup"
  )

  for cmd in "${cmds[@]}"; do
    local label="$cmd"
    eval run_spinner "\"$label\"" $cmd

    if [ $run_spinner_status -eq 0 ]; then
      printf "    ✅ %s\n" "$label"
    else
      printf "    ❌ %s\n" "$label"
    fi
  done

  echo "🍻 Done - Homebrew updated"
}

pull_repos() {
  echo ""
  echo "🗂️ Pulling repos..."

  local updated=0
  local skipped=0
  local failed=0

  find "$HOME/git" -maxdepth 2 -name .git -type d | while IFS= read -r d; do
    local repo_path=$(dirname "$d")
    local repo_name=$(basename "$repo_path")
    local parent_name=$(basename "$(dirname "$repo_path")")
    local display_name="$parent_name/$repo_name"

  run_spinner "$display_name" git -C "$repo_path" pull

  if [ $run_spinner_status -eq 0 ]; then
    if echo "$run_spinner_output" | grep -q "Already up to date"; then
      printf "    ⏭️ %s\n" "$display_name"
      ((skipped++))
    else
      printf "    ✅ %s\n" "$display_name"
      ((updated++))
    fi
  else
    printf "    ❌ %s\n" "$display_name"
    ((failed++))
  fi

  done

  if (( updated > 0 || failed > 0 )); then
    echo "🗂️ Done: $updated updated, $skipped up to date, $failed failed."
  else
    echo "✅ All $skipped repositories were already up to date."
  fi
}

newdev() {
  echo ""
  echo "🔄 Updating all the things..."
  echo ""

  curl -fsSL https://storage.googleapis.com/bkt-c-onboarding-public-us-d9a6/bootstrap.sh | NO_K8S_CONFIG=true bash
  homebrew_update
  pull_repos

  echo ""
  echo "🎉 Done - All the things updated"
  echo ""
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
			--preview-window=right:50%:wrap) || return

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
  file=$(fzf-tmux --exact -p 80%,60% --preview 'bat --theme="gruvbox" --style=plain --color=always {}' --preview-window=right:50%)
  [ -n "$file" ] && vim "$file"
}

fbfind() {
  local file
  file=$(fzf-tmux --exact -p 80%,60% --preview 'bat --theme="gruvbox-dark" --style=plain --color=always {}' --preview-window=right:50%)
  [ -n "$file" ] && bat --theme="gruvbox-dark" --plain --color=always "$file"
}

fnotes() {
  bat --theme="gruvbox-dark" --style=plain "$(find ~/git/setup/groq/notes-groq/* -type f 2> /dev/null | fzf-tmux --exact -p 70%,50% --preview 'bat --theme="gruvbox-dark" --style=plain --color=always {}' --preview-window=right:50%)"
}

