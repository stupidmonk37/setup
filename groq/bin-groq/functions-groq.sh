#!/usr/bin/env bash

#set +m  # Disable job control messages

tspd_logs() {
  local node="$1"

  if [[ -z "$node" ]]; then
    echo "Usage: tspd_logs <node-name>"
    return 1
  fi

  local pod
  pod=$(kubectl get pods --field-selector spec.nodeName="$node" -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep '^tspd-')

  if [[ -z "$pod" ]]; then
    echo "No tspd pod found on node $node"
    return 1
  fi

  kubectl logs -f "$pod" -c bring-up
}

kget_wrong_fw() {
  kubectl get nodes -l groq.node=true -o json |
    jq -r '
      .items[]
      | {name: .metadata.name, labels: .metadata.labels}
      | select([range(0;8) as $i |
            (.labels["validation.groq.io/firmware-bundle-groqA\($i)"] // "MISSING") != "0.0.15"
          ] | any)
      | .name
    ' | sort -V
}

kpods() {
  kubectl get pods --field-selector spec.nodeName="$1"
}

kval_logs() {
  kubectl validation logs fetch --validation $1
}

kval_stop() {
  kubectl validation stop --validation $1
}

kval_requalify() {
  kubectl validation requalify --rack $1
}

kval_retry() {
  kubectl validation retry --validation $1
}

#ping_unreachable() {
#  local racks=$1 # e.g., 83..84
#  local context
#  context=$(kubectl config current-context)
#  local domain="${context}.groq.net"
#  eval "fping -u c0r{$racks}-gn{1..9}{,-bmc}.$domain 2>/dev/null" | awk '{print $1}' | sort -V
#}

ping_site() {
  local node="$1"
  local ctx="${2:-$(kubectl config current-context)}"

  # take just cluster/site name from context (strip user@, etc.)
  local site=$(echo "$ctx" | awk -F'[@.]' '{print $1}')

  local host="${node}.${site}.groq.net"
  echo "Pinging $host ..."
  ping "$host"
}

# Check the label of a rack's nodes
# (ie label-check-rack c1r1)
#label_check_rack() {
#  for RACK in "$@"; do
#    for i in gn{1..9}; do
#      NODE="${RACK}-${i}"
#      value=$(kubectl get node "$NODE" -o json 2>/dev/null | jq -r '.metadata.labels["validation.groq.io/next-complete"]')
#
#      if [[ "$value" == "true" ]]; then
#        echo "$NODE: pass"
#      elif [[ -z "$value" ]] || [[ "$value" == "null" ]]; then
#        echo "$NODE: fail (label missing)"
#      else
#        echo "$NODE: fail"
#      fi
#    done
#  done
#}

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
#kracks() {
#  local all=false
#  local racks=()
#
#  while [[ $# -gt 0 ]]; do
#    if [[ "$1" == "--all" ]]; then
#      all=true
#      shift
#    elif [[ "$1" == "--racks" ]]; then
#      shift
#      while [[ $# -gt 0 && "$1" != --* ]]; do
#        racks+=("$1")
#        shift
#      done
#    else
#      echo "Unknown option: $1"
#      echo "Usage: kracks --all                            # List information for all racks"
#      echo "       kracks --racks <rack1> [rack2] [...]    # List information for specific racks"
#      return 1
#    fi
#  done
#
#  if $all; then
#    kubectl racks -o wide
#  elif [[ ${#racks[@]} -gt 0 ]]; then
#    local conditions='NR == 1'
#    for rack in "${racks[@]}"; do
#      conditions+=" || \$1 == \"$rack\""
#    done
#    kubectl racks -o wide | awk "$conditions"
#  else
#    echo "Missing required flag."
#    echo "Usage: kracks --all                            # List information for all racks"
#    echo "       kracks --racks <rack1> [rack2] [...]    # List information for specific racks"
#    return 1
#  fi
#}

# Execute IPMI power commands on a node
# (ie knodes-ipmi c1r1)
# (ie knodes-ipmi c1r1 cycle)
knodes_ipmi() {
  local node="$1"
  local ipmi_cmd="${2:-"status"}"
  [ -z "$node" ] && {
    echo "Please provide node name (short name)."
    return 1
  }
  kc_context="$(kubectl config current-context)"
  fqdn="${node}-bmc.${kc_context}.groq.net"
  ipmitool -H "$fqdn" -U root -P GroqRocks1 power "$ipmi_cmd"
}

# Function to execute IPMI commands on all nodes in specified racks
# The default action is 'status'
# (ie kracks-ipmi c1r1 c1r2)
# (ie kracks-ipmi cycle c1r1 c1r2)
kracks_ipmi() {
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
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(dig +short {}) $(ipmitool -H {} -U root -P GroqRocks1 power status)' | sort -V
    ;;
  cycle)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power cycle)' | sort -V
    ;;
  on)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power on)' | sort -V
    ;;
  off)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power off)' | sort -V
    ;;
  bios)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 chassis bootdev bios)' | sort -V
    ;;
  disk)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 chassis bootdev disk)' | sort -V
    ;;
  pxe)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 chassis bootdev pxe options=efiboot)' | sort -V
    ;;
  *)
    echo "${bmc_names[@]}" | xargs -n1 | parallel -j 60 echo '{} $(ipmitool -H {} -U root -P GroqRocks1 power status)' | sort -V
    echo "Default is 'power status'. Available: ${ipmi_actions[*]}"
    echo
    ;;
  esac
}

# Get Anodizer leases based on the current context
# (ie get_leases | jq -r 'select(.hostname|test("c1r1")) | [.hostname, .ip] | @tsv'
kget_leases() {
  local filter="$1"
  kc_context="$(kubectl config current-context)"

  if [ -n "$filter" ]; then
    {
      echo -e "HOSTNAME\tIP\tMAC\tSTATUS"
      curl -s "http://anodizer-api.${kc_context}.groq.net/api/v1/dhcp/leases" |
        jq -r --arg f "$filter" '
                    .active[]
                    | select(.hostname | test($f))
                    | [.hostname, .ip, .mac, .status]
                    | @tsv' | sort
    } | column -t -s $'\t'
  else
    curl -s "http://anodizer-api.${kc_context}.groq.net/api/v1/dhcp/leases" |
      jq '.active[]'
  fi
}
