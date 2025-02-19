#!/usr/bin/env bash

RACKS="$@"
[ -z "$RACKS" ] && { echo "Please provide a list of racks."; exit 1; }

clean_racks() {
    #set -x
    local rack_name="$1"
    NAMESPACE="${NAMESPACE:-groq-system}"

    echo "Cleaning up cross-rack, pods, jobs and iei for $rack_name"
    kubectl -n "$NAMESPACE" delete pod -l "validation.groq.io/rack=${rack_name}" | grep -v 'No resources found'
    kubectl -n "$NAMESPACE" delete job -l "validation.groq.io/rack=${rack_name}" | grep -v 'No resources found'
    kubectl -n "$NAMESPACE" delete iei -l "validation.groq.io/rack=${rack_name}" | grep -v 'No resources found'

    # cross-rack (AKA xrk)
    cell_r="$(sed -E "s/(c[0-9]+r)[0-9]+/\1/g" <<< "$rack_name")"
    rack_next="$(( ${rack_name#*r} + 1 ))"
    rack_name_next="${cell_r}${rack_next}"

    kubectl -n "$NAMESPACE" delete pod -l "validation.groq.io/cross-rack-${rack_name}=${rack_name_next}" | grep -v 'No resources found'
    kubectl -n "$NAMESPACE" delete job -l "validation.groq.io/cross-rack-${rack_name}=${rack_name_next}" | grep -v 'No resources found'
    kubectl -n "$NAMESPACE" delete iei -l "validation.groq.io/cross-rack-${rack_name}=${rack_name_next}" | grep -v 'No resources found'
}

export -f clean_racks

echo "$RACKS" | xargs -n 1 | parallel -j 60 clean_racks {}
