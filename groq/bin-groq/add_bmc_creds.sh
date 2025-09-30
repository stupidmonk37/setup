#!/bin/bash
# add_bmc_creds.sh
#
# Creates/enables a BMC user in a specific user slot (default: ID 3) with a set
# username and password, and grants Administrator privileges on the given channel.
#
# Usage: ./add_bmc_creds.sh <bmc_hostname> <current_ADMIN_password>
# Example: ./add_bmc_creds.sh c0r21-gn1-bmc.yul1-prod1.groq.net HYSWXEHMGU
#
# Notes:
# - Uses ipmitool over LAN with -E to avoid exposing passwords in `ps`.
# - Detects whether the target user slot is empty using "Get User Name" (raw 0x06 0x46).
# - Generates the 16-byte payloads for username/password from variables (padded/truncated).
# - Grants channel access via high-level `channel setaccess` for portability.

set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <bmc_hostname> <current_ADMIN_password>"
  exit 1
fi

# -------- Configuration (override via environment if desired) --------
BMC_HOST="$1"
export IPMI_PASSWORD="$2"          # used by ipmitool -E
BMC_USER="${BMC_USER:-ADMIN}"

CHANNEL="${CHANNEL:-1}"            # IPMI channel (often 1)
USER_ID="${USER_ID:-3}"            # Target user slot to (create|enable)

NEW_NAME="${NEW_NAME:-root}"       # Username to set
NEW_PASS_ASCII="${NEW_PASS_ASCII:-GroqRocks1}"  # Password to set

# ipmitool reliability knobs
IPMI_RETRIES="${IPMI_RETRIES:-2}"
IPMI_TIMEOUTS="${IPMI_TIMEOUTS:-3}"

# --------------------------------------------------------------------

ipmi() {
  ipmitool -I lan -H "$BMC_HOST" -U "$BMC_USER" -E -R "$IPMI_RETRIES" -N "$IPMI_TIMEOUTS" "$@"
}

# Convert an ASCII string to a space-prefixed list of 16 hex bytes (0x..), padded/truncated.
to_hex16() {
  # Uses POSIX tools (od/awk). Avoids GNU-specific hexdump formats.
  # Prints: " 0xNN 0xNN ... 0xNN" (16 bytes)
  printf '%-16s' "$1" | cut -c1-16 | od -An -t x1 | awk '{for(i=1;i<=NF;i++) printf " 0x%s", $i}'
}

# Convert ipmitool raw hex output (e.g., "72 6f 6f 74 00 ...") to ASCII (strip trailing NULs).
hexout_to_ascii() {
  local out="$1"
  local bytes=""
  local tok
  for tok in $out; do
    tok="${tok#0x}"   # tolerate "0xNN" or "NN"
    bytes="${bytes}\\x${tok}"
  done
  # shellcheck disable=SC2059
  printf '%b' "$bytes" | tr -d '\000'
}

echo "[*] Checking if user ID ${USER_ID} is already populated on ${BMC_HOST} (channel ${CHANNEL})..."
# Use Get User Name (netfn=0x06, cmd=0x46): payload = <user-id>
# Returns 16 bytes (username, NUL-padded). Empty slot => all 0x00.
name_hex_out="$(ipmi raw 0x06 0x46 "$(printf "0x%02x" "$USER_ID")" | tr -d '\r')"
existing_name="$(hexout_to_ascii "$name_hex_out")"
existing_name_stripped="$(printf '%s' "$existing_name" | xargs || true)" # trim spaces

if [[ -n "${existing_name_stripped}" ]]; then
  echo "[!] User ID ${USER_ID} already in use with name: ${existing_name_stripped}"
  echo "[!] Aborting to avoid overwriting an existing account."
  exit 2
fi

echo "[*] Setting username (${NEW_NAME}) for User ID ${USER_ID}..."
name_hex_list="$(to_hex16 "$NEW_NAME")"
# 0x45 Set User Name: <user-id> <16 bytes of name>
# shellcheck disable=SC2086
ipmi raw 0x06 0x45 "$(printf "0x%02x" "$USER_ID")" ${name_hex_list}

echo "[*] Setting password for User ID ${USER_ID} and enabling the user..."
pw_hex_list="$(to_hex16 "$NEW_PASS_ASCII")"
# 0x47 Set User Password: <user-id> <op=0x02 enable+set> <16 bytes of password>
# shellcheck disable=SC2086
ipmi raw 0x06 0x47 "$(printf "0x%02x" "$USER_ID")" 0x02 ${pw_hex_list}

echo "[*] Granting Administrator privilege and enabling channel access on channel ${CHANNEL}..."
# Use high-level helper to avoid vendor-specific raw flag differences.
# privilege=4 => Administrator; ipmi=on, link=on; disable call-in.
ipmi channel setaccess "$CHANNEL" "$USER_ID" callin=off ipmi=on link=on privilege=4

echo "[*] Verifying user entry..."
# Show header and the line for the target USER_ID
ipmi user list "$CHANNEL" | awk -v id="$USER_ID" 'NR==1 || $1==id {print}'

# Optional functional check: try a simple command with the new creds (commented out by default).
# If you enable this, make sure you won't lock out ADMIN before confirming.
# NEW_USER_TEST="${NEW_USER_TEST:-0}"
# if [[ "$NEW_USER_TEST" == "1" ]]; then
#   echo "[*] Performing a login sanity check with the new user..."
#   IPMI_PASSWORD="$NEW_PASS_ASCII" ipmitool -I lan -H "$BMC_HOST" -U "$NEW_NAME" -E chassis status >/dev/null
#   echo "[*] New user login looks good."
# fi

echo "[✓] Done. User ID ${USER_ID} is now '${NEW_NAME}' with Administrator privileges on channel ${CHANNEL}."

