#!/usr/bin/env python3

import subprocess
import yaml
import sys

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def generate_validation_table(cluster_id_prefix):
    full_node_names = [f"{cluster_id_prefix}-gn{i}" for i in range(1, 10)]
    short_node_names = [f"gn{i}" for i in range(1, 10)]

    merged_validations = {}
    all_validation_names = set()

    # Fetch and merge validation data
    for full_node in full_node_names:
        kubectl_command = f"kubectl get gv {full_node} -o yaml | yq e '.status' -"
        try:
            yaml_output = subprocess.check_output(kubectl_command, shell=True, text=True)
            data = yaml.safe_load(yaml_output)
            node_validations = data.get("validations", {})

            for test, nodes in node_validations.items():
                all_validation_names.add(test)
                if test not in merged_validations:
                    merged_validations[test] = {}
                merged_validations[test][full_node] = nodes.get(full_node, {})
        except subprocess.CalledProcessError as e:
            print(f"Error executing kubectl command for {full_node}: {e}")
            continue

    validations_list = sorted(all_validation_names)

    total_width = 72

    cluster_id_prefix_length = len(cluster_id_prefix)
    space_padding = total_width - cluster_id_prefix_length - len(" -- Node Tests:")

    table_header = [
        "+---------------------------------------------------------------------------------------------------------------------------------+",
        f"|                                                         {cluster_id_prefix} -- Node Tests:{' ' * space_padding}|",
        "+---------------------------------------------------------------------------------------------------------------------------------+",
        "| Test / Node:                          |   gn1   |   gn2   |   gn3   |   gn4   |   gn5   |   gn6   |   gn7   |   gn8   |   gn9   |",
        "+---------------------------------------+---------+---------+---------+---------+---------+---------+---------+---------+---------+"
    ]

    # Initialize the table matrix
    table_matrix = {test: {node: "" for node in short_node_names} for test in validations_list}

    for test in validations_list:
        node_status_map = merged_validations.get(test, {})
        for full_node_name, data in node_status_map.items():
            short_node = full_node_name.split("-")[-1]
            if short_node in short_node_names:
                results = data.get("results", [])
                if results:
                    status = results[0].get("status", "N/A").capitalize()
                else:
                    status = "N/A"
                table_matrix[test][short_node] = "Success" if status.lower() == "success" else "N/A"

    # Assemble table rows
    table_rows = []
    for test in validations_list:
        display_name = test.replace("-", " ").title().replace(" ", " - ", 1) if test.startswith("single") else test.replace("-", " ").title()
        row = f"| {display_name:<37} |"
        for node in short_node_names:
            status = table_matrix[test][node]
            color_status = f"{GREEN}{status:^9}{RESET}" if status == "Success" else f"{RED}{status:^9}{RESET}"
            row += f"{color_status}|"
        table_rows.append(row)

    table_footer = [
        "+---------------------------------------------------------------------------------------------------------------------------------+"
    ]

    return "\n".join(table_header + table_rows + table_footer)

def print_validation_table(cluster_id):
    command = f"kubectl get gv {cluster_id} -o yaml"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        print("Error fetching the validation data")
        print(result.stderr)
        return

    try:
        data = yaml.safe_load(result.stdout)
        status_data = data.get('status', {})
        validations_data = status_data.get('validations', {}) if isinstance(status_data, dict) else {}
    except yaml.YAMLError as e:
        print("YAML parsing error:", e)
        return

    title = f"{cluster_id} -- Rack Tests"
    print(f"+{'-'*101}+")
    print(f"|                                          {title:<59}|")
    print(f"+{'-'*101}+")

    for validation_name, validation_info in validations_data.items():
        print(f"| {validation_name:<89}|  Status  |")
        print("+------------------------------------------------------------------------------------------+----------+")

        for phase_name, phase_info in validation_info.items():
            if isinstance(phase_info, dict):
                results = phase_info.get("results", [])
                raw_status = results[0].get("status", "N/A") if results and isinstance(results[0], dict) else "N/A"
            else:
                raw_status = "Invalid"

            colored_status = f"{GREEN}{raw_status:<8}{RESET}" if raw_status.lower() == "success" else f"{RED}{raw_status:<8}{RESET}"
            print(f"| {phase_name:<88} | {colored_status} |")

        print("+------------------------------------------------------------------------------------------+----------+")

def print_multiple_tables(cluster_id_prefixes):
    for cluster_id_prefix in cluster_id_prefixes:
        table = generate_validation_table(cluster_id_prefix)
        if table:
            print("\n")
            print(table)
            print("\n")  # Add a new line between tables

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python script.py <cluster_id_prefix1> <cluster_id_prefix2> ...")
        sys.exit(1)

    cluster_id_prefixes = sys.argv[1:]

    print_multiple_tables(cluster_id_prefixes)

    for cluster_id_prefix in cluster_id_prefixes:
        print_validation_table(cluster_id_prefix)
        print("\n")
