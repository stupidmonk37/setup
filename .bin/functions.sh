#!/usr/bin/env bash

# parallel uses single quotes which breaks the shellcheck
# shellcheck disable=SC2016

# Get logs from failed pods
# Append strings to filter the output
# (ie stern-failed missing-optics-c1r1)
# You can also append '-o raw' to get a pure json output
#alias stern-failed="stern --no-follow --only-log-lines --field-selector status.phase=Failed"

# Append strings to filter the output
# Never follow the logs, and only show the log lines
#alias stern-no="stern --no-follow --only-log-lines"

# Get metadata about a single rack
# (ie kc_rack_info c1r1)
k-rack-info(){
    local rack="$1"
    [ -z "$rack" ] && { echo "Please provide rack regex"; return 1; }
    kubectl racks -ojson | \
        jq --arg rack "$rack" '.items[] | select(.metadata.name==$rack)'
}

# Get the logs from a node's tspd pod
# (ie kc_tspd_log c1r1-gn1)
#kc_tspd_log() {
#    local node="$1"
#    [ -z "$node" ] && { echo "Please provide a node."; return 1; }
#    kubectl logs -c bring-up \
#        "$(kubectl get pod -l app=tspd --field-selector spec.nodeName="$node" -o name) -f"
#}

# Execute a command on a node's tspd pod and tspd container
# (ie kc_tspd_exec c1r1-gn1 "tspctl status")
#kc_tspd_exec() {
#    local node="$1"
#    [ -z "$node" ] && { echo "Please provide a node."; return 1; }
#    shift
#    local action="$*"
#    [ -z "$action" ] && { echo "Please provide an action to perform."; return 1; }
#    kubectl exec -it -c tspd \
#        "$(kubectl get pod -l app=tspd --field-selector spec.nodeName="$node" -o name)" -- "$action"
#}

# Get the logs from a bios-conformance pod
# (ie kc_bios_conformance_log c1r1-gn1)
#kc_bios_conformance_log() {
#    local node="$1"
#    [ -z "$node" ] && { echo "Please provide a node."; return 1; }
#    kubectl logs \
#        "$(kubectl get pod -l app=bios-conformance --field-selector spec.nodeName="$node" -o name)"
#}

# Get or delete tspd pods from specified racks
# (ie kc_tspd c1r1 c1r2)
# (ie kc_tspd delete c1r1 c1r2)
k-tspd() {
    local action="get"
    local headers="--no-headers"
    if [ "$1" = "delete" ]; then
        action="delete"
        headers=""
        shift
    fi
    local racks=("$@")
    [ ${#racks[@]} -eq 0 ] && { echo "Please provide rack names."; return 1; }
    
    for rack in "${racks[@]}"; do
        echo "$rack $action tspd pod"
        kubectl "$action" $headers \
            "$(
                echo {1..9} | \
                    xargs -n 1 | \
                    parallel -j 9 kubectl get pod \
                        -n groq-system \
                        -l app=tspd \
                        --field-selector spec.nodeName="${rack}-gn{}" \
                        --no-headers \
                        -o name
            )"
    done
}

# Get or delete cilium pods from specified racks
# Note: This is a kube-system pod and you need special permissions to delete it
# https://groq.slack.com/archives/C06TK3B9RB8/p1738874940045959
# (ie kc_cilium c1r1 c1r2)
# (ie kc_cilium delete c1r1 c1r2)
#kc_cilium() {
#    local action="get"
#    local headers="--no-headers"
#    if [ "$1" = "delete" ]; then
#        action="delete"
#        headers=""
#        shift
#    fi
#    local racks=("$@")
#    [ ${#racks[@]} -eq 0 ] && { echo "Please provide rack names."; return 1; }
#
#    for rack in "${racks[@]}"; do
#        echo "$rack $action cilium pod"
#        kubectl -n kube-system "$action" $headers \
#            "$(
#                echo {1..9} |\
#                    xargs -n 1 | \
#                    parallel -j 9 kubectl get pod \
#                        -n kube-system \
#                        -l app.kubernetes.io/name=cilium-agent \
#                        --field-selector spec.nodeName="${rack}-gn{}" \
#                        --no-headers \
#                        -o name
#            )"
#    done
#}

# Get or delete bios-conformance pods from specified racks
# (ie kc_bios_conformance c1r1 c1r2)
# (ie kc_bios_conformance delete c1r1 c1r2)
k-bios-conformance() {
    local action="get"
    local headers="--no-headers"
    if [ "$1" = "delete" ]; then
        action="delete"
        headers=""
        shift
    fi
    local racks=("$@")
    [ ${#racks[@]} -eq 0 ] && { echo "Please provide rack names."; return 1; }

    for rack in "${racks[@]}"; do
        echo "$rack $action bios-conformance pod"
        kubectl -n groq-system "$action" $headers \
            "$(
                echo {1..9} |\
                    xargs -n 1 | \
                    parallel -j 9 kubectl get pod \
                        -n groq-system \
                        -l app=bios-conformance \
                        --field-selector spec.nodeName="${rack}-gn{}" \
                        --no-headers \
                        -o name
            )"
    done
}

# Execute IPMI power commands on a node
# (ie node_ipmi c1r1)
# (ie node_ipmi c1r1 cycle)
k-node-ipmi() {
    local node="$1"
    local ipmi_cmd="${2:-"status"}"
    [ -z "$node" ] && { echo "Please provide node name (short name)."; return 1; }
    kc_context="$(kubectl config current-context)"
    dc="${dc:-${kc_context%-*}}"
    fqdn="${node}-bmc.${dc}.groq.net"

    ipmitool -H "$fqdn" -U root -P GroqRocks1 power "$ipmi_cmd"
}
# Export the function so it can be used in other scripts
export -f k-node-ipmi

# Function to execute IPMI commands on all nodes in specified racks
# The default action is 'status'
# (ie rack_ipmi c1r1 c1r2)
# (ie rack_ipmi cycle c1r1 c1r2)
k-rack-ipmi() {
    local ipmi_action="status"
    local found_action="false"
    local ipmi_actions=(
        status
        cycle
        on
        off
        bios
        disk
        pxe
    )
    
    RACKS=("$@")
    [ "${#RACKS[@]}" -eq 0 ] && {
        echo "Usage: rack_ipmi <action> <rack1> <rack2> ... Default action is 'status'"
        return 1
        }
    
    for action in "${ipmi_actions[@]}"; do
        if [[ "$action" == "$1" ]]; then
            found_action="true"
            break
        fi
    done
    if [[ "$found_action" == "false" ]]; then
        echo "No valid action provided. Defaulting to 'status'."
    fi
    
    bmc_names=()
    kc_context="$(kubectl config current-context)"
    domain="${kc_context%-*}"
    
    for rack in "${RACKS[@]}"; do
        for N in {1..9}; do
            bmc_names+=("${rack}-gn${N}-bmc.${domain}.groq.net")
        done
    done
    
    case "$ipmi_action" in
        status) 
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(digshort {}) $(ipmitool -H {} -U root -P GroqRocks1 power status)' | sort -V ;;
        cycle) 
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power cycle)' | sort -V ;;
        on)
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power on)' | sort -V ;;
        off)
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power off)' | sort -V ;;
        bios)
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 chassis bootdev bios)' | sort -V ;;
        disk)
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 chassis bootdev disk)' | sort -V ;;
        pxe)
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 chassis bootdev pxe options=efiboot)' | sort -V ;;
        *) 
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power status)' | sort -V
            echo "Default is 'power status'. Available: ${ipmi_actions[*]}"
            echo
        ;;
    esac
}
# Export the function so it can be used in other scripts
export -f k-rack-ipmi

# Get the BIOS version of all nodes
k-bios-version() {
    kubectl get node -l groq.node=true -o json | \
        jq -r '
            .items[]
            | [
                .metadata.name,
                .metadata.annotations."dmi.bios_version"
              ]
            | @tsv' | \
        sort -V
}

# Get the board name of all nodes
# The board_name should always the same throughout the fleet
#kc_board_name() {
#    kubectl get node -l groq.node=true -o json | \
#        jq -r '
#            .items[]
#            | [
#                .metadata.name,
#                .metadata.annotations."dmi.board_name"
#              ]
#            | @tsv' | \
#        sort -V
#}

# Open a BMC console for a single node
# (ie node_console c1r1)
#node_console() {
#    local node="$1"
#    [ -z "$node" ] && { echo "Please provide node name (short name)."; return 1; }
#    kc_context="$(kubectl config current-context)"
#    dc="${dc:-${kc_context%-*}}"
#    fqdn="${node}-bmc.${dc}.groq.net"
#
#    ipmiconsole -h "$fqdn" -u root -p GroqRocks1
#}

# Get the tspd image versions of all nodes
# All nodes should be running the same tspd image
k-tspd-images() {
    kc get pods -l app=tspd -o json | \
        jq -r '
            .items[]
            | [.spec.nodeName, (
                [.status.containerStatuses[]
                | select(.name == "agent")][0].imageID)]
                | @tsv' | \
        sort -k 2 -r
}

# Get rack completion status on a per node basis
# This is also a good example of how to use the custom columns output
k-racks-complete() {
    kubectl get nodes \
      -l "topology.groq.io/server-type=smc-groqnode" \
      -o custom-columns="$(
        printf "NODE:.metadata.name,"
        printf "STATUS:.status.conditions[-1].type,"
        printf "NODE_C:.metadata.labels.validation\\.groq\\.io\\/node-complete,"
        printf "RACK_C:.metadata.labels.validation\\.groq\\.io\\/rack-complete,"
        printf "XRACK_C:.metadata.labels.validation\\.groq\\.io\\/cross-rack-complete,"
        printf "NODE_AT:.metadata.annotations.validation\\.groq\\.io\\/node-completed-at,"
        printf "RACK_AT:.metadata.annotations.validation\\.groq\\.io\\/rack-completed-at"
      ) | sort -V"
}

# Get Anodizer leases based on the current context
# (ie get_leases | jq -r 'select(.hostname|test("c1r1")) | [.hostname, .ip] | @tsv'
k-get-leases() {
    kc_context="$(kubectl config current-context)"
    dc="${dc:-${kc_context%-*}}"
    curl -s "http://anodizer-api.${dc}.groq.net/api/v1/dhcp/leases" | jq '.active[]'
}

# Only display validated racks with the the 'next' label
# Requires kubectl-racks version 1.11.0 or higher
#kc_racks() {
#    kubectl racks -o \
#        custom-columns="Rack_Name:metadata.name,Rack_Valid_Date:rackValidatedAt,Next:next"
#}

# Get allocated racks that are in production
# We exclude the groq-system namespace (hw validation)
#kc_allocated() {
#    kubectl racks -o json | \
#        jq -r '
#            .items[]
#            | select(.allocated==true)
#            | select(.modelInstanceNamespace|test("^(?!groq-system)"))
#            | [.metadata.name, .modelInstance] | @tsv' | \
#        sort -V
#}

# Prmarily used at the beginning of a power-pod bring-up
# This will show racks that are ready for hardware validation
#kc_ready() {
#    kubectl racks -o json | \
#        jq -r '
#            .items
#            | .[]
#            | select(.status=="Ready")
#            | .metadata.name' | \
#        sort -V
#}

# Get racks that have at least one node that is NotReady or Missing
#kc_not_ready() {
#    kubectl racks -o json | \
#        jq -r '
#            .items
#            | .[]
#            | select(.status|test("NotReady|NodeMissing"))
#            | .metadata.name' | \
#        sort -V
#}

# Get racks that have at least one node that is cordoned
#kc_repair() {
#    kubectl racks -o json | \
#        jq -r '
#            .items
#            | .[]
#            | select(.status=="Repair")
#            | .metadata.name' | \
#        sort -V
#}

# Get the status of a list of racks
k-get-racks() {
    local racks=("$@")
    echo "${racks[@]}" | xargs -n 1 | \
        parallel -j 60 kubectl get nodes -o wide --no-headers -l topology.groq.io/rack="{}" | sort -V
}

# Get all the pods running on GPCs
# This is useful to check if the GPCs are running the hw validation pods
#kc_gpc_pods() {
#    kubectl get nodes -l topology.groq.io/server-type=dell-gpc -o json | \
#        jq -r '
#            .items[].metadata.name' | \
#        xargs -I {} kubectl get pods -A \
#            --field-selector spec.nodeName={},status.phase!=Succeeded,status.phase!=Failed \
#            -o custom-columns=NODE:.spec.nodeName,NAME:.metadata.name | \
#        sort | uniq
#}
