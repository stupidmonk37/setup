#!/bin/bash

# Check if a rack name is provided
if [ -z "$1" ]; then
    echo "Error: No rack name provided."
    echo "Usage: $0 <rack-name>"
    exit 1
fi

rack="$1"

# Function to run a kubectl command and handle errors
k_command() {
    local description="$1"
    local resource_type="$2"
    shift 2
    local output

    echo ""

    # Run the command and capture both stdout and stderr
    output=$("$@" 2>&1)

    if [ $? -ne 0 ]; then
        echo "Error: Failed to retrieve $description. Details:"
        echo "$output"
        return
    fi

    # Filter results using grep
    filtered_output=$(echo "$output" | grep "$rack")

    if [ -z "$filtered_output" ]; then
        if [[ "$resource_type" == "pods" ]]; then
            echo "✅ No running pods on $rack"
        elif [[ "$resource_type" == "jobs" ]]; then
            echo "✅ No running jobs on $rack"
        else
            echo "No matches found for '$rack' in $description."
        fi
    else
        echo "$filtered_output"
    fi
}

# Check nodes for readiness
check_nodes() {
    local output
    output=$(kubectl get nodes | grep "$rack" )
    echo "$output"

    # Count total number of nodes and check the status of each node
    total_nodes=$(echo "$output" | wc -l)
    total_ready_nodes=$(echo "$output" | grep "Ready" | wc -l)

    # Ensure we have exactly 9 nodes
    if [ "$total_nodes" -ne 9 ]; then
        echo "Error: Expected 9 nodes, but found $total_nodes."
        return
    fi

    # Check if all nodes are in the "Ready" state
    if [ "$total_ready_nodes" -eq 9 ]; then
        echo "✅ All nine nodes are ready."
    else
        echo "The following node(s) are not ready:"
        # Loop through the nodes and show which ones aren't ready
        echo "$output" | while read -r line; do
            node_status=$(echo "$line" | awk '{print $2}')
            node_name=$(echo "$line" | awk '{print $1}')
            if [[ "$node_status" != "Ready" ]]; then
                echo "❌ $node_name is not ready (status: $node_status)"
            fi
        done
    fi
}

# Run the function to check nodes
check_nodes

# Display information with error handling
k_command "PODS" "pods" kubectl get pods -n groq-system
k_command "JOBS" "jobs" kubectl get jobs -n groq-system
k_command "kubectl racks" "racks" kubectl racks  # Ensure this is a valid command

echo ""
