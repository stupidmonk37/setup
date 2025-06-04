#!/bin/bash
cmd="kubectl validation status"
racks=()
only_failed=false
all=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)
      all=true
      shift
      ;;
    --failed)
      only_failed=true
      shift
      ;;
    --racks)
      shift
      while [[ $# -gt 0 && "$1" != --* ]]; do
        racks+=("$1")
        shift
      done
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: kval-status.sh --all"
      echo "       kval-status.sh --racks <rack1> [rack2] [...]"
      echo "       kval-status.sh --failed"
      exit 1
      ;;
  esac
done

if $all; then
  cmd="kubectl validation status"
elif [[ ${#racks[@]} -gt 0 ]]; then
  IFS=','; cmd+=" --racks ${racks[*]}"; IFS=' '
elif $only_failed; then
  cmd+=" --only-failed"
else
  echo "Missing required flag."
  echo "Usage: kval-status.sh --all"
  echo "       kval-status.sh --racks <rack1> [rack2] [...]"
  echo "       kval-status.sh --failed"
  exit 1
fi

if $only_failed; then
  # Capture command output
  output=$($cmd 2>&1)
  marker="Some failures were identified. To inspect the logs, run:"
  if grep -qF "$marker" <<< "$output"; then
    echo "$output" | awk -v marker="$marker" 'BEGIN { found=0 } $0 ~ marker { found=1 } found'
  else
    echo "🎉 No failed racks!"
  fi
else
  eval "$cmd"
fi
