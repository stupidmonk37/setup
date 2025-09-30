#!/usr/bin/env bash
set -euo pipefail

# ---- Config (macOS only; uses BSD `date`) ----
BASE_URL="https://groq.atlassian.net"
JIRA_USER="jjensen@groq.com"
PROJECT_KEY="DCI"
FIELD_ID="customfield_10085" # "Data Center" field id
FIELD_NAME_ESC='Data Center[Dropdown]'
MAX_RESULTS_DEFAULT=20
CURL_OPTS=(--connect-timeout 10 --max-time 60 --retry 2 --retry-delay 1)
REQ_CMDS=(curl jq awk date column)
# ---------------------------------------------

for c in "${REQ_CMDS[@]}"; do
  command -v "$c" >/dev/null 2>&1 || {
    echo "Missing dependency: $c"
    exit 1
  }
done
: "${JIRA_TOKEN:?Please export JIRA_TOKEN=...}"

DC_FILTER=""
COUNT="$MAX_RESULTS_DEFAULT"

show_help() {
  cat <<EOF
Usage: $(basename "$0") [-d DC] [-n COUNT] [-h]
  -d, --dc DC        Optional Data Center (e.g., YUL1). If omitted, you'll be prompted (only in interactive shells).
  -n, --count COUNT  Number of tickets to show (default: ${MAX_RESULTS_DEFAULT}, max 100).
  -h, --help         Show help.

Examples:
  $(basename "$0")
  $(basename "$0") -n 50
  $(basename "$0") -d YUL1
  watch -n 20 './$(basename "$0") -d YUL1 -n 20'
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
  -d | --dc)
    DC_FILTER="${2:-}"
    shift 2
    ;;
  -n | --count)
    COUNT="${2:-}"
    shift 2
    ;;
  -h | --help)
    show_help
    exit 0
    ;;
  *)
    echo "Unknown arg: $1"
    show_help
    exit 2
    ;;
  esac
done

# Cap count (Jira maxResults for this endpoint is typically <=100)
if ! [[ "$COUNT" =~ ^[0-9]+$ ]]; then
  echo "COUNT must be a number"
  exit 2
fi
((COUNT < 1)) && COUNT=1
((COUNT > 100)) && COUNT=100

# Prompt for DC if not provided and running interactively
if [[ -z "$DC_FILTER" ]]; then
  if [[ -t 0 ]]; then
    read -rp "Enter Data Center (e.g., YUL1; leave blank for all): " DC_FILTER
    echo "" # blank line after prompt
  else
    echo "Error: Non-interactive mode detected. Supply DC with -d (e.g., -d YUL1) for watch usage." >&2
    exit 2
  fi
fi

# ---- Build JQL for "recently closed/done/abandoned" ----
# Primary: tickets in Done category (covers Done/Closed/etc.)
JQL="project = ${PROJECT_KEY} AND statusCategory = Done"
# Also include common “abandoned/cancelled/won’t do” names if not mapped to Done
JQL="(${JQL}) OR (project = ${PROJECT_KEY} AND status in (Abandoned, Cancelled, \"Won't Do\", \"Won’t Do\"))"

# Optional DC filter (only add if user typed something)
if [[ -n "${DC_FILTER// /}" ]]; then
  JQL="(${JQL}) AND \"${FIELD_NAME_ESC}\" = \"${DC_FILTER}\""
fi

# Order by the time it entered its current category (Done), most recent first
JQL="${JQL} ORDER BY statuscategorychangedate DESC"

# ---- Fetch once ----
resp="$(curl -sS --fail-with-body "${CURL_OPTS[@]}" \
  -u "$JIRA_USER:$JIRA_TOKEN" -H "Accept: application/json" \
  -G "$BASE_URL/rest/api/3/search/jql" \
  --data-urlencode "jql=$JQL" \
  --data-urlencode "maxResults=$COUNT" \
  --data-urlencode "fields=key,summary,status,statuscategorychangedate,resolution,resolutiondate,${FIELD_ID},reporter,assignee")"

# ---- Shape to TSV (Closed At: prefer resolutiondate else statuscategorychangedate) ----
tsv="$(jq -r --arg base "$BASE_URL" --arg fid "$FIELD_ID" '
  (["DC","Closed At","STATUS","ASSIGNEE","REPORTER","SUMMARY","URL"]),
  (.issues[]? | [
      (.fields[$fid].value // "-"),
      ((.fields.resolutiondate // .fields.statuscategorychangedate) // "-"),
      (.fields.status.name // "-"),
      (.fields.assignee.displayName // "-"),
      (.fields.reporter.displayName // "-"),
      ((.fields.summary // "-") | gsub("[\t\n\r]"; " ")),
      ($base + "/browse/" + .key)
  ]) | @tsv
' <<<"$resp")"

# ---- macOS: format "Closed At" (col 2) to local 12h with BSD date ----
awk -F'\t' 'BEGIN{OFS="\t"}
  NR==1 { print; next }
  {
    if ($2 != "-") {
      gsub(/\.[0-9]+/, "", $2)  # strip milliseconds if present
      cmd = "date -j -f \"%Y-%m-%dT%H:%M:%S%z\" \"" $2 "\" +\"%m/%d/%Y %I:%M %p\""
      cmd | getline f; close(cmd);
      if (f != "") $2 = f
    }
    print
  }' <<<"$tsv" | column -t -s $'\t'
