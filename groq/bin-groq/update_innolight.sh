#!/bin/bash

# Script to delete groq.success-boot-id label and tspd pod from a specific Kubernetes node
# Usage: ./delete_tspd <node-name>

# Check if node name is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <node-name>"
    echo "Example: $0 c0r21-gn1"
    echo ""
    echo "This script will:"
    echo "1. Remove the 'groq.success-boot-id' label from the node"
    echo "2. Delete the tspd pod running on the node"
    exit 1
fi

NODE_NAME="$1"

# Check if kubectl is available
if ! command -v kubectl &> /dev/null; then
    echo "Error: kubectl is not installed or not in PATH"
    exit 1
fi

# Check if the node exists
if ! kubectl get node "$NODE_NAME" &> /dev/null; then
    echo "Error: Node '$NODE_NAME' not found"
    exit 1
fi

echo "Processing node: $NODE_NAME"
echo "================================"

# Step 1: Remove the groq.success-boot-id label from the node
echo "Step 1: Removing 'groq.success-boot-id' label from node '$NODE_NAME'..."
if kubectl label node "$NODE_NAME" groq.success-boot-id- 2>/dev/null; then
    echo "✓ Successfully removed 'groq.success-boot-id' label from node '$NODE_NAME'"
else
    echo "ℹ Label 'groq.success-boot-id' was not present on node '$NODE_NAME' (or removal failed)"
fi

echo ""

# Step 2: Find and delete tspd pod on the node
echo "Step 2: Finding tspd pod on node '$NODE_NAME'..."
TSPD_POD=$(kubectl get pods --all-namespaces --field-selector spec.nodeName="$NODE_NAME" -o custom-columns="NAMESPACE:.metadata.namespace,NAME:.metadata.name" --no-headers | grep tspd)

if [ -z "$TSPD_POD" ]; then
    echo "ℹ No tspd pod found on node '$NODE_NAME'"
    echo ""
    echo "Summary: Label removal completed, no tspd pod to delete"
    exit 0
fi

# Extract namespace and pod name
NAMESPACE=$(echo "$TSPD_POD" | awk '{print $1}')
POD_NAME=$(echo "$TSPD_POD" | awk '{print $2}')

echo "Found tspd pod: $POD_NAME in namespace: $NAMESPACE"
echo "Deleting tspd pod '$POD_NAME' from namespace '$NAMESPACE'..."

if kubectl delete pod "$POD_NAME" -n "$NAMESPACE" 2>/dev/null; then
    echo "✓ Successfully deleted tspd pod '$POD_NAME' from namespace '$NAMESPACE'"
else
    echo "✗ Failed to delete tspd pod '$POD_NAME' from namespace '$NAMESPACE'"
    exit 1
fi

echo ""
echo "Summary: Both operations completed successfully"
echo "- Removed 'groq.success-boot-id' label from node '$NODE_NAME'"
echo "- Deleted tspd pod '$POD_NAME' from namespace '$NAMESPACE'" 