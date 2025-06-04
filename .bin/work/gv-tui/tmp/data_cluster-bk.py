import argparse
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.console import Console
from rich.table import Table
from utils import (
    colorize,
    extract_rack_prefix,
    is_rack_name,
    is_xrk_name,
    kubectl_get_json_resource,
    kubectl_get_json_validation,
    display_cluster_table,
    natural_sort_key,
)

EXPECTED_NODES = {f"gn{i}" for i in range(1, 10)}

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

# update_json_health_status
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

# update_json_validation_status
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
        },
        "racks": rack_list
    }


def main():
    parser = argparse.ArgumentParser(description="Display cluster rack health status.")
    parser.add_argument(
        "--format",
        choices=["json", "table"],
        default="table",
        help="Output format: table (default) or json"
    )
    parser.add_argument(
        "--racks",
        nargs="+",
        help="Optional list of specific racks to include (e.g. c0r1 c0r2)"
    )
    args = parser.parse_args()

    data = get_data_cluster()

    if args.format == "json":
        if args.racks:
            filtered_racks = {r["rack"]: r for r in data["racks"] if r["rack"] in args.racks}
            print(json.dumps(filtered_racks, indent=2))
        else:
            print(json.dumps(data["racks"], indent=2))

    else:
        display_cluster_table(data, rack_filter=args.racks)

        # Print summary separately
        summary = data["summary"]
        print("\nSummary:")
        print(f"            Rack Total: {summary['total_racks']}")
        print(f"           Nodes Ready: {summary['ready_nodes']} / {summary['total_nodes']} " f"({summary['ready_ratio'] * 100:.2f}%)")
        print(f"       Validated Racks: {summary['racks_complete']} / {summary['total_racks']} " f"({summary['racks_ratio'] * 100:.2f}%)")
        print(f"  Validated Crossracks: {summary['xrk_complete']} / {summary['total_racks']} " f"({summary['ready_ratio'] * 100:.2f}%)")


if __name__ == "__main__":
    main()
