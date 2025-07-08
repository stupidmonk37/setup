import argparse
import json
import subprocess
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from utils import (
    kubectl_get_json_validation,
    display_rack_table,
    display_crossrack_table,
    process_node_validations,
    format_timestamp,
    valid_rack_name,
    valid_crossrack_name,
    display_node_table,
    get_data_cluster,
    output_cluster_json,
    output_cluster_table,
    print_cluster_summary,
    print_failed_validations,
    EXPECTED_NODES,
)


# Subcommand handlers
def handle_cluster(args):
    data = get_data_cluster()

    if args.format == "json":
        output_cluster_json(data, args.racks)
    else:
        output_cluster_table(data, args.racks)
        print_cluster_summary(None, data["summary"])
        print_failed_validations()


def handle_node(args):
    if args.format == "json":
        output = {}
        def safe_get_validation(node):
            try:
                data = kubectl_get_json_validation(node)
                return node, data.get("status", {}).get("validations", {})

            except subprocess.CalledProcessError:
                print("Groq validations not made")
                return node, {}

        for rack in args.racks:
            try:
                node_names = [f"{rack}-gn{i}" for i in range(1, 10)]
                validations = {}
                with ThreadPoolExecutor(max_workers=9) as executor:
                    results = executor.map(safe_get_validation, node_names)

                for node_name, node_validations in results:
                    for test_name, test_data in node_validations.items():
                        validations.setdefault(test_name, {})[node_name] = test_data.get(node_name, {})

                output[rack] = process_node_validations(rack, validations)

            except Exception as e:
                output[rack] = {"error": str(e)}

        print(json.dumps(output, indent=2))

    else:
        display_node_table(args.racks, render=True)


def handle_rack(args):
    if args.format == "json":
        output = {}
        for rack in args.racks:
            try:
                run_data = kubectl_get_json_validation(rack)
                validations = run_data.get("status", {}).get("validations", {})
                rack_summary = {}
                for validator_name, node_groups in validations.items():
                    node_summary = {}
                    for node_name, pdata in node_groups.items():
                        phase = pdata.get("phase", "Unknown")
                        results = pdata.get("results", [])
                        results_status = results[0].get("status", "") if results else ""
                        faults = results[0].get("faults", []) if results else []
                        if faults:
                            fault_descriptions = sorted({
                                f"{f.get('fault_type', 'Unknown')} ({f.get('component', '?')})"
                                for f in faults
                            })
                            results_status = "; ".join(fault_descriptions)

                        elif not results_status:
                            results_status = phase.title() if phase else "Not Started"

                        else:
                            results_status = results_status.replace("-", " ").title()

                        node_summary[node_name] = {
                            "results_status": results_status,
                            "started_at": format_timestamp(pdata.get("startedAt")),
                            "phase": phase,
                            "validator": validator_name,
                        }

                    rack_summary[validator_name] = dict(sorted(node_summary.items()))

                output[rack] = rack_summary

            except Exception as e:
                output[rack] = {"error": str(e)}

        print(json.dumps(output, indent=2, sort_keys=True))

    else:
        display_rack_table(args.racks)


def handle_crossrack(args):
    if args.format == "json":
        output = {}
        for rack in args.racks:
            try:
                run_data = kubectl_get_json_validation(rack)
                validations = run_data.get("status", {}).get("validations", {})
                rack_summary = {}
                for validator_name, node_groups in validations.items():
                    node_summary = {}
                    for node_name, pdata in node_groups.items():
                        phase = pdata.get("phase", "Unknown")
                        results = pdata.get("results", [])
                        results_status = results[0].get("status", "") if results else ""
                        faults = results[0].get("faults", []) if results else []
                        if faults:
                            fault_descriptions = sorted({
                                f"{f.get('fault_type', 'Unknown')} ({f.get('component', '?')})"
                                for f in faults
                            })
                            results_status = "; ".join(fault_descriptions)

                        elif not results_status:
                            results_status = phase.title() if phase else "Not Started"

                        else:
                            results_status = results_status.replace("-", " ").title()

                        node_summary[node_name] = {
                            "results_status": results_status,
                            "started_at": pdata.get("startedAt"),
                            "phase": phase,
                            "validator": validator_name,
                        }

                    rack_summary[validator_name] = dict(sorted(node_summary.items()))

                output[rack] = rack_summary

            except Exception as e:
                output[rack] = {"error": str(e)}

        print(json.dumps(output, indent=2, sort_keys=True))

    else:
        display_crossrack_table(args.racks)



# Main
def main():
    parser = argparse.ArgumentParser(description="Groq Validationd Dashboard CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Cluster
    cluster_parser = subparsers.add_parser("cluster")
    cluster_parser.add_argument("--format", choices=["json", "table"], default="table")
    cluster_parser.add_argument("--racks", nargs="+", type=valid_rack_name)
    cluster_parser.set_defaults(func=handle_cluster)

    # Node
    node_parser = subparsers.add_parser("node")
    node_parser.add_argument("--format", choices=["json", "table"], default="table")
    node_parser.add_argument("--racks", nargs="+", type=valid_rack_name, required=True)
    node_parser.set_defaults(func=handle_node)

    # Rack
    rack_parser = subparsers.add_parser("rack")
    rack_parser.add_argument("--format", choices=["json", "table"], default="table")
    rack_parser.add_argument("--racks", nargs="+", type=valid_rack_name, required=True)
    rack_parser.set_defaults(func=handle_rack)

    # Crossrack
    cross_parser = subparsers.add_parser("crossrack")
    cross_parser.add_argument("--format", choices=["json", "table"], default="table")
    cross_parser.add_argument("--racks", nargs="+", type=valid_crossrack_name, required=True)
    cross_parser.set_defaults(func=handle_crossrack)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
