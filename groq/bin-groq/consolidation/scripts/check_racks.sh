#!/bin/bash
set -euo pipefail
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 rack1 rack2 rack3 ..."
    exit 1
fi
all_racks_ready=true
racks_not_ready=()
check_node() {
    local rack="$1"
    local idx="$2"
    local node="${rack}-gn${idx}"
    if kubectl get node "$node" > /dev/null 2>&1; then
        local qsfp mcu ready_status
        qsfp=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.groq\.innolight-updated-qsfp}' 2>/dev/null)
        mcu=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.groq\.mcu-verified}' 2>/dev/null)
        ready_status=$(kubectl get node "$node" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
        [ -z "$qsfp" ] && qsfp="false"
        [ -z "$mcu" ] && mcu="false"
        [ -z "$ready_status" ] && ready_status="False"
        echo -e "\033[94m$node\033[0m: Ready=$ready_status, groq.innolight-updated-qsfp=$qsfp, groq.mcu-verified=$mcu"
    else
        echo -e "\033[94m$node\033[0m: node not found"
    fi
}
export -f check_node
for rack in "$@"; do
    header=$(printf '%*s' ${#rack} '' | tr ' ' '=')
    echo -e "\033[33m$header\033[0m"
    echo -e "\033[33m$rack\033[0m"
    echo -e "\033[33m$header\033[0m"
    results=$(parallel -j9 check_node "$rack" ::: {1..9})
    sorted=$(echo "$results" | awk '{
        sub(/:$/, "", $1)
        split($1, a, "gn")
        print a[2] + 0, $0
    }' | sort -n | cut -d' ' -f2-)
    echo "$sorted"
    ready=true
    not_ready_nodes=""
    while IFS= read -r line; do
        if echo "$line" | grep -q "Node not found" || ! echo "$line" | grep -q "groq.innolight-updated-qsfp=true" || ! echo "$line" | grep -q "groq.mcu-verified=true" || ! echo "$line" | grep -q "Ready=True"; then
            ready=false
            not_ready_nodes+=$(echo -e "\033[31m$line\033[0m")$'\n'
        fi
    done <<< "$sorted"
    if $ready; then
        echo -e "✅ Rack \033[33m$rack\033[0m is ready for use"
    else
        echo -e "❌ Rack \033[33m$rack\033[0m is not ready for use"
        echo
        echo -e "Nodes not ready:"
        echo -e "$not_ready_nodes"
        all_racks_ready=false
        racks_not_ready+=("$rack")
    fi
    echo ""
done
if $all_racks_ready; then
    echo -e "🎉 All racks are ready for use"
else
    echo -e "😢 The following racks are not ready: ${racks_not_ready[*]}"
fi
