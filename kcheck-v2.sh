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
    echo "### $description ###"

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
            echo "No running pods on $rack"
        elif [[ "$resource_type" == "jobs" ]]; then
            echo "No running jobs on $rack"
        else
            echo "No matches found for '$rack' in $description."
        fi
    else
        echo "$filtered_output"
    fi
}

# Display information with error handling
k_command "PODS" "pods" kubectl get pods -n groq-system
k_command "JOBS" "jobs" kubectl get jobs -n groq-system
k_command "NODES" "nodes" kubectl get nodes
k_command "kubectl racks" "racks" kubectl racks  # Ensure this is a valid command

echo ""