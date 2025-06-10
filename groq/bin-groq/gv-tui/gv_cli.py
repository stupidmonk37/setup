#! /usr/bin/env python3

import argparse
import json
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils import (
    colorize,
    extract_rack_prefix,
    is_rack_name,
    is_xrk_name,
    kubectl_get_json_resource,
    kubectl_get_json_validation,
    display_cluster_table,
    display_node_table,
    display_rack_table,
    display_crossrack_table,
    process_node_validations,
    format_timestamp,
    natural_sort_key,
)

EXPECTED_NODES = {f"gn{i}" for i in range(1, 10)}

# Shared
def cluster_table_default_status(name):
    return {
        "rack": name,
        "nodes": {},
        "node_status": "Not Made",
        "rack_status": "Not Made",
        "xrk_status": "Not Made",
        "xrk_name": None,
        "health": None
    }

def valid_rack_name(value: str) -> str:
    if not is_rack_name(value):
        raise argparse.ArgumentTypeError(f"Invalid rack format: '{value}'. Must match c<digit>r<digits> (e.g., c0r1)")
    return value

def valid_crossrack_name(value: str) -> str:
    if not is_xrk_name(value):
        raise argparse.ArgumentTypeError(f"Invalid crossrack format: '{value}'. Must match c0r1-c0r2")
    return value

# Cluster logic
def get_rack_health_info(nodes_json):
    racks = defaultdict(lambda: cluster_table_default_status(""))
    for item in nodes_json.get("items", []):
        name = item["metadata"]["name"]
        rack = extract_rack_prefix(name)
        if not rack:
            continue

        gn = name.split("-")[-1]
        gn_name = gn if gn.startswith("gn") else f"gn{gn}"

        conditions = item.get("status", {}).get("conditions", [])
        ready = any(c["type"] == "Ready" and c["status"] == "True" for c in conditions)

        racks[rack]["rack"] = rack
        racks[rack]["nodes"][gn_name] = ready

    for rack_data in racks.values():
        found_nodes = set(rack_data["nodes"])
        node_statuses = rack_data["nodes"]

        missing = sorted(EXPECTED_NODES - found_nodes)
        not_ready = sorted(n for n in found_nodes if not node_statuses.get(n, False))

        messages = []
        if missing:
            messages.append(f"Missing: {', '.join(missing)}")
        if not_ready:
            messages.append(f"NotReady: {', '.join(not_ready)}")

        rack_data["health"] = "; ".join(messages) if messages else "Healthy"

    return racks

def update_rack_statuses(items, racks):
    for item in items:
        name = item.get("metadata", {}).get("name", "")
        status = item.get("status", {}).get("status", "Not Made")

        if is_rack_name(name):
            key = name
            field = "rack_status"
        elif is_xrk_name(name):
            key = name.split("-", 1)[0]
            racks[key]["xrk_name"] = name
            field = "xrk_status"
        else:
            key = extract_rack_prefix(name)
            field = "node_status"

        if key:
            if key not in racks:
                racks[key] = cluster_table_default_status(key)
            racks[key][field] = status

def get_data_cluster():
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(kubectl_get_json_resource, "nodes"): "nodes",
            executor.submit(kubectl_get_json_validation): "gv",
        }
        results = {name: future.result() for future, name in ((f, futures[f]) for f in as_completed(futures))}

    racks = get_rack_health_info(results["nodes"])
    update_rack_statuses(results["gv"].get("items", []), racks)

    rack_list = sorted(racks.values(), key=lambda r: natural_sort_key(r["rack"]))
    total_nodes = sum(len(r["nodes"]) for r in rack_list)
    ready_nodes = sum(1 for r in rack_list for ready in r["nodes"].values() if ready)

    node_complete = sum(1 for r in rack_list if r["node_status"] == "Success")
    rack_complete = sum(1 for r in rack_list if r["rack_status"] == "Success")
    xrk_complete = sum(1 for r in rack_list if r["xrk_status"] == "Success")

    return {
        "summary": {
            "total_nodes": total_nodes,
            "ready_nodes": ready_nodes,
            "total_racks": len(rack_list),
            "ready_ratio": ready_nodes / total_nodes if total_nodes else 0.0,
            "racks_complete": rack_complete,
            "racks_ratio": rack_complete / len(rack_list) if len(rack_list) else 0.0,
            "xrk_complete": xrk_complete,
            "xrk_ratio": xrk_complete / len(rack_list) if len(rack_list) else 0.0
        },
        "racks": rack_list
    }

# Subcommand handlers
def handle_cluster(args):
    data = get_data_cluster()
    if args.format == "json":
        if args.racks:
            filtered_racks = {r["rack"]: r for r in data["racks"] if r["rack"] in args.racks}
            print(json.dumps(filtered_racks, indent=2))
        else:
            print(json.dumps(data["racks"], indent=2))
    else:
        display_cluster_table(data, rack_filter=args.racks)
        summary = data["summary"]
        print("\nSummary:")
        print(f"            Rack Total: {summary['total_racks']}")
        print(f"           Nodes Ready: {summary['ready_nodes']}/{summary['total_nodes']} ({summary['ready_ratio']*100:.2f}%)")
        print(f"       Validated Racks: {summary['racks_complete']}/{summary['total_racks']} ({summary['racks_ratio']*100:.2f}%)")
        print(f"  Validated Crossracks: {summary['xrk_complete']}/{summary['total_racks']} ({summary['xrk_ratio']*100:.2f}%)")

        try:
            result = subprocess.run(
                ["kubectl", "validation", "status", "--only-failed"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            output_lines = result.stdout.splitlines()
            start_index = None

            for i, line in enumerate(output_lines):
                if line.lstrip().startswith("Some failures were identified. To inspect the logs, run:"):
                    start_index = i
                    break

            if start_index is not None:
                print("\n" + "\n".join(output_lines[start_index:]))
            else:
                print("\n🎉 No failed validations found! 🎉")
        except subprocess.CalledProcessError as e:
            print("Error running validation command:")
            print(e.stderr)


def handle_node(args):
    if args.format == "json":
        output = {}
        for rack in args.racks:
            try:
                node_names = [f"{rack}-gn{i}" for i in range(1, 10)]
                validations = {}

                with ThreadPoolExecutor(max_workers=9) as executor:
                    results = executor.map(
                        lambda node: (node, kubectl_get_json_validation(node).get("status", {}).get("validations", {})),
                        node_names
                    )

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
    parser = argparse.ArgumentParser(description="Unified Health Dashboard CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Cluster
    cluster_parser = subparsers.add_parser("cluster")
    cluster_parser.add_argument("--format", choices=["json", "table"], default="table")
    cluster_parser.add_argument("--racks", nargs="+")
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
