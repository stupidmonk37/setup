#!/bin/bash

RACKS=("$@")

# Create output directory if it doesn't exist
mkdir -p output

# Process each RACK in parallel
for RACK in "${RACKS[@]}"; do
    (
        # Process each RACK sequentially (h and i loops)
        for h in {1..9}; do
            for i in {1..8}; do
                CARD="$RACK-gn${h}-c$((i-1))"
                SERIAL=$(curl -k -sSL -u root:GroqRocks1 -X GET "https://$RACK-gn${h}-bmc.yka1-prod1.groq.net/redfish/v1/Chassis/1/PCIeDevices/Groq${i}" | jq -r .SerialNumber)
                echo "$CARD: $SERIAL"
            done
        done
    ) > "output/$RACK.txt" 2>&1 &
done

# Wait for all background processes to finish
wait
