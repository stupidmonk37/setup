#!/bin/bash

rack="$1"

# check if a rack name is provided
if [ -z "$rack" ]; then
    echo "Usage: $0 <rack-name>"
    exit 1
fi

# Print an empty line
echo ""

# Display PODS information
echo "### PODS ###"
kubectl get pods -n groq-system | grep "$rack"

# Print an empty line
echo ""

# Display JOBS information
echo "### JOBS ###"
kubectl get jobs -n groq-system | grep "$rack"

# Print an empty line
echo ""

# Display NODES information
echo "### NODES ###"
kubectl get nodes | grep "$rack"

# Print an empty line
echo ""

# Display kubectl racks information
echo "### kubectl racks ###"
kubectl racks | grep "$rack"
