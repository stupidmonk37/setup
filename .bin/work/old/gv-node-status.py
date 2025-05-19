#!/usr/bin/env python3

import os
import sys
import subprocess
import argparse
import json
from concurrent.futures import ThreadPoolExecutor

def supports_color():
    return sys.stdout.isatty() and os.environ.get("TERM") not in ("dumb", None)

USE_COLOR = supports_color()
GREEN = "\033[92m" if USE_COLOR else ""
RED = "\033[91m" if USE_COLOR else ""
YELLOW = "\033[93m" if USE_COLOR else ""
RESET = "\033[0m" if USE_COLOR else ""

NODE_COUNT = 9
TABLE_WIDTH = 129

def colorize_status(status):
    if not status:
        return f"{YELLOW}{'N/A':^9}{RESET}"
    status_lower = status.lower()
    if status_lower == "success":
        return f"{GREEN}{'Success':^9}{RESET}"
    elif status_lower == "failure":
        return f"{RED}{'Failure':^9}{RESET}"
    return f"{YELLOW}{status:^9}{RESET}"

def get_node_validation_status(node_name):
    import shlex
    cmd = f"kubectl get gv {node_name} -o json"
    try:
        output = subprocess.check_output(shlex.split(cmd), text=True)
        data = json.loads(output)
        return node_name, data.get("status", {}).get("validations", {})
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ Error running kubectl for {node_name}:{RESET} {e}")
    except json.JSONDecodeError as je:
        print(f"{RED}❌ JSON parsing error for {node_name}:{RESET} {je}")
    return node_name, {}

def generate_validation_table(cluster_id_prefix):
    full_node_names = [f"{cluster_id_prefix}-gn{i}" for i in range(1, NODE_COUNT + 1)]
    short_node_names = [f"gn{i}" for i in range(1, NODE_COUNT + 1)]
    merged_validations = {}

    with ThreadPoolExecutor(max_workers=NODE_COUNT) as executor:
        results = executor.map(get_node_validation_status, full_node_names)

    for full_node, validations in results:
        for test, nodes in validations.items():
            if test not in merged_validations:
                merged_validations[test] = {}
            merged_validations[test][full_node] = nodes.get(full_node, {})

    table_lines = [
        "+" + "-" * TABLE_WIDTH + "+",
        f"|{' ' * ((TABLE_WIDTH - len(cluster_id_prefix) - 19) // 2)}{cluster_id_prefix} -- Node Tests {' ' * ((TABLE_WIDTH - len(cluster_id_prefix) - 19 + 9) // 2)}|",
        "+" + "-" * TABLE_WIDTH + "+",
        "| Test / Node:                          |" + "".join([f" {n:^7} |" for n in short_node_names]),
        "+" + "-" * 39 + "+" + ("-" * 9 + "+") * NODE_COUNT
    ]

    for test, node_data in merged_validations.items():
        formatted_test = test.replace("-", " ").title().replace(" ", " - ", 1) if test.startswith("single") else test.replace("-", " ").title()
        row = f"| {formatted_test:<37} |"
        for short_node in short_node_names:
            full_node = f"{cluster_id_prefix}-{short_node}"
            data = node_data.get(full_node, {})
            status = "N/A"
            if isinstance(data, dict):
                results = data.get("results", [])
                if results and isinstance(results[0], dict):
                    status = results[0].get("status", "N/A")
            row += colorize_status(status) + "|"

        table_lines.append(row)

    table_lines.append("+" + "-" * TABLE_WIDTH + "+")
    return "\n".join(table_lines)

def print_multiple_tables(cluster_ids):
    for prefix in cluster_ids:
        print("\n" + generate_validation_table(prefix) + "\n")

def main():
    parser = argparse.ArgumentParser(
        description="Display node validation statuses for one or more cluster ID prefixes."
    )
    parser.add_argument(
        "cluster_ids",
        nargs="+",
        help="One or more cluster ID prefixes (e.g., c1r66, c2r55)"
    )
    args = parser.parse_args()

    print_multiple_tables(args.cluster_ids)

if __name__ == "__main__":
    main()
