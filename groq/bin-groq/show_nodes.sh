#!/bin/zsh

echo "==== nodes NOT Ready ============"
kubectl get nodes -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Ready") | .status != "True") | .metadata.name' | grep -v c0n | sort -V
echo ""

echo "==== firmware problems =========="
kubectl get nodes -l groq.node=true -o json | jq -r '
    .items[]
    | {name: .metadata.name, labels: .metadata.labels}
    | select([range(0;8) as $i |
          (.labels["validation.groq.io/firmware-bundle-groqA\($i)"] // "MISSING") != "0.0.15"
        ] | any)
    | .name' | sort -V
echo ""

echo "==== bad ecid ==================="
kubectl get gv -o json | grep -B2 '"fault_type": "CARD_BAD_ECID"' | grep '"component":' | awk -F'"' '{print $4}' | sort -V | uniq | wc -l | xargs
echo ""

echo "==== possible bmc mismatches ===="
kubectl get nodes -l groq.node.bmc-match!=true | awk 'NR>1 {print $1}' | grep -v c0g | grep -v c0n | sort -V
echo ""

echo "==== tspd not running ==========="
kubectl get nodes -o json | jq -r '.items[] | select(.spec.taints != null) | select(.spec.taints[] | select(.key=="groq.tspd-not-ready" and .value=="true" and .effect=="NoExecute")) | .metadata.name' | sort -V
echo ""

echo "==== bios-conformance = fail ===="
kubectl get nodes -l groq.node.bios-conformance!=pass | awk 'NR>1 {print $1}' | grep -v c0g | grep -v c0n | sort -V
echo ""

#echo "==== bmc-conformance = fail ===="
#kubectl get nodes -l groq.node.bmc-conformance=fail | awk 'NR>1 {print $1}' | sort -V
#echo ""

echo "==== failed node validations ===="
count=$(kubectl get nodes -l validation.groq.io/node-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | wc -l | xargs)
#echo "Total failed node validations: $count"
kubectl get nodes -l validation.groq.io/node-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | sort -V | head -n 5
if [ "$count" -gt 5 ]; then
  echo "... $((count - 5)) more"
fi
echo ""


echo "==== failed rack validations ===="
count=$(kubectl get nodes -l validation.groq.io/rack-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | cut -d'-' -f1 | sort -uV | wc -l | xargs)
#echo "Total failed rack validations: $count"
kubectl get nodes -l validation.groq.io/rack-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | cut -d'-' -f1 | sort -uV | head -n 5
if [ "$count" -gt 5 ]; then
  echo "... $((count - 5)) more"
fi
echo ""


echo "==== failed xrk validations ====="
count=$(kubectl get nodes -l validation.groq.io/rack-complete=true,validation.groq.io/next-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | cut -d'-' -f1 | sort -uV | awk -F'r' 'NF==2 && $2~/^[0-9]+$/ {n=$2+0; printf "%sr%d-%sr%d\n", $1, n, $1, n+1 }' | wc -l | xargs)
#echo "Total failed xrk validations: $count"
kubectl get nodes -l validation.groq.io/rack-complete=true,validation.groq.io/next-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | cut -d'-' -f1 | sort -uV | awk -F'r' 'NF==2 && $2~/^[0-9]+$/ {n=$2+0; printf "%sr%d-%sr%d\n", $1, n, $1, n+1 }' | head -n 5
if [ "$count" -gt 5 ]; then
  echo "... $((count - 5)) more"
fi
echo ""
