#!/bin/bash
# Usage: ./create_bmc_user.sh <bmc_hostname> <current_password>
# Example: ./create_bmc_user.sh c0r21-gn1-bmc.yul1-prod1.groq.net HYSWXEHMGU

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <bmc_hostname> <current_password>"
  exit 1
fi

BMC_HOST="$1"
BMC_USER="ADMIN"
BMC_PASS="$2"
CHANNEL=1
USER_ID=3
NEW_NAME="root"
# "GroqRocks1" (ASCII hex, zero-padded to 16 bytes)
PW_BYTES=(0x47 0x72 0x6f 0x71 0x52 0x6f 0x63 0x6b 0x73 0x31 0x00 0x00 0x00 0x00 0x00 0x00)

echo "[*] Checking if user ID ${USER_ID} is already populated on ${BMC_HOST} (channel ${CHANNEL})..."
# Grab the username in column 2 for ID 3. If blank or '-' or '(Empty User)', we consider it free.
existing_name="$(ipmitool -I lan -H "$BMC_HOST" -U "$BMC_USER" -P "$BMC_PASS" user list "$CHANNEL" |
  awk -v id="$USER_ID" '($1==id){print $2}')"

if [[ -n "${existing_name:-}" && "${existing_name}" != "-" && "${existing_name}" != "(Empty" && "${existing_name}" != "(EmptyUser)" && "${existing_name}" != "(Empty_User)" ]]; then
  echo "[!] User ID ${USER_ID} already in use with name: ${existing_name}"
  echo "[!] Aborting to avoid overwriting an existing account."
  exit 2
fi

echo "[*] Setting username (${NEW_NAME}) for User ID ${USER_ID}..."
# 0x45 Set User Name: <user-id> <16 bytes of name>
ipmitool -I lan -H "$BMC_HOST" -U "$BMC_USER" -P "$BMC_PASS" \
  raw 0x06 0x45 0x03 \
  0x72 0x6f 0x6f 0x74 \
  0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00 0x00

echo "[*] Setting password for User ID ${USER_ID} and enabling the user..."
# 0x47 Set User Password: <user-id> <op=0x02 enable+set> <16 bytes of password>
ipmitool -I lan -H "$BMC_HOST" -U "$BMC_USER" -P "$BMC_PASS" \
  raw 0x06 0x47 0x03 0x02 "${PW_BYTES[@]}"

echo "[*] Granting Administrator privilege on channel ${CHANNEL}..."
# 0x43 Set User Access: <channel> <user-id> <priv-level> <flags>
# priv 0x04 = Administrator; flags 0x00 is usually fine when user already enabled above
ipmitool -I lan -H "$BMC_HOST" -U "$BMC_USER" -P "$BMC_PASS" \
  raw 0x06 0x43 0x01 0x03 0x04 0x00

echo "[*] Verifying..."
ipmitool -I lan -H "$BMC_HOST" -U "$BMC_USER" -P "$BMC_PASS" user list "$CHANNEL" | sed -n '1,5p'

echo "[✓] Done. User ID ${USER_ID} should now be '${NEW_NAME}' with Admin privileges."
