#!/usr/bin/env bash

#set +m  # Disable job control messages

k-pod-check() {
  local base_nodes=("$@")

  local data
  data=$( (
    for base in "${base_nodes[@]}"; do
      for i in $(seq 1 9); do
        node="${base}-gn${i}"
        kubectl get pods --field-selector spec.nodeName="$node" -o json 2>/dev/null || true
      done
    done
  ) | jq -r '
    .items[]? |
    select(.status.phase != "Succeeded") |
    (.status.phase) as $status |
    (.metadata.name) as $name |
    (.spec.nodeName) as $node |
    ([.status.containerStatuses[]?.ready] | map(if . then 1 else 0 end) | add) as $ready_count |
    ([.status.containerStatuses[]?] | length) as $total_count |
    ($node | capture("c(?<cluster>\\d+)r(?<rack>\\d+)-gn(?<gn>\\d+)")) as $node_match |
    [
      $name,
      ($node_match.gn | tonumber),
      "\($ready_count)/\($total_count)",
      $status,
      $node
    ] | @tsv
  ')

  {
    echo -e "NAME\tREADY\tSTATUS\tNODE"
    echo -e "$data" | sort -t $'\t' -k1,1 -k2,2n | cut -f1,3-5
  } | column -t -s $'\t'

  echo
  echo "Summary:"

  echo "$data" | cut -f1 \
    | sed -E 's/-[a-z0-9]{5}$//' \
    | sort | uniq -c | awk '
      {
        names[$2] = $1
        if (length($2) > max_len) max_len = length($2)
      }
      END {
        for (name in names) {
          printf "%" max_len "s: %s pods\n", name, names[name]
        }
      }' | sort
}


# Check the label of a rack's nodes
# (ie label-check-rack c1r1)
label-check-rack() {
  for RACK in "$@" ; do
    for i in gn{1..9} ; do
      NODE="${RACK}-${i}"
      value=$(kubectl get node "$NODE" -o json 2>/dev/null | jq -r '.metadata.labels["validation.groq.io/next-complete"]')

      if [[ "$value" == "true" ]]; then
        echo "$NODE: pass"
      elif [[ -z "$value" ]] || [[ "$value" == "null" ]]; then
        echo "$NODE: fail (label missing)"
      else
        echo "$NODE: fail"
      fi
    done
  done
}


# Get the status of a list of nodes
# (ie knodes c1r1 c1r2)
knodes() {
  local condition='NR == 1'
  for rack in "$@"; do
    condition+=" || \$1 ~ /${rack}-/"
  done

  kubectl get nodes | awk "$condition"
}


# Get the status of a list of racks
# (ie kracks c1r1 c1r2)
kracks() {
  local all=false
  local racks=()

  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--all" ]]; then
      all=true
      shift
    elif [[ "$1" == "--racks" ]]; then
      shift
      while [[ $# -gt 0 && "$1" != --* ]]; do
        racks+=("$1")
        shift
      done
    else
      echo "Unknown option: $1"
      echo "Usage: kracks --all                            # List information for all racks"
      echo "       kracks --racks <rack1> [rack2] [...]    # List information for specific racks"
      return 1
    fi
  done

  if $all; then
    kubectl racks -o wide
  elif [[ ${#racks[@]} -gt 0 ]]; then
    local conditions='NR == 1'
    for rack in "${racks[@]}"; do
      conditions+=" || \$1 == \"$rack\""
    done
    kubectl racks -o wide | awk "$conditions"
  else
    echo "Missing required flag."
    echo "Usage: kracks --all                            # List information for all racks"
    echo "       kracks --racks <rack1> [rack2] [...]    # List information for specific racks"
    return 1
  fi
}


# Get logs from failed pods
# Append strings to filter the output
# (ie stern-failed missing-optics-c1r1)
# You can also append '-o raw' to get a pure json output
#alias stern-failed="stern --no-follow --only-log-lines --field-selector status.phase=Failed"

# Append strings to filter the output
# Never follow the logs, and only show the log lines
#alias stern-no="stern --no-follow --only-log-lines"

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
            $(
                echo {1..9} | \
                    xargs -n 1 | \
                    parallel -j 9 kubectl get pod \
                        -n groq-system \
                        -l app=tspd \
                        --field-selector spec.nodeName="${rack}-gn{}" \
                        --no-headers \
                        -o name
            )
    done
}


# Execute IPMI power commands on a node
# (ie node_ipmi c1r1)
# (ie node_ipmi c1r1 cycle)
knodes-ipmi() {
    local node="$1"
    local ipmi_cmd="${2:-"status"}"
    [ -z "$node" ] && { echo "Please provide node name (short name)."; return 1; }
    kc_context="$(kubectl config current-context)"
    #dc="${dc:-${kc_context%-*}}"
    fqdn="${node}-bmc.${kc_context}.groq.net"

    ipmitool -H "$fqdn" -U root -P GroqRocks1 power "$ipmi_cmd"
}


# Function to execute IPMI commands on all nodes in specified racks
# The default action is 'status'
# (ie rack_ipmi c1r1 c1r2)
# (ie rack_ipmi cycle c1r1 c1r2)
kracks-ipmi() {
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
    #dc="${dc:-${kc_context%-*}}"
    
    for rack in "${RACKS[@]}"; do
        for N in {1..9}; do
            bmc_names+=("${rack}-gn${N}-bmc.${kc_context}.groq.net")
        done
    done
    
    case "$ipmi_action" in
        status) 
            echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(dig +short {}) $(ipmitool -H {} -U root -P GroqRocks1 power status)' | sort -V ;;
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


# Get Anodizer leases based on the current context
# (ie get_leases | jq -r 'select(.hostname|test("c1r1")) | [.hostname, .ip] | @tsv'
k-get-leases() {
    local filter="$1"
    kc_context="$(kubectl config current-context)"

    if [ -n "$filter" ]; then
        {
            echo -e "HOSTNAME\tIP\tMAC\tSTATUS"
            curl -s "http://anodizer-api.${kc_context}.groq.net/api/v1/dhcp/leases" | \
                jq -r --arg f "$filter" '
                    .active[]
                    | select(.hostname | test($f))
                    | [.hostname, .ip, .mac, .status]
                    | @tsv' | sort
        } | column -t -s $'\t'
    else
        curl -s "http://anodizer-api.${kc_context}.groq.net/api/v1/dhcp/leases" | \
            jq '.active[]'
    fi
}
