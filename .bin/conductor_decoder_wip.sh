#! /bin/bash

conductor="$1"
nova_ncp_reg="N[0-9]/C[0-9]/P[0-9]+ <-> N[0-9]/C[0-9]/P[0-9]+"

kubectl logs -n groq-system -c conductor $conductor | egrep "$nova_ncp_reg" -o | sort -uV
