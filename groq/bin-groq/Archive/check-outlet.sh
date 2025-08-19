#!/bin/bash

# Configuration variables
rack=""             # The rack you're targeting
pdu_number=""      # The PDU number in the rack (e.g., 1, 2, 3, etc.)
outlet_state=""    # Specify "on" or "off"
cluster=""         # Cluster name (required)
port_number=""     # Port number (required)
check_only=""      # If set, only check current state without changing it

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
        --port=*)
            port_number="${1#*=}"
            shift
            ;;
        --port)
            if [[ -n "$2" && "$2" != -* ]]; then
                port_number="$2"
                shift 2
            else
                echo "Error: --port requires a port number"
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
        --state=*)
            outlet_state="${1#*=}"
            shift
            ;;
        --state)
            if [[ -n "$2" && "$2" != -* ]]; then
                outlet_state="$2"
                shift 2
            else
                echo "Error: --state requires an outlet state (on|off)"
                exit 1
            fi
            ;;
        --check)
            check_only="true"
            shift
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
        -h|--help)
            echo "Usage: $0 --cluster=CLUSTER --port=PORT --rack=RACK --pdu=PDU [--state=STATE] [--check]"
            echo ""
            echo "Required Options:"
            echo "  --cluster=CLUSTER       Specify cluster name"
            echo "  --port=PORT            Specify port number"
            echo "  --rack=RACK            Specify rack name"
            echo "  --pdu=PDU              Specify PDU number"
            echo ""
            echo "Mode Options (choose one):"
            echo "  --state=STATE          Specify outlet state (on|off) - changes outlet state"
            echo "  --check                Only check current outlet state (no changes)"
            echo ""
            echo "Alternative formats (space-separated):"
            echo "  --cluster CLUSTER --port PORT --rack RACK --pdu PDU --state STATE"
            echo "  --cluster CLUSTER --port PORT --rack RACK --pdu PDU --check"
            echo ""
            echo "Examples:"
            echo "  $0 --cluster=msp2 --port=19 --rack=c1r144 --pdu=2 --state=on"
            echo "  $0 --cluster=yka1-prod1 --port=25 --rack=c0r99 --pdu=1 --state=off"
            echo "  $0 --cluster=msp2 --port=19 --rack=c1r144 --pdu=2 --check"
            echo "  $0 --cluster msp2 --port 41 --rack c1r144 --pdu 3 --check"
            exit 0
            ;;
        *)
            # No positional arguments allowed - all parameters must be specified with options
            echo "Error: Unknown argument '$1'"
            echo "All parameters must be specified using options"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [ -z "$rack" ] || [ -z "$pdu_number" ] || [ -z "$cluster" ] || [ -z "$port_number" ]; then
    echo "Error: Required parameters are missing"
    echo "Usage: $0 --cluster=CLUSTER --port=PORT --rack=RACK --pdu=PDU [--state=STATE] [--check]"
    echo ""
    echo "Missing parameters:"
    [ -z "$cluster" ] && echo "  --cluster is required"
    [ -z "$port_number" ] && echo "  --port is required"
    [ -z "$rack" ] && echo "  --rack is required"
    [ -z "$pdu_number" ] && echo "  --pdu is required"
    echo ""
    echo "Use --help for more information and examples"
    exit 1
fi

# Validate mode selection - must have either --state or --check
if [ -z "$outlet_state" ] && [ -z "$check_only" ]; then
    echo "Error: You must specify either --state or --check"
    echo "  --state=STATE    Change outlet state (on|off)"
    echo "  --check          Only check current outlet state"
    echo ""
    echo "Use --help for more information and examples"
    exit 1
fi

# Validate that both --state and --check are not specified
if [ -n "$outlet_state" ] && [ -n "$check_only" ]; then
    echo "Error: Cannot specify both --state and --check"
    echo "Choose one mode:"
    echo "  --state=STATE    Change outlet state (on|off)"
    echo "  --check          Only check current outlet state"
    echo ""
    echo "Use --help for more information and examples"
    exit 1
fi

# Convert outlet_state to numeric value (only needed for state changes)
if [ -n "$outlet_state" ]; then
    case "$outlet_state" in
        "on")
            outlet_value=2
            ;;
        "off")
            outlet_value=1
            ;;
        *)
            echo "Error: Invalid outlet_state '$outlet_state'. Use 'on' or 'off'."
            exit 1
            ;;
    esac
fi

# Port number is now directly specified via --port option
echo "Using port: $port_number"

# Automatically construct the PDU name based on rack and pdu_number
pdu="${rack}-pdu${pdu_number}"

# Function to parse SNMP output and display user-friendly message
parse_outlet_state() {
    local snmp_output="$1"
    local state_value=$(echo "$snmp_output" | grep -o "INTEGER: [0-9]*" | cut -d' ' -f2)
    
    # Note: SNMP walk uses different values than SNMP set
    # SNMP walk: 0=OFF, 1=ON
    # SNMP set: 1=OFF, 2=ON
    case "$state_value" in
        0)
            echo "The outlet is OFF"
            ;;
        1)
            echo "The outlet is ON"
            ;;
        *)
            if [ -z "$state_value" ]; then
                echo "The outlet state could not be determined (no value found)"
            else
                echo "The outlet state is UNRECOGNIZED (value: $state_value)"
            fi
            ;;
    esac
}

if [ -n "$check_only" ]; then
    # Check-only mode: only query current state
    echo "Checking current state of port $port_number on $pdu (cluster: $cluster)..."
    snmp_result=$(snmpwalk -c GroqLPUPow3r -v 2c "$pdu"."$cluster".groq.net .1.3.6.1.4.1.318.1.1.32.5.4.1.4.1.$port_number 2>&1)
    
    if echo "$snmp_result" | grep -q "INTEGER:"; then
        parse_outlet_state "$snmp_result"
    else
        echo "Error: Could not retrieve outlet state"
        echo "SNMP output: $snmp_result"
    fi
else
    # State change mode: set state then check
    echo "Setting port $port_number on $pdu (cluster: $cluster) to state $outlet_state..."
    set_result=$(snmpset -c GroqLPUPow3r -v 2c "$pdu"."$cluster".groq.net .1.3.6.1.4.1.318.1.1.32.5.5.1.4.1.$port_number i $outlet_value 2>&1)
    
    if echo "$set_result" | grep -q "INTEGER:"; then
        echo "State change command sent successfully"
    else
        echo "Error: Failed to set outlet state"
        echo "SNMP output: $set_result"
        exit 1
    fi

    #sleep for 2 seconds
    sleep 2

    # Get the current state of the outlet
    echo "Verifying current state of outlet..."
    check_result=$(snmpwalk -c GroqLPUPow3r -v 2c "$pdu"."$cluster".groq.net .1.3.6.1.4.1.318.1.1.32.5.4.1.4.1.$port_number 2>&1)
    
    if echo "$check_result" | grep -q "INTEGER:"; then
        parse_outlet_state "$check_result"
    else
        echo "Error: Could not verify outlet state"
        echo "SNMP output: $check_result"
    fi
fi


