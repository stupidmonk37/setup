#!/bin/bash

# ========================================
# PDU Power On Script
# ========================================
# This script takes a hostname (like c0r21-gn1) and turns on all 4 PSU connections
# using the PDU map and check-outlet.sh, with optional ping monitoring

pdu_map_file="pdu-map"
cluster=""
hostname=""
dry_run=""
verbose=""
ping_monitor=""
ping_timeout="300"  # 5 minutes default timeout for ping monitoring

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --cluster=*)
            cluster="${1#*=}"
            shift
            ;;
        --cluster)
            if [[ -n "$2" && "$2" != -* ]]; then
                cluster="$2"
                shift 2
            else
                echo "Error: --cluster requires a cluster name"
                exit 1
            fi
            ;;
        --map=*)
            pdu_map_file="${1#*=}"
            shift
            ;;
        --map)
            if [[ -n "$2" && "$2" != -* ]]; then
                pdu_map_file="$2"
                shift 2
            else
                echo "Error: --map requires a filename"
                exit 1
            fi
            ;;
        --dry-run)
            dry_run="true"
            shift
            ;;
        --verbose)
            verbose="true"
            shift
            ;;
        --ping)
            ping_monitor="true"
            shift
            ;;
        --ping-timeout=*)
            ping_timeout="${1#*=}"
            shift
            ;;
        --ping-timeout)
            if [[ -n "$2" && "$2" != -* ]]; then
                ping_timeout="$2"
                shift 2
            else
                echo "Error: --ping-timeout requires a timeout value in seconds"
                exit 1
            fi
            ;;
        -h|--help)
            echo "Usage: $0 HOSTNAME [--cluster=CLUSTER] [--map=MAPFILE] [--dry-run] [--verbose] [--ping] [--ping-timeout=SECONDS]"
            echo ""
            echo "Arguments:"
            echo "  HOSTNAME               Target hostname (e.g., c0r21-gn1)"
            echo ""
            echo "Options:"
            echo "  --cluster=CLUSTER      Specify cluster name (e.g., msp2, yka1-prod1)"
            echo "  --map=MAPFILE         PDU map file (default: pdu-map)"
            echo "  --dry-run             Show what would be done without executing"
            echo "  --verbose             Show detailed output"
            echo "  --ping                Monitor node with ping to verify startup"
            echo "  --ping-timeout=SEC    Timeout for ping monitoring (default: 300 seconds)"
            echo ""
            echo "Examples:"
            echo "  $0 c0r21-gn1 --cluster=msp2"
            echo "  $0 c0r99-gn5 --cluster=yka1-prod1 --dry-run"
            echo "  $0 c1r144-gn3 --cluster=msp2 --verbose"
            echo "  $0 c0r51-gn8 --cluster=yka1-prod1 --ping"
            echo "  $0 c0r51-gn8 --cluster=yka1-prod1 --ping --ping-timeout=600"
            echo ""
            echo "This script will:"
            echo "  1. Look up the hostname in the PDU map"
            echo "  2. Find all 4 PSU connections (PSU1, PSU2, PSU3, PSU4)"
            echo "  3. Turn ON all 4 connections using check-outlet.sh"
            echo "  4. If --ping is specified, monitor the full FQDN until it comes online"
            exit 0
            ;;
        -*)
            echo "Error: Unknown option '$1'"
            echo "Use --help for usage information"
            exit 1
            ;;
        *)
            if [[ -z "$hostname" ]]; then
                hostname="$1"
                shift
            else
                echo "Error: Only one hostname can be specified"
                echo "Use --help for usage information"
                exit 1
            fi
            ;;
    esac
done

# Validate required arguments
if [[ -z "$hostname" ]]; then
    echo "Error: Hostname is required"
    echo "Usage: $0 HOSTNAME [--cluster=CLUSTER] [--dry-run] [--verbose] [--ping]"
    echo "Use --help for more information"
    exit 1
fi

if [[ -z "$cluster" ]]; then
    echo "Error: --cluster is required"
    echo "Usage: $0 HOSTNAME --cluster=CLUSTER [--dry-run] [--verbose] [--ping]"
    echo "Use --help for more information"
    exit 1
fi

# Validate ping timeout if specified
if [[ -n "$ping_timeout" && ! "$ping_timeout" =~ ^[0-9]+$ ]]; then
    echo "Error: --ping-timeout must be a positive integer (seconds)"
    exit 1
fi

# Check if PDU map file exists
if [[ ! -f "$pdu_map_file" ]]; then
    echo "Error: PDU map file '$pdu_map_file' not found"
    exit 1
fi

# Check if check-outlet.sh exists
if [[ ! -f "check-outlet.sh" ]]; then
    echo "Error: check-outlet.sh not found in current directory"
    exit 1
fi

# Function to extract node number from hostname
extract_node_number() {
    local hostname="$1"
    # Extract pattern like c0r21-gn1 -> N1, c0r99-gn5 -> N5, etc.
    if [[ "$hostname" =~ gn([0-9]+) ]]; then
        echo "N${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# Function to extract rack from hostname  
extract_rack() {
    local hostname="$1"
    # Extract pattern like c0r21-gn1 -> c0r21, c0r99-gn5 -> c0r99, etc.
    if [[ "$hostname" =~ ^(c[0-9]+r[0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# Function to construct full FQDN from hostname and cluster
construct_fqdn() {
    local hostname="$1"
    local cluster="$2"
    echo "${hostname}.${cluster}.groq.net"
}

# Function to monitor node startup with ping
monitor_startup() {
    local fqdn="$1"
    local timeout="$2"
    
    echo "========================================="
    echo "Monitoring node startup: $fqdn"
    echo "Timeout: ${timeout} seconds"
    echo "========================================="
    
    # Check if node is initially reachable
    echo "Checking initial connectivity..."
    if ping -c 1 -W 5 "$fqdn" &>/dev/null; then
        echo "✓ Node $fqdn is already online!"
        return 0
    fi
    
    echo "Node $fqdn is currently offline"
    echo "Monitoring for startup... (Press Ctrl+C to stop monitoring)"
    echo
    
    local start_time=$(date +%s)
    local consecutive_successes=0
    local ping_interval=5  # 5 seconds between pings
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        # Check timeout
        if [[ $elapsed -gt $timeout ]]; then
            echo
            echo "⏰ Timeout reached (${timeout} seconds). Node has not come online."
            echo "Total monitoring time: ${elapsed} seconds"
            return 1
        fi
        
        # Ping the node
        if ping -c 1 -W 3 "$fqdn" &>/dev/null; then
            # Node responded
            consecutive_successes=$((consecutive_successes + 1))
            printf "\r[%s] Node responding (%d/%d) (elapsed: %ds)" "$(date '+%H:%M:%S')" "$consecutive_successes" "3" "$elapsed"
            
            # Consider node online after 3 consecutive successes
            if [[ $consecutive_successes -ge 3 ]]; then
                echo
                echo
                echo "🔌 Node $fqdn is now ONLINE!"
                echo "Total startup time: ${elapsed} seconds"
                return 0
            fi
        else
            # Node didn't respond
            consecutive_successes=0
            printf "\r[%s] Node still offline (elapsed: %ds)" "$(date '+%H:%M:%S')" "$elapsed"
        fi
        
        sleep $ping_interval
    done
}

# Function to find PSU connections in PDU map
find_psu_connections() {
    local node_name="$1"
    declare -a connections
    
    # Read PDU map and find all PSU connections for this node
    current_device=""
    current_cable=""
    expect_cable=false
    expect_pdu=false
    
    while IFS= read -r line || [[ -n "$line" ]]; do
        # Skip empty lines and headers
        if [[ -z "$line" || "$line" =~ ^[[:space:]]*$ || "$line" =~ ^(Side|Power Cable)$ ]]; then
            continue
        fi
        
        # Skip numeric-only lines
        if [[ "$line" =~ ^[[:space:]]*[0-9]+[[:space:]]*$ ]]; then
            continue
        fi
        
        # Check if this line contains our target node
        if [[ "$line" =~ ${node_name}/PSU[0-9]+ ]]; then
            current_device="$line"
            expect_cable=true
            expect_pdu=false
            continue
        fi
        
        # Check if this line contains cable length info
        if [[ "$expect_cable" == true && "$line" =~ [0-9]+ft/[0-9.]+m ]]; then
            current_cable="$line"
            expect_cable=false
            expect_pdu=true
            continue
        fi
        
        # Check if this line contains PDU info
        if [[ "$expect_pdu" == true && "$line" =~ PDU([0-9]+)/([0-9]+) ]]; then
            local pdu_num="${BASH_REMATCH[1]}"
            local port_num="${BASH_REMATCH[2]}"
            
            if [[ -n "$current_device" ]]; then
                connections+=("$current_device|$pdu_num|$port_num|$current_cable")
            fi
            
            # Reset state
            current_device=""
            current_cable=""
            expect_cable=false
            expect_pdu=false
            continue
        fi
        
        # If we get here with unexpected content, reset state
        if [[ "$expect_cable" == true || "$expect_pdu" == true ]]; then
            current_device=""
            current_cable=""
            expect_cable=false
            expect_pdu=false
        fi
    done < "$pdu_map_file"
    
    # Return connections array
    printf '%s\n' "${connections[@]}"
}

# Extract node number and rack from hostname
node_number=$(extract_node_number "$hostname")
rack=$(extract_rack "$hostname")

if [[ -z "$node_number" ]]; then
    echo "Error: Could not extract node number from hostname '$hostname'"
    echo "Expected format: c0r21-gn1, c0r99-gn5, etc."
    exit 1
fi

if [[ -z "$rack" ]]; then
    echo "Error: Could not extract rack from hostname '$hostname'"
    echo "Expected format: c0r21-gn1, c0r99-gn5, etc."
    exit 1
fi

[[ -n "$verbose" ]] && echo "Hostname: $hostname"
[[ -n "$verbose" ]] && echo "Node: $node_number"
[[ -n "$verbose" ]] && echo "Rack: $rack"
[[ -n "$verbose" ]] && echo "Cluster: $cluster"
[[ -n "$verbose" ]] && echo

# Find PSU connections for this node
echo "Looking up PSU connections for $node_number in PDU map..."
connections=$(find_psu_connections "$node_number")

if [[ -z "$connections" ]]; then
    echo "Error: No PSU connections found for node $node_number in PDU map"
    echo "Available nodes in map:"
    grep -E "N[0-9]+/PSU[0-9]+" "$pdu_map_file" | sed 's|/PSU.*||' | sort -u | head -10
    exit 1
fi

# Count connections
connection_count=$(echo "$connections" | wc -l)
echo "Found $connection_count PSU connections for $node_number"

if [[ "$connection_count" -ne 4 ]]; then
    echo "Warning: Expected 4 PSU connections but found $connection_count"
fi

echo

# Process each connection
success_count=0
failure_count=0

while IFS='|' read -r device pdu_num port_num cable; do
    echo "Processing: $device -> PDU$pdu_num/Port$port_num ($cable)"
    
    # Construct the check-outlet.sh command
    cmd="./check-outlet.sh --cluster=$cluster --rack=$rack --pdu=$pdu_num --port=$port_num --state=on"
    
    if [[ -n "$dry_run" ]]; then
        echo "  [DRY RUN] Would execute: $cmd"
        success_count=$((success_count + 1))
    else
        if [[ -n "$verbose" ]]; then
            echo "  Executing: $cmd"
        fi
        
        # Execute the command and capture output
        if output=$($cmd 2>&1); then
            if [[ -n "$verbose" ]]; then
                echo "  Success: $output"
            else
                echo "  ✓ Successfully turned ON $device on PDU$pdu_num/Port$port_num"
            fi
            success_count=$((success_count + 1))
        else
            echo "  ✗ Failed to turn ON $device on PDU$pdu_num/Port$port_num"
            if [[ -n "$verbose" ]]; then
                echo "  Error output: $output"
            fi
            failure_count=$((failure_count + 1))
        fi
    fi
    echo
done <<< "$connections"

# Summary
echo "========================================="
echo "Summary for $hostname ($node_number)"
echo "========================================="
echo "Total connections processed: $connection_count"
echo "Successful operations: $success_count"
echo "Failed operations: $failure_count"

if [[ -n "$dry_run" ]]; then
    echo "Note: This was a dry run - no actual changes were made"
fi

if [[ "$failure_count" -gt 0 ]]; then
    echo
    echo "⚠️  Some operations failed. Check the output above for details."
    exit 1
elif [[ "$success_count" -gt 0 ]]; then
    echo
    if [[ -n "$dry_run" ]]; then
        echo "✅ All operations would succeed"
        if [[ -n "$ping_monitor" ]]; then
            echo "Note: Ping monitoring would be performed if not in dry-run mode"
        fi
    else
        echo "✅ All PSU connections for $hostname have been turned ON"
        
        # Start ping monitoring if requested
        if [[ -n "$ping_monitor" ]]; then
            echo
            fqdn=$(construct_fqdn "$hostname" "$cluster")
            echo "Starting ping monitoring to verify node startup..."
            
            if monitor_startup "$fqdn" "$ping_timeout"; then
                echo "✅ Node startup confirmed via ping monitoring"
            else
                echo "⚠️  Node startup monitoring timed out or failed"
                echo "The PSU connections have been turned on, but the node may not be online yet"
                echo "This could indicate:"
                echo "  - Node is still booting (may take longer than timeout)"
                echo "  - Hardware or firmware issues preventing startup"
                echo "  - Network connectivity issues"
                echo "  - Node requires manual intervention to start"
            fi
        fi
    fi
fi 