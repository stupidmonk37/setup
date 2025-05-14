#!/usr/bin/env bash

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

kval-logs() {
  local cmd="kubectl-validation logs fetch --validation"
  local racks=()
  local all=false

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
      echo "Usage: kval-logs --all                            # Fetch logs for all nodes/racks"
      echo "       kval-logs --racks <rack1> [rack2] [...]    # Fetch logs for specific rack(s)"
      return 1
    fi
  done

  if $all; then
    cmd+=" --all"
  elif [[ ${#racks[@]} -gt 0 ]]; then
    cmd+=" ${(j: :)${racks[@]}}"
  else
    echo "Missing required flag."
    echo "Usage: kval-logs --all                            # Fetch logs for all nodes/racks"
    echo "       kval-logs --racks <rack1> [rack2] [...]    # Fetch logs for specific rack(s)"
    return 1
  fi

  eval "$cmd"
}

kval-status() {
  local cmd="kubectl validation status"
  local racks=()
  local only_failed=false
  local all=false

  while [[ $# -gt 0 ]]; do
    if [[ "$1" == "--all" ]]; then
      all=true
      shift
    elif [[ "$1" == "--failed" ]]; then
      only_failed=true
      shift
    elif [[ "$1" == "--racks" ]]; then
      shift
      while [[ $# -gt 0 && "$1" != --* ]]; do
        racks+=("$1")
        shift
      done
    else
      echo "Unknown option: $1"
      echo "Usage: kval-status --all                            # Show validation status for all nodes"
      echo "       kval-status --racks <rack1> [rack2] [...]    # Show status for specific racks"
      echo "       kval-status --failed                         # Show only failed validations"
      return 1
    fi
  done

  if $all; then
    cmd="kubectl validation status"
  elif [[ ${#racks[@]} -gt 0 ]]; then
    cmd+=" --racks ${(j:,:)"${racks[@]}"}"
  elif $only_failed; then
    cmd+=" --only-failed"
  else
    echo "Missing required flag."
    echo "Usage: kval-status --all                            # Show validation status for all nodes"
    echo "       kval-status --racks <rack1> [rack2] [...]    # Show status for specific racks"
    echo "       kval-status --failed                         # Show only failed validations"
    return 1
  fi

  eval "$cmd"
}

kctx() {
  local context
  context=$(kubectl config get-contexts -o name | fzf --prompt="K8s Context > ")
  [[ -n "$context" ]] && kubectl config use-context "$context"
}

k8s-switch() {
  echo "🔍 Select a Kubernetes context:"
  local context=$(kubectl config get-contexts -o name | fzf --prompt="Context > ")
  [[ -z "$context" ]] && echo "❌ No context selected." && return

  kubectl config use-context "$context"

  echo "📦 Fetching namespaces for context: $context"
  local namespace=$(kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n' | fzf --prompt="Namespace > ")
  [[ -z "$namespace" ]] && echo "⚠️ No namespace selected — keeping default." && return

  kubectl config set-context --current --namespace="$namespace"

  echo "✅ Switched to context: $context with namespace: $namespace"
}

knodes() {
  local condition='NR == 1'
  for rack in "$@"; do
    condition+=" || \$1 ~ /${rack}-/"
  done

  kubectl get nodes | awk "$condition"
}

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

kcheck() {
    if [ "$#" -eq 0 ]; then
        echo "Usage: kcheck <rack1> [rack2] [...]"
        return 1
    fi

    local racks=("$@")

    echo "\nRack information:"
    echo "=========================="
    local rack_conditions="NR == 1"
    for rack in "${racks[@]}"; do
        rack_conditions+=" || \$1 == \"$rack\""
    done
    kubectl racks -o wide | awk "$rack_conditions"

    echo "\nNode status:"
    echo "=========================="
    local node_conditions="NR == 1"
    for rack in "${racks[@]}"; do
        node_conditions+=" || \$1 ~ /^${rack}-/"
    done
    kubectl get nodes | awk "$node_conditions"

    echo "\nValidation status:"
    echo "=========================="
    kubectl validation status --racks "$(IFS=,; echo "${racks[*]}")"
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

# Execute IPMI power commands on a node
# (ie node_ipmi c1r1)
# (ie node_ipmi c1r1 cycle)
knodes-ipmi() {
    local node="$1"
    local ipmi_cmd="${2:-"status"}"
    [ -z "$node" ] && { echo "Please provide node name (short name)."; return 1; }
    kc_context="$(kubectl config current-context)"
    dc="${dc:-${kc_context%-*}}"
    fqdn="${node}-bmc.${dc}.groq.net"

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

# Get Anodizer leases based on the current context
# (ie get_leases | jq -r 'select(.hostname|test("c1r1")) | [.hostname, .ip] | @tsv'
k-get-leases() {
    kc_context="$(kubectl config current-context)"
    dc="${dc:-${kc_context%-*}}"
    curl -s "http://anodizer-api.${dc}.groq.net/api/v1/dhcp/leases" | jq '.active[]'
}

# Get the status of a list of racks
k-get-racks() {
    local racks=("$@")
    echo "${racks[@]}" | xargs -n 1 | \
        parallel -j 60 kubectl get nodes -o wide --no-headers -l topology.groq.io/rack="{}" | sort -V
}
