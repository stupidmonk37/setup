#!/bin/bash

# Usage info
usage() {
  echo "Usage: ./new_validation.sh <session-name> [--nopull]"
  exit 1
}

# Require at least one argument (session name)
#if [ $# -lt 1 ]; then
#  usage
#fi

# Default session name: current date/time like 2025-06-12_14-32-00
DEFAULT_SESSION_NAME=$(date +"%m/%d")
SESSION_NAME=""
NOPULL=false


# +--------------------------+
# |        |        |   1.2  |
# |  1.0   |   1.1  |--------|
# |        |        |   1.3  |
# +--------------------------+

SESSION_NAME=""
NOPULL=false
GIT_SETUP_DIR="$HOME/git/setup"
GV_TUI_DIR="$GIT_SETUP_DIR/groq/bin-groq/gv-tui"
#GV_TUI_VENV="$GV_TUI_DIR/gv_tui_venv/bin/activate"
GV_TUI_PY="$GV_TUI_DIR/gv_tui.py"
PANE_0_CMD="gv_tui"
PANE_1_CMD="gv_tui"
PANE_2_CMD="k9s -c nodes"
PANE_3_CMD="watch -n30 kval_status.sh --failed"

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

# Use default session name if none provided
if [ -z "$SESSION_NAME" ]; then
  SESSION_NAME="$DEFAULT_SESSION_NAME"
fi

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
    tmux send-keys -t "$SESSION_NAME:1.$pane" "source $HOME/.zshrc" C-m
  done

  # Clear panes 2 and 3
  for pane in 2 3; do
    tmux send-keys -t "$SESSION_NAME:1.$pane" C-c "source $HOME/.zshrc" C-m
  done

    # Attach to session
  if [ -z "$TMUX" ]; then
    tmux attach-session -t "$SESSION_NAME"
  else
    echo "✅ Session '$SESSION_NAME' created (you're already in tmux)"
  fi
  exit 0

else
  # Create new session
  tmux new-session -d -s "$SESSION_NAME" -n validation

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
