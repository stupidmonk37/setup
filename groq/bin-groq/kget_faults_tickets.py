#!/usr/bin/env python3

import json
import subprocess
import sys
import re

def run_command(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command {' '.join(cmd)}:\n{e.stderr}", file=sys.stderr)
        sys.exit(1)

def natural_keys(text):
    """
    Sort helper function to do natural sorting.
    Splits the text into list of strings and ints to sort human-friendly.
    """
    def atoi(t):
        return int(t) if t.isdigit() else t.lower()
    return [atoi(c) for c in re.split(r'(\d+)', text)]

def main():
    filter_arg = None
    if len(sys.argv) > 1:
        filter_arg = sys.argv[1].lower()

    faults_json = run_command(['kubectl', 'get', 'faults', '-o', 'json'])
    tickets_json = run_command(['kubectl', 'get', 'tickets', '-o', 'json'])

    faults = json.loads(faults_json).get('items', [])
    tickets = json.loads(tickets_json).get('items', [])

    ticket_map = {t['metadata']['name']: t for t in tickets}

    rows = []
    header = ["COMPONENT", "FAULTTYPE", "PHASE", "JIRASTATUS", "TICKETURL"]
    rows.append(header)

    for fault in faults:
        spec = fault.get('spec', {})
        status = fault.get('status', {})
        component = spec.get('component', 'N/A')

        # Apply filter if specified
        if filter_arg:
            parts = component.split('/')
            if len(parts) < 2:
                continue
            chassis_rack = (parts[0] + parts[1]).lower()
            if chassis_rack != filter_arg:
                continue

        faulttype = spec.get('faultType', 'N/A')
        phase = status.get('phase', 'N/A')

        ticket_ref = status.get('ticketRef', {})
        ticket_name = ticket_ref.get('name')

        jira_status = 'N/A'
        ticket_url = 'N/A'

        if ticket_name and ticket_name in ticket_map:
            ticket = ticket_map[ticket_name]
            ticket_status = ticket.get('status', {})
            jira_status = ticket_status.get('jiraStatus', 'N/A')
            ticket_url = ticket_status.get('ticketURL', 'N/A')

        rows.append([component, faulttype, phase, jira_status, ticket_url])

    # Sort rows naturally by component (skip header)
    sorted_rows = [header] + sorted(rows[1:], key=lambda r: natural_keys(r[0]))

    # Calculate max width of each column
    col_widths = [max(len(str(row[i])) for row in sorted_rows) for i in range(len(header))]

    # Print rows with padding
    for i, row in enumerate(sorted_rows):
        line = "  ".join(str(cell).ljust(col_widths[idx]) for idx, cell in enumerate(row))
        print(line)
        if i == 0:
            print("  ".join("-" * w for w in col_widths))

if __name__ == '__main__':
    main()
