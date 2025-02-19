#!/bin/bash
# TODO - add allocation check

set -uo pipefail
if [ "$#" -eq 0 ]; then
    echo "Usage: $0 rack1 rack2 rack3 ..."
    exit 1
fi

context=$(kubectl config current-context)
header=$(printf '%*s' ${#context} '' | tr ' ' '=')
echo -e "\033[33m$header\033[0m"
echo -e "\033[33m$context\033[0m"
echo -e "\033[33m$header\033[0m"

all_racks_ready=true
racks_not_ready=()
check_node() {
    local rack="$1"
    local idx="$2"
    local node="${rack}-gn${idx}"
    if kubectl get node "$node" > /dev/null 2>&1; then
        local qsfp mcu ready_status pcie usb bios_conform bios_version
        qsfp=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.groq\.innolight-updated-qsfp}' 2>/dev/null)
        mcu=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.groq\.mcu-verified}' 2>/dev/null)
        ready_status=$(kubectl get node "$node" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)
        pcie=$(kubectl get node "$node" -o jsonpath='{.metadata.annotations.groq\.pci-devices}' 2>/dev/null)
        usb=$(kubectl get node "$node" -o jsonpath='{.metadata.annotations.groq\.usb-devices}' 2>/dev/null)
        bios_conform=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.groq\.node\.bios-conformance}' 2>/dev/null)
        bios_version=$(kubectl get node "$node" -o jsonpath='{.metadata.labels.groq\.node\.bios-version}' 2>/dev/null)
        pods=$(kubectl get pods -n groq-system | grep "$node" | awk '{print$1, $3}' 2>/dev/null)
        [ -z "$qsfp" ] && qsfp="false"
        [ -z "$mcu" ] && mcu="false"
        [ -z "$ready_status" ] && ready_status="False"
        [ -z "$pcie" ] && pcie="missing device"
        [ -z "$usb" ] && usb="missing device"
        [ -z "$bios_conform" ] && bios_conform="Check bios"
        [ -z "$bios_version" ] && bios_version="Check bios"
        echo -e "\033[94m$node\033[0m: Ready=$ready_status, groq.innolight-updated-qsfp=$qsfp, groq.mcu-verified=$mcu, pcie-devices=$pcie, usb-devices=$usb, bios-conformance=$bios_conform, bios-version=$bios_version"
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

    status=$(kubectl get pods -n groq-system | grep "$rack" | awk '{print$1, $3, $5}')

    if [ -z "$status" ]; then
        echo -e "\033[32mNo running pods\033[0m"
        #echo -e "\033[32mNo running pods\033[0m"
    else
        echo -e "\033[33mMost recent pods:\033[0m"
        #echo -e "\033[33mMost recent pods:\033[0m"
        echo "$status" | while IFS= read -r line; do
            echo -e "\033[33m$line\033[0m"
        done
    fi





    #echo "$status" | while IFS= read -r line; do
    #    echo -e "\033[31m$line\033[0m"
    #done
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
        if echo "$line" | grep -q "Node not found" || ! echo "$line" | grep -q "groq.innolight-updated-qsfp=true" || ! echo "$line" | grep -q "groq.mcu-verified=true" || ! echo "$line" | grep -q "Ready=True" || ! echo "$line" | grep -q "pcie-devices=0,1,2,3,4,5,6,7" || ! echo "$line" | grep -q "usb-devices=0,1,2,3,4,5,6,7" || ! echo "$line" | grep -q "bios-conformance=pass" || ! echo "$line" | grep -q "bios-version=2.8.v2"; then
            ready=false
            not_ready_nodes+=$(echo -e "\033[31m$line\033[0m")$'\n'
        fi
    done <<< "$sorted"
    if $ready; then
        echo -e "✅ Rack \033[33m$rack\033[0m is ready for use"
    else
        echo -e "❌ Rack \033[33m$rack\033[0m is not ready for use"
        echo -e "Nodes not ready:"
        echo -e "$not_ready_nodes"
        all_racks_ready=false
        racks_not_ready+=("$rack")
    fi
    echo ""
done
if $all_racks_ready; then
    echo -e "🎉 Rack(s) are ready for use"
else
    echo -e "😢 The following racks are not ready: ${racks_not_ready[*]}"
fi
