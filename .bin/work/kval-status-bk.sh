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

eval "$cmd"
