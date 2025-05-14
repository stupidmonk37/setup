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

gv-status-summary() {
  for RACK in "$@" ; do
    for NODE in gn{1..9}; do
      echo "Node: $RACK-$NODE"
      kubectl describe gv "$RACK-$NODE" 2>/dev/null | \
        awk '
          /^[[:space:]]{4}[^:]+:$/ {
            # Capture test name across multiple words
            test_name = $1
            for (i = 2; i <= NF; i++) {
              test_name = test_name " " $i
            }
            sub(/:$/, "", test_name)

            # Skip 4 lines, get to the 5th (Status line)
            for (i = 0; i < 5 && getline > 0; i++);

            if ($1 == "Status:") {
              status = $2
              printf "  %-40s %s\n", test_name, status
            }
          }
        '
      echo ""
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

gv_info() {
  local compact=0
  local targets=()

  while [[ "$1" =~ ^- ]]; do
    case "$1" in
      -c|--compact) compact=1 ;;
    esac
    shift
  done

  targets=("$@")

  run_gv() {
    local target="$1"

    output=$(kc describe gv "$target" 2>/dev/null)
    if [[ -z "$output" ]]; then
      if [[ "$compact" -eq 1 ]]; then
        printf "%-15s : \033[31mNOT FOUND\033[0m\n" "$target"
      else
        echo -e "\033[31mError:\033[0m Target '$target' not found."
      fi
      return
    fi

    echo "$output" | awk -v compact="$compact" -v target="$target" '
      BEGIN {
        status_keys = "groq-sweep-xt4444-8c:|Mcu:|Missing - Optics:|Pcie:|Single - Chip:|Single - Node - Link:|Single - Node - Link - Sweep:"
        separator = "======================================"

        COLOR_GREEN  = "\033[32m"
        COLOR_RED    = "\033[31m"
        COLOR_YELLOW = "\033[33m"
        COLOR_BLUE   = "\033[34m"
        COLOR_ORANGE = "\033[38;5;208m"
        COLOR_RESET  = "\033[0m"

        in_status = 0
        printed_any = 0
        name_count = 0
        all_success = 1
      }

      /^Status:/       { in_status = 1 }
      /^Events:/       { in_status = 0 }

      in_status && $0 ~ status_keys {
        status_line = $0
        countdown = 6
      }

      /Name:/ {
        if (compact == 0 && printed_any) print separator
        printed_any = 1

        name_count++
        split($0, parts, ":")
        gsub(/^[ \t]+/, "", parts[1])
        gsub(/^[ \t]+/, "", parts[2])
        if (compact == 0)
          printf "%-30s %s%s%s\n", parts[1] ":", COLOR_ORANGE, parts[2], COLOR_RESET
      }

      in_status && countdown == 1 {
        gsub(/Status:/, "", status_line)
        gsub(/Status:/, "", $0)
        sub(/^[ \t]+/, "", status_line)
        sub(/^[ \t]+/, "", $0)

        if ($0 ~ /success/) {
          gsub(/success/, COLOR_GREEN "&" COLOR_RESET)
        } else if ($0 ~ /fail|error/) {
          gsub(/(fail|error)/, COLOR_RED "&" COLOR_RESET)
          all_success = 0
        } else if ($0 ~ /in[- ]?progress|running/) {
          gsub(/(in[- ]?progress|running)/, COLOR_YELLOW "&" COLOR_RESET)
          all_success = 0
        } else if ($0 ~ /pending|waiting/) {
          gsub(/(pending|waiting)/, COLOR_BLUE "&" COLOR_RESET)
          all_success = 0
        }

        if (compact == 0)
          printf "%-30s %s\n", status_line, $0
      }

      in_status && countdown > 0 { countdown-- }

      END {
        if (compact == 0 && printed_any) print separator
        if (compact == 1) {
          result = (all_success ? COLOR_GREEN "OK" : COLOR_RED "FAIL") COLOR_RESET
          printf "%-15s : %s\n", target, result
        }
      }
    '
  }

  for tgt in "${targets[@]}"; do
    run_gv "$tgt"
  done
}

gv_info1() {
  local compact=0
  local targets=()

  while [[ "$1" =~ ^- ]]; do
    case "$1" in
      -c|--compact) compact=1 ;;
    esac
    shift
  done

  targets=("$@")

  run_gv() {
    local target="$1"

    output=$(kc describe gv "$target" 2>/dev/null)
    if [[ -z "$output" ]]; then
      if [[ "$compact" -eq 1 ]]; then
        printf "%-15s : \033[31mNOT FOUND\033[0m\n" "$target"
      else
        echo -e "\033[31mError:\033[0m Target '$target' not found."
      fi
      return
    fi

    echo "$output" | awk -v compact="$compact" -v target="$target" '
      BEGIN {
        status_keys = "groq-sweep-xt4444-8c:|Mcu:|Missing - Optics:|Pcie:|Single - Chip:|Single - Node - Link:|Single - Node - Link - Sweep:"
        separator = "======================================"

        COLOR_GREEN  = "\033[32m"
        COLOR_RED    = "\033[31m"
        COLOR_YELLOW = "\033[33m"
        COLOR_BLUE   = "\033[34m"
        COLOR_ORANGE = "\033[38;5;208m"
        COLOR_RESET  = "\033[0m"

        in_status = 0
        name_count = 0
        all_success = 1
      }

      /^Status:/       { in_status = 1 }
      /^Events:/       { in_status = 0 }

      in_status && $0 ~ status_keys {
        status_line = $0
        countdown = 6
      }

      /Name:/ {
        name_count++
        if (compact == 0 && name_count == 1) print separator
        if (name_count == 1 || (name_count - 1) % 8 == 0) {
          split($0, parts, ":")
          gsub(/^[ \t]+/, "", parts[1])
          gsub(/^[ \t]+/, "", parts[2])
          if (compact == 0)
            printf "%-30s %s%s%s\n", parts[1] ":", COLOR_ORANGE, parts[2], COLOR_RESET
        }
      }

      in_status && countdown == 1 {
        gsub(/Status:/, "", status_line)
        gsub(/Status:/, "", $0)
        sub(/^[ \t]+/, "", status_line)
        sub(/^[ \t]+/, "", $0)

        if ($0 ~ /success/) {
          gsub(/success/, COLOR_GREEN "&" COLOR_RESET)
        } else if ($0 ~ /fail|error/) {
          gsub(/(fail|error)/, COLOR_RED "&" COLOR_RESET)
          all_success = 0
        } else if ($0 ~ /in[- ]?progress|running/) {
          gsub(/(in[- ]?progress|running)/, COLOR_YELLOW "&" COLOR_RESET)
          all_success = 0
        } else if ($0 ~ /pending|waiting/) {
          gsub(/(pending|waiting)/, COLOR_BLUE "&" COLOR_RESET)
          all_success = 0
        }

        if (compact == 0)
          printf "%-30s %s\n", status_line, $0

        if (status_line ~ /Single - Node - Link - Sweep:/ && compact == 0)
          print separator
      }

      in_status && countdown > 0 { countdown-- }

      END {
        if (compact == 1) {
          result = (all_success ? COLOR_GREEN "OK" : COLOR_RED "FAIL") COLOR_RESET
          printf "%-15s : %s\n", target, result
        }
      }
    '
  }

  for target in "${targets[@]}"; do
    run_gv "$target"
  done
}

gv_status() {
  local compact=0
  local targets=()

  while [[ "$1" =~ ^- ]]; do
    case "$1" in
      -c|--compact) compact=1 ;;
    esac
    shift
  done

  targets=("$@")

  run_gv() {
    local target="$1"

    # Try to fetch data, handle errors gracefully
    output=$(kc describe gv "$target" 2>/dev/null)
    if [[ -z "$output" ]]; then
      if [[ "$compact" -eq 1 ]]; then
        printf "%-15s : \033[31mNOT FOUND\033[0m\n" "$target"
      else
        echo -e "\033[31mError:\033[0m Target '$target' not found."
      fi
      return
    fi

    echo "$output" | awk -v compact="$compact" -v target="$target" '
      BEGIN {
        status_keys = "groq-sweep-xt4444-8c:|Mcu:|Missing - Optics:|Pcie:|Single - Chip:|Single - Node - Link:|Single - Node - Link - Sweep:"
        separator = "======================================"

        COLOR_GREEN  = "\033[32m"
        COLOR_RED    = "\033[31m"
        COLOR_YELLOW = "\033[33m"
        COLOR_BLUE   = "\033[34m"
        COLOR_ORANGE = "\033[38;5;208m"
        COLOR_RESET  = "\033[0m"

        name_count = 0
        all_success = 1
      }

      $0 ~ status_keys {
        status_line = $0
        countdown = 6
      }

      /Name:/ {
        name_count++
        if (compact == 0 && name_count == 1) print separator
        if (name_count == 1 || (name_count - 1) % 8 == 0) {
          split($0, parts, ":")
          gsub(/^[ \t]+/, "", parts[1])
          gsub(/^[ \t]+/, "", parts[2])
          if (compact == 0)
            printf "%-30s %s%s%s\n", parts[1] ":", COLOR_ORANGE, parts[2], COLOR_RESET
        }
      }

      countdown == 1 {
        gsub(/Status:/, "", status_line)
        gsub(/Status:/, "", $0)
        sub(/^[ \t]+/, "", status_line)
        sub(/^[ \t]+/, "", $0)

        if ($0 ~ /success/) {
          gsub(/success/, COLOR_GREEN "&" COLOR_RESET)
        } else if ($0 ~ /fail|error/) {
          gsub(/(fail|error)/, COLOR_RED "&" COLOR_RESET)
          all_success = 0
        } else if ($0 ~ /in[- ]?progress|running/) {
          gsub(/(in[- ]?progress|running)/, COLOR_YELLOW "&" COLOR_RESET)
          all_success = 0
        } else if ($0 ~ /pending|waiting/) {
          gsub(/(pending|waiting)/, COLOR_BLUE "&" COLOR_RESET)
          all_success = 0
        }

        if (compact == 0)
          printf "%-30s %s\n", status_line, $0

        if (status_line ~ /Single - Node - Link - Sweep:/ && compact == 0)
          print separator
      }

      countdown > 0 { countdown-- }

      END {
        if (compact == 1) {
          result = (all_success ? COLOR_GREEN "OK" : COLOR_RED "FAIL") COLOR_RESET
          printf "%-15s : %s\n", target, result
        }
      }
    '
  }

  for target in "${targets[@]}"; do
    run_gv "$target"
  done
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
