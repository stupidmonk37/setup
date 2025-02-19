#!/bin/bash

rack="$1"

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
kubectl get nodes -n groq-system | grep "$rack"

# Print an empty line
echo ""

# Display kubectl racks information
echo "### kubectl racks ###"
kubectl racks | grep "$rack"
