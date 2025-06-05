#!/bin/bash

# Check if session name is provided
if [ -z "$1" ]; then
  echo "Usage: $0 <session-name>"
  exit 1
fi

SESSION_NAME="$1"

source ~/.bin/home-functions.sh
pullallrepos
# Start a new detached tmux session
tmux new-session -d -s "$SESSION_NAME"

tmux select-pane -t "$SESSION_NAME:1.0"
tmux split-window -h

tmux select-pane -t "$SESSION_NAME:1.1"
tmux split-window -h

tmux select-pane -t "$SESSION_NAME:1.2"
tmux split-window -v

tmux send-keys -t "$SESSION_NAME:1.0" "cd ~/git/dc-tools/tools/gv-tui && ./setup.sh && source gv_tui_venv/bin/activate && python3 gv_tui.py" C-m
tmux send-keys -t "$SESSION_NAME:1.1" "cd ~/git/dc-tools/tools/gv-tui && ./setup.sh && source gv_tui_venv/bin/activate && python3 gv_tui.py" C-m
tmux send-keys -t "$SESSION_NAME:1.2" "k9s -c pod" C-m
tmux send-keys -t "$SESSION_NAME:1.3" "watch -n30 kval-status.sh --failed" C-m

# Attach to the session
tmux attach-session -t "$SESSION_NAME"
