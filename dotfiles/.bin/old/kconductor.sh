#!/bin/bash

POD="$1"

kubectl logs -c conductor -n groq-system $POD | egrep "$nova_ncp_reg" -o | sort -uV
