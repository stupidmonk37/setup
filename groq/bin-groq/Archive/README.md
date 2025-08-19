# PDU Management and Audit Tools

A comprehensive collection of scripts for managing Power Distribution Units (PDUs) and processing PDU audit results.

## Overview

This toolkit provides complete PDU management capabilities including:
- Individual outlet control
- Bulk port status checking
- Node-level power management (all 4 PSUs)
- PDU mapping and visualization
- Audit result processing

## Scripts

### PDU Control Scripts

#### `check-outlet.sh` - Individual Outlet Control
Control individual PDU outlets with SNMP commands.

**Usage:**
```bash
# Turn on a specific outlet
./check-outlet.sh --cluster=msp2 --rack=c1r144 --pdu=2 --port=19 --state=on

# Turn off a specific outlet
./check-outlet.sh --cluster=msp2 --rack=c1r144 --pdu=2 --port=19 --state=off

# Check current outlet state
./check-outlet.sh --cluster=msp2 --rack=c1r144 --pdu=2 --port=19 --check
```

**Features:**
- SNMP-based outlet control (on/off)
- Read-only status checking
- User-friendly state messages ("The outlet is ON/OFF")
- Comprehensive error handling

#### `check-pdu-all-ports.sh` - Bulk Port Status Checker
Check the status of all ports on a PDU at once.

**Usage:**
```bash
# Check all ports on a PDU
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=2

# Show only ports that are ON
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=2 --only-on

# Check specific port range
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=2 --start=1 --end=24
```

**Features:**
- Scans all ports (default range 1-42)
- Customizable port ranges
- Filter to show only ON ports
- Summary statistics (total/responsive/on/off counts)

#### `pdu-off.sh` - Node Power OFF
Turn off all 4 PSU connections for a hostname using the PDU map.

**Usage:**
```bash
# Turn off all PSUs for a node
./pdu-off.sh c0r21-gn1 --cluster=msp2

# Dry run to see what would happen
./pdu-off.sh c0r21-gn1 --cluster=msp2 --dry-run

# Verbose output
./pdu-off.sh c0r21-gn1 --cluster=msp2 --verbose
```

**What it does:**
- Extracts node number from hostname (c0r21-gn1 → N1)
- Looks up all 4 PSU connections in PDU map
- Turns OFF all 4 outlets using `check-outlet.sh`
- Provides detailed success/failure reporting

#### `pdu-on.sh` - Node Power ON
Turn on all 4 PSU connections for a hostname using the PDU map.

**Usage:**
```bash
# Turn on all PSUs for a node
./pdu-on.sh c0r21-gn1 --cluster=msp2

# Dry run to see what would happen
./pdu-on.sh c0r21-gn1 --cluster=msp2 --dry-run
```

**Features:**
- Same functionality as `pdu-off.sh` but turns outlets ON
- Automatic PDU map lookup
- Error handling and progress reporting

### PDU Mapping and Audit Scripts

#### `process_pdu_file.sh` - Audit Result Processor
Process PDU audit files and execute kubectl repair ticket commands based on node status.

**Usage:**
```bash
# Process all entries in a file
./process_pdu_file.sh --file=audit_results.txt

# Dry run to see what would be executed
./process_pdu_file.sh --file=audit_results.txt --dry-run

# Process only FAIL entries
./process_pdu_file.sh --file=audit_results.txt --status=FAIL
```

**Input File Format:**
```
hostname<TAB>status<TAB>[optional details]
```

**Example:**
```
c0r2-gn5.yka1-prod1.groq.net	FAIL
c0r3-gn5.yka1-prod1.groq.net	EXCEPTION	PSUs are not all on: indices [1]
c0r5-gn5.yka1-prod1.groq.net	WARN
```

### Data Files

#### `pdu-map` - PDU Connection Mapping
Contains the mapping between nodes/devices and their PDU connections.

**Format:**
- Each node (N1-N9) has 4 PSU connections
- PSU1/PSU2 connect to PDU1
- PSU3/PSU4 connect to PDU2
- Includes cable length information

**Example mapping:**
```
N1/PSU1 -> PDU1/Port39 (2ft/0.6m)
N1/PSU2 -> PDU1/Port41 (2ft/0.6m)
N1/PSU3 -> PDU2/Port39 (2ft/0.6m)
N1/PSU4 -> PDU2/Port41 (2ft/0.6m)
```

## Common Usage Patterns

### Emergency Node Shutdown
```bash
# Emergency shutdown of a problematic node
./pdu-off.sh c0r21-gn1 --cluster=msp2

# Verify all PSUs are off
./check-pdu-all-ports.sh --cluster=msp2 --rack=c0r21 --pdu=1 --only-on | grep -E "(39|41)"
./check-pdu-all-ports.sh --cluster=msp2 --rack=c0r21 --pdu=2 --only-on | grep -E "(39|41)"

# Power back on when ready
./pdu-on.sh c0r21-gn1 --cluster=msp2
```

### PDU Health Check
```bash
# Check status of all ports on both PDUs
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=1
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=2

# Show only powered outlets
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=1 --only-on
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=2 --only-on
```

### Processing Audit Results
```bash
# Always test first
./process_pdu_file.sh --file=audit_results.txt --dry-run

# Process FAIL entries first (most critical)
./process_pdu_file.sh --file=audit_results.txt --status=FAIL

# Then process WARN entries
./process_pdu_file.sh --file=audit_results.txt --status=WARN
```

## Hostname Format

All scripts expect hostnames in this format:
- `c0r21-gn1` → Node N1, Rack c0r21
- `c0r99-gn5` → Node N5, Rack c0r99
- `c1r144-gn3` → Node N3, Rack c1r144

## Configuration

### SNMP Settings
- **Community String:** `GroqLPUPow3r`
- **Version:** SNMPv2c
- **PDU Hostname Format:** `{rack}-pdu{number}.{cluster}.groq.net`

### Port Mapping
- **Default Range:** 1-42 ports per PDU
- **Node PSUs:** Each node has 4 PSUs (PSU1-PSU4)
- **PDU Distribution:** PSU1/PSU2 → PDU1, PSU3/PSU4 → PDU2

## Safety Features

### Dry Run Mode
All scripts support `--dry-run` to show what would be executed without making changes:
```bash
./pdu-off.sh c0r21-gn1 --cluster=msp2 --dry-run
./process_pdu_file.sh --file=audit.txt --dry-run
```

### Error Handling
- Network timeout protection
- SNMP command validation
- Comprehensive error reporting
- Graceful failure handling

### Validation
- Required parameter checking
- Hostname format validation
- PDU map lookup verification
- File existence checking

## Quick Start Guide

1. **Individual Outlet Control:**
   ```bash
   ./check-outlet.sh --cluster=msp2 --rack=c1r144 --pdu=2 --port=19 --check
   ```

2. **Node-Level Power Management:**
   ```bash
   ./pdu-off.sh c0r21-gn1 --cluster=msp2 --dry-run
   ./pdu-off.sh c0r21-gn1 --cluster=msp2
   ```

3. **PDU Health Monitoring:**
   ```bash
   ./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=1 --only-on
   ```

4. **Audit Processing:**
   ```bash
   ./process_pdu_file.sh --file=audit_results.txt --status=FAIL --dry-run
   ```

## Troubleshooting

### Common Issues
- **SNMP Timeouts:** Check network connectivity and PDU hostname resolution
- **Permission Errors:** Verify SNMP community string and access rights
- **Invalid Hostnames:** Ensure format matches `c0r21-gn1` pattern
- **Missing PDU Map:** Verify `pdu-map` file exists and contains target node

### Debug Options
- Use `--verbose` for detailed output
- Use `--dry-run` to test without executing
- Check individual outlets with `check-outlet.sh --check`
- Verify PDU map with available node listings

## Examples

### Complete Node Power Cycle
```bash
# 1. Check current status
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=1 --only-on | grep -E "(39|41)"

# 2. Power off (dry run first)
./pdu-off.sh c1r144-gn1 --cluster=msp2 --dry-run
./pdu-off.sh c1r144-gn1 --cluster=msp2

# 3. Wait for shutdown...

# 4. Power back on
./pdu-on.sh c1r144-gn1 --cluster=msp2

# 5. Verify all PSUs are back online
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=1 --only-on | grep -E "(39|41)"
./check-pdu-all-ports.sh --cluster=msp2 --rack=c1r144 --pdu=2 --only-on | grep -E "(39|41)"
```

This toolkit provides comprehensive PDU management capabilities from individual outlet control to full node power management and audit processing. 