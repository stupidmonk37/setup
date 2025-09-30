#!/usr/bin/env bash
set -euo pipefail

# ---- Config (macOS only: uses BSD `date`) ----
BASE_URL="https://groq.atlassian.net"
JIRA_USER="jjensen@groq.com"
PROJECT_KEY="DCI"
FIELD_ID="customfield_10085" # "Data Center" field id
FIELD_NAME_ESC='Data Center[Dropdown]'
MAX_RESULTS=200
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

DC_CHOICE=""
SUMMARY_FILTER=""
show_help() {
  cat <<EOF
Usage: $(basename "$0") [-d DC] [-q QUERY]
  -d, --dc DC        Data Center value (e.g., YUL1). REQUIRED for non-interactive runs (e.g., watch).
  -q, --query QUERY  Optional summary text filter (e.g., "c0r72").
  -h, --help         Show this help.
Examples:
  $(basename "$0") -d YUL1
  watch -n 20 './$(basename "$0") -d YUL1 -q c0r72'
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
  -d | --dc)
    DC_CHOICE="${2:-}"
    shift 2
    ;;
  -q | --query)
    SUMMARY_FILTER="${2:-}"
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

# Prompt for DC only if interactive AND not provided
if [[ -z "${DC_CHOICE}" ]]; then
  if [[ -t 0 ]]; then
    read -rp "Enter Data Center (e.g., YUL1): " DC_CHOICE
    [[ -z "${DC_CHOICE// /}" ]] && {
      echo "No DC provided. Exiting."
      exit 1
    }
    echo "" # blank line for readability
  else
    echo "Error: DC is required in non-interactive mode. Use -d YUL1 (for watch)." >&2
    exit 2
  fi
fi

# Build JQL
JQL="project = ${PROJECT_KEY} AND issuetype = Sub-task AND \"${FIELD_NAME_ESC}\" = \"${DC_CHOICE}\" AND statusCategory IN (\"To Do\",\"In Progress\")"
if [[ -n "${SUMMARY_FILTER}" ]]; then
  # quote the filter for JQL text search in summary
  JQL="${JQL} AND summary ~ \"${SUMMARY_FILTER}\""
fi
JQL="${JQL} ORDER BY created ASC"

# Fetch
resp="$(curl -sS --fail-with-body "${CURL_OPTS[@]}" \
  -u "$JIRA_USER:$JIRA_TOKEN" -H "Accept: application/json" \
  -G "$BASE_URL/rest/api/3/search/jql" \
  --data-urlencode "jql=$JQL" \
  --data-urlencode "maxResults=$MAX_RESULTS" \
  --data-urlencode "fields=key,summary,status,statuscategorychangedate,${FIELD_ID},reporter,assignee")"

# Shape to TSV (Updated At raw ISO)
tsv="$(jq -r --arg base "$BASE_URL" --arg fid "$FIELD_ID" '
  (["DC","Updated At","STATUS","ASSIGNEE","REPORTER","SUMMARY","URL"]),
  (.issues[]? | [
      (.fields[$fid].value // "-"),
      (.fields.statuscategorychangedate // "-"),
      (.fields.status.name // "-"),
      (.fields.assignee.displayName // "-"),
      (.fields.reporter.displayName // "-"),
      ((.fields.summary // "-") | gsub("[\t\n\r]"; " ")),
      ($base + "/browse/" + .key)
  ]) | @tsv
' <<<"$resp")"

# macOS: format col 2 with BSD `date` to local 12h
awk -F'\t' -v dc="$DC_CHOICE" 'BEGIN{OFS="\t"}
  NR==1 { print; next }
  {
    if ($2 != "-") {
      gsub(/\.[0-9]+/, "", $2)  # strip .mmm
      cmd = "date -j -f \"%Y-%m-%dT%H:%M:%S%z\" \"" $2 "\" +\"%m/%d/%Y %I:%M %p\""
      cmd | getline f; close(cmd);
      if (f != "") $2 = f
    }
    print
  }' <<<"$tsv" |
  column -t -s $'\t'
