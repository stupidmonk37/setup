#!/bin/bash

POD="$1"

kubectl logs -c conductor $POD | egrep "$nova_ncp_reg" -o | sort -uV
