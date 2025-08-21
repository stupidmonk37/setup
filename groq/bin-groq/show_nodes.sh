#!/bin/zsh

echo "==== nodes NOT Ready ============"
kubectl get nodes -o json | jq -r '.items[] | select(.status.conditions[] | select(.type=="Ready") | .status != "True") | .metadata.name' | sort -V
echo ""

echo "==== firmware problems =========="
#kubectl get nodes -l groq.fw-bundle-lowest!=0.0.15 | egrep -v c0g | awk 'NR>1 {print $1}' | sort -V
kubectl get nodes -l groq.node=true -o json | jq -r '
  .items[] |
  select(
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA0"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA1"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA2"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA3"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA4"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA5"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA6"] // "MISSING") != "0.0.15" or
    (.metadata.labels["validation.groq.io/firmware-bundle-groqA7"] // "MISSING") != "0.0.15"
  ) |
  .metadata.name' | sort -V
echo ""

echo "==== bad ecid ==================="
kubectl get gv -o json | grep -B2 '"fault_type": "CARD_BAD_ECID"' | grep '"component":' | awk -F'"' '{print $4}' | sort -V | uniq | wc -l
echo ""

echo "==== possible bmc mismatches ===="
kubectl get nodes -l groq.node.bmc-match!=true | awk 'NR>1 {print $1}' | grep -v c0g | sort -V
echo ""

echo "==== tspd not running ==========="
kubectl get nodes -o json | jq -r '.items[] | select(.spec.taints != null) | select(.spec.taints[] | select(.key=="groq.tspd-not-ready" and .value=="true" and .effect=="NoExecute")) | .metadata.name' | sort -V
echo ""

echo "==== bios-conformance = fail ===="
kubectl get nodes -l groq.node.bios-conformance=fail | awk 'NR>1 {print $1}' | sort -V
echo ""

#echo "==== bmc-conformance = fail ===="
#kubectl get nodes -l groq.node.bmc-conformance=fail | awk 'NR>1 {print $1}' | sort -V
#echo ""

echo "==== failed node validations ===="
kubectl get nodes -l validation.groq.io/node-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | sort -V
echo ""

echo "==== failed rack validations ===="
kubectl get nodes -l validation.groq.io/rack-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | cut -d'-' -f1 | sort -uV
echo ""

echo "==== failed xrk validations ====="
kubectl get nodes -l validation.groq.io/rack-complete=true,validation.groq.io/next-complete=failed -o custom-columns=NAME:.metadata.name --no-headers | cut -d'-' -f1 | sort -uV | awk -F'r' 'NF==2 && $2~/^[0-9]+$/ {n=$2+0; printf "%sr%d-%sr%d\n", $1, n, $1, n+1 }'
echo ""
