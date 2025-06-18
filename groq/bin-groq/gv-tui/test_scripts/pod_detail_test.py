#!/usr/bin/env python3

import argparse
import json
from rich.console import Console
from utils import (
    valid_rack_name,
    display_node_table,
    collect_pod_entries,
    build_pod_status_ui,
    aggregate_pod_issues,
)

console = Console()

def main():
    parser = argparse.ArgumentParser(description="Node validation and pod status dashboard")
    parser.add_argument("--racks", nargs="+", type=valid_rack_name, required=True, help="List of racks (e.g., c0r1)")
    parser.add_argument("--format", choices=["json", "table"], default="table", help="Output format")
    parser.add_argument("--pod-check", action="store_true", help="Check pod statuses instead of validations")
    args = parser.parse_args()

    if args.pod_check:
        entries = collect_pod_entries(args.racks)
        table, summary = build_pod_status_ui(entries, args.racks)
        console.print(table)
        console.print(summary)
    else:
        if args.format == "json":
            output = {}
            for rack in args.racks:
                try:
                    from utils import fetch_validations, process_node_validations
                    validations = fetch_validations(rack)
                    output[rack] = process_node_validations(rack, validations)
                except Exception as e:
                    output[rack] = {"error": str(e)}
            print(json.dumps(output, indent=2))
        else:
            display_node_table(args.racks, render=True)


if __name__ == "__main__":
    main()
