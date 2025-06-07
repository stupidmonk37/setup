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

# +--------------------------+
# |        |        |   1.2  |
# |  1.0   |   1.1  |--------|
# |        |        |   1.3  |
# +--------------------------+

SESSION_NAME=""
NOPULL=false
DC_TOOLS_DIR="$HOME/git/dc-tools"
GV_TUI_DIR="$DC_TOOLS_DIR/tools/gv-tui"
GV_TUI_VENV="$GV_TUI_DIR/gv_tui_venv"
GV_TUI_PY="$GV_TUI_DIR/gv_tui.py"
PANE_0_CMD="cd $GV_TUI_DIR && ./setup.sh && source $GV_TUI_VENV/bin/activate && python3 $GV_TUI_PY"
PANE_1_CMD="cd $GV_TUI_DIR && ./setup.sh && source $GV_TUI_VENV/bin/activate && python3 $GV_TUI_PY"
PANE_2_CMD="k9s -c nodes"
PANE_3_CMD="watch -n30 kval-status.sh --failed"

PANE_CMDS=(
  "$PANE_0_CMD"
  "$PANE_1_CMD"
  "$PANE_2_CMD"
  "$PANE_3_CMD"
)

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
  if [ -f ~/git/setup/dotfiles/.bin/home-functions.sh ]; then
    source ~/git/setup/dotfiles/.bin/home-functions.sh
    newdev
  else
    echo "❌ Could not find home-functions.sh"
    exit 1
  fi
else
  echo "🛑 Skipping git pull..."
fi

# If session exists, refresh all panes
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  # Kill panes 0 and 1
  for pane in 0 1; do
    tmux send-keys -t "$SESSION_NAME:1.$pane" "q" C-m
    sleep 0.5
    tmux send-keys -t "$SESSION_NAME:1.$pane" "exec zsh" C-m
  done

  # Clear panes 2 and 3
  for pane in 2 3; do
    tmux send-keys -t "$SESSION_NAME:1.$pane" C-c "exec zsh" C-m
  done

  # Attach to session
  tmux attach-session -t "$SESSION_NAME"
  exit 0

else
  # Create new session
  tmux new-session -d -s "$SESSION_NAME" -n validation
  tmux send-keys -t "$SESSION_NAME:1.0" "exec zsh" C-m

  # Split panes
  tmux select-pane -t "$SESSION_NAME:1.0"
  tmux split-window -h
  tmux select-pane -t "$SESSION_NAME:1.1"
  tmux split-window -h
  tmux select-pane -t "$SESSION_NAME:1.2"
  tmux split-window -v

  # Send commands to panes
  for pane in 0 1 2 3; do
    tmux send-keys -t "$SESSION_NAME:1.$pane" "${PANE_CMDS[$pane]}" C-m
  done

  # Attach to session
  tmux attach-session -t "$SESSION_NAME"
fi
