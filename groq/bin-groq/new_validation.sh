#!/bin/bash

# Usage info
usage() {
  echo "Usage: ./new_validation.sh <session-name> [--nopull]"
  exit 1
}

# Require at least one argument (session name)
if [ $# -lt 1 ]; then
  usage
fi

SESSION_NAME=""
NOPULL=false

# Parse arguments
for arg in "$@"; do
  case "$arg" in
    --nopull)
      NOPULL=true
      ;;
    *)
      if [ -z "$SESSION_NAME" ]; then
        SESSION_NAME="$arg"
      else
        echo "❌ Unknown argument: $arg"
        usage
      fi
      ;;
  esac
done

# Run newdev unless --nopull is passed
if [ "$NOPULL" = false ]; then
  source ~/.bin/home-functions.sh
  newdev
else
  echo "🛑 Skipping git pull..."
fi

# If session exists, refresh all panes
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  echo "🔄 Session '$SESSION_NAME' already exists. Refreshing panes..."

  for pane in 0 1 2 3; do
    tmux send-keys -t "$SESSION_NAME:1.$pane" C-c "exec zsh" C-m
  done

  tmux attach-session -t "$SESSION_NAME"
  exit 0
fi

# Create new tmux session and layout
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
tmux send-keys -t "$SESSION_NAME:1.2" "k9s -c nodes" C-m

# Bottom right pane
tmux send-keys -t "$SESSION_NAME:1.3" "watch -n30 kval-status.sh --failed" C-m

# Attach to the session
tmux attach-session -t "$SESSION_NAME"
