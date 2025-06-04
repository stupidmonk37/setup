#!/bin/bash

rack="$1"

kubectl racks -o json | jq --arg rack "$rack" '.items[] | select(.metadata.name==$rack)'

# check for model
kubectl racks -o json | jq --arg rack "$rack" '.items[] | select(.metadata.name==$rack)' | grep '"modelInstance":'
