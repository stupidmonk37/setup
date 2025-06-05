#! /bin/bash

newdev() {

# =========================================================================
# =====[ UPDATE HOMEBREW ]=================================================
# =========================================================================
#update_homebrew() {
#  header "Updating and cleaning Homebrew"
#  run_with_spinner " Updating brew" brew update
#  run_with_spinner " Upgrading brew" brew upgrade
#  run_with_spinner " Upgrading casks" brew upgrade --cask
#  run_with_spinner " Cleaning up" brew cleanup
#}

  local updated=0
  local skipped=0
  local failed=0

  # groq specific tools
  #update-tools
  curl -fsSL https://storage.googleapis.com/bkt-c-onboarding-public-us-d9a6/bootstrap.sh | NO_K8S_CONFIG=true bash

  echo ""
  echo "🗂️ Pulling repos..."
  echo ""

  find "$HOME/git" -maxdepth 3 -name .git -type d | while IFS= read -r d; do
    local repo_path
    repo_path=$(dirname "$d")
    local parent_name
    parent_name=$(basename "$(dirname "$repo_path")")
    local repo_name
    repo_name=$(basename "$repo_path")
    local display_name="$parent_name/$repo_name"

    local output_file
    output_file=$(mktemp)

    git -C "$repo_path" pull &> "$output_file" &
    local pid=$!

    local spin='-\|/'
    local i=0

    while kill -0 $pid 2>/dev/null; do
      i=$(( (i + 1) % 4 ))
      printf "\r    [%s] %s" "${spin:$i:1}" "$display_name"
      sleep 0.1
    done

    wait $pid
    local exit_status=$?

    local output
    output=$(<"$output_file")
    rm -f "$output_file"

    if [ $exit_status -eq 0 ]; then
      if echo "$output" | grep -q "Already up to date"; then
        printf "\r\033[K    ⏭️  %s\n" "$display_name"
        skipped=$((skipped + 1))
      else
        printf "\r\033[K    ✅ %s\n" "$display_name"
        updated=$((updated + 1))
      fi
    else
      printf "\r\033[K    ❌ %s\n" "$display_name"
      failed=$((failed + 1))
    fi
  done

  echo ""
  if (( updated > 0 || failed > 0 )); then
    echo "🎉 Done: $updated updated, $skipped up to date, $failed failed."
  else
    echo "✅ All $skipped repositories were already up to date."
  fi
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

fh() {
  eval "$(history | fzf | sed 's/ *[0-9]* *//')"
}

fnotes() {
  bat --theme="gruvbox-dark" --style=plain "$(find ~/git/setup/groq/notes-groq/* -type f 2> /dev/null | fzf-tmux --exact -p 70%,50% --preview 'bat --theme="gruvbox-dark" --style=plain --color=always {}' --preview-window=right:50%)"
}

