#!/bin/bash

#==============================================================================
# PDU Audit Processing Script
#==============================================================================
# Description: Process PDU audit files and execute kubectl repair ticket commands
#              based on node status (FAIL, WARN, EXCEPTION)
# 
# Usage: ./process_ykapdu.sh --file=FILENAME [options]
#==============================================================================

#------------------------------------------------------------------------------
# Global Variables
#------------------------------------------------------------------------------
INPUT_FILE=""                    # Path to input file (required)
DRY_RUN=false                   # Flag for dry-run mode (no actual execution)
STATUS_FILTER=""                # Raw status filter string from command line
declare -a STATUS_ARRAY=()      # Array of status values to filter on

#------------------------------------------------------------------------------
# Command Line Argument Parsing
#------------------------------------------------------------------------------
# Process all command line arguments and set global variables accordingly
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            # Enable dry-run mode (show commands but don't execute)
            DRY_RUN=true
            shift
            ;;
        --status=*)
            # Parse status filter (can be comma-separated list)
            STATUS_FILTER="${1#*=}"
            # Split comma-separated values into array for easier processing
            IFS=',' read -ra STATUS_ARRAY <<< "$STATUS_FILTER"
            shift
            ;;
        --file=*)
            # Parse file argument in --file=filename format
            INPUT_FILE="${1#*=}"
            shift
            ;;
        -f|--file)
            # Parse file argument in -f filename or --file filename format (with space)
            if [[ -n "$2" && "$2" != -* ]]; then
                INPUT_FILE="$2"
                shift 2
            else
                echo "Error: $1 requires a filename"
                exit 1
            fi
            ;;
        -h|--help)
            # Display comprehensive help message
            echo "Usage: $0 --file=FILE [options]"
            echo ""
            echo "Required:"
            echo "  --file=FILE, -f FILE    Specify input file to process"
            echo ""
            echo "Optional:"
            echo "  --dry-run               Show what would be done without executing commands"
            echo "  --status=STATUS         Only process entries with specified status"
            echo "                          Can be single (FAIL) or multiple comma-separated (FAIL,WARN,EXCEPTION)"
            echo "                          If not specified, processes all entries"
            echo "  -h, --help              Show this help message"
            echo ""
            echo "Input File Format:"
            echo "  The input file must be tab-separated with the following format:"
            echo "  hostname<TAB>status<TAB>[optional details]"
            echo ""
            echo "  Example file content:"
            echo "    c0r2-gn5.yka1-prod1.groq.net	FAIL"
            echo "    c0r3-gn5.yka1-prod1.groq.net	WARN"
            echo "    c0r4-gn5.yka1-prod1.groq.net	EXCEPTION	PSUs are not all on: indices [1]"
            echo ""
            echo "  Supported status values: FAIL, WARN, EXCEPTION"
            echo ""
            echo "Examples:"
            echo "  $0 --file=ykapdu                         # Process all entries in ykapdu file"
            echo "  $0 --file=ykapdu --dry-run               # Dry run all entries in ykapdu file"
            echo "  $0 --file=ykapdu --dry-run --status=FAIL"
            echo "  $0 -f custom_file.txt --status=WARN"
            echo "  $0 --file=data.txt --status=FAIL,EXCEPTION --dry-run"
            echo "  $0 --file=audit.txt --status=FAIL,WARN,EXCEPTION"
            exit 0
            ;;
        *)
            # Handle unknown options or positional arguments
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            shift
            ;;
    esac
done

#------------------------------------------------------------------------------
# Input Validation
#------------------------------------------------------------------------------

# Ensure a file was specified (required parameter)
if [[ -z "$INPUT_FILE" ]]; then
    echo "Error: Input file is required. Use --file=FILENAME or -f FILENAME"
    echo "Use --help for usage information"
    exit 1
fi

# Verify the specified file actually exists
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: File '$INPUT_FILE' not found"
    exit 1
fi

#------------------------------------------------------------------------------
# Utility Functions
#------------------------------------------------------------------------------

# Function to extract node name from hostname
# Input: Full hostname (e.g., c0r2-gn5.yka1-prod1.groq.net)
# Output: Short node name (e.g., c0r2-gn5)
extract_node_name() {
    local hostname="$1"
    echo "${hostname%%.*}"  # Remove everything after the first dot
}

# Function to check if a status matches the current filter criteria
# Input: Status string to check (FAIL, WARN, EXCEPTION, etc.)
# Output: Returns 0 (true) if status should be processed, 1 (false) if filtered out
status_matches_filter() {
    local status="$1"
    
    # If no filter is set, match everything (process all entries)
    if [[ ${#STATUS_ARRAY[@]} -eq 0 ]]; then
        return 0
    fi
    
    # Check if the status is in our filter array
    for filter_status in "${STATUS_ARRAY[@]}"; do
        if [[ "$status" == "$filter_status" ]]; then
            return 0  # Found a match, include this entry
        fi
    done
    
    return 1  # No match found, exclude this entry
}

# Function to execute appropriate command based on node status
# Input: hostname, status, optional details
# Output: Executes kubectl repair ticket or other commands based on status
execute_command() {
    local hostname="$1"     # Full hostname from input file
    local status="$2"       # Status (FAIL, WARN, EXCEPTION)
    local details="$3"      # Optional details/error message
    local cmd=""            # Command to execute
    local node_name         # Short node name for kubectl commands
    
    # Extract short node name for use in kubectl commands
    node_name=$(extract_node_name "$hostname")
    
    # Determine which command to execute based on status
    case "$status" in
        "FAIL")
            # FAIL status: Create repair ticket for PSU/PDU mapping issues
            # This indicates PSUs are miswired or unresponsive, preventing safe power cycling
            cmd="kubectl repair ticket --node $node_name --title \"Repair node $node_name PSU/PDU mapping - FAIL\" --desc \"One or more PSUs are miswired or unresponsive in a way that prevents safe power cycling. Ensure correct the psu -> pdu mapping to match the design found here https://docs.google.com/document/d/1rQ4Vt1hWTTt518j5SRBXWDMOufl2eASRGrWVNIt6SeQ/edit?tab=t.0#heading=h.t0akymhogtwy\""
            ;;
        "WARN")
            # WARN status: Create repair ticket for incorrect PSU wiring
            # This indicates at least one PSU is wired to the wrong outlet
            cmd="kubectl repair ticket --node $node_name --title \"Repair node $node_name PSU/PDU mapping - WARN\" --desc \"At least one PSU is wired to the wrong outlet. Ensure correct the psu -> pdu mapping to match the design found here https://docs.google.com/document/d/1rQ4Vt1hWTTt518j5SRBXWDMOufl2eASRGrWVNIt6SeQ/edit?tab=t.0#heading=h.t0akymhogtwy\""
            ;;
        "EXCEPTION")
            # EXCEPTION status: Handle special cases (BMC failures, connection issues, etc.)
            # Currently just logs the exception, but could be extended for specific handling
            cmd="echo 'HANDLING EXCEPTION: $hostname - $details'"
            # TODO: Replace with your actual command for exception handling, e.g.:
            # cmd="ssh $hostname 'systemctl status service && journalctl -u service'"
            ;;
        *)
            # Unknown status - log error and return failure
            echo "Unknown status '$status' for $hostname"
            return 1
            ;;
    esac
    
    # Display the command that will be executed
    echo "Executing: $cmd"
    
    # Check if we're in dry-run mode (show commands but don't execute)
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would execute: $cmd"
        return 0
    fi
    
    # Execute the command with timeout protection (if available)
    if command -v timeout >/dev/null 2>&1; then
        # Use timeout command if available (typically on Linux)
        if timeout 30s bash -c "$cmd"; then
            echo "✓ Success for $hostname"
            return 0
        else
            echo "✗ Failed for $hostname"
            return 1
        fi
    else
        # Fallback for systems without timeout command (like macOS)
        if bash -c "$cmd"; then
            echo "✓ Success for $hostname"
            return 0
        else
            echo "✗ Failed for $hostname"
            return 1
        fi
    fi
}

#------------------------------------------------------------------------------
# Main Processing Logic
#------------------------------------------------------------------------------

# Initialize counters for tracking progress and results
success_count=0          # Number of successfully executed commands
failure_count=0          # Number of failed command executions
total_count=0            # Total number of entries processed (after filtering)
line_num=0               # Current line number in input file

# Display processing information and configuration
echo "Processing file: $INPUT_FILE"
if [[ "$DRY_RUN" == "true" ]]; then
    echo "DRY RUN MODE - Commands will not be executed"
fi
if [[ ${#STATUS_ARRAY[@]} -gt 0 ]]; then
    echo "Filtering for status: ${STATUS_ARRAY[*]}"
fi
echo "$(printf '%.0s-' {1..50})"

# Main processing loop - read input file line by line
# Expected format: hostname<TAB>status<TAB>[optional details]
while IFS=$'\t' read -r hostname status details || [[ -n "$hostname" ]]; do
    ((line_num++))
    
    # Skip empty lines (common at end of files)
    [[ -z "$hostname" ]] && continue
    
    # Apply status filtering if user specified --status option
    if ! status_matches_filter "$status"; then
        continue  # Skip this entry, doesn't match filter criteria
    fi
    
    # Increment counter for entries that pass filtering
    ((total_count++))
    
    # Display current entry information
    echo ""
    echo "Line $line_num: $hostname -> $status"
    if [[ -n "$details" ]]; then
        echo "  Details: $details"
    fi
    
    # Execute the appropriate command for this entry
    if execute_command "$hostname" "$status" "$details"; then
        ((success_count++))    # Command succeeded
    else
        ((failure_count++))    # Command failed
    fi
    
done < "$INPUT_FILE"

#------------------------------------------------------------------------------
# Summary and Results
#------------------------------------------------------------------------------

# Display final summary of processing results
echo ""
echo "$(printf '%.0s=' {1..50})"
echo "Processing complete!"
echo "Total processed: $total_count"

# Only show success/failure counts if we actually executed commands
if [[ "$DRY_RUN" != "true" ]]; then
    echo "Successful: $success_count"
    echo "Failed: $failure_count"
fi 