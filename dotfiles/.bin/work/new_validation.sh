#!/bin/bash

# Check if session name is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <session-name> [--nopull]"
  exit 1
fi

SESSION_NAME="$1"

# Optionally run newdev if --nopull is not passed
if [[ -z "$2" ]]; then
  source ~/.bin/home-functions.sh
  newdev
elif [[ "$2" == "--nopull" ]]; then
  echo "🛑 Skipping git pull..."
fi

# If session exists, refresh all panes instead of creating a new one
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "🔄 Session '$SESSION_NAME' already exists. Refreshing panes..."

  for pane in 0 1 2 3; do
    # Interrupt any running command, then reload zsh
    tmux send-keys -t "$SESSION_NAME:1.$pane" C-c "exec zsh" C-m
  done

  tmux attach-session -t "$SESSION_NAME"
  exit 0
fi

# Create a new tmux session and window layout
tmux new-session -d -s "$SESSION_NAME" -n validation

tmux select-pane -t "$SESSION_NAME:1.0"
tmux split-window -h
tmux select-pane -t "$SESSION_NAME:1.1"
tmux split-window -h
tmux select-pane -t "$SESSION_NAME:1.2"
tmux split-window -v

# Left vertical pane
tmux send-keys -t "$SESSION_NAME:1.0" "cd ~/git/dc-tools/tools/gv-tui && ./setup.sh && source gv_tui_venv/bin/activate && python3 gv_tui.py" C-m

# Middle vertical pane
tmux send-keys -t "$SESSION_NAME:1.1" "cd ~/git/dc-tools/tools/gv-tui && ./setup.sh && source gv_tui_venv/bin/activate && python3 gv_tui.py" C-m

# Top right pane
tmux send-keys -t "$SESSION_NAME:1.2" "k9s -c pod" C-m

# Bottom right pane
tmux send-keys -t "$SESSION_NAME:1.3" "watch -n30 kval-status.sh --failed" C-m

# Attach to the session
tmux attach-session -t "$SESSION_NAME"
