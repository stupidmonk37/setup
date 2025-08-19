./#!/bin/bash

# ========================================
# PDU All Ports Status Checker
# ========================================
# This script checks all available ports on a specified PDU
# and displays their current state (ON/OFF)

# Configuration variables
rack=""             # The rack you're targeting
pdu_number=""      # The PDU number in the rack (e.g., 1, 2, 3, etc.)
cluster=""         # Cluster name (required)
port_range_start=1  # Start scanning from port 1
port_range_end=42   # Scan up to port 48 (typical maximum)
show_only_on=""     # If set, only show ports that are ON

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
        --rack=*)
            rack="${1#*=}"
            shift
            ;;
        --rack)
            if [[ -n "$2" && "$2" != -* ]]; then
                rack="$2"
                shift 2
            else
                echo "Error: --rack requires a rack name"
                exit 1
            fi
            ;;
        --pdu=*)
            pdu_number="${1#*=}"
            shift
            ;;
        --pdu)
            if [[ -n "$2" && "$2" != -* ]]; then
                pdu_number="$2"
                shift 2
            else
                echo "Error: --pdu requires a PDU number"
                exit 1
            fi
            ;;
        --start=*)
            port_range_start="${1#*=}"
            shift
            ;;
        --start)
            if [[ -n "$2" && "$2" != -* ]]; then
                port_range_start="$2"
                shift 2
            else
                echo "Error: --start requires a port number"
                exit 1
            fi
            ;;
        --end=*)
            port_range_end="${1#*=}"
            shift
            ;;
        --end)
            if [[ -n "$2" && "$2" != -* ]]; then
                port_range_end="$2"
                shift 2
            else
                echo "Error: --end requires a port number"
                exit 1
            fi
            ;;
        --only-on)
            show_only_on="true"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 --cluster=CLUSTER --rack=RACK --pdu=PDU [--start=PORT] [--end=PORT] [--only-on]"
            echo ""
            echo "Required Options:"
            echo "  --cluster=CLUSTER       Specify cluster name"
            echo "  --rack=RACK            Specify rack name"
            echo "  --pdu=PDU              Specify PDU number"
            echo ""
            echo "Optional Options:"
            echo "  --start=PORT           Start scanning from this port (default: 1)"
            echo "  --end=PORT             End scanning at this port (default: 48)"
            echo "  --only-on              Only show ports that are ON"
            echo ""
            echo "Alternative formats (space-separated):"
            echo "  --cluster CLUSTER --rack RACK --pdu PDU"
            echo ""
            echo "Examples:"
            echo "  $0 --cluster=msp2 --rack=c1r144 --pdu=2"
            echo "  $0 --cluster=yka1-prod1 --rack=c0r99 --pdu=1 --only-on"
            echo "  $0 --cluster=msp2 --rack=c1r144 --pdu=2 --start=1 --end=24"
            echo "  $0 --cluster msp2 --rack c1r144 --pdu 2 --only-on"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'"
            echo "All parameters must be specified using options"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$rack" ] || [ -z "$pdu_number" ] || [ -z "$cluster" ]; then
    echo "Error: Required parameters are missing"
    echo "Usage: $0 --cluster=CLUSTER --rack=RACK --pdu=PDU [--start=PORT] [--end=PORT] [--only-on]"
    echo ""
    echo "Missing parameters:"
    [ -z "$cluster" ] && echo "  --cluster is required"
    [ -z "$rack" ] && echo "  --rack is required"
    [ -z "$pdu_number" ] && echo "  --pdu is required"
    echo ""
    echo "Use --help for more information and examples"
    exit 1
fi

# Validate port range
if ! [[ "$port_range_start" =~ ^[0-9]+$ ]] || ! [[ "$port_range_end" =~ ^[0-9]+$ ]]; then
    echo "Error: Port numbers must be integers"
    exit 1
fi

if [ "$port_range_start" -gt "$port_range_end" ]; then
    echo "Error: Start port ($port_range_start) cannot be greater than end port ($port_range_end)"
    exit 1
fi

# Automatically construct the PDU name based on rack and pdu_number
pdu="${rack}-pdu${pdu_number}"

# Function to parse SNMP output and return state
get_outlet_state() {
    local snmp_output="$1"
    local state_value=$(echo "$snmp_output" | grep -o "INTEGER: [0-9]*" | cut -d' ' -f2)
    
    # Note: SNMP walk uses different values than SNMP set
    # SNMP walk: 0=OFF, 1=ON
    case "$state_value" in
        0)
            echo "OFF"
            ;;
        1)
            echo "ON"
            ;;
        *)
            echo "UNKNOWN"
            ;;
    esac
}

# Display header
echo "========================================="
echo "PDU All Ports Status Report"
echo "========================================="
echo "PDU: $pdu"
echo "Cluster: $cluster"
echo "Port Range: $port_range_start-$port_range_end"
if [ -n "$show_only_on" ]; then
    echo "Filter: Showing only ON ports"
fi
echo "========================================="
echo

# Initialize counters
total_checked=0
total_responsive=0
total_on=0
total_off=0

# Scan each port in the range
for port in $(seq $port_range_start $port_range_end); do
    total_checked=$((total_checked + 1))
    
    # Query the port state
    snmp_result=$(snmpwalk -c GroqLPUPow3r -v 2c "$pdu"."$cluster".groq.net .1.3.6.1.4.1.318.1.1.32.5.4.1.4.1.$port 2>&1)
    .1.3.6.1.4.1.318.1.1.28.1.1.0
    
    # Check if we got a valid response
    if echo "$snmp_result" | grep -q "INTEGER:"; then
        total_responsive=$((total_responsive + 1))
        state=$(get_outlet_state "$snmp_result")
        
        # Count states
        if [ "$state" = "ON" ]; then
            total_on=$((total_on + 1))
        elif [ "$state" = "OFF" ]; then
            total_off=$((total_off + 1))
        fi
        
        # Display based on filter settings
        if [ -n "$show_only_on" ]; then
            # Only show ON ports
            if [ "$state" = "ON" ]; then
                printf "Port %2d: %s\n" "$port" "$state"
            fi
        else
            # Show all responsive ports
            printf "Port %2d: %s\n" "$port" "$state"
        fi
    else
        # Port didn't respond - likely doesn't exist
        continue
    fi
done

# Display summary
echo
echo "========================================="
echo "Summary"
echo "========================================="
echo "Total ports checked: $total_checked"
echo "Responsive ports: $total_responsive"
echo "Ports ON: $total_on"
echo "Ports OFF: $total_off"
echo "Non-responsive ports: $((total_checked - total_responsive))"

if [ "$total_responsive" -eq 0 ]; then
    echo
    echo "Warning: No ports responded to SNMP queries."
    echo "This could indicate:"
    echo "  - Incorrect PDU hostname ($pdu.$cluster.groq.net)"
    echo "  - Network connectivity issues"
    echo "  - SNMP community string issues"
    echo "  - PDU is powered off or unreachable"
fi 